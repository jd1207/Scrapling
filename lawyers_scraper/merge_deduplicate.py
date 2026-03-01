"""
Merge and deduplicate lawyer records from all sources.

Combines Avvo, Justia, and Lawyers.com results into a single dataset:
- Deduplicates by normalized name + city
- Merges fields across sources (prefers richer source for each field)
- Filters to small practices (1-5 attorneys)
- Exports to both JSON and CSV

Usage:
    python -m lawyers_scraper.merge_deduplicate
"""

import csv
import json
import re
from pathlib import Path
from collections import defaultdict

from lawyers_scraper.config import (
    MAX_FIRM_SIZE,
    AVVO_OUTPUT,
    JUSTIA_OUTPUT,
    LAWYERS_COM_OUTPUT,
    MERGED_JSON_OUTPUT,
    MERGED_CSV_OUTPUT,
)


def normalize_name(name: str) -> str:
    """Normalize a lawyer name for deduplication."""
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [", esq.", ", esq", " esq.", " esq", ", jr.", ", jr", ", sr.", ", sr",
                   ", ii", ", iii", ", iv", ", j.d.", ", jd", ", llc", ", pllc", ", p.c.",
                   ", pc", ", pa", ", p.a."]:
        name = name.replace(suffix, "")
    # Remove extra whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def normalize_city(city: str) -> str:
    """Normalize city name."""
    city = city.lower().strip()
    # Normalize common variants
    variants = {
        "new york": "new york",
        "new york city": "new york",
        "nyc": "new york",
        "manhattan": "new york",
        "brooklyn": "brooklyn",
        "queens": "queens",
        "bronx": "bronx",
        "newark": "newark",
        "jersey city": "jersey city",
        "east orange": "east orange",
        "elizabeth": "elizabeth",
    }
    return variants.get(city, city)


def parse_firm_size(firm_size_text: str) -> int | None:
    """Parse firm size from text like '3 attorneys', 'Solo', '1-5 Attorneys'."""
    if not firm_size_text:
        return None
    text = firm_size_text.lower().strip()

    if "solo" in text:
        return 1

    # Try to extract a number
    match = re.search(r'(\d+)\s*(?:attorney|lawyer)', text)
    if match:
        return int(match.group(1))

    # Try range like "1-5"
    match = re.search(r'(\d+)\s*-\s*(\d+)', text)
    if match:
        return int(match.group(2))  # Use upper bound

    # Try just a number
    match = re.search(r'(\d+)', text)
    if match:
        return int(match.group(1))

    return None


def is_small_practice_heuristic(record: dict) -> bool:
    """Use heuristics to guess if this is a small practice when firm_size is unavailable."""
    firm = record.get("firm_name", "").lower()
    name = record.get("name", "").lower()

    # Common patterns for solo/small practices
    solo_patterns = [
        "law office of",
        "law offices of",
        "law firm of",
        "attorney at law",
        "attorneys at law",
    ]
    for pattern in solo_patterns:
        if pattern in firm:
            return True

    # If firm name contains the lawyer's last name, likely small
    if name:
        last_name = name.split()[-1] if name.split() else ""
        if last_name and last_name in firm:
            return True

    return True  # Default: include if we can't determine size


def load_json(path: str) -> list[dict]:
    """Load JSON file, return empty list if not found."""
    p = Path(path)
    if not p.exists():
        print(f"  Skipping {path} (not found)")
        return []
    with open(p) as f:
        data = json.load(f)
    print(f"  Loaded {len(data)} records from {path}")
    return data


def merge_records(records: list[dict]) -> dict:
    """Merge multiple records for the same lawyer into one, preferring non-empty fields."""
    if len(records) == 1:
        return records[0]

    # Priority order for sources
    source_priority = {"avvo": 0, "lawyers_com": 1, "justia": 2}
    records.sort(key=lambda r: source_priority.get(r.get("source", ""), 99))

    merged = {}
    all_sources = []
    all_source_urls = []

    for record in records:
        all_sources.append(record.get("source", "unknown"))
        all_source_urls.append(record.get("source_url", ""))

        for key, value in record.items():
            if key in ("source", "source_url", "scraped_at"):
                continue

            # For list fields, combine and deduplicate
            if isinstance(value, list) and value:
                existing = merged.get(key, [])
                if isinstance(existing, list):
                    combined = existing + value
                    # Deduplicate while preserving order
                    seen = set()
                    deduped = []
                    for item in combined:
                        item_key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
                        if item_key not in seen:
                            seen.add(item_key)
                            deduped.append(item)
                    merged[key] = deduped
                else:
                    merged[key] = value
            # For scalar fields, prefer non-empty
            elif value and (key not in merged or not merged[key]):
                merged[key] = value

    merged["sources"] = all_sources
    merged["source_urls"] = all_source_urls
    return merged


