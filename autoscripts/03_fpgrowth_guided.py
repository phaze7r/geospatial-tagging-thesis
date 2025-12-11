import os
import pandas as pd
import logging
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import fpgrowth
from datetime import datetime

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATAREPORTED_DIR = os.path.join(BASE_DIR, "datareported")
INPUT_FILE = os.path.join(DATAREPORTED_DIR, "preprocessed", "merged_dataset.csv")
OUTPUT_DIR = os.path.join(DATAREPORTED_DIR, "fp_growth")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_PATTERNS = os.path.join(OUTPUT_DIR, "guided_patterns.csv")

# Logging
log_filename = os.path.join(OUTPUT_DIR, f"pattern_mining_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()]
)

def main():
    logging.info("Starting Guided FP-Growth (Autoscript 03)...")
    
    if not os.path.exists(INPUT_FILE):
        logging.error(f"Input file not found: {INPUT_FILE}")
        return

    # 1. Load Data
    df = pd.read_csv(INPUT_FILE)
    logging.info(f"Loaded {len(df)} records.")
    
    # 2. Prepare Transactions
    # We use 'adj_noun_pairs' as items. 
    # Also include the individual words from normalized text to find co-occurrences?
    # The requirement says "FP-Growth to find frequent itemsets of Adjective-Noun pairs."
    
    # Filter rows with pairs
    valid_df = df.dropna(subset=['adj_noun_pairs'])
    transactions = []
    
    for _, row in valid_df.iterrows():
        pairs = str(row['adj_noun_pairs']).split(", ")
        pairs = [p.strip() for p in pairs if p.strip()]
        
        # Also add the target tag key (e.g. 'amenity') to "guide" the mining
        # This helps us find patterns that co-occur with specific tag types
        if row.get('osm_tag_key'):
             pairs.append(f"TAG_KEY:{row['osm_tag_key']}")
             
        if pairs:
            transactions.append(pairs)
            
    logging.info(f"Transactions prepared: {len(transactions)}")

    # 3. FP-Growth
    te = TransactionEncoder()
    te_ary = te.fit(transactions).transform(transactions)
    df_trans = pd.DataFrame(te_ary, columns=te.columns_)
    
    logging.info("Running FP-Growth (min_support=0.001)...")
    # Low support because specific pairs might be rare but predictive
    frequent_itemsets = fpgrowth(df_trans, min_support=0.001, use_colnames=True)
    
    logging.info(f"Found {len(frequent_itemsets)} frequent itemsets.")

    # 4. "Guided" Filtering
    # We only care about itemsets that contain at least one linguistic feature (not just TAG_KEYs)
    # And preferably patterns that appear with TAG_KEYs
    
    def is_interesting(itemset):
        items = list(itemset)
        has_tag = any(i.startswith("TAG_KEY:") for i in items)
        has_feature = any(not i.startswith("TAG_KEY:") for i in items)
        return has_feature # Keep any linguistic pattern, but later we analyze co-occurrence
    
    frequent_itemsets['is_relevant'] = frequent_itemsets['itemsets'].apply(is_interesting)
    relevant_patterns = frequent_itemsets[frequent_itemsets['is_relevant']]
    
    # Sort by support
    relevant_patterns = relevant_patterns.sort_values(by='support', ascending=False)
    
    # Save
    relevant_patterns.to_csv(OUTPUT_PATTERNS, index=False)
    logging.info(f"Saved {len(relevant_patterns)} relevant patterns to {OUTPUT_PATTERNS}")
    
    # Preview top patterns
    top_10 = relevant_patterns.head(10)['itemsets'].tolist()
    logging.info(f"Top 10 Patterns: {top_10}")

if __name__ == "__main__":
    main()
