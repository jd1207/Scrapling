"""
Main entry point for the lawyer scraping tool.

Usage:
    # Run a specific spider
    python -m lawyers_scraper.run --source avvo
    python -m lawyers_scraper.run --source justia
    python -m lawyers_scraper.run --source lawyers_com

    # Run all spiders sequentially
    python -m lawyers_scraper.run --all

    # Merge results from all sources into JSON + CSV
    python -m lawyers_scraper.run --merge

    # Run everything: all spiders then merge
    python -m lawyers_scraper.run --full

    # Resume a paused spider
    python -m lawyers_scraper.run --source avvo --resume
"""

import argparse
import sys
from pathlib import Path

from lawyers_scraper.config import (
    AVVO_OUTPUT,
    JUSTIA_OUTPUT,
    LAWYERS_COM_OUTPUT,
)


def run_avvo():
    """Run the Avvo spider."""
    from lawyers_scraper.spiders.avvo_spider import AvvoLawyerSpider

    print("=" * 60)
    print("Running Avvo Spider...")
    print("=" * 60)

    spider = AvvoLawyerSpider(crawldir="lawyers_scraper/checkpoints/avvo")
    result = spider.start()

    print(f"\nAvvo results: {len(result.items)} lawyers scraped")
    if result.items:
        result.items.to_json(AVVO_OUTPUT, indent=True)
        print(f"Saved to {AVVO_OUTPUT}")

    return result


def run_justia():
    """Run the Justia spider."""
    from lawyers_scraper.spiders.justia_spider import JustiaLawyerSpider

    print("=" * 60)
    print("Running Justia Spider...")
    print("=" * 60)

    spider = JustiaLawyerSpider(crawldir="lawyers_scraper/checkpoints/justia")
    result = spider.start()

    print(f"\nJustia results: {len(result.items)} lawyers scraped")
    if result.items:
        result.items.to_json(JUSTIA_OUTPUT, indent=True)
        print(f"Saved to {JUSTIA_OUTPUT}")

    return result


def run_lawyers_com():
    """Run the Lawyers.com spider."""
    from lawyers_scraper.spiders.lawyers_com_spider import LawyersComSpider

    print("=" * 60)
    print("Running Lawyers.com Spider...")
    print("=" * 60)

    spider = LawyersComSpider(crawldir="lawyers_scraper/checkpoints/lawyers_com")
    result = spider.start()

    print(f"\nLawyers.com results: {len(result.items)} lawyers scraped")
    if result.items:
        result.items.to_json(LAWYERS_COM_OUTPUT, indent=True)
        print(f"Saved to {LAWYERS_COM_OUTPUT}")

    return result


def run_merge():
    """Merge and deduplicate results from all sources."""
    from lawyers_scraper.merge_deduplicate import main as merge_main

    print("=" * 60)
    print("Merging and deduplicating results...")
    print("=" * 60)

    merge_main()


SPIDERS = {
    "avvo": run_avvo,
    "justia": run_justia,
    "lawyers_com": run_lawyers_com,
}


def main():
    parser = argparse.ArgumentParser(
        description="Scrape lawyer information from online directories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m lawyers_scraper.run --source avvo        # Run only Avvo spider
  python -m lawyers_scraper.run --all                # Run all spiders
  python -m lawyers_scraper.run --merge              # Merge existing results
  python -m lawyers_scraper.run --full               # Run all spiders + merge
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--source", choices=list(SPIDERS.keys()),
        help="Run a specific spider",
    )
    group.add_argument(
        "--all", action="store_true",
        help="Run all spiders sequentially",
    )
    group.add_argument(
        "--merge", action="store_true",
        help="Merge results from all sources into JSON + CSV",
    )
    group.add_argument(
        "--full", action="store_true",
        help="Run all spiders then merge results",
    )

    args = parser.parse_args()

    # Ensure output directory exists
    Path("lawyers_scraper/output").mkdir(parents=True, exist_ok=True)
    Path("lawyers_scraper/checkpoints").mkdir(parents=True, exist_ok=True)

    if args.source:
        SPIDERS[args.source]()
    elif args.all:
        for name, spider_fn in SPIDERS.items():
            try:
                spider_fn()
            except Exception as e:
                print(f"\nError running {name} spider: {e}")
                print("Continuing with next spider...\n")
    elif args.merge:
        run_merge()
    elif args.full:
        for name, spider_fn in SPIDERS.items():
            try:
                spider_fn()
            except Exception as e:
                print(f"\nError running {name} spider: {e}")
                print("Continuing with next spider...\n")
        run_merge()


if __name__ == "__main__":
    main()
