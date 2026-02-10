"""
Google Places API scraper.
Pulls venue data (name, location, photos, ratings) for bars/pubs in supported cities.
This gives us the venue foundation — deals get layered on via other scrapers + LLM parsing.
"""

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.venue import Venue


PLACE_TYPES = ["bar", "night_club", "pub"]
BASE_URL = "https://maps.googleapis.com/maps/api/place"


async def search_venues_in_city(city_name: str) -> list[dict]:
    """Search Google Places for bars/pubs in a city."""
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

            # Follow next_page_token for more results
            next_token = data.get("next_page_token")
            while next_token:
                import asyncio
                await asyncio.sleep(2)  # Google requires a short delay
                params = {"pagetoken": next_token, "key": settings.google_places_api_key}
                resp = await client.get(f"{BASE_URL}/nearbysearch/json", params=params)
                data = resp.json()
                for place in data.get("results", []):
                    all_places.append(_parse_place(place, city_name))
                next_token = data.get("next_page_token")

    return all_places


async def get_place_details(place_id: str) -> dict:
    """Get detailed info for a single place (website, phone, hours)."""
    if not settings.google_places_api_key:
        return {}

    async with httpx.AsyncClient(timeout=30) as client:
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


def save_venues_to_db(places: list[dict]) -> int:
    """Upsert scraped venues into the database."""
    db = SessionLocal()
    count = 0
    try:
        for place in places:
            existing = (
                db.query(Venue)
                .filter(Venue.source == "google", Venue.source_id == place["source_id"])
                .first()
            )
            if existing:
                # Update existing
                for key, value in place.items():
                    if value is not None and key != "source_id":
                        setattr(existing, key, value)
            else:
                venue = Venue(**place)
                # Set PostGIS geography point
                venue.location = func.ST_SetSRID(
                    func.ST_MakePoint(place["lng"], place["lat"]), 4326
                )
                db.add(venue)
                count += 1
        db.commit()
    finally:
        db.close()
    return count


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
