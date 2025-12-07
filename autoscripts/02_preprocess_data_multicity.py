import os
import pandas as pd
import re
import logging
import html
import glob
from datetime import datetime

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
INPUT_PATTERN = os.path.join(PROCESSED_DIR, "descriptions_*.csv")
OUTPUT_CSV = os.path.join(PROCESSED_DIR, "descriptions_cleaned.csv")
LOG_FILE = os.path.join(PROCESSED_DIR, f"preprocessing_log_multicity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Logging Setup
os.makedirs(PROCESSED_DIR, exist_ok=True)
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
    logging.info("Starting Data Preprocessing (Autoscript 02 Multicity)...")
    
    input_files = glob.glob(INPUT_PATTERN)
    # Exclude the output file itself if it exists and matches the pattern
    input_files = [f for f in input_files if os.path.basename(f) != "descriptions_cleaned_multicity.csv" and os.path.basename(f) != "descriptions_cleaned.csv"]
    
    if not input_files:
        logging.error(f"No input files found matching: {INPUT_PATTERN}")
        return

    logging.info(f"Found input files: {[os.path.basename(f) for f in input_files]}")
    
    all_dfs = []
    
    # Read and merge all CSVs
    for f_path in input_files:
        try:
            df_part = pd.read_csv(f_path, encoding='utf-8', dtype=str)
            all_dfs.append(df_part)
            logging.info(f"Loaded {len(df_part)} rows from {os.path.basename(f_path)}")
        except Exception as e:
            logging.error(f"Failed to read {f_path}: {e}")

    if not all_dfs:
        logging.error("No valid dataframes loaded.")
        return

    df = pd.concat(all_dfs, ignore_index=True)
    logging.info(f"Total rows merged: {len(df)}")

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
        if idx % 500 == 0:
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
