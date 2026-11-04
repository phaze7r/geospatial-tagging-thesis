# OSM Data Collection Script for Islamabad
import os
import overpy
import pandas as pd
import decimal
import json
from datetime import datetime
import time


def collect_osm_data_islamabad():
    """
    Collect OSM data for Islamabad with place descriptions and tags
    Focus on places that have names, descriptions, or other text attributes
    """

    # Initialize Overpass API
    api = overpy.Overpass()

    # Islamabad bounding box coordinates (approximate)
    # [south, west, north, east]
    islamabad_bbox = "33.4734, 72.8397, 33.7480, 73.2047"

    # Define queries for different types of places with descriptions
    queries = {
        'amenities': f"""
        [out:json][timeout:60];
        (
          node["amenity"](bbox:{islamabad_bbox});
          way["amenity"](bbox:{islamabad_bbox});
          relation["amenity"](bbox:{islamabad_bbox});
        );
        out body;
        >;
        out skel qt;
        """,

        'tourism': f"""
        [out:json][timeout:60];
        (
          node["tourism"](bbox:{islamabad_bbox});
          way["tourism"](bbox:{islamabad_bbox});
          relation["tourism"](bbox:{islamabad_bbox});
        );
        out body;
        >;
        out skel qt;
        """,

        'leisure': f"""
        [out:json][timeout:60];
        (
          node["leisure"](bbox:{islamabad_bbox});
          way["leisure"](bbox:{islamabad_bbox});
          relation["leisure"](bbox:{islamabad_bbox});
        );
        out body;
        >;
        out skel qt;
        """,

        'shop': f"""
        [out:json][timeout:60];
        (
          node["shop"](bbox:{islamabad_bbox});
          way["shop"](bbox:{islamabad_bbox});
          relation["shop"](bbox:{islamabad_bbox});
        );
        out body;
        >;
        out skel qt;
        """
    }

    all_data = []

    print("🚀 Starting OSM data collection for Islamabad...")
    print(f"📍 Bounding box: {islamabad_bbox}")

    for category, query in queries.items():
        print(f"\n📊 Collecting {category} data...")

        try:
            # Execute query with retry logic
            result = api.query(query)

            # Process nodes
            for node in result.nodes:
                data_entry = process_osm_element(node, 'node', category)
                if data_entry:
                    all_data.append(data_entry)

            # Process ways
            for way in result.ways:
                data_entry = process_osm_element(way, 'way', category)
                if data_entry:
                    all_data.append(data_entry)

            # Process relations
            for relation in result.relations:
                data_entry = process_osm_element(relation, 'relation', category)
                if data_entry:
                    all_data.append(data_entry)

            print(f"✅ Collected {len([d for d in all_data if d['category'] == category])} {category} entries")

            # Be nice to the API
            time.sleep(2)

        except Exception as e:
            print(f"❌ Error collecting {category}: {str(e)}")
            continue

    return all_data


def process_osm_element(element, element_type, category):
    """
    Process an OSM element (node, way, or relation) and extract relevant data
    """
    tags = element.tags

    # Skip if no useful tags
    if not tags:
        return None

    # Extract coordinates
    if element_type == 'node':
        lat, lon = element.lat, element.lon
    elif element_type == 'way' and element.nodes:
        # Use center of first and last node as approximation
        lat = (element.nodes[0].lat + element.nodes[-1].lat) / 2
        lon = (element.nodes[0].lon + element.nodes[-1].lon) / 2
    else:
        lat, lon = None, None

    # Extract name and description-like fields
    name = tags.get('name', '')
    name_en = tags.get('name:en', '')
    name_ur = tags.get('name:ur', '')
    description = tags.get('description', '')

    # Create a combined description from available text fields
    text_parts = []
    if name: text_parts.append(name)
    if name_en and name_en != name: text_parts.append(f"({name_en})")
    if name_ur and name_ur != name: text_parts.append(f"[{name_ur}]")
    if description: text_parts.append(description)

    combined_description = " ".join(text_parts).strip()

    # Skip if no meaningful text content
    if not combined_description:
        return None

    # Determine primary OSM tag
    primary_key = None
    primary_value = None

    # Priority order for main tags
    priority_tags = ['amenity', 'tourism', 'leisure', 'shop', 'building', 'landuse']
    for tag in priority_tags:
        if tag in tags:
            primary_key = tag
            primary_value = tags[tag]
            break

    if not primary_key:
        return None

    # Detect language (simple heuristic)
    language = detect_language_simple(combined_description)

    return {
        'osm_id': element.id,
        'element_type': element_type,
        'category': category,
        'description': combined_description,
        'name': name,
        'name_en': name_en,
        'name_ur': name_ur,
        'language': language,
        'location': 'Islamabad',
        'osm_tag_key': primary_key,
        'osm_tag_value': primary_value,
        'source': 'OSM',
        'coordinates': [lon, lat] if lat and lon else None,
        'latitude': lat,
        'longitude': lon,
        'all_tags': dict(tags),
        'collected_at': datetime.now().isoformat()
    }


def detect_language_simple(text):
    """
    Simple language detection based on character patterns
    """
    if not text:
        return 'unknown'

    # Count different character types
    urdu_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')  # Arabic/Urdu block
    english_chars = sum(1 for c in text if c.isalpha() and ord(c) < 128)

    total_chars = len([c for c in text if c.isalpha()])

    if total_chars == 0:
        return 'unknown'

    urdu_ratio = urdu_chars / total_chars
    english_ratio = english_chars / total_chars

    if urdu_ratio > 0.3:
        return 'Urdu'
    elif english_ratio > 0.7:
        return 'English'
    else:
        return 'Mixed'


# Run the collection
print("Starting OSM data collection for Islamabad...")
osm_data = collect_osm_data_islamabad()

print(f"\n🎉 Collection complete! Found {len(osm_data)} entries with descriptions.")

# Convert to DataFrame for analysis
df = pd.DataFrame(osm_data)

if len(df) > 0:
    print(f"\n Data Summary:")
    print(f"Total entries: {len(df)}")
    print(f"Categories: {df['category'].value_counts().to_dict()}")
    print(f"Languages: {df['language'].value_counts().to_dict()}")
    print(f"Top OSM tags: {df['osm_tag_key'].value_counts().head().to_dict()}")

    # Show sample entries
    print(f"\n Sample entries:")
    for i, row in df.head(5).iterrows():
        print(f"{i + 1}. {row['name']} ({row['osm_tag_key']}={row['osm_tag_value']})")
        print(f"   Description: {row['description'][:100]}...")
        print(f"   Language: {row['language']}, Location: {row['coordinates']}")
        print()


    def convert_decimals(obj):
        if isinstance(obj, list):
            return [convert_decimals(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, decimal.Decimal):
            return float(obj)
        else:
            return obj

    # Ensure the data directory exists
    os.makedirs('../data', exist_ok=True)

    output_file = '../data/islamabad_osm_data.csv'
    raw_json_file = '../data/islamabad_osm_raw.json'

    # Save CSV
    df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"💾 Data saved to: {output_file}")

    # Save JSON (with decimal fix)
    with open(raw_json_file, 'w', encoding='utf-8') as f:
        json.dump(convert_decimals(osm_data), f, ensure_ascii=False, indent=2)
    print(f"💾 Raw data saved to: {raw_json_file}")

else:
    print("⚠️ No data collected. This might be due to network issues or API limits.")