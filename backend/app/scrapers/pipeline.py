"""
Main scraping pipeline. Orchestrates:
1. Pull venues from Google Places + Zomato
2. Scrape venue detail pages for happy hour text
3. LLM-parse raw text into structured deals
4. Save everything to DB

Run manually or on a schedule via APScheduler.
"""

import asyncio
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.venue import Venue
from app.models.deal import Deal
from app.scrapers import google_places, zomato
from app.services.llm_parser import extract_deals_from_text

logger = logging.getLogger(__name__)


async def run_full_pipeline(cities: list[str] | None = None):
    """
    Run the full scraping + parsing pipeline for specified cities.
    If no cities specified, runs for all supported cities.
    """
    if cities is None:
        cities = list(settings.supported_cities.keys())

    for city in cities:
        logger.info(f"=== Processing {city} ===")

        # Step 1: Scrape venues
        await _scrape_venues_for_city(city)

        # Step 2: Scrape detail pages + extract deals
        await _extract_deals_for_city(city)

    logger.info("Pipeline complete.")


async def _scrape_venues_for_city(city: str):
    """Pull venue data from all sources for a city."""

    # Google Places
    if settings.google_places_api_key:
        logger.info(f"Scraping Google Places for {city}...")
        places = await google_places.search_venues_in_city(city)
        count = google_places.save_venues_to_db(places)
        logger.info(f"  Added {count} new venues from Google Places")

    # Zomato
    logger.info(f"Scraping Zomato for {city}...")
    zomato_venues = await zomato.scrape_bars_in_city(city)
    count = zomato.save_venues_to_db(zomato_venues)
    logger.info(f"  Added {count} new venues from Zomato")


async def _extract_deals_for_city(city: str):
    """For each venue in a city, scrape details and extract deals via LLM."""
    db = SessionLocal()
    try:
        venues = db.query(Venue).filter(Venue.city == city).all()
        logger.info(f"Extracting deals for {len(venues)} venues in {city}...")

        for venue in venues:
            # Skip if we already have recent deals
            existing_deals = db.query(Deal).filter(Deal.venue_id == venue.id).count()
            if existing_deals > 0:
                continue

            # Scrape detail page if we have a source URL
            raw_text = ""
            if venue.source_url and "zomato" in (venue.source or ""):
                detail = await zomato.scrape_venue_detail(venue.source_url)
                raw_text = detail.get("raw_text", "")

            if not raw_text:
                continue

            # LLM extraction
            parsed_deals = extract_deals_from_text(
                raw_text=raw_text,
                venue_name=venue.name,
                city=city,
            )

            # Save deals
            for deal_data in parsed_deals:
                deal = Deal(venue_id=venue.id, **deal_data)
                db.add(deal)

            if parsed_deals:
                logger.info(f"  {venue.name}: extracted {len(parsed_deals)} deals")

        db.commit()
    finally:
        db.close()


def run_pipeline_sync(cities: list[str] | None = None):
    """Synchronous wrapper for the async pipeline — use this from APScheduler."""
    asyncio.run(run_full_pipeline(cities))
