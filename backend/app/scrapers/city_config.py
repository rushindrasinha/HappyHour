"""
City configuration for the scraping pipeline.
Adding a new city = adding one entry here. The pipeline is city-agnostic.

Each city defines:
- center: lat/lng of the city center
- bounds: bounding box (north, south, east, west) for grid search
- grid_spacing_km: how far apart grid search points are (smaller = more thorough)
- sources: ordered list of source plugins to use, with priority
- zomato_slug: URL slug for Zomato (None if not on Zomato)
- dineout_slug: URL slug for Dineout (None if not on Dineout)
"""

from dataclasses import dataclass, field


@dataclass
class CityBounds:
    north: float
    south: float
    east: float
    west: float


@dataclass
class CityConfig:
    name: str
    display_name: str
    center_lat: float
    center_lng: float
    bounds: CityBounds
    grid_spacing_km: float = 1.0  # 1km grid = ~800 cells for Mumbai
    radius_km: float = 30.0
    zomato_slug: str | None = None
    dineout_slug: str | None = None
    # Source priority for deal extraction (tried in order, first success wins)
    deal_sources: list[str] = field(default_factory=lambda: ["website", "dineout", "zomato"])
    # Place types to search for in Google Places
    place_types: list[str] = field(default_factory=lambda: ["bar", "night_club", "pub"])


# ─── City Definitions ───────────────────────────────────────────────

CITIES: dict[str, CityConfig] = {
    "mumbai": CityConfig(
        name="mumbai",
        display_name="Mumbai",
        center_lat=19.0760,
        center_lng=72.8777,
        bounds=CityBounds(
            north=19.2700,  # Borivali / Dahisar
            south=18.8900,  # Colaba / Navy Nagar
            east=72.9800,   # Vashi / Navi Mumbai fringe
            west=72.7700,   # Andheri West / Juhu coastline
        ),
        grid_spacing_km=1.0,
        radius_km=30.0,
        zomato_slug="mumbai",
        dineout_slug="mumbai",
    ),
    "bangalore": CityConfig(
        name="bangalore",
        display_name="Bangalore",
        center_lat=12.9716,
        center_lng=77.5946,
        bounds=CityBounds(
            north=13.0900,
            south=12.8400,
            east=77.7600,
            west=77.4600,
        ),
        grid_spacing_km=1.0,
        radius_km=30.0,
        zomato_slug="bangalore",
        dineout_slug="bangalore",
    ),
    "pune": CityConfig(
        name="pune",
        display_name="Pune",
        center_lat=18.5204,
        center_lng=73.8567,
        bounds=CityBounds(
            north=18.6300,
            south=18.4300,
            east=73.9700,
            west=73.7500,
        ),
        grid_spacing_km=1.0,
        radius_km=25.0,
        zomato_slug="pune",
        dineout_slug="pune",
    ),
    "delhi": CityConfig(
        name="delhi",
        display_name="Delhi NCR",
        center_lat=28.6139,
        center_lng=77.2090,
        bounds=CityBounds(
            north=28.8800,
            south=28.4000,
            east=77.4500,
            west=77.0000,
        ),
        grid_spacing_km=1.5,  # Larger city, slightly coarser grid
        radius_km=35.0,
        zomato_slug="delhi-ncr",
        dineout_slug="delhi-ncr",
    ),
    "chennai": CityConfig(
        name="chennai",
        display_name="Chennai",
        center_lat=13.0827,
        center_lng=80.2707,
        bounds=CityBounds(
            north=13.2000,
            south=12.9500,
            east=80.3200,
            west=80.1800,
        ),
        grid_spacing_km=1.0,
        radius_km=25.0,
        zomato_slug="chennai",
        dineout_slug="chennai",
    ),
    "goa": CityConfig(
        name="goa",
        display_name="Goa",
        center_lat=15.4909,
        center_lng=73.8278,
        bounds=CityBounds(
            north=15.8000,
            south=15.2000,
            east=74.0500,
            west=73.6500,
        ),
        grid_spacing_km=1.5,
        radius_km=40.0,
        zomato_slug="goa",
        dineout_slug="goa",
    ),
    "hyderabad": CityConfig(
        name="hyderabad",
        display_name="Hyderabad",
        center_lat=17.3850,
        center_lng=78.4867,
        bounds=CityBounds(
            north=17.5500,
            south=17.2500,
            east=78.6500,
            west=78.3000,
        ),
        grid_spacing_km=1.0,
        radius_km=25.0,
        zomato_slug="hyderabad",
        dineout_slug="hyderabad",
    ),
    "kolkata": CityConfig(
        name="kolkata",
        display_name="Kolkata",
        center_lat=22.5726,
        center_lng=88.3639,
        bounds=CityBounds(
            north=22.6700,
            south=22.4700,
            east=88.4500,
            west=88.2800,
        ),
        grid_spacing_km=1.0,
        radius_km=20.0,
        zomato_slug="kolkata",
        dineout_slug="kolkata",
    ),
}


def get_city(name: str) -> CityConfig | None:
    """Get city config by name (case-insensitive)."""
    return CITIES.get(name.lower())


def list_cities() -> list[str]:
    """Return all configured city names."""
    return list(CITIES.keys())
