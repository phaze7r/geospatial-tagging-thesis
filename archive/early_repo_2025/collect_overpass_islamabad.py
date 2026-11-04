# scripts/collect_overpass_islamabad.py

# This script queries the Overpass API for Islamabad using a tiled bbox strategy, retries with
# exponential backoff on rate limits/errors, and saves:
# - data/raw/islamabad_overpass_raw.jsonl: raw OSM elements (node/way/relation) one per line
# - data/processed/descriptions_raw.csv: flattened records in the canonical schema subset
# - data/processed/collection_log.json: summary counts, tiles, and error metrics
#
# It focuses on a Pakistan-first, Islamabad-bbox targeted pull and only collects features
# relevant to the pilot tag list for efficiency and reproducibility.

import os  # Provides functions to interact with the operating system (paths, dirs)
import json  # For reading and writing JSON data (config and logs)
import time  # For sleeping during retries and backoff
import math  # For simple math operations used in tiling
import yaml  # For loading YAML configs (bbox, labels)
import uuid  # For generating dedup_group_id seeds if needed
import random  # For setting seeds to ensure reproducibility
import logging  # For console/file logging of progress and errors
import requests  # For making HTTP requests to the Overpass API
import csv  # For writing the flattened CSV output
from datetime import datetime  # For timestamping logs and output files

# Set a global random seed for reproducibility as per project standards
random.seed(42)  # Ensures any random behavior is consistent across runs

# Define constants for directories and files according to the project structure
RAW_DIR = "data/raw"  # Directory for raw outputs
PROCESSED_DIR = "data/processed"  # Directory for processed outputs
CONFIG_DIR = "config"  # Directory for configuration files
BBOX_CONFIG = os.path.join(CONFIG_DIR, "islamabad_bbox.yaml")  # BBox config path
LABELS_CONFIG = os.path.join(CONFIG_DIR, "labels_pk.yaml")  # Labels (tag list) config path

# Ensure output directories exist; create them if missing
os.makedirs(RAW_DIR, exist_ok=True)  # Create raw directory if needed
os.makedirs(PROCESSED_DIR, exist_ok=True)  # Create processed directory if needed
os.makedirs(CONFIG_DIR, exist_ok=True)  # Create config directory if needed

# Initialize Python logging for console output
logging.basicConfig(  # Configure logging settings
    level=logging.INFO,  # Set log level to INFO for progress updates
    format="%(asctime)s - %(levelname)s - %(message)s"  # Define log message format
)

# Define Overpass API endpoint and a fallback list for resilience
OVERPASS_ENDPOINTS = [  # List of Overpass API endpoints to attempt
    "https://overpass-api.de/api/interpreter",  # Primary public Overpass instance
    "https://lz4.overpass-api.de/api/interpreter",  # Alternate Overpass instance
    "https://z.overpass-api.de/api/interpreter"  # Another alternate instance
]

# Helper function to load YAML config or use sensible defaults
def load_yaml_or_default(path, default_dict):
    # Try to load the YAML file; if missing or invalid, return the provided default
    if os.path.exists(path):  # Check if the file exists
        with open(path, "r", encoding="utf-8") as f:  # Open the file safely
            try:  # Attempt to parse YAML
                return yaml.safe_load(f)  # Return parsed dict
            except Exception as e:  # Catch parsing errors
                logging.warning(f"Failed to parse {path}, using defaults. Error: {e}")  # Warn
                return default_dict  # Return default
    else:  # If file does not exist
        logging.warning(f"{path} not found. Using default values.")  # Warn
        return default_dict  # Return default

# Load Islamabad bbox from config, with a safe default if not present
bbox_cfg = load_yaml_or_default(  # Load bbox config or default to Islamabad approximate bbox
    BBOX_CONFIG,
    {
        "name": "Islamabad",
        "bbox": [ 72.8, 33.5, 73.4, 33.9 ]  # [min_lon, min_lat, max_lon, max_lat] approximate
    }
)

