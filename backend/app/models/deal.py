from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Deal(Base):
    """A happy hour deal at a venue."""

    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False, index=True)

    # What's the deal
    item_name = Column(String(255), nullable=False)  # "Kingfisher Pint", "House Wine"
    description = Column(Text)  # "Buy 1 get 1 free on all draft beers"
    category = Column(String(50), index=True)  # "beer", "wine", "cocktail", "food", "spirits"
    original_price = Column(Float)  # regular price
    deal_price = Column(Float)  # happy hour price
    discount_text = Column(String(255))  # "50% off", "BOGO", "₹149"
    photo_url = Column(String(500))

    # When is it active
    day_of_week = Column(String(20), index=True)  # "monday", "tuesday", ... or "all"
    start_time = Column(String(10))  # "16:00" (24h format)
    end_time = Column(String(10))  # "20:00"
    is_all_day = Column(Boolean, default=False)

    # Data quality
    verified = Column(Boolean, default=False)
    confidence = Column(Float, default=0.5)  # 0-1, how confident we are in parsed data
    source_text = Column(Text)  # raw text this was extracted from
    last_verified_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    venue = relationship("Venue", back_populates="deals")

    def __repr__(self):
        return f"<Deal {self.item_name} @ {self.deal_price} ({self.day_of_week} {self.start_time}-{self.end_time})>"
