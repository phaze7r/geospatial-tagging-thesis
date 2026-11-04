import os
import glob
import pandas as pd
import re
import logging
import spacy
from datetime import datetime

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATAREPORTED_DIR = os.path.join(BASE_DIR, "datareported")
RAW_DIR = os.path.join(DATAREPORTED_DIR, "raw")
PROCESSED_DIR = os.path.join(DATAREPORTED_DIR, "preprocessed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(PROCESSED_DIR, "merged_dataset.csv")

# Logging
log_filename = os.path.join(PROCESSED_DIR, f"preprocess_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()]
)

# Reference: Common Roman Urdu Mappings from Thesis context
ROMAN_URDU_MAP = {
    "chowk": "intersection",
    "masjid": "mosque",
    "bazaar": "market",
    "bazar": "market",
    "dhabba": "restaurant",
    "dhaba": "restaurant",
    "hotel": "restaurant", # In Pak context, small hotels often mean restaurants
    "karyana": "grocery",
    "kiryana": "grocery",
    "medical store": "pharmacy",
    "dawakhana": "pharmacy",
    "school": "school",
    "college": "college",
    "road": "road",
    "sarak": "road",
    "gali": "street",
    "mohalla": "neighborhood",
    "colony": "neighborhood",
    "nagar": "town",
    "pul": "bridge",
    "qila": "fort",
    "darbar": "shrine",
    "mazar": "shrine",
    "ground": "park",
    "bagh": "garden",
    "markaz": "center",
    "plaza": "shopping_mall"
}

# Load Spacy
nlp = spacy.load("en_core_web_sm")

def clean_text(text):
    if not isinstance(text, str):
        return ""
    # Remove HTML
    text = re.sub(r'<[^>]+>', '', text)
    # Remove URLs
    text = re.sub(r'http\S+', '', text)
    # Remove non-alphanumeric (keep spaces)
    text = re.sub(r'[^a-zA-Z\s]', ' ', text)
    # Lowercase & Strip
    text = text.lower().strip()
    return text

def normalize_roman_urdu(text):
    words = text.split()
    normalized = [ROMAN_URDU_MAP.get(w, w) for w in words]
    return " ".join(normalized)

def extract_pos_features(text):
    """
    Extract Adjective-Noun pairs using Spacy.
    Returns string of comma-separated pairs: "spicy_food, old_fort"
    """
    doc = nlp(text)
    pairs = []
    
    # Iterate and look for ADJ + NOUN patterns
    # Also consider NOUN + NOUN (compound nouns)
    for i in range(len(doc) - 1):
        w1 = doc[i]
        w2 = doc[i+1]
        
        # Pattern 1: Adj + Noun (e.g., "famous mosque")
        if w1.pos_ == "ADJ" and w2.pos_ == "NOUN":
            pairs.append(f"{w1.text}_{w2.text}")
            
        # Pattern 2: Noun + Noun (e.g., "chicken shop")
        elif w1.pos_ == "NOUN" and w2.pos_ == "NOUN":
            pairs.append(f"{w1.text}_{w2.text}")
            
    return ", ".join(pairs)

def main():
    logging.info("Starting Extended Preprocessing (Autoscript 02)...")

    # 1. Merge CSVs
    all_files = glob.glob(os.path.join(RAW_DIR, "*_raw.csv"))
    logging.info(f"Found {len(all_files)} raw CSV files.")
    
    df_list = []
    total_raw_rows = 0
    
    for f in all_files:
        try:
            temp_df = pd.read_csv(f)
            total_raw_rows += len(temp_df)
            df_list.append(temp_df)
        except Exception as e:
            logging.error(f"Error reading {f}: {e}")
            
    if not df_list:
        logging.error("No data found to merge.")
        return

    df = pd.concat(df_list, ignore_index=True)
    logging.info(f"Merged Data Shape: {df.shape}")

    # 2. Synthesis & Cleaning
    df['description_final'] = df.apply(
        lambda row: row['description_raw'] if pd.notnull(row['description_raw']) and str(row['description_raw']).strip() 
        else f"{row['name'] or ''} {row['osm_tag_value'] or ''} {row['osm_tag_key'] or ''}",
        axis=1
    )
    
    # Basic Cleaning
    df['clean_text'] = df['description_final'].apply(clean_text)
    
    # 3. Roman Urdu Normalization
    logging.info("Applying Roman Urdu Normalization...")
    df['normalized_text'] = df['clean_text'].apply(normalize_roman_urdu)
    
    # 4. POS Tagging (Adj-Noun Extraction)
    # Sampling for speed if dataset is huge, but 20k is fine for full pass
    logging.info("Extracting POS Features (Adj-Noun pairs)...")
    df['adj_noun_pairs'] = df['normalized_text'].apply(extract_pos_features)

    # 5. Filter Invalid
    # Remove empty descriptions
    df = df[df['clean_text'].str.len() > 3]
    
    # Save
    logging.info(f"Saving {len(df)} processed rows to {OUTPUT_FILE}")
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')
    logging.info("Preprocessing Complete.")

if __name__ == "__main__":
    main()
