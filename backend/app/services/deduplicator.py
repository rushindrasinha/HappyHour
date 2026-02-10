"""
Venue deduplication service.

When scraping from multiple sources (Google, Zomato, Dineout), the same bar
appears multiple times. This service merges duplicates into a single venue
with the best available data from each source.

Deduplication strategy:
1. Exact source_id match (same source, same ID → same venue)
2. Name + proximity match (similar name within 100m → likely same venue)
3. Merge: keep the venue with the most data, enrich with fields from the other
"""

import logging
import math
import re
from difflib import SequenceMatcher

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.venue import Venue

logger = logging.getLogger(__name__)

# Two venues within this distance (meters) with similar names are likely the same
PROXIMITY_THRESHOLD_M = 150

# Minimum name similarity score (0-1) to consider a match
NAME_SIMILARITY_THRESHOLD = 0.7


def deduplicate_venues_in_city(city: str) -> int:
    """
    Find and merge duplicate venues in a city.
    Returns the number of duplicates merged.
    """
    db = SessionLocal()
    merged_count = 0

    try:
        venues = (
            db.query(Venue)
            .filter(Venue.city == city)
            .order_by(Venue.created_at)  # Keep the oldest (first-scraped) as primary
            .all()
        )

        logger.info(f"Deduplicating {len(venues)} venues in {city}")

        # Build an index for fast lookup
        processed = set()
        merge_groups = []

        for i, v1 in enumerate(venues):
            if v1.id in processed:
                continue

            group = [v1]
            for j in range(i + 1, len(venues)):
                v2 = venues[j]
                if v2.id in processed:
                    continue

                if _is_duplicate(v1, v2):
                    group.append(v2)
                    processed.add(v2.id)

            if len(group) > 1:
                merge_groups.append(group)
                processed.add(v1.id)

        # Merge each group
        for group in merge_groups:
            _merge_venue_group(db, group)
            merged_count += len(group) - 1

        db.commit()
        logger.info(f"Merged {merged_count} duplicate venues in {city} ({len(merge_groups)} groups)")

    finally:
        db.close()

    return merged_count


def _is_duplicate(v1: Venue, v2: Venue) -> bool:
    """Check if two venues are likely the same place."""
    # Must be in the same city
    if v1.city != v2.city:
        return False

    # Check name similarity
    name_sim = _name_similarity(v1.name, v2.name)
    if name_sim < NAME_SIMILARITY_THRESHOLD:
        return False

    # Check proximity
    if v1.lat and v1.lng and v2.lat and v2.lng:
        distance = _haversine_m(v1.lat, v1.lng, v2.lat, v2.lng)
        if distance > PROXIMITY_THRESHOLD_M:
            return False
    else:
        # If we don't have coords for one, rely on name similarity alone
        # but require a higher threshold
        if name_sim < 0.9:
            return False

    return True


def _name_similarity(name1: str, name2: str) -> float:
    """
    Compute similarity between two venue names.
    Normalizes names before comparison (lowercase, strip common suffixes, etc.)
    """
    n1 = _normalize_name(name1)
    n2 = _normalize_name(name2)

    if n1 == n2:
        return 1.0

    return SequenceMatcher(None, n1, n2).ratio()


def _normalize_name(name: str) -> str:
    """Normalize a venue name for comparison."""
    name = name.lower().strip()
    # Remove common suffixes that vary between sources
    for suffix in [
        " bar", " pub", " brewery", " brewpub", " lounge",
        " restaurant", " restro", " cafe", " kitchen",
        " and bar", " & bar", " - bar",
        " mumbai", " bangalore", " pune", " delhi", " chennai",
        " india",
    ]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    # Remove special characters
    name = re.sub(r"[^\w\s]", "", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _merge_venue_group(db: Session, group: list[Venue]):
    """
    Merge a group of duplicate venues into the primary (first) venue.
    Keeps the primary, enriches it with data from duplicates, deletes the rest.
    """
    primary = group[0]

    for duplicate in group[1:]:
        # Enrich primary with any data it's missing
        _enrich_venue(primary, duplicate)

        # Move any deals from duplicate to primary
        for deal in duplicate.deals:
            deal.venue_id = primary.id

        logger.debug(f"Merged '{duplicate.name}' ({duplicate.source}) into '{primary.name}' ({primary.source})")

        # Delete the duplicate
        db.delete(duplicate)


def _enrich_venue(primary: Venue, other: Venue):
    """Fill in missing fields on primary from other venue."""
    enrichable_fields = [
        "address", "phone", "website", "photo_url", "photos",
        "rating", "price_range", "cuisine_tags", "source_url",
    ]

    for field in enrichable_fields:
        primary_val = getattr(primary, field)
        other_val = getattr(other, field)

        if not primary_val and other_val:
            setattr(primary, field, other_val)
        elif field == "rating" and other_val and primary_val:
            # Average the ratings
            setattr(primary, field, round((primary_val + other_val) / 2, 1))

    # If primary has no coordinates (0,0) but other does, use other's
    if (not primary.lat or primary.lat == 0) and other.lat and other.lat != 0:
        primary.lat = other.lat
        primary.lng = other.lng


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
