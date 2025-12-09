import os
import pandas as pd
import re
import logging
import html
from datetime import datetime

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_CSV = os.path.join(BASE_DIR, "data", "processed", "descriptions_raw.csv")
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "processed", "descriptions_cleaned.csv")
LOG_FILE = os.path.join(BASE_DIR, "data", "processed", f"preprocessing_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# --- Helper Functions ---

def clean_text(text):
    """
    Cleans text while preserving Urdu and other non-ASCII characters.
    - Unescapes HTML entities
    - Removes excessive whitespace
    - Preserves all unicode letters/marks (regex \w matches unicode in Python 3 default)
    """
    if not isinstance(text, str) or pd.isna(text):
        return ""
    
    # Unescape HTML (e.g., &amp; -> &)
    text = html.unescape(text)
    
    # Replace newlines/tabs with space
    text = re.sub(r'[\r\n\t]+', ' ', text)
    
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    return text.strip()

def synthesize_description(row):
    """
    Creates a final description from available fields if description_raw is empty.
    Priority: description_raw > name + tags > tags only
    """
    # 1. Use existing description if available
    raw_desc = clean_text(row.get('description_raw', ''))
    if raw_desc:
        return raw_desc, "Explicit"

    # 2. Synthesize from Name + Type
    name = clean_text(row.get('name', ''))
    name_ur = clean_text(row.get('name_ur', ''))
    tag_key = row.get('osm_tag_key', '')
    tag_val = row.get('osm_tag_value', '')
    
    # Combine English and Urdu names if both exist
    full_name = name
    if name_ur and name_ur != name:
        if full_name:
            full_name = f"{full_name} ({name_ur})"
        else:
            full_name = name_ur

    if full_name:
        # e.g. "Faisal Mosque is a mosque."
        # Using simple template
        return f"{full_name} is a {tag_val.replace('_', ' ')}.", "Synthesized_Name"

    # 3. Fallback to just Type
    if tag_val:
        return f"This is a {tag_val.replace('_', ' ')}.", "Synthesized_Tag"

    return "", "Empty"

# --- Main Execution ---

def main():
    logging.info("Starting Data Preprocessing (Autoscript 02)...")
    
    if not os.path.exists(INPUT_CSV):
        logging.error(f"Input file not found: {INPUT_CSV}")
        return

    logging.info(f"Reading input CSV: {INPUT_CSV}")
    
    # Read CSV
    try:
        df = pd.read_csv(INPUT_CSV, encoding='utf-8', dtype=str)
    except Exception as e:
        logging.error(f"Failed to read CSV: {e}")
        return

    logging.info(f"Loaded {len(df)} rows.")

    # Apply Cleaning
    logging.info("Applying text cleaning and description synthesis...")
    
    # We will update 'description_final' and 'description_source'
    final_descs = []
    sources = []

    for idx, row in df.iterrows():
        desc, source = synthesize_description(row)
        final_descs.append(desc)
        sources.append(source)
        
        # Log a few examples of Urdu names/descriptions if found
        if idx % 100 == 0:
            name_ur = row.get('name_ur', '')
            if name_ur and not pd.isna(name_ur):
                logging.info(f"Sample Urdu preservation (Row {idx}): {name_ur} -> {desc}")

    df['description_final'] = final_descs
    df['description_source'] = sources

    # Basic stats
    valid_counts = df['description_final'].apply(lambda x: 1 if x else 0).sum()
    logging.info(f"Rows with valid final descriptions: {valid_counts}/{len(df)}")
    
    # Save output
    logging.info(f"Saving cleaned data to: {OUTPUT_CSV}")
    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
    logging.info("Preprocessing complete.")

if __name__ == "__main__":
    main()
