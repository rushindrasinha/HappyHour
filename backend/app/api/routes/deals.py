from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.deal_service import (
    get_nearby_deals,
    get_deal_detail,
    record_interaction,
    get_saved_deals,
    get_next_window,
)

router = APIRouter(prefix="/api/deals", tags=["deals"])


@router.get("/nearby")
def nearby_deals(
    lat: float = Query(..., description="User latitude"),
    lng: float = Query(..., description="User longitude"),
    radius_km: float = Query(5.0, ge=0.5, le=50, description="Search radius in km"),
    category: Optional[str] = Query(None, description="Filter: beer, wine, cocktail, food, spirits"),
    day: Optional[str] = Query(None, description="Day of week (monday, tuesday, etc.)"),
    time: Optional[str] = Query(None, description="Time in HH:MM 24h format for Plan Ahead mode (defaults to now)"),
    now_only: bool = Query(True, description="Only show deals active right now"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    device_id: Optional[str] = Query(None, description="Device ID to exclude already-seen deals"),
    db: Session = Depends(get_db),
):
    """
    Get happy hour deals near you. This is the main feed endpoint.
    Returns deal cards sorted by distance.

    Default: only deals active RIGHT NOW.
    Plan Ahead: pass day=friday&time=20:00 to browse future time slots.
    """
    return get_nearby_deals(
        db=db,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        category=category,
        day=day,
        time=time,
        now_only=now_only,
        skip=skip,
        limit=limit,
        device_id=device_id,
    )


@router.get("/next-window")
def next_window(
    lat: float = Query(..., description="User latitude"),
    lng: float = Query(..., description="User longitude"),
    radius_km: float = Query(5.0, ge=0.5, le=50, description="Search radius in km"),
    db: Session = Depends(get_db),
):
    """
    When no deals are active right now, returns info about the NEXT upcoming
    happy hour window so the frontend can show "Next happy hours at 4:00 PM"
    instead of just an empty state.
    """
    return get_next_window(db=db, lat=lat, lng=lng, radius_km=radius_km)


@router.get("/{deal_id}")
def deal_detail(deal_id: int, db: Session = Depends(get_db)):
    """Get full details for a deal — expanded card view."""
    detail = get_deal_detail(db, deal_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Deal not found")
    return detail


@router.post("/{deal_id}/interact")
def interact(
    deal_id: int,
    action: str = Query(..., description="save, skip, or tap"),
    device_id: str = Query(..., description="Anonymous device identifier"),
    db: Session = Depends(get_db),
):
    """Record a swipe interaction — save, skip, or tap to expand."""
    if action not in ("save", "skip", "tap"):
        raise HTTPException(status_code=400, detail="Action must be save, skip, or tap")
    record_interaction(db, device_id, deal_id, action)
    return {"ok": True}


@router.get("/saved/list")
def saved(
    device_id: str = Query(..., description="Anonymous device identifier"),
    db: Session = Depends(get_db),
):
    """Get all deals this user has saved."""
    return get_saved_deals(db, device_id)
