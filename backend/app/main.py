from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api.routes import deals, venues, health

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HappyHour API",
    description="It's always happy hour somewhere near you.",
    version="0.1.0",
)

# CORS — allow Lovable frontend to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router)
app.include_router(deals.router)
app.include_router(venues.router)


@app.get("/")
def root():
    return {
        "app": "HappyHour",
        "tagline": "It's always happy hour somewhere near you.",
        "docs": "/docs",
        "cities": list(settings.supported_cities.keys()),
    }
