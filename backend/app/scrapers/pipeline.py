"""
Main scraping pipeline orchestrator.

Three phases, run independently or together:
  Phase 1 — VENUES:   Discover every bar in the city (Google Places grid + Zomato + Dineout)
  Phase 2 — ENRICH:   Get detailed info (website, phone) for each venue via Google Place Details
  Phase 3 — DEALS:    Extract happy hour deals from each venue's website/Zomato/Dineout page

Usage:
  python -m scripts.scrape_city --city=mumbai --phase=all
  python -m scripts.scrape_city --city=mumbai --phase=venues
  python -m scripts.scrape_city --city=mumbai --phase=deals
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.venue import Venue
from app.models.deal import Deal
from app.scrapers import google_places, zomato, dineout, website_scraper
from app.scrapers.city_config import CityConfig, get_city, list_cities, CITIES
from app.services.llm_parser import extract_deals_from_text
from app.services.deduplicator import deduplicate_venues_in_city

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


# ─── Phase 1: Venue Discovery ──────────────────────────────────────

async def discover_venues(city: CityConfig):
    """
    Phase 1: Find every bar/pub in the city using all available sources.
    - Google Places grid search (primary — most comprehensive)
    - Zomato scraping (supplementary — good for Indian cities)
    - Dineout scraping (supplementary — sometimes has venues others miss)
    """
    logger.info(f"{'='*60}")
    logger.info(f"PHASE 1: Discovering venues in {city.display_name}")
    logger.info(f"{'='*60}")

    total_new = 0
    total_updated = 0

    # Source 1: Google Places grid search
    logger.info(f"\n--- Google Places Grid Search ---")
    google_venues = await google_places.grid_search_city(city)
    if google_venues:
        new, updated = google_places.save_venues_to_db(google_venues)
        total_new += new
        total_updated += updated
        logger.info(f"Google Places: {new} new, {updated} updated, {len(google_venues)} total found")

    # Source 2: Zomato
    if city.zomato_slug:
        logger.info(f"\n--- Zomato Scraping ---")
        zomato_venues = await zomato.scrape_bars_in_city(city.name, pages=10)
        if zomato_venues:
            zomato_count = zomato.save_venues_to_db(zomato_venues)
            total_new += zomato_count
            logger.info(f"Zomato: {zomato_count} new venues from {len(zomato_venues)} scraped")

    # Source 3: Dineout
    if city.dineout_slug:
        logger.info(f"\n--- Dineout Scraping ---")
        dineout_venues = await dineout.search_bars_in_city(city, pages=10)
        if dineout_venues:
            # Save Dineout venues (they often lack lat/lng, will be enriched later)
            db = SessionLocal()
            dineout_new = 0
            try:
                for v in dineout_venues:
                    if not v.get("source_id"):
                        continue
                    existing = (
                        db.query(Venue)
                        .filter(Venue.source == "dineout", Venue.source_id == v["source_id"])
                        .first()
                    )
                    if not existing:
                        venue = Venue(**v)
                        db.add(venue)
                        dineout_new += 1
                db.commit()
            finally:
                db.close()
            total_new += dineout_new
            logger.info(f"Dineout: {dineout_new} new venues from {len(dineout_venues)} scraped")

    # Deduplicate
    logger.info(f"\n--- Deduplication ---")
    merged = deduplicate_venues_in_city(city.name)

    logger.info(f"\nPhase 1 complete: {total_new} new + {total_updated} updated venues, {merged} duplicates merged")

    # Count total
    db = SessionLocal()
    try:
        total = db.query(Venue).filter(Venue.city == city.name).count()
        logger.info(f"Total venues in {city.display_name}: {total}")
    finally:
        db.close()


# ─── Phase 2: Venue Enrichment ─────────────────────────────────────

async def enrich_venues(city: CityConfig):
    """
    Phase 2: Enrich venues with detailed info from Google Place Details.
    Gets: website, phone, full address, photos, price level.
    Only enriches venues that are missing key fields (website, phone).
    """
    logger.info(f"{'='*60}")
    logger.info(f"PHASE 2: Enriching venues in {city.display_name}")
    logger.info(f"{'='*60}")

    db = SessionLocal()
    try:
        # Find venues that need enrichment (have a Google source_id but missing website/phone)
        venues_to_enrich = (
            db.query(Venue)
            .filter(
                Venue.city == city.name,
                Venue.source == "google",
                Venue.source_id.isnot(None),
                # Missing website or phone
                ((Venue.website.is_(None)) | (Venue.phone.is_(None))),
            )
            .all()
        )

        if not venues_to_enrich:
            logger.info("All venues already enriched")
            return

        logger.info(f"Enriching {len(venues_to_enrich)} venues...")

        place_ids = [v.source_id for v in venues_to_enrich]
        details = await google_places.enrich_venue_details(place_ids)

        enriched_count = 0
        for venue in venues_to_enrich:
            detail = details.get(venue.source_id)
            if not detail:
                continue

            if detail.get("website") and not venue.website:
                venue.website = detail["website"]
            if detail.get("phone") and not venue.phone:
                venue.phone = detail["phone"]
            if detail.get("address") and not venue.address:
                venue.address = detail["address"]
            if detail.get("price_range") and not venue.price_range:
                venue.price_range = detail["price_range"]
            if detail.get("rating") and not venue.rating:
                venue.rating = detail["rating"]
            if detail.get("source_url") and not venue.source_url:
                venue.source_url = detail["source_url"]

            enriched_count += 1

        db.commit()
        logger.info(f"Phase 2 complete: enriched {enriched_count}/{len(venues_to_enrich)} venues")

    finally:
        db.close()


# ─── Phase 3: Deal Extraction ──────────────────────────────────────

async def extract_deals(city: CityConfig, force: bool = False):
    """
    Phase 3: For each venue, scrape deal text from available sources and
    parse with LLM.

    Source priority (tried in order from city config):
    1. "website" — venue's own website (highest quality)
    2. "dineout" — Dineout venue page
    3. "zomato"  — Zomato venue detail page

    Args:
        force: If True, re-extract deals even for venues that already have them
    """
    logger.info(f"{'='*60}")
    logger.info(f"PHASE 3: Extracting deals in {city.display_name}")
    logger.info(f"{'='*60}")

    db = SessionLocal()
    try:
        query = db.query(Venue).filter(Venue.city == city.name)

        if not force:
            # Only process venues without existing deals
            venues_with_deals = (
                db.query(Deal.venue_id).distinct().subquery()
            )
            query = query.filter(~Venue.id.in_(db.query(venues_with_deals)))

        venues = query.all()
        logger.info(f"Extracting deals for {len(venues)} venues (force={force})")

        deals_extracted = 0
        venues_with_deals = 0

        for i, venue in enumerate(venues):
            raw_text = ""
            source_used = None

            # Try each deal source in priority order
            for source in city.deal_sources:
                if source == "website" and venue.website:
                    result = await website_scraper.scrape_venue_website(
                        venue.website, venue.name
                    )
                    if result.get("has_happy_hour_mention") or result.get("raw_text"):
                        raw_text = result["raw_text"]
                        source_used = "website"
                        break

                elif source == "dineout" and venue.source_url and "swiggy" in (venue.source_url or ""):
                    result = await dineout.scrape_venue_deals(venue.source_url)
                    if result.get("raw_text"):
                        raw_text = result["raw_text"]
                        source_used = "dineout"
                        break

                elif source == "zomato" and venue.source_url and "zomato" in (venue.source or ""):
                    result = await zomato.scrape_venue_detail(venue.source_url)
                    if result.get("raw_text"):
                        raw_text = result["raw_text"]
                        source_used = "zomato"
                        break

            if not raw_text:
                continue

            # Parse with LLM
            parsed_deals = extract_deals_from_text(
                raw_text=raw_text,
                venue_name=venue.name,
                city=city.name,
            )

            if not parsed_deals:
                continue

            # Save deals
            if force:
                # Delete existing deals first
                db.query(Deal).filter(Deal.venue_id == venue.id).delete()

            for deal_data in parsed_deals:
                deal = Deal(venue_id=venue.id, **deal_data)
                db.add(deal)
                deals_extracted += 1

            venues_with_deals += 1
            logger.info(
                f"  [{i+1}/{len(venues)}] {venue.name}: "
                f"{len(parsed_deals)} deals from {source_used}"
            )

            # Rate limit for politeness
            await asyncio.sleep(0.5)

            # Commit in batches of 50
            if (i + 1) % 50 == 0:
                db.commit()
                logger.info(f"  Committed batch at {i+1}/{len(venues)}")

        db.commit()
        logger.info(
            f"\nPhase 3 complete: {deals_extracted} deals from "
            f"{venues_with_deals}/{len(venues)} venues"
        )

    finally:
        db.close()


# ─── Full Pipeline ──────────────────────────────────────────────────

async def run_full_pipeline(city_name: str | None = None, phase: str = "all", force: bool = False):
    """
    Run the full pipeline for a city.

    Args:
        city_name: City to process (None = all cities)
        phase: "venues", "enrich", "deals", or "all"
        force: If True, re-process even existing data
    """
    if city_name:
        cities_to_process = [city_name]
    else:
        cities_to_process = list_cities()

    for name in cities_to_process:
        city = get_city(name)
        if not city:
            logger.warning(f"Unknown city: {name}")
            continue

        logger.info(f"\n{'#'*60}")
        logger.info(f"Processing: {city.display_name}")
        logger.info(f"{'#'*60}\n")

        start = datetime.now(IST)

        if phase in ("venues", "all"):
            await discover_venues(city)

        if phase in ("enrich", "all"):
            await enrich_venues(city)

        if phase in ("deals", "all"):
            await extract_deals(city, force=force)

        elapsed = (datetime.now(IST) - start).total_seconds()
        logger.info(f"\n{city.display_name} complete in {elapsed:.0f}s")

    logger.info("\nPipeline complete!")


def run_pipeline_sync(city_name: str | None = None, phase: str = "all", force: bool = False):
    """Synchronous wrapper — use from APScheduler or CLI."""
    asyncio.run(run_full_pipeline(city_name, phase, force))
