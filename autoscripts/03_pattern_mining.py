import os
import pandas as pd
import json
import logging
from collections import Counter
from datetime import datetime
import re

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_CSV = os.path.join(BASE_DIR, "data", "processed", "descriptions_cleaned.csv")
OUTPUT_PATTERNS = os.path.join(BASE_DIR, "data", "processed", "frequent_patterns.csv")
LOG_FILE = os.path.join(BASE_DIR, "data", "processed", f"pattern_mining_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

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

def tokenize(text):
    """
    Simple tokenization: lowercase, remove punctuation, split by space.
    Preserves non-ascii words (Urdu).
    """
    if pd.isna(text): return []
    # Remove punctuation but keep words
    text = str(text).lower()
    # Regex to keep alphanumeric matches (including urdu)
    # \w matches unicode alpha-numeric
    tokens = re.findall(r'\w+', text)
    # Filter stopwords (basic list + extended for this domain)
    stopwords = set(['is', 'a', 'the', 'of', 'in', 'and', 'to', 'for', 'this', 'located', 'near', 'at'])
    return [t for t in tokens if t not in stopwords and len(t) > 2]

def get_frequent_itemsets(transactions, min_support=0.01):
    """
    Finds frequent itemsets (1-grams and 2-grams) manually.
    Equivalent to basic frequent pattern mining.
    """
    total_count = len(transactions)
    min_count = max(1, int(total_count * min_support))
    
    logging.info(f"Mining with Min Support: {min_support} ({min_count} occurrences)")
    
    # 1. Frequent 1-itemsets
    c1 = Counter()
    for t in transactions:
        c1.update(t)
    
    L1 = {k: v for k, v in c1.items() if v >= min_count}
    logging.info(f"Found {len(L1)} frequent 1-itemsets.")
    
    # 2. Frequent 2-itemsets
    # Generate pairs only from reliable L1 items to save time
    c2 = Counter()
    L1_keys = set(L1.keys())
    
    for t in transactions:
        # Filter transaction to only frequent items
        filtered_t = [x for x in t if x in L1_keys]
        # Generate pairs
        for i in range(len(filtered_t)):
            for j in range(i + 1, len(filtered_t)):
                pair = tuple(sorted((filtered_t[i], filtered_t[j])))
                c2[pair] += 1
                
    L2 = {k: v for k, v in c2.items() if v >= min_count}
    logging.info(f"Found {len(L2)} frequent 2-itemsets.")
    
    # Combine results
    patterns = []
    for k, v in L1.items():
        patterns.append({'items': k, 'support': v/total_count, 'count': v})
    for k, v in L2.items():
        patterns.append({'items': f"{k[0]}, {k[1]}", 'support': v/total_count, 'count': v})
        
    return pd.DataFrame(patterns).sort_values(by='support', ascending=False)

# --- Main Execution ---

def main():
    logging.info("Starting Pattern Mining (Autoscript 03)...")
    
    if not os.path.exists(INPUT_CSV):
        logging.error(f"Input file not found: {INPUT_CSV}")
        return

    # Load Data
    df = pd.read_csv(INPUT_CSV, encoding='utf-8')
    logging.info(f"Loaded {len(df)} descriptions.")
    
    # Tokenize
    transactions = df['description_final'].apply(tokenize).tolist()
    
    # Run Mining
    fs_df = get_frequent_itemsets(transactions, min_support=0.01)
    
    if fs_df.empty:
        logging.warning("No patterns found with default support. Retrying with lower support (0.005).")
        fs_df = get_frequent_itemsets(transactions, min_support=0.005)

    # Save
    logging.info(f"Saving {len(fs_df)} patterns to {OUTPUT_PATTERNS}")
    fs_df.to_csv(OUTPUT_PATTERNS, index=False, encoding='utf-8')
    
    # Show top patterns
    logging.info("Top 10 Patterns:")
    for idx, row in fs_df.head(10).iterrows():
        logging.info(f"{row['items']}: {row['count']} ({row['support']:.4f})")

    logging.info("Pattern Mining complete.")

if __name__ == "__main__":
    main()
