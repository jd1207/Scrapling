"""
Avvo.com spider — Scrapes lawyer profiles from Avvo for Newark NJ and NYC areas.

Avvo is the richest source for ratings, reviews, education, practice areas, and
years of experience. It has moderate anti-bot protection, so we use FetcherSession
with Chrome TLS impersonation (fast) and fall back to AsyncStealthySession if blocked.

Usage:
    from lawyers_scraper.spiders.avvo_spider import AvvoLawyerSpider
    result = AvvoLawyerSpider(crawldir="lawyers_scraper/checkpoints/avvo").start()
    result.items.to_json("lawyers_scraper/output/avvo_lawyers.json", indent=True)
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


class AvvoLawyerSpider(Spider):
    name = "avvo_lawyers"
    allowed_domains = {"www.avvo.com", "avvo.com"}
    concurrent_requests = CONCURRENT_REQUESTS
    concurrent_requests_per_domain = CONCURRENT_REQUESTS_PER_DOMAIN
    download_delay = DOWNLOAD_DELAY
    max_blocked_retries = MAX_BLOCKED_RETRIES

    def configure_sessions(self, manager):
        # Primary: fast HTTP with Chrome TLS impersonation
        manager.add("default", FetcherSession(
            impersonate="chrome",
            stealthy_headers=True,
            timeout=30,
        ))
        # Fallback: stealth browser for anti-bot bypass
        manager.add("stealth", AsyncStealthySession(
            headless=True,
            disable_resources=True,
            network_idle=True,
        ), lazy=True)

    async def start_requests(self):
        """Generate search URLs for each location × practice area."""
        for city, state_abbrev, state_full in LOCATIONS:
            # All lawyers in location
            url = f"https://www.avvo.com/all-lawyers/{state_abbrev}/{city}.html"
            yield Request(url, meta={"city": city, "state": state_abbrev, "page": 1})

            # By practice area for better coverage
            for area in PRACTICE_AREAS:
                url = f"https://www.avvo.com/{area}-lawyer/{state_abbrev}/{city}.html"
                yield Request(url, meta={"city": city, "state": state_abbrev, "area": area, "page": 1})

    async def parse(self, response: Response):
        """Parse listing page: extract profile links and follow pagination."""
        meta = response.meta
        page = meta.get("page", 1)

        # Extract lawyer profile links from listing
        # Avvo uses various selectors for profile cards — try multiple patterns
        profile_links = set()
        for selector in [
            'a[href*="/attorneys/"]::attr(href)',
            '.lawyer-search-result a::attr(href)',
            'a.search-result-link::attr(href)',
            '[data-lawyer-id] a::attr(href)',
            'a[href*="/lawyers/"]::attr(href)',
        ]:
            links = response.css(selector).getall()
            profile_links.update(links)

        if not profile_links:
            # Try XPath as fallback
            links = response.xpath('//a[contains(@href, "/attorneys/")]/@href').getall()
            profile_links.update(links)
            links = response.xpath('//a[contains(@href, "/lawyers/")]/@href').getall()
            profile_links.update(links)

        for link in profile_links:
            # Filter to actual profile pages (not search/category links)
            if "/attorneys/" in link or ("/lawyers/" in link and link.count("/") >= 5):
                yield response.follow(
                    link,
                    callback=self.parse_profile,
                    meta={"city": meta.get("city"), "state": meta.get("state")},
                )

        # Follow pagination
        if MAX_PAGES_PER_SEARCH == 0 or page < MAX_PAGES_PER_SEARCH:
            next_selectors = [
                'a.pagination-next::attr(href)',
                'a[rel="next"]::attr(href)',
                '.pagination a.next::attr(href)',
                'link[rel="next"]::attr(href)',
            ]
            for sel in next_selectors:
                next_url = response.css(sel).get()
                if next_url:
                    yield response.follow(
                        next_url,
                        meta={**meta, "page": page + 1},
                    )
                    break

    async def parse_profile(self, response: Response):
        """Parse an individual lawyer profile page."""
        # Name — try multiple selectors
        name = (
            response.css('h1[itemprop="name"]::text').get("")
            or response.css("h1.lawyer-name::text").get("")
            or response.css("h1::text").get("")
        ).strip()

        if not name:
            return

        # Avvo rating
        rating = (
            response.css('.avvo-rating::text').get("")
            or response.css('[class*="rating"] .number::text').get("")
            or response.css('[itemprop="ratingValue"]::text').get("")
        ).strip()

        # Phone
        phone = (
            response.css('[itemprop="telephone"]::text').get("")
            or response.css('a[href^="tel:"]::text').get("")
            or response.css('.phone-number::text').get("")
        ).strip()

        # Address components
        street = response.css('[itemprop="streetAddress"]::text').get("").strip()
        locality = response.css('[itemprop="addressLocality"]::text').get("").strip()
        region = response.css('[itemprop="addressRegion"]::text').get("").strip()
        postal = response.css('[itemprop="postalCode"]::text').get("").strip()
        address = ", ".join(filter(None, [street, locality, region, postal]))
        if not address:
            address = response.css('.address::text').get("").strip()

        # Website
        website = (
            response.css('a[itemprop="url"]::attr(href)').get("")
            or response.css('a.website-link::attr(href)').get("")
            or response.css('a[data-track="website"]::attr(href)').get("")
        ).strip()

        # Practice areas
        practice_areas = (
            response.css('[itemprop="knowsAbout"]::text').getall()
            or response.css('.practice-area::text').getall()
            or response.css('.practice-areas li::text').getall()
        )
        practice_areas = [pa.strip() for pa in practice_areas if pa.strip()]

        # Years of experience / licensed since
        years_exp = response.css('.years-experience::text').get("").strip()
        licensed_since = response.css('.licensed-since::text').get("").strip()

        # Education
        education = []
        for edu in response.css('.education-item, [itemprop="alumniOf"]'):
            school = edu.css('[itemprop="name"]::text').get("").strip() or edu.css("::text").get("").strip()
            if school:
                education.append(school)

        # Bar admissions
        bar_admissions = []
        for bar in response.css('.bar-admission, .license-item'):
            state = bar.css('.state::text').get("").strip() or bar.css("::text").get("").strip()
            year = bar.css('.year::text').get("").strip()
            if state:
                bar_admissions.append({"state": state, "year": year})

        # Reviews count
        num_reviews = response.css('.review-count::text').get("").strip()
        reviews_summary = response.css('.reviews-summary::text').get("").strip()

        # Firm name
        firm_name = (
            response.css('[itemprop="worksFor"] [itemprop="name"]::text').get("")
            or response.css('.firm-name::text').get("")
        ).strip()

        # Email (rarely exposed publicly)
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
            "years_experience": years_exp,
            "licensed_since": licensed_since,
            "education": education,
            "bar_admissions": bar_admissions,
            "rating": rating,
            "num_reviews": num_reviews,
            "reviews_summary": reviews_summary,
            "source": "avvo",
            "source_url": response.url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

    async def is_blocked(self, response):
        """Detect Avvo-specific blocking patterns."""
        if response.status in {401, 403, 429, 503}:
            return True
        # Check for CAPTCHA or challenge pages
        if response.css('[class*="captcha"], [id*="challenge"]').get():
            return True
        return False

    async def retry_blocked_request(self, request, response):
        """Switch to stealth session on block."""
        request.sid = "stealth"
        return request
