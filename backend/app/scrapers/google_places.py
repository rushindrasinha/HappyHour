"""
Google Places API scraper with grid search for full city coverage.

The key insight: Google Places Nearby Search returns max 60 results per query.
A city like Mumbai has 2000+ bars. So we tile the city into a grid of small
overlapping circles and search each one, then deduplicate.

Cost estimate for Mumbai (~800 grid cells × 3 place types):
- Nearby Search: ~2,400 calls × $0.032 = ~$77
- Place Details: ~3,000 calls × $0.017 = ~$51
- Total: ~$128 one-time
"""

import asyncio
import logging
import math
from typing import Optional

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.venue import Venue
from app.scrapers.city_config import CityConfig, CityBounds

logger = logging.getLogger(__name__)

PLACE_TYPES = ["bar", "night_club", "pub"]
BASE_URL = "https://maps.googleapis.com/maps/api/place"

# Google Places returns max 60 results per query (20 per page × 3 pages)
MAX_RESULTS_PER_QUERY = 60


def generate_grid_points(bounds: CityBounds, spacing_km: float) -> list[tuple[float, float]]:
    """
    Generate a grid of lat/lng points covering the city bounding box.
    Each point becomes a search center with radius = spacing_km.

    We use overlapping circles (radius = spacing * 0.75) to ensure no gaps.
    """
    # 1 degree of latitude ≈ 111km everywhere
    lat_step = spacing_km / 111.0

    # 1 degree of longitude varies by latitude
    mid_lat = (bounds.north + bounds.south) / 2
    lng_step = spacing_km / (111.0 * math.cos(math.radians(mid_lat)))

    points = []
    lat = bounds.south
    while lat <= bounds.north:
        lng = bounds.west
        while lng <= bounds.east:
            points.append((round(lat, 6), round(lng, 6)))
            lng += lng_step
        lat += lat_step

    return points


async def grid_search_city(city: CityConfig, place_types: list[str] | None = None) -> list[dict]:
    """
    Search an entire city for bars using a grid of overlapping Google Places queries.
    Returns deduplicated list of venue dicts.
    """
    if not settings.google_places_api_key:
        logger.warning("No Google Places API key configured — skipping grid search")
        return []

    if place_types is None:
        place_types = city.place_types

    grid = generate_grid_points(city.bounds, city.grid_spacing_km)
    logger.info(
        f"Grid search: {city.display_name} — {len(grid)} grid points × "
        f"{len(place_types)} types = {len(grid) * len(place_types)} queries"
    )

    # Search radius in meters (slightly larger than spacing to ensure overlap)
    search_radius_m = int(city.grid_spacing_km * 750)  # 75% of spacing in meters

    all_places = {}  # place_id -> venue dict (natural dedup)

    async with httpx.AsyncClient(timeout=30) as client:
        # Process grid points in batches to respect rate limits
        batch_size = 10  # 10 concurrent requests
        total_queries = len(grid) * len(place_types)
        completed = 0

        for place_type in place_types:
            for i in range(0, len(grid), batch_size):
                batch = grid[i : i + batch_size]
                tasks = [
                    _search_single_point(client, lat, lng, search_radius_m, place_type, city.name)
                    for lat, lng in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        logger.warning(f"Grid search error: {result}")
                        continue
                    for place in result:
                        place_id = place.get("source_id")
                        if place_id and place_id not in all_places:
                            all_places[place_id] = place

                completed += len(batch)
                if completed % 100 == 0 or completed == total_queries:
                    logger.info(
                        f"  Progress: {completed}/{total_queries} queries — "
                        f"{len(all_places)} unique venues found"
                    )

                # Rate limiting: ~10 QPS is safe for Google Places
                await asyncio.sleep(0.2)

    logger.info(f"Grid search complete: {len(all_places)} unique venues in {city.display_name}")
    return list(all_places.values())


async def _search_single_point(
    client: httpx.AsyncClient,
    lat: float,
    lng: float,
    radius_m: int,
    place_type: str,
    city_name: str,
) -> list[dict]:
    """Search Google Places at a single grid point. Follows pagination."""
    places = []

    params = {
        "location": f"{lat},{lng}",
        "radius": radius_m,
        "type": place_type,
        "key": settings.google_places_api_key,
    }

    try:
        resp = await client.get(f"{BASE_URL}/nearbysearch/json", params=params)
        data = resp.json()

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            logger.warning(f"Google Places error at ({lat},{lng}): {data.get('status')}")
            return []

        for place in data.get("results", []):
            places.append(_parse_place(place, city_name))

        # Follow pagination (up to 3 pages = 60 results)
        next_token = data.get("next_page_token")
        page = 1
        while next_token and page < 3:
            await asyncio.sleep(2)  # Google requires delay before using next_page_token
            page_params = {"pagetoken": next_token, "key": settings.google_places_api_key}
            resp = await client.get(f"{BASE_URL}/nearbysearch/json", params=page_params)
            data = resp.json()
            for place in data.get("results", []):
                places.append(_parse_place(place, city_name))
            next_token = data.get("next_page_token")
            page += 1

    except httpx.HTTPError as e:
        logger.warning(f"HTTP error at ({lat},{lng}): {e}")

    return places


async def enrich_venue_details(place_ids: list[str], batch_size: int = 5) -> dict[str, dict]:
    """
    Fetch detailed info (website, phone, hours) for a batch of venues.
    Returns dict of place_id -> details.
    """
    if not settings.google_places_api_key:
        return {}

    details = {}
    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(place_ids), batch_size):
            batch = place_ids[i : i + batch_size]
            tasks = [_get_place_details(client, pid) for pid in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for pid, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.warning(f"Details error for {pid}: {result}")
                    continue
                details[pid] = result

            # Rate limit
            await asyncio.sleep(0.3)

            if (i + batch_size) % 50 == 0:
                logger.info(f"  Enriched {min(i + batch_size, len(place_ids))}/{len(place_ids)} venues")

    return details


async def _get_place_details(client: httpx.AsyncClient, place_id: str) -> dict:
    """Get detailed info for a single place."""
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,formatted_phone_number,website,opening_hours,photos,price_level,rating,url",
        "key": settings.google_places_api_key,
    }
    resp = await client.get(f"{BASE_URL}/details/json", params=params)
    data = resp.json().get("result", {})

    return {
        "phone": data.get("formatted_phone_number"),
        "website": data.get("website"),
        "address": data.get("formatted_address"),
        "price_range": data.get("price_level"),
        "rating": data.get("rating"),
        "source_url": data.get("url"),
    }


