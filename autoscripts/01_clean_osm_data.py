import pandas as pd
import glob
import os

def clean_osm_data():
    raw_dir = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\raw"
    output_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\final_osm_classes_pakistan.csv"
    report_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\report_class_distribution.csv"

    # Load all raw CSV files
    csv_files = glob.glob(os.path.join(raw_dir, "*_raw.csv"))
    if not csv_files:
        print("No raw CSV files found!")
        return

    df_list = []
    for f in csv_files:
        df_list.append(pd.read_csv(f))
    
    df = pd.concat(df_list, ignore_index=True)
    print(f"Loaded {len(df)} rows from {len(csv_files)} files.")

    # Filter vague rows
    vague_filters = [
        ('amenity', 'yes'),
        ('shop', 'yes'),
        ('building', 'yes')
    ]
    
    initial_len = len(df)
    for key, val in vague_filters:
        df = df[~((df['osm_tag_key'] == key) & (df['osm_tag_value'] == val))]
    
    print(f"Dropped {initial_len - len(df)} vague rows.")

    # Create target_label
    df['target_label'] = df['osm_tag_key'] + "__" + df['osm_tag_value']

    # Label frequencies and cut-off
    counts = df['target_label'].value_counts()
    valid_labels = counts[counts >= 50].index
    
    df_clean = df[df['target_label'].isin(valid_labels)]
    print(f"Kept {len(df_clean)} rows after dropping labels with < 50 occurrences (Remaining labels: {len(valid_labels)}).")

    # Save clean list
    df_clean.to_csv(output_file, index=False)
    print(f"Saved cleaned data to {output_file}")

    # Thesis Artifact: Top 50 classes report
    report_df = counts.head(50).reset_index()
    report_df.columns = ['target_label', 'count']
    report_df.to_csv(report_file, index=False)
    print(f"Saved distribution report to {report_file}")

if __name__ == "__main__":
    clean_osm_data()
