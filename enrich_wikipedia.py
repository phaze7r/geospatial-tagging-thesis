# scripts/enrich_wikipedia.py

# This script enriches the raw descriptions with Wikipedia/Wikidata using the MediaWiki API.
# It follows this priority:
# 1) If 'wikipedia' tag was present (title known), fetch summary/URL directly.
# 2) Else if 'wikidata' present, resolve sitelinks -> Wikipedia title, then fetch summary/URL.
# 3) Else perform coordinate-based geosearch to find a nearby page and fetch summary/URL.
#
# Outputs:
# - data/processed/descriptions_enriched.csv
# - data/processed/enrichment_log.json

import os  # For handling file paths and directories
import csv  # For reading and writing CSV files
import time  # For sleeping between requests to respect API rate limits
import json  # For logging and structured data handling
import uuid  # For potential dedup group id assistance if needed
import math  # For distance heuristics if applied later
import logging  # For console logging of enrichment progress
import requests  # For HTTP requests to MediaWiki and Wikidata APIs
from datetime import datetime  # For timestamps in logs

# Define input and output paths matching project conventions
PROCESSED_DIR = "data/processed"  # Base processed directory
INPUT_CSV = os.path.join(PROCESSED_DIR, "descriptions_raw.csv")  # Input from Step 1
OUTPUT_CSV = os.path.join(PROCESSED_DIR, "descriptions_enriched.csv")  # Enriched output
LOG_JSON = os.path.join(PROCESSED_DIR, "enrichment_log.json")  # Log of enrichment metrics

# Ensure processed directory exists
os.makedirs(PROCESSED_DIR, exist_ok=True)  # Create directory if missing

# Configure logging for informative outputs
logging.basicConfig(  # Set up logging
    level=logging.INFO,  # Info level to show progress
    format="%(asctime)s - %(levelname)s - %(message)s"  # Message format
)

# Define MediaWiki API endpoint (English; we may also query Urdu if relevant)
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"  # English Wikipedia API base URL
# Define Wikidata API endpoint
WIKIDATA_API = "https://www.wikidata.org/w/api.php"  # Wikidata API base URL

# Helper to perform a GET request with retries and polite sleeping
def http_get(url, params, max_retries=5, base_backoff=1.5):
    # Iterate through attempts for robust fetching
    for attempt in range(max_retries):
        try:
            # Send GET request with a reasonable timeout
            resp = requests.get(url, params=params, timeout=30)
            # Raise for non-200 statuses
            resp.raise_for_status()
            # Parse and return JSON
            return resp.json()
        except Exception as e:
            # Compute exponential backoff with slight jitter
            delay = base_backoff * (2 ** attempt) + (0.25 * attempt)
            # Log the issue with attempt count and delay
            logging.warning(f"HTTP error on {url}: {e}. Retrying in {delay:.1f}s")
            # Sleep before retrying
            time.sleep(delay)
    # If all retries exhausted, raise a runtime error
    raise RuntimeError(f"Failed GET after retries: {url}")

# Resolve a Wikidata QID to an English Wikipedia title via sitelinks
def wikidata_to_enwiki_title(qid):
    # Validate QID format (should start with Q and be followed by digits)
    if not qid or not qid.startswith("Q") or not qid[1:].isdigit():
        logging.warning(f"Invalid Wikidata QID format: {qid}")
        return ""
    # Define parameters for wikidata API to fetch sitelinks
    params = {
        "action": "wbgetentities",  # API action to get entities
        "ids": qid,  # The QID to resolve
        "props": "sitelinks",  # Request sitelinks to get enwiki title
        "format": "json"  # Response format JSON
    }
    try:
        # Perform the API request
        data = http_get(WIKIDATA_API, params)
        # Navigate JSON safely to get the enwiki title
        title = data.get("entities", {}).get(qid, {}).get("sitelinks", {}).get("enwiki", {}).get("title", "")
        # Return the found title or empty string
        return title
    except Exception as e:
        logging.warning(f"Failed to resolve Wikidata QID {qid}: {e}")
        return ""

