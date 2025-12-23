import pandas as pd
import json
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import fpgrowth, association_rules
import os

def run_fpgrowth():
    input_json = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\extracted_transactions.json"
    output_csv = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\frequent_patterns.csv"
    report_csv = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\report_top_patterns.csv"
    osm_classes_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\final_osm_classes_pakistan.csv"

    if not os.path.exists(input_json):
        print(f"Input file not found: {input_json}")
        return

    # Load transactions
    with open(input_json, 'r') as f:
        dataset = json.load(f)
    print(f"Loaded {len(dataset)} transactions.")

    # Load valid OSM classes for filtering
    if os.path.exists(osm_classes_file):
        osm_classes_df = pd.read_csv(osm_classes_file)
        osm_classes = set(osm_classes_df['target_label'].unique())
    else:
        osm_classes = set()
        print("Warning: final_osm_classes_pakistan.csv not found.")

    # Transaction Encoding
    te = TransactionEncoder()
    te_ary = te.fit(dataset).transform(dataset)
    df = pd.DataFrame(te_ary, columns=te.columns_)

    # Run FP-Growth
    min_support = 0.005
    frequent_itemsets = fpgrowth(df, min_support=min_support, use_colnames=True)
    print(f"Found {len(frequent_itemsets)} frequent itemsets with min_support={min_support}")

    if frequent_itemsets.empty:
        print("No frequent itemsets found. Try lowering min_support.")
        return

    # Association Rules
    rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=0.1)
    
    # Filter rules where Consequent is an OSM Class
    # We check if any item in 'consequents' is in our osm_classes set
    def is_osm_consequent(consequent):
        # consequent is an enriched items (frozenset)
        return any(item in osm_classes for item in consequent)

    osm_rules = rules[rules['consequents'].apply(is_osm_consequent)].copy()
    print(f"Found {len(osm_rules)} rules with OSM Class consequents.")

    # Save frequent patterns
    osm_rules.to_csv(output_csv, index=False)
    print(f"Saved rules to {output_csv}")

    # Thesis Artifact: Top patterns report
    report_df = osm_rules.sort_values(by='confidence', ascending=False).head(50)
    report_df.to_csv(report_csv, index=False)
    print(f"Saved top patterns report to {report_csv}")

if __name__ == "__main__":
    run_fpgrowth()
