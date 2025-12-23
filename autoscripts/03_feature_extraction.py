import pandas as pd
import spacy
import json
import os

def load_spacy_model(model_name):
    try:
        return spacy.load(model_name)
    except OSError:
        print(f"Downloading SpaCy model: {model_name}")
        spacy.cli.download(model_name)
        return spacy.load(model_name)

def extract_features():
    train_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\train_set.csv"
    output_json = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\extracted_transactions.json"
    sample_csv = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\sample_extracted_features.csv"

    if not os.path.exists(train_file):
        print(f"Training file not found: {train_file}")
        return

    # Load data
    df = pd.read_csv(train_file)
    print(f"Loaded {len(df)} training rows.")

    # Load SpaCy model (Multilingual)
    nlp = load_spacy_model("en_core_web_sm")

    transactions = []
    sample_rows = []

    for idx, row in df.iterrows():
        doc = nlp(str(row['sentence']))
        
        # Extract Adj-Noun pairs
        # We also include the OSM Class (target_label) in the transaction for FP-Growth
        transaction = []
        
        # Simple extraction: all nouns and adjectives
        for token in doc:
            if token.pos_ in ['ADJ', 'NOUN']:
                transaction.append(token.lemma_.lower())
        
        # Add the OSM class as a specific item for FP-Growth targeting
        osm_class = row['target_label']
        transaction.append(osm_class)
        
        # Remove duplicates within a transaction
        transaction = list(set(transaction))
        transactions.append(transaction)

        if idx < 10:
            sample_rows.append({
                'sentence': row['sentence'],
                'transaction': transaction,
                'target_label': osm_class
            })

    # Save all transactions
    with open(output_json, 'w') as f:
        json.dump(transactions, f)
    print(f"Saved {len(transactions)} transactions to {output_json}")

    # Save sample for thesis artifact
    sample_df = pd.DataFrame(sample_rows)
    sample_df.to_csv(sample_csv, index=False)
    print(f"Saved sample to {sample_csv}")

if __name__ == "__main__":
    extract_features()
