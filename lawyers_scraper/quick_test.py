"""
Quick test script — Use Scrapling's Fetcher directly to test scraping a single page.

This helps you verify selectors before running full spiders. Run this first to
inspect the HTML structure of each source and adjust selectors as needed.

Usage:
    python -m lawyers_scraper.quick_test
"""

from scrapling.fetchers import Fetcher


def test_avvo():
    """Fetch a single Avvo page and inspect the structure."""
    print("=" * 60)
    print("Testing Avvo.com...")
    print("=" * 60)

    try:
        page = Fetcher.get(
            "https://www.avvo.com/all-lawyers/nj/newark.html",
            impersonate="chrome",
            stealthy_headers=True,
        )
        print(f"Status: {page.status}")
        print(f"Title: {page.css('title::text').get()}")

        # Try to find lawyer links
        links = page.css('a[href*="/attorneys/"]::attr(href)').getall()
        print(f"Attorney links found: {len(links)}")
        for link in links[:5]:
            print(f"  {link}")

        if not links:
            print("No links found with attorney selector. Trying alternatives...")
            all_links = page.css('a::attr(href)').getall()
            lawyer_links = [l for l in all_links if '/lawyer' in l.lower() or '/attorney' in l.lower()]
            print(f"Alternative lawyer links: {len(lawyer_links)}")
            for link in lawyer_links[:5]:
                print(f"  {link}")

    except Exception as e:
        print(f"Error: {e}")
        print("This is expected if the site blocks non-browser requests.")
        print("The spider uses StealthyFetcher as fallback for anti-bot bypass.")


def test_justia():
    """Fetch a single Justia page and inspect the structure."""
    print("\n" + "=" * 60)
    print("Testing Justia.com...")
    print("=" * 60)

    try:
        page = Fetcher.get(
            "https://www.justia.com/lawyers/new-jersey/newark",
            impersonate="chrome",
            stealthy_headers=True,
        )
        print(f"Status: {page.status}")
        print(f"Title: {page.css('title::text').get()}")

        links = page.css('a[href*="/lawyers/"]::attr(href)').getall()
        print(f"Lawyer links found: {len(links)}")
        for link in links[:5]:
            print(f"  {link}")

    except Exception as e:
        print(f"Error: {e}")


def test_lawyers_com():
    """Fetch a single Lawyers.com page and inspect the structure."""
    print("\n" + "=" * 60)
    print("Testing Lawyers.com...")
    print("=" * 60)

    try:
        page = Fetcher.get(
            "https://www.lawyers.com/newark/new-jersey/",
            impersonate="chrome",
            stealthy_headers=True,
        )
        print(f"Status: {page.status}")
        print(f"Title: {page.css('title::text').get()}")

        links = page.css('a[href*="/attorney/"]::attr(href)').getall()
        print(f"Attorney links found: {len(links)}")
        for link in links[:5]:
            print(f"  {link}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    print("Quick selector test — inspects page structure from each source")
    print("Run this to verify/adjust CSS selectors before running full spiders.\n")
    test_avvo()
    test_justia()
    test_lawyers_com()
    print("\n" + "=" * 60)
    print("Done! Adjust selectors in spiders/ based on the HTML you see above.")
    print("=" * 60)
