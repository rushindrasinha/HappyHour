"""
Zomato web scraper.
Zomato's public API is limited, so we scrape bar/pub pages for happy hour info.
Focuses on Indian cities where Zomato has deep coverage.
"""

import re

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.venue import Venue


# Zomato city IDs for our supported cities
ZOMATO_CITY_SLUGS = {
    "mumbai": "mumbai",
    "bangalore": "bangalore",
    "pune": "pune",
    "delhi": "delhi-ncr",
    "chennai": "chennai",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


async def scrape_bars_in_city(city_name: str, pages: int = 5) -> list[dict]:
    """
    Scrape Zomato for bar/pub listings in a city.
    Returns a list of venue dicts ready for DB insertion.
    """
    slug = ZOMATO_CITY_SLUGS.get(city_name)
    if not slug:
        return []

    venues = []

    async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for page in range(1, pages + 1):
            url = f"https://www.zomato.com/{slug}/bars?page={page}"
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                restaurant_cards = soup.select("[data-res-id]")

                for card in restaurant_cards:
                    venue_data = _parse_zomato_card(card, city_name)
                    if venue_data:
                        venues.append(venue_data)

            except httpx.HTTPError:
                continue

    return venues


async def scrape_venue_detail(venue_url: str) -> dict:
    """
    Scrape a single Zomato venue page for detailed info including happy hour mentions.
    Returns raw text content that can be passed to LLM for deal extraction.
    """
    async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        try:
            resp = await client.get(venue_url)
            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract all text that might mention happy hour deals
            text_content = []

            # Menu sections
            for section in soup.select("[class*='menu'], [class*='Menu']"):
                text_content.append(section.get_text(separator=" ", strip=True))

            # Info/about sections
            for section in soup.select("[class*='info'], [class*='about'], [class*='highlight']"):
                text_content.append(section.get_text(separator=" ", strip=True))

            # Look for happy hour specific mentions
            page_text = soup.get_text(separator=" ", strip=True)
            happy_hour_patterns = [
                r"happy\s*hour[^.]*\.",
                r"(?:BOGO|buy\s*one\s*get\s*one)[^.]*\.",
                r"\d+%\s*off[^.]*\.",
                r"₹\s*\d+[^.]*(?:pint|beer|wine|cocktail|drink)[^.]*\.",
            ]
            for pattern in happy_hour_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                text_content.extend(matches)

            return {
                "raw_text": " ".join(text_content)[:5000],  # Cap at 5k chars
                "url": venue_url,
            }

        except httpx.HTTPError:
            return {"raw_text": "", "url": venue_url}


def save_venues_to_db(venues: list[dict]) -> int:
    """Upsert Zomato-scraped venues into the database."""
    db = SessionLocal()
    count = 0
    try:
        for v in venues:
            if not v.get("lat") or not v.get("lng"):
                continue

            existing = (
                db.query(Venue)
                .filter(Venue.source == "zomato", Venue.source_id == v.get("source_id"))
                .first()
            )
            if existing:
                for key, value in v.items():
                    if value is not None and key != "source_id":
                        setattr(existing, key, value)
            else:
                venue = Venue(**v)
                venue.location = func.ST_SetSRID(
                    func.ST_MakePoint(v["lng"], v["lat"]), 4326
                )
                db.add(venue)
                count += 1
        db.commit()
    finally:
        db.close()
    return count


def _parse_zomato_card(card, city_name: str) -> dict | None:
    """Parse a Zomato restaurant card HTML element into a venue dict."""
    try:
        res_id = card.get("data-res-id")
        if not res_id:
            return None

        name_el = card.select_one("[class*='name'], h3, h4")
        name = name_el.get_text(strip=True) if name_el else None
        if not name:
            return None

        # Try to extract location data
        address_el = card.select_one("[class*='address'], [class*='location'], [class*='subzone']")
        area = address_el.get_text(strip=True) if address_el else None

        # Rating
        rating_el = card.select_one("[class*='rating']")
        rating = None
        if rating_el:
            try:
                rating = float(rating_el.get_text(strip=True).split("/")[0])
            except (ValueError, IndexError):
                pass

        # Image
        img_el = card.select_one("img[src*='res_']") or card.select_one("img")
        photo_url = img_el.get("src") if img_el else None

        # Link
        link_el = card.select_one("a[href]")
        source_url = None
        if link_el:
            href = link_el.get("href", "")
            source_url = href if href.startswith("http") else f"https://www.zomato.com{href}"

        return {
            "name": name,
            "slug": f"zomato-{res_id}",
            "area": area,
            "city": city_name,
            "lat": 0.0,  # Will be enriched from detail page or Google geocoding
            "lng": 0.0,
            "photo_url": photo_url,
            "rating": rating,
            "cuisine_tags": "bar,pub",
            "source": "zomato",
            "source_id": str(res_id),
            "source_url": source_url,
        }
    except Exception:
        return None