# Load labels (OSM tag key=value pairs) from config, with defaults per the pilot list
labels_cfg = load_yaml_or_default(  # Load label config or provide default categories/values
    LABELS_CONFIG,
    {
        "core": {
            "amenity": ["mosque", "marketplace", "bank", "atm", "police", "fire_station"],
            "leisure": ["park"],
            "tourism": ["museum"],
            "historic": ["fort"]
        },
        "services": {
            "healthcare": ["hospital", "clinic", "pharmacy"],
            "education": ["school", "college", "university"]
        },
        "transport": {
            "public_transport": ["bus_station", "bus_stop"],
            "railway": ["station"]
        },
        "places_natural": {
            "place": ["neighbourhood"],
            "natural": ["water"],
            "landuse": ["cemetery"]
        }
    }
)

# Convert the labels config into a flat list of (key, value) pairs for querying
def flatten_label_pairs(labels_dict):
    # Initialize an empty list to collect pairs
    pairs = []
    # Iterate through top-level groups (e.g., core, services)
    for _, keyvals in labels_dict.items():
        # Iterate through tag keys (e.g., amenity, healthcare)
        for k, vals in keyvals.items():
            # For each value under the key, add a (k, v) pair
            for v in vals:
                pairs.append((k, v))
    # Return the complete list of pairs
    return pairs

# Create the flat list of (key, value) pairs from the config
TARGET_TAG_PAIRS = flatten_label_pairs(labels_cfg)  # List like [('amenity','mosque'), ...]

# Extract bbox coordinates from the config
MIN_LON, MIN_LAT, MAX_LON, MAX_LAT = bbox_cfg["bbox"]  # Unpack bbox list into variables

# Define a function to tile the bbox into an N x N grid for controlled query sizes
def tile_bbox(min_lon, min_lat, max_lon, max_lat, tiles_per_side=6):
    # Calculate the longitudinal step per tile
    lon_step = (max_lon - min_lon) / tiles_per_side
    # Calculate the latitudinal step per tile
    lat_step = (max_lat - min_lat) / tiles_per_side
    # Initialize a list to hold tile bounding boxes
    tiles = []
    # Iterate across columns
    for i in range(tiles_per_side):
        # Compute tile's min longitude
        tl_min_lon = min_lon + i * lon_step
        # Compute tile's max longitude
        tl_max_lon = min_lon + (i + 1) * lon_step
        # Iterate across rows
        for j in range(tiles_per_side):
            # Compute tile's min latitude
            tl_min_lat = min_lat + j * lat_step
            # Compute tile's max latitude
            tl_max_lat = min_lat + (j + 1) * lat_step
            # Append the tile bbox as [min_lon, min_lat, max_lon, max_lat]
            tiles.append([tl_min_lon, tl_min_lat, tl_max_lon, tl_max_lat])
    # Return the full list of tiles
    return tiles

# Build Overpass QL for a given bbox and list of (key, value) tags
def build_overpass_query(bbox, tag_pairs):
    # Unpack the bbox into variables for readability
    min_lon, min_lat, max_lon, max_lat = bbox
    # Start the query with output format and timeout
    header = '[out:json][timeout:180];'  # Specify JSON output and a generous timeout
    # Start the union block to collect all matching elements
    body = "(\n"  # Begin union of all tag pairs
    # Iterate through each (key, value) pair to create selectors
    for k, v in tag_pairs:
        # Add node selector for this key=value within bbox
        body += f'  node["{k}"="{v}"]({min_lat},{min_lon},{max_lat},{max_lon});\n'
        # Add way selector for this key=value within bbox
        body += f'  way["{k}"="{v}"]({min_lat},{min_lon},{max_lat},{max_lon});\n'
        # Add relation selector for this key=value within bbox
        body += f'  relation["{k}"="{v}"]({min_lat},{min_lon},{max_lat},{max_lon});\n'
    # Close the union block
    body += ");\n"
    # Request center points and tags for ways/relations, and full tags for nodes
    footer = "out center qt;"  # Use quick timestamps and include geometric center where applicable
    # Combine header, body, and footer into a full query
    return header + body + footer

