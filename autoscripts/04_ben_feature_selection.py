import os
import json
import logging
import pandas as pd
import numpy as np
import pickle
from datetime import datetime
from sklearn.linear_model import SGDClassifier
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATAREPORTED_DIR = os.path.join(BASE_DIR, "datareported")
INPUT_DATA = os.path.join(DATAREPORTED_DIR, "preprocessed", "merged_dataset.csv")
INPUT_PATTERNS = os.path.join(DATAREPORTED_DIR, "fp_growth", "guided_patterns.csv")
OUTPUT_DIR = os.path.join(DATAREPORTED_DIR, "ben_features")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FEATURES = os.path.join(OUTPUT_DIR, "ben_selected_features.json")
OUTPUT_MODEL = os.path.join(OUTPUT_DIR, "ben_model.pkl")

# Logging
log_filename = os.path.join(OUTPUT_DIR, f"ben_selection_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()]
)

def main():
    logging.info("Starting Bayesian Elastic Net Feature Selection (Autoscript 04)...")
    
    # 1. Load Data
    df = pd.read_csv(INPUT_DATA)
    # Target: osm_tag_value (e.g., restaurant, mosque)
    # We filter out rare classes to ensure model stability
    class_counts = df['osm_tag_value'].value_counts()
    valid_classes = class_counts[class_counts >= 10].index
    df = df[df['osm_tag_value'].isin(valid_classes)]
    df = df.dropna(subset=['clean_text', 'osm_tag_value'])
    logging.info(f"Training data shape: {df.shape}. Classes: {len(valid_classes)}")

    # 2. Load Patterns (to use as vocabulary/features)
    # The patterns from FP-Growth are itemsets like "spicy_food", "old_fort"
    # We will simply take the unique items from these patterns as our vocabulary for BoW
    patterns_df = pd.read_csv(INPUT_PATTERNS)
    
    vocab = set()
    for itemset_str in patterns_df['itemsets']:
        # itemset_str is like "frozenset({'item1', 'item2'})" 
        # But we saved it via mlxtend which keeps python obj repr if not careful, 
        # wait, mlxtend to_csv saves as string representation like "frozenset({'...'})"
        # We need to parse it. Or better yet, we just look at the 'adj_noun_pairs' in input data
        # which generated these patterns.
        
        # Actually, let's use the patterns as direct feature names? 
        # Simpler approach: Use the underlying words/chunks from the patterns as the vocabulary 
        # for a CountVectorizer on the 'adj_noun_pairs' column.
        
        # Better: Let's extract all unique linguistic tokens from the patterns
        # We ignore "TAG_KEY:..." items
        import ast
        try:
            items = ast.literal_eval(itemset_str) # safely eval frozenset string
            for i in items:
                if not i.startswith("TAG_KEY:"):
                    vocab.add(i)
        except:
            pass
            
    vocab = list(vocab)
    logging.info(f"Extracted {len(vocab)} unique linguistic features from patterns.")
    
    if len(vocab) == 0:
        logging.warning("No vocab from patterns. Falling back to simple unigrams/bigrams from text.")
        feature_source = df['clean_text']
        vectorizer = CountVectorizer(max_features=1000, ngram_range=(1,2))
    else:
        # We use 'adj_noun_pairs' column as input text, treating the comma-sep pairs as tokens
        # We need a custom tokenizer that splits by comma
        feature_source = df['adj_noun_pairs'].fillna("")
        vectorizer = CountVectorizer(vocabulary=vocab, tokenizer=lambda x: [t.strip() for t in x.split(',')], token_pattern=None)

    # 3. Vectorize
    X = vectorizer.fit_transform(feature_source)
    y = LabelEncoder().fit_transform(df['osm_tag_value'])
    
    logging.info(f"Feature Matrix: {X.shape}")

    # 4. Bayesian Elastic Net (Approximation via SGD)
    # Regularization: Elastic Net (L1 + L2)
    # We want to force sparsity (L1) to select features
    logging.info("Training Elastic Net SGDClassifier...")
    
    clf = SGDClassifier(
        loss='log_loss', 
        penalty='elasticnet', 
        alpha=0.001,       # Regularization strength
        l1_ratio=0.85,     # High L1 ratio for sparsity (Bayesian Lasso prior)
        max_iter=1000, 
        tol=1e-3, 
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    
    clf.fit(X, y)
    
    # 5. Feature Selection
    # Identify features with non-zero coefficients
    feature_names = vectorizer.get_feature_names_out()
    
    # clf.coef_ is (n_classes, n_features)
    # We compute the max absolute coefficient for each feature across all classes
    # If a feature is important for ANY class, we keep it.
    max_coefs = np.max(np.abs(clf.coef_), axis=0)
    
    selected_indices = np.where(max_coefs > 0.001)[0] # Threshold
    selected_features = [feature_names[i] for i in selected_indices]
    
    logging.info(f"Selected {len(selected_features)} features out of {len(feature_names)}")
    
    # Save
    data = {
        "total_features": len(feature_names),
        "selected_count": len(selected_features),
        "features": selected_features,
        "coefficents_summary": "Saved in model pickle"
    }
    
    with open(OUTPUT_FEATURES, "w") as f:
        json.dump(data, f, indent=2)
        
    with open(OUTPUT_MODEL, "wb") as f:
        pickle.dump(clf, f)
        
    logging.info(f"Saved selected features to {OUTPUT_FEATURES}")

if __name__ == "__main__":
    main()
