from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_MakePoint
from sqlalchemy import func

from app.core.database import get_db
from app.models.venue import Venue
from app.models.deal import Deal

router = APIRouter(prefix="/api/venues", tags=["venues"])


@router.get("/nearby")
def nearby_venues(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(5.0, ge=0.5, le=50),
    db: Session = Depends(get_db),
):
    """Get venues near a location (for the map view)."""
    user_point = func.ST_SetSRID(ST_MakePoint(lng, lat), 4326)
    radius_meters = radius_km * 1000

    results = (
        db.query(
            Venue,
            ST_Distance(Venue.location, user_point).label("distance_m"),
            func.count(Deal.id).label("deal_count"),
        )
        .outerjoin(Deal, Deal.venue_id == Venue.id)
        .filter(ST_DWithin(Venue.location, user_point, radius_meters))
        .group_by(Venue.id)
        .order_by("distance_m")
        .limit(100)
        .all()
    )

    return [
        {
            "id": venue.id,
            "name": venue.name,
            "area": venue.area,
            "city": venue.city,
            "lat": venue.lat,
            "lng": venue.lng,
            "photo_url": venue.photo_url,
            "rating": venue.rating,
            "deal_count": deal_count,
            "distance_km": round(distance_m / 1000, 1),
        }
        for venue, distance_m, deal_count in results
    ]


@router.get("/{venue_id}")
def venue_detail(venue_id: int, db: Session = Depends(get_db)):
    """Get full venue info with all its deals."""
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Venue not found")

    deals = db.query(Deal).filter(Deal.venue_id == venue.id).all()

    return {
        "id": venue.id,
        "name": venue.name,
        "address": venue.address,
        "area": venue.area,
        "city": venue.city,
        "lat": venue.lat,
        "lng": venue.lng,
        "photo_url": venue.photo_url,
        "photos": venue.photos.split(",") if venue.photos else [],
        "rating": venue.rating,
        "price_range": venue.price_range,
        "cuisine_tags": venue.cuisine_tags.split(",") if venue.cuisine_tags else [],
        "phone": venue.phone,
        "website": venue.website,
        "source_url": venue.source_url,
        "deals": [
            {
                "id": d.id,
                "item_name": d.item_name,
                "description": d.description,
                "category": d.category,
                "original_price": d.original_price,
                "deal_price": d.deal_price,
                "discount_text": d.discount_text,
                "photo_url": d.photo_url,
                "day_of_week": d.day_of_week,
                "start_time": d.start_time,
                "end_time": d.end_time,
                "is_all_day": d.is_all_day,
                "verified": d.verified,
            }
            for d in deals
        ],
    }
