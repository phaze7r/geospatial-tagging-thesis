import pandas as pd
import numpy as np

# Read the CSV files
adj_noun_df = pd.read_csv('../data/islamabad_adj_noun_phrases.csv')
noun_df = pd.read_csv('../data/islamabad_noun_phrases.csv')

print("=== Adjective-Noun Phrases DataFrame ===")
print(f"Shape: {adj_noun_df.shape}")
print(f"Columns: {list(adj_noun_df.columns)}")
print("\nFirst 5 rows:")
print(adj_noun_df.head())
print("\nData types:")
print(adj_noun_df.dtypes)

print("\n" + "="*50)

print("=== Noun Phrases DataFrame ===")
print(f"Shape: {noun_df.shape}")
print(f"Columns: {list(noun_df.columns)}")
print("\nFirst 5 rows:")
print(noun_df.head())
print("\nData types:")
print(noun_df.dtypes)

# Additional analysis for FP-Growth preparation
print("\n=== Additional Analysis for FP-Growth ===")

# Check unique values and frequencies for adj-noun phrases
if 'phrase' in adj_noun_df.columns:
    print(f"\nUnique adj-noun phrases: {adj_noun_df['phrase'].nunique()}")
    print("Top 10 most frequent adj-noun phrases:")
    print(adj_noun_df['phrase'].value_counts().head(10))

# Check unique values and frequencies for noun phrases
if 'phrase' in noun_df.columns:
    print(f"\nUnique noun phrases: {noun_df['phrase'].nunique()}")
    print("Top 10 most frequent noun phrases:")
    print(noun_df['phrase'].value_counts().head(10))
elif 'noun' in noun_df.columns:
    print(f"\nUnique nouns: {noun_df['noun'].nunique()}")
    print("Top 10 most frequent nouns:")
    print(noun_df['noun'].value_counts().head(10))