
import pandas as pd
import spacy
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import fpgrowth
import os
from tqdm import tqdm

# --- Config ---
INPUT_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../datareported/final_enriched_dataset.csv'))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../datareported'))
HYBRID_FILE = os.path.join(OUTPUT_DIR, 'dataset_hybrid.csv')

def main():
    print("[*] Rescue Hybrid Dataset Generation...")
    if not os.path.exists(INPUT_FILE):
        print(f"[!] Input file not found: {INPUT_FILE}")
        return
        
    df = pd.read_csv(INPUT_FILE).fillna("")
    print(f"[*] Loaded {len(df)} records.")

    try:
        nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"]) 
        # Parser is needed for POS tagging in some pipelines? 
        # en_core_web_sm: 'tagger' is needed for POS. 'parser' for dependencies.
        # Noun chunks need parser? Yes.
        # But we only need POS (ADJ, NOUN).
        # So disable 'parser' and 'ner' to speed up?
        # NO, checking docs: attribute_ruler, lemmatizer, tagger needed. Parser not needed for .pos_
        # But we previously used `doc.noun_chunks` which needs parser.
        # Now we only do ADJ+NOUN sequence. Dependency parse NOT needed.
        # Disabling parser will speed it up 10x!
        # nlp.enable_pipe("tagger") is default.
    except:
        return

    print("[*] Processing Text (Hybrid Logic Only)...")
    
    hybrid_candidates_list = []
    texts = df['enriched_description'].tolist()
    
    # Disable parser/ner for speed
    with nlp.select_pipes(disable=["parser", "ner"]):
        for doc in tqdm(nlp.pipe(texts, batch_size=200, n_process=1), total=len(texts)):
            compounds = []
            for i in range(len(doc) - 1):
                t1 = doc[i]
                t2 = doc[i+1]
                if t1.pos_ == 'ADJ' and t2.pos_ == 'NOUN':
                    c = f"{t1.text.lower()}_{t2.text.lower()}"
                    compounds.append(c)
            hybrid_candidates_list.append(compounds)

    # --- FP-Growth ---
    print("[*] Running FP-Growth...")
    te = TransactionEncoder()
    te_ary = te.fit(hybrid_candidates_list).transform(hybrid_candidates_list)
    df_trans = pd.DataFrame(te_ary, columns=te.columns_)
    
    # Use 0.01 support to ensure results
    frequent_itemsets = fpgrowth(df_trans, min_support=0.01, use_colnames=True)
    print(f"    - Frequent Itemsets (0.01): {len(frequent_itemsets)}")
    
    allowed_compounds = set()
    for itemset in frequent_itemsets['itemsets']:
        for item in itemset:
            allowed_compounds.add(item)
            
    # Include ALL if less than 50 compounds found (fallback)
    if len(allowed_compounds) < 50:
         print("    [!] Low frequency items. Keeping top 1000 compounds by raw count.")
         # Manual count
         from collections import Counter
         all_c = [c for sublist in hybrid_candidates_list for c in sublist]
         counts = Counter(all_c).most_common(1000)
         allowed_compounds = set([x[0] for x in counts])
         
    final_hybrid_texts = []
    for compounds in hybrid_candidates_list:
        valid = [c for c in compounds if c in allowed_compounds]
        final_hybrid_texts.append(" ".join(valid))
        
    df['text_hybrid'] = final_hybrid_texts
    df[['osm_id', 'city', 'text_hybrid']].to_csv(HYBRID_FILE, index=False)
    print(f"[+] Saved Hybrid Dataset to {HYBRID_FILE}")

if __name__ == "__main__":
    main()