# Perform a single Overpass request with retries and endpoint rotation
def overpass_request(query, endpoints, max_retries=5, base_backoff=2.0):
    # Iterate over retry attempts
    for attempt in range(max_retries):
        # Choose an endpoint based on attempt number for rotation and resilience
        endpoint = endpoints[attempt % len(endpoints)]
        try:
            # Send POST request to Overpass with the query in the "data" field
            resp = requests.post(endpoint, data={"data": query}, timeout=300)
            # If the response status indicates rate limit or server busy, raise for retry
            if resp.status_code in (429, 504, 502, 503):
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            # If not OK (200), raise for retry as well
            resp.raise_for_status()
            # Parse JSON content
            data = resp.json()
            # Return parsed JSON on success
            return data
        except Exception as e:
            # Compute exponential backoff delay with jitter
            delay = base_backoff * (2 ** attempt) + random.uniform(0, 0.5)
            # Log the error and planned retry wait time
            logging.warning(f"Overpass error on attempt {attempt+1} at {endpoint}: {e}. Retrying in {delay:.1f}s")
            # Sleep before next retry
            time.sleep(delay)
    # After exhausting retries, raise a RuntimeError to notify caller
    raise RuntimeError("Overpass request failed after retries across endpoints")

# Flatten an OSM element into our canonical schema subset for the raw CSV
def flatten_element(elem, city="Islamabad", province="Islamabad Capital Territory", country="Pakistan"):
    # Extract the type of OSM geometry (node, way, or relation)
    osm_geom_type = elem.get("type", "")
    # Extract the OSM id
    osm_id = elem.get("id", None)
    # Get tags dict safely
    tags = elem.get("tags", {}) or {}
    # Extract display names in English and Urdu if present
    name = tags.get("name", "")
    name_ur = tags.get("name:ur", "")
    # Extract alternate name and description tags if present
    alt_name = tags.get("alt_name", "")
    description_raw = tags.get("description", "")
    # Extract Wikipedia/Wikidata references if present
    wikipedia = tags.get("wikipedia", "")
    wikidata = tags.get("wikidata", "")
    # Extract brand/operator if helpful in future enrichment
    brand = tags.get("brand", "")
    operator = tags.get("operator", "")
    # Determine latitude/longitude: nodes have 'lat','lon'; ways/relations provide 'center'
    if "lat" in elem and "lon" in elem:
        lat = elem.get("lat", None)
        lon = elem.get("lon", None)
    else:
        center = elem.get("center", {}) or {}
        lat = center.get("lat", None)
        lon = center.get("lon", None)
    # Identify the first matching key=value among our targets for labeling
    osm_tag_key = ""
    osm_tag_value = ""
    for k, v in TARGET_TAG_PAIRS:
        if tags.get(k) == v:
            osm_tag_key = k
            osm_tag_value = v
            break
    # Build a canonical row dict with required/available fields
    row = {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"osm:{osm_geom_type}:{osm_id}")),
        "osm_id": osm_id,
        "osm_geom_type": osm_geom_type,
        "osm_tag_key": osm_tag_key,
        "osm_tag_value": osm_tag_value,
        "name": name,
        "name_ur": name_ur,
        "alt_name": alt_name,
        "description_raw": description_raw,
        "description_final": "",  # Will be filled during preprocessing later
        "description_source": "OSM",
        "wikipedia_title": wikipedia.split(":")[1] if ":" in wikipedia else "",
        "wikipedia_url": "",  # To be filled during enrichment
        "lat": lat,
        "lon": lon,
        "city": city,
        "province": province,
        "country": country,
        "language": "",  # To be filled during preprocessing/language detection
        "dedup_group_id": "",  # To be assigned during preprocessing/dedup
        "brand": brand,
        "operator": operator,
        "wikidata": wikidata
    }
    # Return the flattened row
    return row