def filter_small_practices(records: list[dict]) -> list[dict]:
    """Filter to small practices (1-5 attorneys)."""
    # Group by firm name to count attorneys per firm
    firm_attorneys = defaultdict(set)
    for record in records:
        firm = record.get("firm_name", "").strip()
        name = record.get("name", "").strip()
        if firm and name:
            firm_attorneys[normalize_name(firm)].add(normalize_name(name))

    filtered = []
    for record in records:
        # Check explicit firm size
        firm_size = parse_firm_size(record.get("firm_size", ""))
        if firm_size is not None:
            if firm_size <= MAX_FIRM_SIZE:
                record["firm_size_parsed"] = firm_size
                filtered.append(record)
            continue

        # Check by counting attorneys per firm in our dataset
        firm = normalize_name(record.get("firm_name", "").strip())
        if firm and firm in firm_attorneys:
            count = len(firm_attorneys[firm])
            if count <= MAX_FIRM_SIZE:
                record["firm_size_parsed"] = count
                filtered.append(record)
            continue

        # Fall back to heuristics
        if is_small_practice_heuristic(record):
            record["firm_size_parsed"] = None
            filtered.append(record)

    return filtered


def export_csv(records: list[dict], path: str):
    """Export records to CSV."""
    if not records:
        print("No records to export")
        return

    # Flatten list fields for CSV
    csv_records = []
    for record in records:
        flat = {}
        for key, value in record.items():
            if isinstance(value, list):
                if value and isinstance(value[0], dict):
                    flat[key] = "; ".join(
                        ", ".join(f"{k}: {v}" for k, v in item.items()) if isinstance(item, dict) else str(item)
                        for item in value
                    )
                else:
                    flat[key] = "; ".join(str(v) for v in value)
            else:
                flat[key] = value
        csv_records.append(flat)

    # Determine column order
    priority_cols = [
        "name", "firm_name", "firm_size_parsed", "phone", "email",
        "address", "city", "state", "zip", "website",
        "practice_areas", "years_experience", "licensed_since",
        "education", "bar_admissions", "rating", "num_reviews",
        "bio", "sources", "source_urls",
    ]
    all_cols = set()
    for record in csv_records:
        all_cols.update(record.keys())

    fieldnames = [c for c in priority_cols if c in all_cols]
    fieldnames += sorted(all_cols - set(fieldnames))

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(csv_records)

    print(f"Exported {len(csv_records)} records to {path}")


def main():
    print("Loading source data...")
    avvo_data = load_json(AVVO_OUTPUT)
    justia_data = load_json(JUSTIA_OUTPUT)
    lawyers_com_data = load_json(LAWYERS_COM_OUTPUT)

    all_records = avvo_data + justia_data + lawyers_com_data
    print(f"\nTotal records across all sources: {len(all_records)}")

    if not all_records:
        print("No records found. Run the spiders first:")
        print("  python -m lawyers_scraper.run --source avvo")
        print("  python -m lawyers_scraper.run --source justia")
        print("  python -m lawyers_scraper.run --source lawyers_com")
        return

    # Deduplicate by normalized name + city
    print("\nDeduplicating...")
    groups = defaultdict(list)
    for record in all_records:
        key = (
            normalize_name(record.get("name", "")),
            normalize_city(record.get("city", "")),
        )
        groups[key].append(record)

    merged_records = [merge_records(records) for records in groups.values()]
    print(f"After deduplication: {len(merged_records)} unique lawyers")

    # Filter to small practices
    print("\nFiltering to small practices (≤{} attorneys)...".format(MAX_FIRM_SIZE))
    filtered = filter_small_practices(merged_records)
    print(f"After filtering: {len(filtered)} small-practice lawyers")

    # Export
    print("\nExporting...")
    Path(MERGED_JSON_OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    with open(MERGED_JSON_OUTPUT, "w") as f:
        json.dump(filtered, f, indent=2, default=str)
    print(f"Saved JSON to {MERGED_JSON_OUTPUT}")

    export_csv(filtered, MERGED_CSV_OUTPUT)

    # Print summary statistics
    print("\n--- Summary ---")
    print(f"Total unique lawyers: {len(filtered)}")

    cities = defaultdict(int)
    areas = defaultdict(int)
    for record in filtered:
        city = record.get("city", "unknown")
        cities[city] += 1
        for area in record.get("practice_areas", []):
            areas[area] += 1

    print("\nBy city:")
    for city, count in sorted(cities.items(), key=lambda x: -x[1])[:10]:
        print(f"  {city}: {count}")

    print("\nTop practice areas:")
    for area, count in sorted(areas.items(), key=lambda x: -x[1])[:10]:
        print(f"  {area}: {count}")


if __name__ == "__main__":
    main()
