"""
LLM-powered parser that takes raw unstructured text (from scraped pages, menus,
Instagram posts, etc.) and extracts structured happy hour deal data.

This is the secret sauce — turns messy real-world text into clean deal cards.
"""

import json
from typing import Optional

from openai import OpenAI

from app.core.config import settings

EXTRACTION_PROMPT = """You are a happy hour deal extractor. Given raw text from a bar/restaurant page,
extract ALL happy hour deals into structured JSON.

For each deal found, return:
- item_name: What's on offer (e.g. "Kingfisher Pint", "House Red Wine", "Mojito")
- description: Brief description if available
- category: One of: beer, wine, cocktail, spirits, food
- original_price: Regular price if mentioned (number only, INR)
- deal_price: Happy hour price (number only, INR)
- discount_text: Human-readable discount (e.g. "50% off", "BOGO", "₹149")
- day_of_week: When it's available — "monday", "tuesday", etc., or "all" for every day
- start_time: Start time in 24h format "HH:MM" (e.g. "16:00")
- end_time: End time in 24h format "HH:MM" (e.g. "20:00")
- is_all_day: true/false
- confidence: 0.0-1.0 how confident you are in this extraction

Return a JSON array of deals. If no deals found, return an empty array [].
Be generous in interpretation — if something looks like a deal, include it with lower confidence.
Prices should be in INR (Indian Rupees) for Indian venues.

Raw text:
{text}

Venue name: {venue_name}
City: {city}

Return ONLY valid JSON array, no other text."""


def extract_deals_from_text(
    raw_text: str,
    venue_name: str = "",
    city: str = "",
) -> list[dict]:
    """
    Use an LLM to extract structured deals from raw text.
    Returns a list of deal dicts ready for DB insertion.
    """
    if not settings.openai_api_key or not raw_text.strip():
        return []

    client = OpenAI(api_key=settings.openai_api_key)

    prompt = EXTRACTION_PROMPT.format(
        text=raw_text[:4000],  # Cap input
        venue_name=venue_name,
        city=city,
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2000,
        )

        content = response.choices[0].message.content.strip()

        # Clean up response — sometimes LLMs wrap in ```json blocks
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0]

        deals = json.loads(content)

        if not isinstance(deals, list):
            return []

        # Validate and clean each deal
        cleaned = []
        for deal in deals:
            cleaned_deal = _validate_deal(deal)
            if cleaned_deal:
                cleaned_deal["source_text"] = raw_text[:1000]
                cleaned.append(cleaned_deal)

        return cleaned

    except (json.JSONDecodeError, Exception):
        return []


def _validate_deal(deal: dict) -> Optional[dict]:
    """Validate and normalize a parsed deal."""
    if not deal.get("item_name"):
        return None

    valid_categories = {"beer", "wine", "cocktail", "spirits", "food"}
    category = deal.get("category", "").lower()
    if category not in valid_categories:
        category = "beer"  # default

    valid_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "all"}
    day = deal.get("day_of_week", "all").lower()
    if day not in valid_days:
        day = "all"

    return {
        "item_name": str(deal["item_name"])[:255],
        "description": str(deal.get("description", ""))[:500] or None,
        "category": category,
        "original_price": _safe_float(deal.get("original_price")),
        "deal_price": _safe_float(deal.get("deal_price")),
        "discount_text": str(deal.get("discount_text", ""))[:255] or None,
        "day_of_week": day,
        "start_time": _safe_time(deal.get("start_time"), "16:00"),
        "end_time": _safe_time(deal.get("end_time"), "20:00"),
        "is_all_day": bool(deal.get("is_all_day", False)),
        "confidence": min(max(float(deal.get("confidence", 0.5)), 0.0), 1.0),
    }


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_time(val, default: str) -> str:
    if not val or not isinstance(val, str):
        return default
    # Validate HH:MM format
    import re
    if re.match(r"^\d{2}:\d{2}$", val):
        return val
    return default
