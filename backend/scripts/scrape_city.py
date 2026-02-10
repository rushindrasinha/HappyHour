"""
CLI script to run the scraping pipeline for a city.

Usage:
  # Scrape everything for Mumbai (all 3 phases)
  python -m scripts.scrape_city --city=mumbai

  # Just discover venues (Phase 1 only — Google Places grid search)
  python -m scripts.scrape_city --city=mumbai --phase=venues

  # Just enrich venues with details (Phase 2 only — Google Place Details)
  python -m scripts.scrape_city --city=mumbai --phase=enrich

  # Just extract deals (Phase 3 only — website scraping + LLM parsing)
  python -m scripts.scrape_city --city=mumbai --phase=deals

  # Re-extract deals even for venues that already have them
  python -m scripts.scrape_city --city=mumbai --phase=deals --force

  # Run for ALL configured cities
  python -m scripts.scrape_city --all

  # List available cities
  python -m scripts.scrape_city --list

  # Dry run: just show grid search stats without making API calls
  python -m scripts.scrape_city --city=mumbai --dry-run
"""

import argparse
import logging
import sys

from app.scrapers.city_config import get_city, list_cities, CITIES
from app.scrapers.google_places import generate_grid_points
from app.scrapers.pipeline import run_pipeline_sync


def main():
    parser = argparse.ArgumentParser(
        description="HappyHour scraping pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.scrape_city --city=mumbai              # Full pipeline for Mumbai
  python -m scripts.scrape_city --city=mumbai --phase=venues  # Just venue discovery
  python -m scripts.scrape_city --city=mumbai --phase=deals   # Just deal extraction
  python -m scripts.scrape_city --all                       # All cities
  python -m scripts.scrape_city --list                      # Show available cities
  python -m scripts.scrape_city --city=mumbai --dry-run     # Show stats only
        """,
    )

    parser.add_argument(
        "--city",
        type=str,
        help="City name (e.g., mumbai, bangalore, pune, delhi, chennai)",
    )
    parser.add_argument(
        "--phase",
        type=str,
        choices=["venues", "enrich", "deals", "all"],
        default="all",
        help="Pipeline phase to run (default: all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_cities",
        help="Run for all configured cities",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process even if data already exists",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_cities",
        help="List all available cities and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making API calls",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    args = parser.parse_args()

    # Set up logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # List cities
    if args.list_cities:
        print("\nAvailable cities:")
        print("-" * 50)
        for name, city in CITIES.items():
            grid = generate_grid_points(city.bounds, city.grid_spacing_km)
            print(
                f"  {name:<12} {city.display_name:<15} "
                f"{len(grid):>4} grid points  "
                f"({len(grid) * len(city.place_types)} API calls for venues)"
            )
        print()
        return

    # Dry run
    if args.dry_run:
        city_name = args.city
        if not city_name:
            print("--dry-run requires --city")
            sys.exit(1)

        city = get_city(city_name)
        if not city:
            print(f"Unknown city: {city_name}")
            print(f"Available: {', '.join(list_cities())}")
            sys.exit(1)

        grid = generate_grid_points(city.bounds, city.grid_spacing_km)
        queries = len(grid) * len(city.place_types)

        print(f"\n{'='*50}")
        print(f"Dry Run: {city.display_name}")
        print(f"{'='*50}")
        print(f"  Bounds: N={city.bounds.north}, S={city.bounds.south}, E={city.bounds.east}, W={city.bounds.west}")
        print(f"  Grid spacing: {city.grid_spacing_km} km")
        print(f"  Grid points: {len(grid)}")
        print(f"  Place types: {', '.join(city.place_types)}")
        print(f"  Total Nearby Search queries: {queries}")
        print(f"  Est. Nearby Search cost: ${queries * 0.032:.2f}")
        print(f"  Est. unique venues: ~{queries * 2}-{queries * 4}")
        print(f"  Est. Place Details cost: ${queries * 3 * 0.017:.2f} (assuming ~{queries * 3} venues)")
        print(f"  Deal sources: {', '.join(city.deal_sources)}")
        print(f"  Zomato slug: {city.zomato_slug or 'N/A'}")
        print(f"  Dineout slug: {city.dineout_slug or 'N/A'}")
        print()
        return

    # Validate args
    if not args.city and not args.all_cities:
        parser.print_help()
        print("\nError: specify --city=<name> or --all")
        sys.exit(1)

    if args.city and args.all_cities:
        print("Error: specify --city or --all, not both")
        sys.exit(1)

    # Validate city
    city_name = None
    if args.city:
        city_name = args.city.lower()
        if not get_city(city_name):
            print(f"Unknown city: {city_name}")
            print(f"Available: {', '.join(list_cities())}")
            sys.exit(1)

    # Run pipeline
    print(f"\nStarting pipeline: city={'ALL' if args.all_cities else city_name}, phase={args.phase}, force={args.force}\n")

    run_pipeline_sync(
        city_name=city_name,
        phase=args.phase,
        force=args.force,
    )


if __name__ == "__main__":
    main()
