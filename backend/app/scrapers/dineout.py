"""
Dineout (Swiggy Dineout) scraper plugin.
Scrapes bar/pub listings and deals from Dineout, which often has
offers and happy hour information that Zomato/Google don't have.
"""

import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.city_config import CityConfig

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Dineout uses city slugs in URLs
DINEOUT_BASE = "https://www.swiggy.com/dineout"


async def search_bars_in_city(city: CityConfig, pages: int = 10) -> list[dict]:
    """
    Search Dineout for bars/pubs in a city.
    Returns list of venue dicts with partial info (name, area, source_url).
    """
    if not city.dineout_slug:
        return []

    venues = []

    async with httpx.AsyncClient(
        timeout=30,
        headers=HEADERS,
        follow_redirects=True,
    ) as client:
        for page in range(1, pages + 1):
            url = f"{DINEOUT_BASE}/{city.dineout_slug}/bars-and-pubs?page={page}"
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.debug(f"Dineout page {page} returned {resp.status_code}")
                    break

                soup = BeautifulSoup(resp.text, "html.parser")

                # Dineout restaurant cards
                cards = soup.select("[class*='RestaurantCard'], [class*='restaurant-card'], [data-testid*='restaurant']")
                if not cards:
                    # Try broader selectors
                    cards = soup.select("a[href*='/restaurant/']")

                if not cards:
                    logger.debug(f"No cards found on Dineout page {page}, stopping")
                    break

                for card in cards:
                    venue = _parse_dineout_card(card, city.name)
                    if venue:
                        venues.append(venue)

                logger.info(f"  Dineout page {page}: found {len(cards)} cards")
                await asyncio.sleep(1)  # Rate limit

            except httpx.HTTPError as e:
                logger.warning(f"Dineout error on page {page}: {e}")
                break

    logger.info(f"Dineout: found {len(venues)} venues in {city.display_name}")
    return venues


async def scrape_venue_deals(venue_url: str) -> dict:
    """
    Scrape a Dineout venue page for deal/offer information.
    Returns raw text for LLM parsing.
    """
    if not venue_url:
        return {"raw_text": "", "url": venue_url}

    async with httpx.AsyncClient(
        timeout=20,
        headers=HEADERS,
        follow_redirects=True,
    ) as client:
        try:
            resp = await client.get(venue_url)
            if resp.status_code != 200:
                return {"raw_text": "", "url": venue_url}

            soup = BeautifulSoup(resp.text, "html.parser")
            text_parts = []

            # Look for offer/deal sections
            for selector in [
                "[class*='offer'], [class*='Offer']",
                "[class*='deal'], [class*='Deal']",
                "[class*='happy'], [class*='Happy']",
                "[class*='discount'], [class*='Discount']",
                "[class*='menu'], [class*='Menu']",
                "[class*='highlight'], [class*='Highlight']",
                "[class*='promotion'], [class*='Promotion']",
            ]:
                for el in soup.select(selector):
                    text = el.get_text(separator=" ", strip=True)
                    if text and len(text) > 10:
                        text_parts.append(text)

            # Extract any happy hour specific patterns from full page
            page_text = soup.get_text(separator=" ", strip=True)
            hh_patterns = [
                r"happy\s*hour[^.]{0,300}\.",
                r"(?:BOGO|buy\s*one\s*get\s*one)[^.]{0,200}\.",
                r"\d+%\s*off[^.]{0,200}\.",
                r"₹\s*\d+[^.]{0,100}(?:pint|beer|wine|cocktail|drink)[^.]{0,100}\.",
                r"flat\s*\d+%[^.]{0,200}\.",
            ]
            for pattern in hh_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                text_parts.extend(matches)

            # Also grab the main info section
            for selector in ["[class*='about'], [class*='info'], [class*='description']"]:
                for el in soup.select(selector):
                    text = el.get_text(separator=" ", strip=True)
                    if text and len(text) > 20:
                        text_parts.append(text)

            combined = "\n".join(text_parts)

            return {
                "raw_text": combined[:5000],
                "url": venue_url,
            }

        except (httpx.HTTPError, Exception) as e:
            logger.debug(f"Failed to scrape Dineout venue {venue_url}: {e}")
            return {"raw_text": "", "url": venue_url}


def _parse_dineout_card(card, city_name: str) -> dict | None:
    """Parse a Dineout restaurant card into a venue dict."""
    try:
        # Extract name
        name_el = card.select_one("h2, h3, h4, [class*='name'], [class*='title']")
        name = name_el.get_text(strip=True) if name_el else None
        if not name:
            # If the card itself is a link, try to get text
            name = card.get_text(strip=True)[:100]
        if not name or len(name) < 2:
            return None

        # Extract URL
        link = card.get("href") or ""
        if not link:
            link_el = card.select_one("a[href]")
            link = link_el.get("href", "") if link_el else ""

        if link and not link.startswith("http"):
            link = f"https://www.swiggy.com{link}"

        # Extract area/location
        area_el = card.select_one("[class*='location'], [class*='area'], [class*='address'], [class*='subtitle']")
        area = area_el.get_text(strip=True) if area_el else None

        # Extract rating
        rating = None
        rating_el = card.select_one("[class*='rating']")
        if rating_el:
            try:
                rating_text = re.search(r"[\d.]+", rating_el.get_text())
                if rating_text:
                    rating = float(rating_text.group())
            except ValueError:
                pass

        # Extract a unique ID from the URL
        source_id = None
        if "/restaurant/" in link:
            parts = link.rstrip("/").split("/")
            source_id = parts[-1] if parts else None

        return {
            "name": name[:255],
            "area": area,
            "city": city_name,
            "source": "dineout",
            "source_id": f"dineout-{source_id}" if source_id else None,
            "source_url": link or None,
            "rating": rating,
            "cuisine_tags": "bar,pub",
        }

    except Exception:
        return None
