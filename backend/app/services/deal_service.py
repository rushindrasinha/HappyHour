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
    time: Optional[str] = None,
    now_only: bool = True,
    skip: int = 0,
    limit: int = 20,
    device_id: Optional[str] = None,
) -> list[dict]:
    """
    Get happy hour deals near a location, optionally filtered by category and time.
    Returns deals sorted by distance, with venue info attached.

    - Default (now_only=True, no time param): shows deals active RIGHT NOW.
    - Plan Ahead (now_only=True, time="20:00", day="friday"): shows deals
      active at that specific future time slot.
    - Browse All (now_only=False): shows all deals for the given day regardless
      of time.
    """
    # Build point from user's location
    user_point = func.ST_SetSRID(ST_MakePoint(lng, lat), 4326)
    radius_meters = radius_km * 1000

    # Resolve the effective time context
    now = datetime.now()
    effective_time = time if time else now.strftime("%H:%M")
    effective_day = day if day else now.strftime("%A").lower()
    is_current_time = (time is None) and (day is None)

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
    query = query.filter(or_(Deal.day_of_week == effective_day, Deal.day_of_week == "all"))

    # Filter to deals active at the effective time
    if now_only:
        query = query.filter(
            or_(
                Deal.is_all_day == True,  # noqa: E712
                and_(Deal.start_time <= effective_time, Deal.end_time >= effective_time),
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
    current_time_str = now.strftime("%H:%M")
    for deal, venue, distance_m in query.all():
        card = _format_deal_card(deal, venue, distance_m)
        card["time_status"] = _compute_time_status(deal, current_time_str, is_current_time)
        results.append(card)

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


def get_next_window(
    db: Session,
    lat: float,
    lng: float,
    radius_km: float = 5.0,
) -> dict:
    """
    When no deals are active right now, find the NEXT upcoming deal window.
    Returns info about when deals start next so the empty state can say
    "Next happy hours start at 4:00 PM" instead of just "nothing found".
    """
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_day = now.strftime("%A").lower()

    user_point = func.ST_SetSRID(ST_MakePoint(lng, lat), 4326)
    radius_meters = radius_km * 1000

    # Find the earliest deal that starts AFTER now, today
    next_today = (
        db.query(Deal.start_time)
        .join(Venue, Deal.venue_id == Venue.id)
        .filter(
            ST_DWithin(Venue.location, user_point, radius_meters),
            or_(Deal.day_of_week == current_day, Deal.day_of_week == "all"),
            Deal.start_time > current_time,
            Deal.is_all_day == False,  # noqa: E712
        )
        .order_by(Deal.start_time.asc())
        .first()
    )

    if next_today:
        return {
            "has_upcoming": True,
            "next_start_time": next_today[0],
            "next_day": "today",
            "message": f"Next happy hours start at {_format_12h(next_today[0])}",
        }

    # Nothing left today — check tomorrow
    day_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    today_idx = day_order.index(current_day)
    tomorrow = day_order[(today_idx + 1) % 7]

    next_tomorrow = (
        db.query(Deal.start_time)
        .join(Venue, Deal.venue_id == Venue.id)
        .filter(
            ST_DWithin(Venue.location, user_point, radius_meters),
            or_(Deal.day_of_week == tomorrow, Deal.day_of_week == "all"),
            Deal.is_all_day == False,  # noqa: E712
        )
        .order_by(Deal.start_time.asc())
        .first()
    )

    if next_tomorrow:
        return {
            "has_upcoming": True,
            "next_start_time": next_tomorrow[0],
            "next_day": "tomorrow",
            "message": f"Next happy hours start tomorrow at {_format_12h(next_tomorrow[0])}",
        }

    return {
        "has_upcoming": False,
        "next_start_time": None,
        "next_day": None,
        "message": "No upcoming happy hours found nearby",
    }


def _compute_time_status(deal: Deal, current_time: str, is_current_time: bool) -> str:
    """
    Compute a time_status label for each deal card:
    - "happening_now": deal is active at the current real time
    - "starting_soon": deal starts within the next 60 minutes
    - "later_today": deal is later today
    - "upcoming": deal is for a future day (Plan Ahead mode)
    """
    if deal.is_all_day:
        return "happening_now" if is_current_time else "upcoming"

    if deal.start_time <= current_time <= deal.end_time:
        return "happening_now"

    if not is_current_time:
        return "upcoming"

    # Check if starting within 60 min
    try:
        now_h, now_m = map(int, current_time.split(":"))
        start_h, start_m = map(int, deal.start_time.split(":"))
        now_mins = now_h * 60 + now_m
        start_mins = start_h * 60 + start_m
        diff = start_mins - now_mins
        if 0 < diff <= 60:
            return "starting_soon"
    except (ValueError, AttributeError):
        pass

    return "later_today"


def _format_12h(time_str: str) -> str:
    """Convert '16:00' to '4:00 PM'."""
    try:
        h, m = map(int, time_str.split(":"))
        period = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {period}"
    except (ValueError, AttributeError):
        return time_str


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
