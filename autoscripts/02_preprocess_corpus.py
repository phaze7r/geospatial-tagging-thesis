import pandas as pd
from sklearn.model_selection import train_test_split
import os

def preprocess_corpus():
    corpus_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\pakistan_natural_osm_corpus.csv"
    osm_classes_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\final_osm_classes_pakistan.csv"
    train_output = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\train_set.csv"
    test_output = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\test_set.csv"

    if not os.path.exists(corpus_file):
        print(f"Corpus file not found: {corpus_file}")
        return

    # Load corpus
    df = pd.read_csv(corpus_file)
    print(f"Loaded corpus with {len(df)} rows.")

    # Normalize text
    df['sentence'] = df['sentence'].str.lower()

    # Map labels to target_label format
    df['target_label'] = df['osm_key'] + "__" + df['osm_value']

    # Filter labels based on standardized classes from Task 1.1
    if os.path.exists(osm_classes_file):
        osm_classes_df = pd.read_csv(osm_classes_file)
        valid_labels = set(osm_classes_df['target_label'].unique())
        
        initial_count = len(df)
        df = df[df['target_label'].isin(valid_labels)]
        print(f"Filtered corpus: {initial_count} -> {len(df)} rows (labels must exist in Task 1.1 output).")
    else:
        print("Warning: final_osm_classes_pakistan.csv not found. Skipping filtering.")

    # Split data (80% Train, 20% Test)
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, shuffle=True, stratify=df['target_label'])

    print(f"Split data into {len(train_df)} training and {len(test_df)} testing rows.")

    # Save sets
    train_df.to_csv(train_output, index=False)
    test_df.to_csv(test_output, index=False)
    print(f"Saved training set to {train_output}")
    print(f"Saved testing set to {test_output}")

if __name__ == "__main__":
    preprocess_corpus()
