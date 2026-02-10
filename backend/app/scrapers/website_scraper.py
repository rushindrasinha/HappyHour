"""
Website scraper plugin.
For each venue that has a website URL, scrapes the site for happy hour info.

This is the highest-quality source for deal data because bars often list their
own deals on their website. The LLM parser handles the variety of formats.
"""

import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Keywords that indicate happy hour content on a page
HAPPY_HOUR_KEYWORDS = [
    "happy hour", "happyhour", "happy-hour",
    "drink deals", "drink special", "drinks special",
    "bar menu", "bar offers",
    "buy one get one", "bogo", "b1g1",
    "half price", "half off", "50% off",
    "weekday special", "evening special",
    "cocktail hour", "sundowner",
    "ladies night", "ladies' night",
    "pitcher deal", "pint deal",
    "beer special", "wine special",
]

# URL paths that might contain happy hour info
INTERESTING_PATHS = [
    "/happy-hour", "/happyhour", "/happy_hour",
    "/drinks", "/bar", "/bar-menu",
    "/menu", "/food-and-drinks",
    "/offers", "/deals", "/specials", "/promotions",
    "/events",
]


async def scrape_venue_website(website_url: str, venue_name: str = "") -> dict:
    """
    Scrape a venue's website for happy hour deal information.

    Strategy:
    1. Fetch the homepage and look for happy hour keywords
    2. Find links to relevant subpages (menu, offers, happy hour)
    3. Scrape those subpages too
    4. Combine all relevant text for LLM parsing

    Returns: {
        "raw_text": str,   # Combined text from all pages (max 8000 chars)
        "url": str,        # Original URL
        "pages_scraped": int,
        "has_happy_hour_mention": bool,
    }
    """
    if not website_url:
        return {"raw_text": "", "url": "", "pages_scraped": 0, "has_happy_hour_mention": False}

    # Normalize URL
    if not website_url.startswith("http"):
        website_url = f"https://{website_url}"

    all_text = []
    pages_scraped = 0
    has_hh_mention = False

    async with httpx.AsyncClient(
        timeout=15,
        headers=HEADERS,
        follow_redirects=True,
        max_redirects=5,
    ) as client:
        # Step 1: Scrape the homepage
        homepage_text, homepage_links = await _scrape_page(client, website_url)
        if homepage_text:
            all_text.append(homepage_text)
            pages_scraped += 1

            if _has_happy_hour_mention(homepage_text):
                has_hh_mention = True

        # Step 2: Find and scrape relevant subpages
        relevant_urls = _find_relevant_links(homepage_links, website_url)

        for url in relevant_urls[:5]:  # Cap at 5 subpages
            page_text, _ = await _scrape_page(client, url)
            if page_text:
                all_text.append(page_text)
                pages_scraped += 1
                if _has_happy_hour_mention(page_text):
                    has_hh_mention = True
            await asyncio.sleep(0.5)  # Be polite

    combined = "\n\n---\n\n".join(all_text)

    return {
        "raw_text": combined[:8000],
        "url": website_url,
        "pages_scraped": pages_scraped,
        "has_happy_hour_mention": has_hh_mention,
    }


async def _scrape_page(client: httpx.AsyncClient, url: str) -> tuple[str, list[dict]]:
    """
    Scrape a single page. Returns (extracted_text, links).
    Links are dicts with 'href' and 'text' keys.
    """
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return "", []

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return "", []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise
        for tag in soup.select("script, style, nav, footer, header, iframe, noscript"):
            tag.decompose()

        # Extract meaningful text
        text_parts = []

        # Look for sections with relevant content
        for selector in [
            "[class*='happy'], [class*='hour'], [class*='deal'], [class*='offer']",
            "[class*='menu'], [class*='drink'], [class*='bar']",
            "[class*='special'], [class*='promotion'], [class*='event']",
            "[id*='happy'], [id*='hour'], [id*='deal'], [id*='offer']",
            "[id*='menu'], [id*='drink'], [id*='bar']",
        ]:
            for el in soup.select(selector):
                text = el.get_text(separator=" ", strip=True)
                if text and len(text) > 20:
                    text_parts.append(text)

        # If no targeted sections found, grab main content
        if not text_parts:
            main = soup.select_one("main, article, [role='main'], .content, #content")
            if main:
                text_parts.append(main.get_text(separator=" ", strip=True))
            else:
                body = soup.select_one("body")
                if body:
                    text_parts.append(body.get_text(separator=" ", strip=True))

        # Also extract happy hour specific patterns from full page text
        full_text = soup.get_text(separator=" ", strip=True)
        hh_patterns = [
            r"happy\s*hour[^.]{0,200}\.",
            r"(?:BOGO|buy\s*one\s*get\s*one)[^.]{0,200}\.",
            r"\d+%\s*off[^.]{0,200}\.",
            r"₹\s*\d+[^.]{0,100}(?:pint|beer|wine|cocktail|drink|shot)[^.]{0,100}\.",
            r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s*(?:special|deal|offer)[^.]{0,200}\.",
            r"(?:4|5|6|7|8)\s*(?:pm|PM)\s*(?:to|–|-|till)\s*(?:7|8|9|10|11)\s*(?:pm|PM)[^.]{0,200}\.",
        ]
        for pattern in hh_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            text_parts.extend(matches)

        # Extract links for subpage discovery
        links = []
        for a in soup.select("a[href]"):
            links.append({
                "href": a.get("href", ""),
                "text": a.get_text(strip=True).lower(),
            })

        combined = "\n".join(text_parts)
        # Clean up excessive whitespace
        combined = re.sub(r"\s{3,}", " ", combined)

        return combined[:4000], links

    except (httpx.HTTPError, Exception) as e:
        logger.debug(f"Failed to scrape {url}: {e}")
        return "", []


def _find_relevant_links(links: list[dict], base_url: str) -> list[str]:
    """Find links that likely point to happy hour / menu / deals pages."""
    from urllib.parse import urljoin, urlparse

    base_domain = urlparse(base_url).netloc
    relevant = []
    seen = set()

    for link in links:
        href = link.get("href", "")
        text = link.get("text", "")

        # Skip empty, anchor-only, or external links
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Stay on same domain
        if parsed.netloc != base_domain:
            continue

        # Skip if already seen
        if full_url in seen:
            continue
        seen.add(full_url)

        # Check if URL path matches interesting patterns
        path = parsed.path.lower()
        is_relevant_path = any(p in path for p in INTERESTING_PATHS)

        # Check if link text mentions relevant keywords
        is_relevant_text = any(
            kw in text
            for kw in ["menu", "drink", "bar", "happy", "hour", "offer", "deal", "special", "event"]
        )

        if is_relevant_path or is_relevant_text:
            relevant.append(full_url)

    return relevant


def _has_happy_hour_mention(text: str) -> bool:
    """Check if text contains any happy hour related keywords."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in HAPPY_HOUR_KEYWORDS)
