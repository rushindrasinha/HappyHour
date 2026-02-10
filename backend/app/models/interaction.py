from sqlalchemy import Column, Integer, String, DateTime, func, UniqueConstraint

from app.core.database import Base


class Interaction(Base):
    """Tracks user swipe interactions (save/skip) for future recommendations."""

    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(255), nullable=False, index=True)  # anonymous device fingerprint
    deal_id = Column(Integer, nullable=False, index=True)
    action = Column(String(20), nullable=False)  # "save", "skip", "tap"
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("device_id", "deal_id", "action", name="uq_device_deal_action"),
    )
