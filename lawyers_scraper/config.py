"""
Configuration for lawyer scraping tool.
Adjust locations, practice areas, rate limits, and proxy settings here.
"""

# Target locations: (city, state_abbrev, state_full)
LOCATIONS = [
    ("newark", "nj", "new-jersey"),
    ("new-york", "ny", "new-york"),
    ("jersey-city", "nj", "new-jersey"),
    ("east-orange", "nj", "new-jersey"),
    ("elizabeth", "nj", "new-jersey"),
    ("brooklyn", "ny", "new-york"),
    ("queens", "ny", "new-york"),
    ("bronx", "ny", "new-york"),
    ("manhattan", "ny", "new-york"),
]

# Practice areas to search (used for building search URLs)
PRACTICE_AREAS = [
    "criminal-defense",
    "personal-injury",
    "family",
    "immigration",
    "bankruptcy",
    "business",
    "real-estate",
    "employment-labor",
    "estate-planning",
    "civil-rights",
    "tax",
    "traffic-tickets",
    "dui-dwi",
    "workers-compensation",
]

# Spider throttling settings
CONCURRENT_REQUESTS = 2
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 2.0  # seconds between requests to same domain
MAX_BLOCKED_RETRIES = 3

# Max pages of results to scrape per location+practice_area combo (0 = unlimited)
MAX_PAGES_PER_SEARCH = 20

# Max firm size to include (1-5 attorneys = small practice)
MAX_FIRM_SIZE = 5

# Output paths
OUTPUT_DIR = "lawyers_scraper/output"
AVVO_OUTPUT = f"{OUTPUT_DIR}/avvo_lawyers.json"
JUSTIA_OUTPUT = f"{OUTPUT_DIR}/justia_lawyers.json"
LAWYERS_COM_OUTPUT = f"{OUTPUT_DIR}/lawyers_com_lawyers.json"
MERGED_JSON_OUTPUT = f"{OUTPUT_DIR}/all_lawyers_merged.json"
MERGED_CSV_OUTPUT = f"{OUTPUT_DIR}/all_lawyers_merged.csv"

# Optional: proxy list for rotation (fill in with your proxies)
# Format: ["http://user:pass@host:port", ...]
PROXIES = []