# Fetch a page summary and URL from English Wikipedia given a page title
def fetch_enwiki_summary(title):
    # Validate title is not empty
    if not title or not title.strip():
        return "", ""
    # Clean the title
    title = title.strip()
    # Define parameters for the summary extract query
    params = {
        "action": "query",  # Use 'query' action
        "prop": "extracts|info",  # Request extracts and basic info
        "exintro": True,  # Only the introduction part of the page
        "explaintext": True,  # Plain text without HTML
        "exlimit": 1,  # Limit to one extract
        "inprop": "url",  # Include full URL in the response
        "titles": title,  # The page title to query
        "format": "json"  # Response format JSON
    }
    try:
        # Perform the API request
        data = http_get(WIKIPEDIA_API, params)
        # Parse the page object from the response
        pages = data.get("query", {}).get("pages", {}) or {}
        # Iterate through pages to find the first valid one
        for _, page in pages.items():
            # Skip missing pages
            if "missing" in page:
                continue
            # Extract the full URL and summary extract
            url = page.get("fullurl", "")
            extract = page.get("extract", "")
            # Only return if we have meaningful content
            if extract and len(extract.strip()) > 10:
                return url, extract.strip()
        # If nothing found, return empty strings
        return "", ""
    except Exception as e:
        logging.warning(f"Failed to fetch Wikipedia summary for '{title}': {e}")
        return "", ""

# Perform a coordinate-based geosearch on English Wikipedia to find nearby pages
def geosearch_enwiki(lat, lon, radius_m=500):
    # If coordinates are missing, return no result
    if lat is None or lon is None:
        return ""
    # Define parameters for the geosearch query
    params = {
        "action": "query",  # 'query' action
        "list": "geosearch",  # Use the geosearch list
        "gscoord": f"{lat}|{lon}",  # Latitude and longitude as string
        "gsradius": radius_m,  # Search radius in meters
        "gslimit": 1,  # Return only the top match
        "format": "json"  # Response format JSON
    }
    # Perform the API request
    data = http_get(WIKIPEDIA_API, params)
    # Extract the first result's title if available
    items = data.get("query", {}).get("geosearch", []) or []
    # Return found title or empty string
    return items[0]["title"] if items else ""

