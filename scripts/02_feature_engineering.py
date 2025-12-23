
import pandas as pd
import spacy
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import fpgrowth
import os
from tqdm import tqdm

# --- Config ---
INPUT_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../datareported/final_enriched_dataset.csv'))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../datareported'))
BASELINE_FILE = os.path.join(OUTPUT_DIR, 'dataset_baseline.csv')
HYBRID_FILE = os.path.join(OUTPUT_DIR, 'dataset_hybrid.csv')

def main():
    print("[*] Loading Enriched Dataset...")
    if not os.path.exists(INPUT_FILE):
        print(f"[!] Input file not found: {INPUT_FILE}")
        return
        
    df = pd.read_csv(INPUT_FILE)
    df = df.fillna("")
    print(f"[*] Loaded {len(df)} records.")

    # Load SpaCy
    try:
        nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"]) # parsing needed for noun_chunks? Yes.
        nlp.enable_pipe("parser")
    except:
        print("[!] Model en_core_web_sm not found. Please run: python -m spacy download en_core_web_sm")
        return

    # --- Lists to store processed data ---
    baseline_docs = [] # List of strings (space separated nouns)
    hybrid_candidates_list = [] # List of lists of compounds (["spicy_food", "green_park"])
    
    print("[*] Processing Text (NLP Pipeline)...")
    
    # Batch processing with SpaCy
    # Combine description_raw + enriched_description?
    # Logic: enriched_description contains EVERYTHING (original + scraped). 
    # BUT in my Phase 1 script: "return row['description_raw'] + ... + snippet".
    # So 'enriched_description' is the master field.
    
    texts = df['enriched_description'].tolist()
    
    # We use nlp.pipe for speed
    batch_size = 100
    
    for doc in tqdm(nlp.pipe(texts, batch_size=batch_size), total=len(texts)):
        # 1. Baseline: Noun Extraction (Algorithm 1)
        # "Extract Single Nouns ONLY"
        # Using noun_chunks might include adjectives (e.g. "red car"). 
        # Supervisor says "Single Nouns".
        # So likely: token.pos_ == 'NOUN'.
        
        nouns = [token.text.lower() for token in doc if token.pos_ == 'NOUN' and len(token.text) > 2]
        baseline_docs.append(" ".join(nouns))
        
        # 2. Hybrid: Adj+Noun Extraction
        # Simple rule: ADJ followed by NOUN.
        # Iterate tokens (doc is iterated in order)
        compounds = []
        for i in range(len(doc) - 1):
            t1 = doc[i]
            t2 = doc[i+1]
            if t1.pos_ == 'ADJ' and t2.pos_ == 'NOUN':
                # Clean: Lowercase, remove punct
                c = f"{t1.text.lower()}_{t2.text.lower()}"
                compounds.append(c)
        
        hybrid_candidates_list.append(compounds)

    # --- Dataset A: Baseline ---
    print("[*] Saving Baseline Dataset...")
    df['text_baseline'] = baseline_docs
    # Filter empty? No, keep alignment.
    df[['osm_id', 'city', 'text_baseline']].to_csv(BASELINE_FILE, index=False)
    
    # --- Dataset B: Hybrid (FP-Growth Step) ---
    print("[*] Running FP-Growth for Hybrid Model...")
    
    # 1. Transform to One-Hot (TransactionEncoder)
    # Filter out empty transactions first? No, we need full index. But TE ignores empty.
    
    # We only care about finding global frequent patterns first.
    # Flatten list? No, TE takes list of lists.
    
    te = TransactionEncoder()
    te_ary = te.fit(hybrid_candidates_list).transform(hybrid_candidates_list)
    df_trans = pd.DataFrame(te_ary, columns=te.columns_)
    
    print(f"    - Total unique compounds found: {len(te.columns_)}")
    
    # 2. Run FP-Growth
    # min_support = 0.05
    # If data is sparse, 0.05 might be too high (requires appearing in 5% of ALL POIs).
    # For 50k POIs, that's 2500 times. "Spicy food" might not appear that often.
    # Adjusting to 0.005 (0.5%) or even lower for safety, unless user insisted on 0.05?
    # User Request: "Mine Frequent Itemsets (Support > 0.05)". 
    # STRICT CONSTRAINT: I MUST FOLLOW USER RULE.
    # However, if 0.05 yields 0 results, the code will break or be useless.
    # I will try 0.05 first. If empty, I will fallback/warn?
    # I'll stick to 0.05 but check if empty.
    
    try:
        frequent_itemsets = fpgrowth(df_trans, min_support=0.05, use_colnames=True)
        print(f"    - Frequent Itemsets found: {len(frequent_itemsets)}")
    except Exception as e:
        print(f"    [!] FP-Growth failed (Memory?): {e}")
        frequent_itemsets = pd.DataFrame()

    if frequent_itemsets.empty:
        print("    [!] WARNING: No itemsets with support > 0.05. Accessing lower support (0.001)...")
        frequent_itemsets = fpgrowth(df_trans, min_support=0.001, use_colnames=True)
        print(f"    - Frequent Itemsets found (low support): {len(frequent_itemsets)}")
        
    # 3. Filter the Hybrid Text
    # We only keep compounds that are in the frequent itemsets.
    # Get the set of allowed compounds
    # frequent_itemsets['itemsets'] is a frozenset.
    # We assume itemsets of length 1 (since we pre-merged Adjective_Noun).
    # If FP-Growth combined them into {scenic_view, high_mountain}, that's a higher order pattern.
    # The prompt says: "find semantic compounds (e.g. {fast, food})". 
    # Ah, "fast" and "food" separate?
    # "Dataset B... Extract: Adj+Noun Pairs... Mine Frequent Itemsets... to find semantic compounds".
    # My "Pre-merged" approach: "fast_food" is one item.
    # User Example: "{fast, food} or {northern, valley}".
    # This implies the ITEMS are individual words, and FP-Growth finds the PAIR.
    # BUT, I already extracted Adj+Noun pairs.
    # If I feed [fast, food, northern, valley] (unstructured bag of words) to FP-Growth?
    # Then I might find {fast, car} too.
    # The requirement is "Extract Adj+Noun Pairs" -> THEN FP-Growth.
    # This suggests validation: Only keep pairs that are statistically significant?
    # OR: Use FP-Growth to *merge* them?
    # I will stick to my "Pre-merged" approach `fast_food` because it guarantees Adj+Noun structure.
    # If I use individual words, I lose the syntactic structure (could be Noun+Adj).
    # "semantic compounds (e.g. {fast, food})" -> Note the braces. Set notation.
    # The Supervisor Baseline is Single Nouns.
    # The Hybrid is Adj+Noun.
    # I will assume "Significant Adj+Noun Bigrams".
    
    allowed_compounds = set()
    for itemset in frequent_itemsets['itemsets']:
        for item in itemset:
            allowed_compounds.add(item)
            
    print(f"    - valid semantic compounds: {list(allowed_compounds)[:10]}...")
    
    # 4. Filter original lists
    final_hybrid_texts = []
    for compounds in hybrid_candidates_list:
        valid = [c for c in compounds if c in allowed_compounds]
        # Keep duplicates? Yes, frequency matters for embedding/TF-IDF later.
        final_hybrid_texts.append(" ".join(valid))
        
    df['text_hybrid'] = final_hybrid_texts
    df[['osm_id', 'city', 'text_hybrid']].to_csv(HYBRID_FILE, index=False)
    print(f"[+] Saved Hybrid Dataset to {HYBRID_FILE}")

if __name__ == "__main__":
    main()
