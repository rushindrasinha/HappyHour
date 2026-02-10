from sqlalchemy import Column, Integer, String, Float, Text, DateTime, func
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography

from app.core.database import Base


class Venue(Base):
    """A bar, pub, or restaurant that has happy hour deals."""

    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), unique=True, index=True)

    # Location
    address = Column(Text)
    area = Column(String(255), index=True)  # e.g. "Lower Parel", "Koramangala"
    city = Column(String(100), nullable=False, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    location = Column(Geography(geometry_type="POINT", srid=4326))

    # Venue info
    cuisine_tags = Column(Text)  # comma-separated: "bar,pub,brewery"
    rating = Column(Float)
    price_range = Column(Integer)  # 1-4 ($ to $$$$)
    phone = Column(String(20))
    website = Column(String(500))

    # Images
    photo_url = Column(String(500))
    photos = Column(Text)  # JSON array of photo URLs

    # Data source tracking
    source = Column(String(50))  # "zomato", "google", "manual"
    source_id = Column(String(255))  # external ID from source
    source_url = Column(String(500))

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    deals = relationship("Deal", back_populates="venue", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Venue {self.name} ({self.city})>"
