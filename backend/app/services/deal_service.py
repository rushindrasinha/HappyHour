from datetime import datetime
from typing import Optional

from sqlalchemy import func, and_, or_, cast, Float
from sqlalchemy.orm import Session, joinedload
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_MakePoint

from app.models.venue import Venue
from app.models.deal import Deal
from app.models.interaction import Interaction


def get_nearby_deals(
    db: Session,
    lat: float,
    lng: float,
    radius_km: float = 5.0,
    category: Optional[str] = None,
    day: Optional[str] = None,
    now_only: bool = True,
    skip: int = 0,
    limit: int = 20,
    device_id: Optional[str] = None,
) -> list[dict]:
    """
    Get happy hour deals near a location, optionally filtered by category and time.
    Returns deals sorted by distance, with venue info attached.
    """
    # Build point from user's location
    user_point = func.ST_SetSRID(ST_MakePoint(lng, lat), 4326)
    radius_meters = radius_km * 1000

    # Base query: deals with venues within radius
    query = (
        db.query(Deal, Venue, ST_Distance(Venue.location, user_point).label("distance_m"))
        .join(Venue, Deal.venue_id == Venue.id)
        .filter(ST_DWithin(Venue.location, user_point, radius_meters))
    )

    # Filter by category
    if category:
        query = query.filter(Deal.category == category.lower())

    # Filter by day of week
    if day is None:
        day = datetime.now().strftime("%A").lower()
    query = query.filter(or_(Deal.day_of_week == day, Deal.day_of_week == "all"))

    # Filter to only live-right-now deals
    if now_only:
        current_time = datetime.now().strftime("%H:%M")
        query = query.filter(
            or_(
                Deal.is_all_day == True,  # noqa: E712
                and_(Deal.start_time <= current_time, Deal.end_time >= current_time),
            )
        )

    # Exclude already-seen deals for this device
    if device_id:
        seen_deal_ids = (
            db.query(Interaction.deal_id)
            .filter(Interaction.device_id == device_id)
            .subquery()
        )
        query = query.filter(~Deal.id.in_(seen_deal_ids))

    # Order by distance
    query = query.order_by("distance_m").offset(skip).limit(limit)

    results = []
    for deal, venue, distance_m in query.all():
        results.append(_format_deal_card(deal, venue, distance_m))

    return results


def get_deal_detail(db: Session, deal_id: int) -> Optional[dict]:
    """Get full details for a single deal + its venue + sibling deals."""
    result = (
        db.query(Deal, Venue)
        .join(Venue, Deal.venue_id == Venue.id)
        .filter(Deal.id == deal_id)
        .first()
    )
    if not result:
        return None

    deal, venue = result

    # Get all other deals at this venue
    sibling_deals = db.query(Deal).filter(Deal.venue_id == venue.id, Deal.id != deal.id).all()

    detail = _format_deal_card(deal, venue, distance_m=None)
    detail["venue_details"] = {
        "address": venue.address,
        "phone": venue.phone,
        "website": venue.website,
        "rating": venue.rating,
        "price_range": venue.price_range,
        "cuisine_tags": venue.cuisine_tags.split(",") if venue.cuisine_tags else [],
        "photos": venue.photos.split(",") if venue.photos else [],
        "source_url": venue.source_url,
    }
    detail["other_deals"] = [
        {
            "id": d.id,
            "item_name": d.item_name,
            "deal_price": d.deal_price,
            "discount_text": d.discount_text,
            "category": d.category,
            "start_time": d.start_time,
            "end_time": d.end_time,
        }
        for d in sibling_deals
    ]
    return detail


def record_interaction(db: Session, device_id: str, deal_id: int, action: str) -> None:
    """Record a swipe interaction (save/skip/tap)."""
    interaction = Interaction(device_id=device_id, deal_id=deal_id, action=action)
    db.merge(interaction)
    db.commit()


def get_saved_deals(db: Session, device_id: str) -> list[dict]:
    """Get all deals a user has saved."""
    results = (
        db.query(Deal, Venue)
        .join(Venue, Deal.venue_id == Venue.id)
        .join(Interaction, Interaction.deal_id == Deal.id)
        .filter(Interaction.device_id == device_id, Interaction.action == "save")
        .order_by(Interaction.created_at.desc())
        .all()
    )
    return [_format_deal_card(deal, venue, distance_m=None) for deal, venue in results]


def _format_deal_card(deal: Deal, venue: Venue, distance_m: Optional[float]) -> dict:
    """Format a deal + venue into the card shape the frontend expects."""
    card = {
        "id": deal.id,
        "venue_id": venue.id,
        "venue_name": venue.name,
        "area": venue.area,
        "city": venue.city,
        "venue_photo": venue.photo_url,
        "item_name": deal.item_name,
        "description": deal.description,
        "category": deal.category,
        "original_price": deal.original_price,
        "deal_price": deal.deal_price,
        "discount_text": deal.discount_text,
        "deal_photo": deal.photo_url,
        "day_of_week": deal.day_of_week,
        "start_time": deal.start_time,
        "end_time": deal.end_time,
        "is_all_day": deal.is_all_day,
        "verified": deal.verified,
    }
    if distance_m is not None:
        card["distance_km"] = round(distance_m / 1000, 1)
    return card
