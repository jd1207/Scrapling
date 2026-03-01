"""
Justia.com spider — Scrapes lawyer profiles from Justia's lawyer directory.

Justia has clean, well-structured pages that are generally easy to scrape.
Uses basic FetcherSession (no stealth needed for most pages).

Usage:
    from lawyers_scraper.spiders.justia_spider import JustiaLawyerSpider
    result = JustiaLawyerSpider(crawldir="lawyers_scraper/checkpoints/justia").start()
    result.items.to_json("lawyers_scraper/output/justia_lawyers.json", indent=True)
"""

from datetime import datetime, timezone

from scrapling.spiders import Spider, Request, Response
from scrapling.fetchers import FetcherSession

from lawyers_scraper.config import (
    LOCATIONS,
    PRACTICE_AREAS,
    CONCURRENT_REQUESTS,
    CONCURRENT_REQUESTS_PER_DOMAIN,
    DOWNLOAD_DELAY,
    MAX_BLOCKED_RETRIES,
    MAX_PAGES_PER_SEARCH,
)


class JustiaLawyerSpider(Spider):
    name = "justia_lawyers"
    allowed_domains = {"www.justia.com", "justia.com"}
    concurrent_requests = CONCURRENT_REQUESTS
    concurrent_requests_per_domain = CONCURRENT_REQUESTS_PER_DOMAIN
    download_delay = DOWNLOAD_DELAY
    max_blocked_retries = MAX_BLOCKED_RETRIES

    def configure_sessions(self, manager):
        manager.add("default", FetcherSession(
            impersonate="chrome",
            stealthy_headers=True,
            timeout=30,
        ))

    async def start_requests(self):
        """Generate Justia search URLs for each location × practice area."""
        for city, _state_abbrev, state_full in LOCATIONS:
            # All lawyers in location
            url = f"https://www.justia.com/lawyers/{state_full}/{city}"
            yield Request(url, meta={"city": city, "state": state_full, "page": 1})

            # By practice area
            for area in PRACTICE_AREAS:
                # Justia uses slightly different area slugs
                justia_area = area.replace("-", "-")  # already hyphenated
                url = f"https://www.justia.com/lawyers/{justia_area}/{state_full}/{city}"
                yield Request(url, meta={"city": city, "state": state_full, "area": area, "page": 1})

    async def parse(self, response: Response):
        """Parse listing page: extract profile links and follow pagination."""
        meta = response.meta
        page = meta.get("page", 1)

        # Extract lawyer profile links
        profile_links = set()
        for selector in [
            'a[href*="/lawyers/"]::attr(href)',
            '.lawyer-card a::attr(href)',
            '.attorney-listing a.name::attr(href)',
            'a.lawyer-name::attr(href)',
            'h3 a::attr(href)',
        ]:
            links = response.css(selector).getall()
            for link in links:
                # Filter to individual profile pages (not category/listing pages)
                if "/lawyers/" in link and link.count("/") >= 6:
                    profile_links.add(link)

        # Also try structured data
        for link in response.xpath('//a[contains(@href, "justia.com/lawyer/")]/@href').getall():
            profile_links.add(link)

        for link in profile_links:
            yield response.follow(
                link,
                callback=self.parse_profile,
                meta={"city": meta.get("city"), "state": meta.get("state")},
            )

        # Follow pagination
        if MAX_PAGES_PER_SEARCH == 0 or page < MAX_PAGES_PER_SEARCH:
            next_url = (
                response.css('a[rel="next"]::attr(href)').get()
                or response.css('.pagination a.next::attr(href)').get()
                or response.css('a:contains("Next")::attr(href)').get()
            )
            if next_url:
                yield response.follow(
                    next_url,
                    meta={**meta, "page": page + 1},
                )

    async def parse_profile(self, response: Response):
        """Parse an individual Justia lawyer profile."""
        # Name
        name = (
            response.css('h1[itemprop="name"]::text').get("")
            or response.css("h1::text").get("")
        ).strip()

        if not name:
            return

        # Firm
        firm_name = (
            response.css('[itemprop="worksFor"]::text').get("")
            or response.css('.law-firm-name::text').get("")
            or response.css('[itemprop="legalName"]::text').get("")
        ).strip()

        # Phone
        phone = (
            response.css('[itemprop="telephone"]::text').get("")
            or response.css('a[href^="tel:"]::text').get("")
        ).strip()

        # Address
        street = response.css('[itemprop="streetAddress"]::text').get("").strip()
        locality = response.css('[itemprop="addressLocality"]::text').get("").strip()
        region = response.css('[itemprop="addressRegion"]::text').get("").strip()
        postal = response.css('[itemprop="postalCode"]::text').get("").strip()
        address = ", ".join(filter(None, [street, locality, region, postal]))

        # Website
        website = (
            response.css('a[itemprop="url"]::attr(href)').get("")
            or response.css('a.website::attr(href)').get("")
        ).strip()

        # Practice areas
        practice_areas = (
            response.css('[itemprop="knowsAbout"]::text').getall()
            or response.css('.practice-areas a::text').getall()
            or response.css('.practice-area-list li::text').getall()
        )
        practice_areas = [pa.strip() for pa in practice_areas if pa.strip()]

        # Education
        education = []
        for edu_el in response.css('.education-entry, [itemprop="alumniOf"]'):
            school = (
                edu_el.css('[itemprop="name"]::text').get("")
                or edu_el.css("::text").get("")
            ).strip()
            degree = edu_el.css('.degree::text').get("").strip()
            year = edu_el.css('.year::text').get("").strip()
            if school:
                education.append({
                    "school": school,
                    "degree": degree,
                    "year": year,
                })

        # Bar admissions
        bar_admissions = []
        for bar_el in response.css('.bar-admission, .jurisdictions li'):
            text = bar_el.css("::text").get("").strip()
            if text:
                bar_admissions.append(text)

        # Bio / about
        bio = response.css('[itemprop="description"]::text').get("").strip()

        # Email
        email = response.css('[itemprop="email"]::text').get("").strip()

        yield {
            "name": name,
            "firm_name": firm_name,
            "phone": phone,
            "email": email,
            "address": address,
            "city": locality or response.meta.get("city", ""),
            "state": region or response.meta.get("state", ""),
            "zip": postal,
            "website": website,
            "practice_areas": practice_areas,
            "education": education,
            "bar_admissions": bar_admissions,
            "bio": bio,
            "source": "justia",
            "source_url": response.url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