# Main enrichment function
def main():
    # Log start of enrichment
    logging.info("Starting Wikipedia/Wikidata enrichment...")
    # Check if input file exists
    if not os.path.exists(INPUT_CSV):
        logging.error(f"Input file not found: {INPUT_CSV}")
        logging.error("Please run the collection script first: python scripts/collect_overpass_islamabad.py")
        return
    # Read input CSV rows into memory
    rows = []
    # Track stats for the log
    n_input = 0
    n_has_wikipedia = 0
    n_has_wikidata = 0
    n_geosearch_used = 0
    n_enriched = 0
    n_errors = 0
    # Open the input CSV for reading
    try:
        with open(INPUT_CSV, "r", encoding="utf-8") as f:
            # Use DictReader to parse header and rows
            reader = csv.DictReader(f)
            # Iterate through each row and collect
            for row in reader:
                # Increment input counter
                n_input += 1
                # Append to rows list
                rows.append(row)
    except Exception as e:
        logging.error(f"Failed to read input CSV {INPUT_CSV}: {e}")
        return
    # Log input stats
    logging.info(f"Loaded {n_input} rows from {INPUT_CSV}")
    # Iterate through rows to enrich with progress tracking
    for idx, row in enumerate(rows):
        try:
            # Show progress every 50 rows
            if idx % 50 == 0 and idx > 0:
                logging.info(f"Progress: {idx}/{n_input} rows processed ({idx/n_input*100:.1f}%)")
            # Initialize local variables for found title, url, and summary description
            title = ""
            url = ""
            summary = ""
            # Get candidate fields from row for decision making
            wikipedia_title = (row.get("wikipedia_title") or "").strip()
            wikidata_qid = (row.get("wikidata") or "").strip()
            lat = row.get("lat")
            lon = row.get("lon")
            # Convert coordinates to float if available with better validation
            try:
                lat = float(lat) if lat not in (None, "", "None", "null") else None
                lon = float(lon) if lon not in (None, "", "None", "null") else None
                # Validate coordinate ranges
                if lat is not None and (lat < -90 or lat > 90):
                    lat = None
                if lon is not None and (lon < -180 or lon > 180):
                    lon = None
            except (ValueError, TypeError):
                lat = None
                lon = None
            # If a wikipedia title is already present, use it
            if wikipedia_title:
                # Count this path usage
                n_has_wikipedia += 1
                # Set title from the row
                title = wikipedia_title
                # Fetch URL and summary via the title
                url, summary = fetch_enwiki_summary(title)
                # Be polite with a short sleep
                time.sleep(0.3)
            # Else try Wikidata resolution
            elif wikidata_qid:
                # Count this path usage
                n_has_wikidata += 1
                # Resolve to enwiki title via sitelinks
                title = wikidata_to_enwiki_title(wikidata_qid)
                # If a title was found, fetch summary and URL
                if title:
                    url, summary = fetch_enwiki_summary(title)
                # Be polite with a short sleep
                time.sleep(0.4)
            # Else attempt geosearch by coordinates
            else:
                # Only attempt geosearch if coordinates are available
                if lat is not None and lon is not None:
                    # Count geosearch path usage
                    n_geosearch_used += 1
                    # Find the nearest page title
                    title = geosearch_enwiki(lat, lon, radius_m=1000)  # Increased radius
                    # If a title is found, fetch URL and summary
                    if title:
                        url, summary = fetch_enwiki_summary(title)
                    # Be polite with a short sleep
                    time.sleep(0.4)
            # If we managed to get a summary, consider the row enriched
            if summary:
                n_enriched += 1
                # Write back the fields into canonical columns
                row["wikipedia_title"] = title
                row["wikipedia_url"] = url
                # If description_raw was empty, use summary as a proxy text source
                if not (row.get("description_raw") or "").strip():
                    row["description_raw"] = summary
                    # Annotate the description source
                    row["description_source"] = "Wikipedia"
                # If description_raw exists but description_source is empty, mark as OSM+Wikipedia
                elif not (row.get("description_source") or "").strip():
                    row["description_source"] = "OSM+Wikipedia"
            # If no summary found, leave row as-is but ensure description_source is set
            else:
                if not (row.get("description_source") or "").strip():
                    row["description_source"] = "OSM"
        except Exception as e:
            # Log error and increment error counter but continue
            logging.warning(f"Enrichment error for osm_id={row.get('osm_id')}: {e}")
            n_errors += 1
            # Sleep a bit after an error to reduce repeated failures
            time.sleep(0.8)
    # Write the enriched CSV with the same field order as input plus any updates
    if not rows:
        logging.warning("No rows to write to output CSV")
        return
    fieldnames = rows[0].keys() if rows else []
    # Open the output CSV for writing
    try:
        with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
            # Initialize DictWriter with discovered/consistent headers
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            # Write header row
            writer.writeheader()
            # Write all rows
            for row in rows:
                writer.writerow(row)
        logging.info(f"Successfully wrote {len(rows)} rows to {OUTPUT_CSV}")
    except Exception as e:
        logging.error(f"Failed to write output CSV {OUTPUT_CSV}: {e}")
        return
    # Prepare enrichment log with key metrics
    log = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "input_rows": n_input,
        "used_wikipedia_title": n_has_wikipedia,
        "used_wikidata": n_has_wikidata,
        "used_geosearch": n_geosearch_used,
        "enriched_rows": n_enriched,
        "errors": n_errors,
        "input_csv": INPUT_CSV,
        "output_csv": OUTPUT_CSV
    }
    # Write the log JSON to disk
    with open(LOG_JSON, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    # Log a summary to console
    logging.info(f"Enrichment done. Input: {n_input}, Enriched: {n_enriched}, Errors: {n_errors}")
    logging.info(f"Wrote: {OUTPUT_CSV}, {LOG_JSON}")

# Run main when executed directly
if __name__ == "__main__":
    main()  # Start enrichment