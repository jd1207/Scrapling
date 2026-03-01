"""
Lawyers.com (Martindale-Hubbell) spider — Scrapes lawyer profiles with firm size data.

Lawyers.com is the best source for firm-size information, which is critical for
filtering to small practices (1-5 attorneys). Uses FetcherSession with impersonation.

Usage:
    from lawyers_scraper.spiders.lawyers_com_spider import LawyersComSpider
    result = LawyersComSpider(crawldir="lawyers_scraper/checkpoints/lawyers_com").start()
    result.items.to_json("lawyers_scraper/output/lawyers_com_lawyers.json", indent=True)
"""

from datetime import datetime, timezone

from scrapling.spiders import Spider, Request, Response
from scrapling.fetchers import FetcherSession, AsyncStealthySession

from lawyers_scraper.config import (
    LOCATIONS,
    PRACTICE_AREAS,
    CONCURRENT_REQUESTS,
    CONCURRENT_REQUESTS_PER_DOMAIN,
    DOWNLOAD_DELAY,
    MAX_BLOCKED_RETRIES,
    MAX_PAGES_PER_SEARCH,
)


class LawyersComSpider(Spider):
    name = "lawyers_com"
    allowed_domains = {"www.lawyers.com", "lawyers.com"}
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
        manager.add("stealth", AsyncStealthySession(
            headless=True,
            disable_resources=True,
            network_idle=True,
        ), lazy=True)

    async def start_requests(self):
        """Generate Lawyers.com search URLs."""
        for city, _state_abbrev, state_full in LOCATIONS:
            # Lawyers.com uses city/state in path
            url = f"https://www.lawyers.com/{city}/{state_full}/"
            yield Request(url, meta={"city": city, "state": state_full, "page": 1})

            # By practice area
            for area in PRACTICE_AREAS:
                url = f"https://www.lawyers.com/{area}/{city}/{state_full}/"
                yield Request(url, meta={
                    "city": city, "state": state_full, "area": area, "page": 1,
                })

    async def parse(self, response: Response):
        """Parse listing page."""
        meta = response.meta
        page = meta.get("page", 1)

        # Extract lawyer profile links
        profile_links = set()
        for selector in [
            'a[href*="/attorney/"]::attr(href)',
            '.search-result a::attr(href)',
            '.listing-name a::attr(href)',
            'a.attorney-name::attr(href)',
            'h2 a[href*="lawyers.com"]::attr(href)',
        ]:
            links = response.css(selector).getall()
            profile_links.update(links)

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
                or response.css('a.next-page::attr(href)').get()
                or response.css('.pagination a:last-child::attr(href)').get()
            )
            if next_url:
                yield response.follow(
                    next_url,
                    meta={**meta, "page": page + 1},
                )

    async def parse_profile(self, response: Response):
        """Parse an individual Lawyers.com lawyer profile."""
        name = (
            response.css('h1[itemprop="name"]::text').get("")
            or response.css("h1::text").get("")
        ).strip()

        if not name:
            return

        # Firm name and size — this is the key differentiator for Lawyers.com
        firm_name = (
            response.css('[itemprop="worksFor"] [itemprop="name"]::text').get("")
            or response.css('.firm-name::text').get("")
            or response.css('[itemprop="legalName"]::text').get("")
        ).strip()

        # Firm size (critical for filtering small practices)
        firm_size_text = (
            response.css('.firm-size::text').get("")
            or response.css('[data-firm-size]::text').get("")
            or response.css('.attorneys-count::text').get("")
        ).strip()

        # Also try to find firm size in descriptive text
        if not firm_size_text:
            for text_el in response.css('.firm-details ::text').getall():
                text = text_el.strip().lower()
                if "attorney" in text or "lawyer" in text:
                    firm_size_text = text
                    break

        # Martindale-Hubbell rating (peer review ratings)
        mh_rating = (
            response.css('.martindale-rating::text').get("")
            or response.css('.peer-rating::text').get("")
            or response.css('[itemprop="ratingValue"]::text').get("")
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
            or response.css('a.website-link::attr(href)').get("")
        ).strip()

        # Practice areas
        practice_areas = (
            response.css('[itemprop="knowsAbout"]::text').getall()
            or response.css('.practice-areas li::text').getall()
            or response.css('.practice-area a::text').getall()
        )
        practice_areas = [pa.strip() for pa in practice_areas if pa.strip()]

        # Education
        education = []
        for edu_el in response.css('.education-item, [itemprop="alumniOf"]'):
            school = edu_el.css('[itemprop="name"]::text').get("").strip()
            if school:
                education.append(school)

        # Email
        email = response.css('[itemprop="email"]::text').get("").strip()

        # Reviews
        num_reviews = response.css('.review-count::text').get("").strip()

        yield {
            "name": name,
            "firm_name": firm_name,
            "firm_size": firm_size_text,
            "phone": phone,
            "email": email,
            "address": address,
            "city": locality or response.meta.get("city", ""),
            "state": region or response.meta.get("state", ""),
            "zip": postal,
            "website": website,
            "practice_areas": practice_areas,
            "education": education,
            "rating": mh_rating,
            "num_reviews": num_reviews,
            "source": "lawyers_com",
            "source_url": response.url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

    async def is_blocked(self, response):
        if response.status in {401, 403, 429, 503}:
            return True
        return False

    async def retry_blocked_request(self, request, response):
        request.sid = "stealth"
        return request
