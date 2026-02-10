from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://user:password@localhost:5432/happyhour"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # External APIs
    zomato_api_key: Optional[str] = None
    google_places_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # App
    app_env: str = "development"
    port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Supported cities (lat, lng, radius_km) — legacy format kept for backward compat
    # Full city config with bounding boxes is in app/scrapers/city_config.py
    supported_cities: dict = {
        "mumbai": {"lat": 19.0760, "lng": 72.8777, "radius_km": 30},
        "bangalore": {"lat": 12.9716, "lng": 77.5946, "radius_km": 30},
        "pune": {"lat": 18.5204, "lng": 73.8567, "radius_km": 25},
        "delhi": {"lat": 28.6139, "lng": 77.2090, "radius_km": 35},
        "chennai": {"lat": 13.0827, "lng": 80.2707, "radius_km": 25},
        "goa": {"lat": 15.4909, "lng": 73.8278, "radius_km": 40},
        "hyderabad": {"lat": 17.3850, "lng": 78.4867, "radius_km": 25},
        "kolkata": {"lat": 22.5726, "lng": 88.3639, "radius_km": 20},
    }

    class Config:
        env_file = ".env"


settings = Settings()