# Main execution block to run the collection process
def main():
    # Announce start of the collection
    logging.info("Starting Overpass collection for Islamabad pilot...")
    # Log the target tag pairs for debugging
    logging.info(f"Target tag pairs: {TARGET_TAG_PAIRS}")
    logging.info(f"Total tag pairs to query: {len(TARGET_TAG_PAIRS)}")
    # Generate tiles across the bbox for controlled, smaller queries
    tiles = tile_bbox(MIN_LON, MIN_LAT, MAX_LON, MAX_LAT, tiles_per_side=6)
    # Prepare outputs with stable names (no timestamps) per project convention
    raw_jsonl_path = os.path.join(RAW_DIR, "islamabad_overpass_raw.jsonl")
    csv_path = os.path.join(PROCESSED_DIR, "descriptions_raw.csv")
    log_path = os.path.join(PROCESSED_DIR, "collection_log.json")
    # Maintain a set of seen (type,id) to avoid duplicates across overlapping tiles
    seen = set()
    # Initialize counters for logging
    total_elements = 0
    kept_rows = 0
    errors = 0
    tile_stats = []
    # Open the raw JSONL file for writing raw elements
    with open(raw_jsonl_path, "w", encoding="utf-8") as raw_out:
        # Iterate through each tile bbox
        for idx, tile in enumerate(tiles):
            # Build the Overpass query for this tile
            query = build_overpass_query(tile, TARGET_TAG_PAIRS)
            # Log which tile we are processing
            logging.info(f"Querying tile {idx+1}/{len(tiles)}: {tile}")
            # Log the query for the first tile to debug
            if idx == 0:
                logging.info(f"Sample query for debugging:\n{query}")
            try:
                # Execute the Overpass request with retries and endpoint rotation
                data = overpass_request(query, OVERPASS_ENDPOINTS, max_retries=6, base_backoff=2.0)
                # Extract the elements list safely
                elements = data.get("elements", []) or []
                # Count before filtering duplicates
                tile_count = 0
                # Write each new element to JSONL and update counters
                for elem in elements:
                    # Build unique key for de-duplication across tiles
                    key = (elem.get("type", ""), elem.get("id", None))
                    # Skip if this element was already seen
                    if key in seen:
                        continue
                    # Mark as seen
                    seen.add(key)
                    # Write the raw element as a JSON line
                    raw_out.write(json.dumps(elem, ensure_ascii=False) + "\n")
                    # Increment counters
                    total_elements += 1
                    tile_count += 1
                # Record tile-level stats
                tile_stats.append({"tile_index": idx, "bbox": tile, "elements": tile_count})
                # Be polite to Overpass with a short sleep between tiles
                time.sleep(1.0)
            except Exception as e:
                # Log the error, increment error counter, and proceed to next tile
                logging.error(f"Failed tile {idx}: {e}")
                errors += 1
                # Record the failed tile with zero elements
                tile_stats.append({"tile_index": idx, "bbox": tile, "elements": 0, "error": str(e)})
                # Add a longer sleep after a failure to reduce pressure on the API
                time.sleep(3.0)
    # After raw collection, we flatten to CSV according to canonical schema subset
    rows = []
    # Re-open the raw JSONL to read back and flatten
    with open(raw_jsonl_path, "r", encoding="utf-8") as raw_in:
        # Iterate through each JSON line
        for line in raw_in:
            # Parse the JSON element
            elem = json.loads(line)
            # Flatten into a canonical row
            row = flatten_element(elem)
            # Only keep rows that actually matched a target tag key/value
            if row["osm_tag_key"] and row["osm_tag_value"]:
                # Append to rows list
                rows.append(row)
    # Define CSV column order per canonical schema (plus helpful extras kept here)
    fieldnames = [
        "id", "osm_id", "osm_geom_type", "osm_tag_key", "osm_tag_value",
        "name", "name_ur", "alt_name",
        "description_raw", "description_final", "description_source",
        "wikipedia_title", "wikipedia_url",
        "lat", "lon", "city", "province", "country",
        "language", "dedup_group_id",
        "brand", "operator", "wikidata"
    ]
    # Write the flattened CSV
    with open(csv_path, "w", encoding="utf-8", newline="") as csv_out:
        # Create a DictWriter with the specified fields
        writer = csv.DictWriter(csv_out, fieldnames=fieldnames)
        # Write the CSV header row
        writer.writeheader()
        # Iterate through flattened rows and write them
        for row in rows:
            # Increment kept rows counter
            kept_rows += 1
            # Write the row to CSV
            writer.writerow(row)
    # Prepare and write the collection log JSON with key metrics
    log = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "bbox": bbox_cfg["bbox"],
        "tiles": len(tiles),
        "total_raw_elements": total_elements,
        "kept_rows": kept_rows,
        "errors": errors,
        "tile_stats": tile_stats,
        "target_tag_pairs": TARGET_TAG_PAIRS
    }
    # Write the log JSON to disk
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    # Log a summary to console for quick visibility
    logging.info(f"Done. Raw elements: {total_elements}, Kept rows: {kept_rows}, Errors: {errors}")
    logging.info(f"Wrote: {raw_jsonl_path}, {csv_path}, {log_path}")

# Run main if this script is executed directly
if __name__ == "__main__":
    main()  # Invoke the main function to start the pipeline