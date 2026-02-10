"""
Seed the database with sample venues and deals for development/demo purposes.
Run: python -m scripts.seed_data
"""

from sqlalchemy import func

from app.core.database import engine, SessionLocal, Base
from app.models.venue import Venue
from app.models.deal import Deal


SAMPLE_VENUES = [
    {
        "name": "The Irish House",
        "slug": "the-irish-house-lower-parel",
        "address": "Ground Floor, Trade View Building, Lower Parel, Mumbai",
        "area": "Lower Parel",
        "city": "mumbai",
        "lat": 18.9935,
        "lng": 72.8270,
        "rating": 4.3,
        "price_range": 3,
        "cuisine_tags": "bar,pub,irish,brewery",
        "source": "seed",
        "source_id": "seed-irish-house-mumbai",
        "photo_url": None,
        "deals": [
            {"item_name": "Kingfisher Draught Pint", "category": "beer", "deal_price": 149, "original_price": 350, "discount_text": "₹149 pints", "day_of_week": "all", "start_time": "16:00", "end_time": "20:00", "confidence": 1.0},
            {"item_name": "House Red Wine", "category": "wine", "deal_price": 199, "original_price": 450, "discount_text": "₹199 glasses", "day_of_week": "all", "start_time": "16:00", "end_time": "20:00", "confidence": 1.0},
            {"item_name": "Classic Mojito", "category": "cocktail", "deal_price": 249, "original_price": 550, "discount_text": "Buy 1 Get 1", "day_of_week": "friday", "start_time": "17:00", "end_time": "21:00", "confidence": 1.0},
        ],
    },
    {
        "name": "Toit Brewpub",
        "slug": "toit-brewpub-indiranagar",
        "address": "298, 100 Feet Rd, Indiranagar, Bangalore",
        "area": "Indiranagar",
        "city": "bangalore",
        "lat": 12.9784,
        "lng": 77.6408,
        "rating": 4.5,
        "price_range": 3,
        "cuisine_tags": "brewery,bar,craft-beer",
        "source": "seed",
        "source_id": "seed-toit-bangalore",
        "photo_url": None,
        "deals": [
            {"item_name": "Toit Lager Pint", "category": "beer", "deal_price": 199, "original_price": 400, "discount_text": "50% off craft pints", "day_of_week": "wednesday", "start_time": "15:00", "end_time": "19:00", "confidence": 1.0},
            {"item_name": "Basmati Blonde Pint", "category": "beer", "deal_price": 199, "original_price": 400, "discount_text": "50% off craft pints", "day_of_week": "wednesday", "start_time": "15:00", "end_time": "19:00", "confidence": 1.0},
            {"item_name": "Loaded Nachos", "category": "food", "deal_price": 149, "original_price": 299, "discount_text": "Half price starters", "day_of_week": "all", "start_time": "15:00", "end_time": "19:00", "confidence": 1.0},
        ],
    },
    {
        "name": "Monkey Bar",
        "slug": "monkey-bar-koregaon-park",
        "address": "Mundhwa Road, Koregaon Park, Pune",
        "area": "Koregaon Park",
        "city": "pune",
        "lat": 18.5362,
        "lng": 73.8938,
        "rating": 4.2,
        "price_range": 3,
        "cuisine_tags": "bar,gastropub,casual-dining",
        "source": "seed",
        "source_id": "seed-monkey-bar-pune",
        "photo_url": None,
        "deals": [
            {"item_name": "LIIT", "category": "cocktail", "deal_price": 299, "original_price": 599, "discount_text": "₹299 LIIT", "day_of_week": "thursday", "start_time": "16:00", "end_time": "20:00", "confidence": 1.0},
            {"item_name": "Bira White Pint", "category": "beer", "deal_price": 149, "original_price": 300, "discount_text": "₹149", "day_of_week": "all", "start_time": "12:00", "end_time": "19:00", "confidence": 1.0},
        ],
    },
    {
        "name": "Hauz Khas Social",
        "slug": "hauz-khas-social-delhi",
        "address": "9-A & 12, Hauz Khas Village, New Delhi",
        "area": "Hauz Khas",
        "city": "delhi",
        "lat": 28.5494,
        "lng": 77.2001,
        "rating": 4.1,
        "price_range": 2,
        "cuisine_tags": "bar,cafe,social,co-working",
        "source": "seed",
        "source_id": "seed-social-delhi",
        "photo_url": None,
        "deals": [
            {"item_name": "Budweiser Pint", "category": "beer", "deal_price": 99, "original_price": 299, "discount_text": "₹99 pints!", "day_of_week": "tuesday", "start_time": "15:00", "end_time": "19:00", "confidence": 1.0},
            {"item_name": "Sangria Pitcher", "category": "wine", "deal_price": 399, "original_price": 799, "discount_text": "Half price pitchers", "day_of_week": "friday", "start_time": "16:00", "end_time": "20:00", "confidence": 1.0},
            {"item_name": "Vodka Shots (3)", "category": "spirits", "deal_price": 199, "original_price": 450, "discount_text": "3 shots for ₹199", "day_of_week": "saturday", "start_time": "18:00", "end_time": "22:00", "confidence": 1.0},
        ],
    },
    {
        "name": "Bay 146",
        "slug": "bay-146-chennai",
        "address": "146, TTK Road, Alwarpet, Chennai",
        "area": "Alwarpet",
        "city": "chennai",
        "lat": 13.0339,
        "lng": 80.2506,
        "rating": 4.0,
        "price_range": 3,
        "cuisine_tags": "bar,lounge,pub",
        "source": "seed",
        "source_id": "seed-bay-146-chennai",
        "photo_url": None,
        "deals": [
            {"item_name": "Carlsberg Draught", "category": "beer", "deal_price": 129, "original_price": 300, "discount_text": "₹129 draughts", "day_of_week": "all", "start_time": "16:00", "end_time": "20:00", "confidence": 1.0},
            {"item_name": "Cosmopolitan", "category": "cocktail", "deal_price": 249, "original_price": 500, "discount_text": "50% off cocktails", "day_of_week": "wednesday", "start_time": "17:00", "end_time": "21:00", "confidence": 1.0},
        ],
    },
]


def seed():
    """Create tables and insert sample data."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        for venue_data in SAMPLE_VENUES:
            deals_data = venue_data.pop("deals")

            # Check if already seeded
            existing = db.query(Venue).filter(Venue.source_id == venue_data["source_id"]).first()
            if existing:
                print(f"  Skipping {venue_data['name']} (already exists)")
                continue

            venue = Venue(**venue_data)
            venue.location = func.ST_SetSRID(
                func.ST_MakePoint(venue_data["lng"], venue_data["lat"]), 4326
            )
            db.add(venue)
            db.flush()  # Get venue.id

            for deal_data in deals_data:
                deal = Deal(venue_id=venue.id, verified=True, **deal_data)
                db.add(deal)

            print(f"  Seeded {venue_data['name']} with {len(deals_data)} deals")

        db.commit()
        print("\nSeed complete!")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