def save_venues_to_db(places: list[dict]) -> tuple[int, int]:
    """
    Upsert scraped venues into the database.
    Returns (new_count, updated_count).
    """
    db = SessionLocal()
    new_count = 0
    updated_count = 0
    try:
        for place in places:
            if not place.get("lat") or not place.get("lng"):
                continue

            existing = (
                db.query(Venue)
                .filter(Venue.source == "google", Venue.source_id == place["source_id"])
                .first()
            )
            if existing:
                for key, value in place.items():
                    if value is not None and key not in ("source_id", "source"):
                        setattr(existing, key, value)
                updated_count += 1
            else:
                venue = Venue(**place)
                venue.location = func.ST_SetSRID(
                    func.ST_MakePoint(place["lng"], place["lat"]), 4326
                )
                db.add(venue)
                new_count += 1
        db.commit()
    finally:
        db.close()
    return new_count, updated_count


# ─── Legacy single-point search (kept for backward compat) ──────────

async def search_venues_in_city(city_name: str) -> list[dict]:
    """Legacy: search from a single center point. Use grid_search_city instead."""
    city = settings.supported_cities.get(city_name)
    if not city or not settings.google_places_api_key:
        return []

    all_places = []
    async with httpx.AsyncClient(timeout=30) as client:
        for place_type in PLACE_TYPES:
            params = {
                "location": f"{city['lat']},{city['lng']}",
                "radius": city["radius_km"] * 1000,
                "type": place_type,
                "key": settings.google_places_api_key,
            }
            resp = await client.get(f"{BASE_URL}/nearbysearch/json", params=params)
            data = resp.json()
            for place in data.get("results", []):
                all_places.append(_parse_place(place, city_name))

            next_token = data.get("next_page_token")
            while next_token:
                await asyncio.sleep(2)
                params = {"pagetoken": next_token, "key": settings.google_places_api_key}
                resp = await client.get(f"{BASE_URL}/nearbysearch/json", params=params)
                data = resp.json()
                for place in data.get("results", []):
                    all_places.append(_parse_place(place, city_name))
                next_token = data.get("next_page_token")

    return all_places


async def get_place_details(place_id: str) -> dict:
    """Legacy wrapper for single place details."""
    if not settings.google_places_api_key:
        return {}
    async with httpx.AsyncClient(timeout=30) as client:
        return await _get_place_details(client, place_id)


def _parse_place(place: dict, city_name: str) -> dict:
    """Parse a Google Places result into our venue format."""
    location = place.get("geometry", {}).get("location", {})
    photo_ref = None
    if place.get("photos"):
        photo_ref = place["photos"][0].get("photo_reference")

    photo_url = None
    if photo_ref and settings.google_places_api_key:
        photo_url = (
            f"{BASE_URL}/photo?maxwidth=800"
            f"&photo_reference={photo_ref}"
            f"&key={settings.google_places_api_key}"
        )

    return {
        "name": place.get("name"),
        "slug": place.get("place_id", "").lower().replace(" ", "-"),
        "address": place.get("vicinity"),
        "area": place.get("vicinity", "").split(",")[-1].strip() if place.get("vicinity") else None,
        "city": city_name,
        "lat": location.get("lat"),
        "lng": location.get("lng"),
        "photo_url": photo_url,
        "rating": place.get("rating"),
        "price_range": place.get("price_level"),
        "cuisine_tags": ",".join(place.get("types", [])),
        "source": "google",
        "source_id": place.get("place_id"),
    }
