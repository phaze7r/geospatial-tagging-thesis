import pandas as pd
import numpy as np
import json
import os
from sklearn.linear_model import ElasticNetCV
from sklearn.preprocessing import MultiLabelBinarizer, LabelEncoder
import spacy

def load_spacy_model(model_name):
    try:
        return spacy.load(model_name)
    except OSError:
        spacy.cli.download(model_name)
        return spacy.load(model_name)

def run_ben_selection():
    train_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\train_set.csv"
    patterns_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\frequent_patterns.csv"
    output_json = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\selected_features.json"

    if not os.path.exists(train_file) or not os.path.exists(patterns_file):
        print("Required files missing.")
        return

    # Load data
    train_df = pd.read_csv(train_file)
    patterns_df = pd.read_csv(patterns_file)
    
    # Extract unique antecedents as candidate features
    # Antecedents are saved as strings like "frozenset({'spicy', 'karahi'})"
    # We need to parse them back to sets/lists
    def parse_frozenset(s):
        # Very hacky parse for "frozenset({'item1', 'item2'})"
        if 'frozenset' in s:
            content = s.split('{')[1].split('}')[0]
            items = [i.strip().strip("'") for i in content.split(',') if i.strip()]
            return items
        return []

    patterns_df['antecedents_list'] = patterns_df['antecedents'].apply(parse_frozenset)
    
    # Filter unique candidate features
    unique_candidates = []
    seen_candidates = set()
    for items in patterns_df['antecedents_list']:
        feat_key = tuple(sorted(items))
        if feat_key and feat_key not in seen_candidates:
            unique_candidates.append(items)
            seen_candidates.add(feat_key)
    
    print(f"Candidate features: {len(unique_candidates)}")

    # Load SpaCy to process sentences (same as Task 2.1)
    nlp = load_spacy_model("en_core_web_sm")

    # Create binary matrix X
    # X[i, j] = 1 if unique_candidates[j] is a subset of tokens in train_df[i]
    X_list = []
    for idx, row in train_df.iterrows():
        doc = nlp(str(row['sentence']))
        tokens = set([token.lemma_.lower() for token in doc])
        
        row_vec = []
        for feat_items in unique_candidates:
            if set(feat_items).issubset(tokens):
                row_vec.append(1)
            else:
                row_vec.append(0)
        X_list.append(row_vec)
    
    X = np.array(X_list)
    print(f"Matrix X shape: {X.shape}")

    # Target y: OSM Labels (encoded)
    le = LabelEncoder()
    y = le.fit(train_df['target_label'])
    y_encoded = le.transform(train_df['target_label'])
    
    # For ElasticNetCV (regression), we can use a Multi-output approach or just 
    # run it on the labels. Given the prompt "Run sklearn.ElasticNetCV", 
    # I'll use a simple approach: find features that have non-zero coefficients 
    # in an ElasticNet regression predicting the label index (or one-hot).
    # Since ElasticNet is for regression, let's use One-Hot encoded targets 
    # to find features relevant for ANY class.
    
    from sklearn.preprocessing import OneHotEncoder
    ohe = OneHotEncoder(sparse_output=False)
    y_ohe = ohe.fit_transform(y_encoded.reshape(-1, 1))
    
    selected_indices = set()
    # Run ElasticNet for each class to find relevant features
    # (This is a common way to use ElasticNet for multi-class feature selection)
    from sklearn.multioutput import MultiOutputRegressor
    
    print("Running ElasticNetCV for feature selection...")
    en_cv = MultiOutputRegressor(ElasticNetCV(l1_ratio=0.5, cv=5, random_state=42))
    en_cv.fit(X, y_ohe)
    
    # Extract non-zero coefficient indices
    for estimator in en_cv.estimators_:
        non_zero = np.where(estimator.coef_ != 0)[0]
        for idx in non_zero:
            selected_indices.add(int(idx))
    
    winning_features = [unique_candidates[i] for i in selected_indices]
    print(f"Selected {len(winning_features)} winning features.")

    # Save Winning Features
    with open(output_json, 'w') as f:
        json.dump(winning_features, f)
    print(f"Saved selected features to {output_json}")

if __name__ == "__main__":
    run_ben_selection()
