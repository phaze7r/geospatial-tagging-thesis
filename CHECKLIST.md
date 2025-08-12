Thesis Completion Checklist

This checklist outlines the daily tasks and deliverables for completing the thesis methodology and writing within 4 weeks. Each task is tied to a specific goal and deliverable to ensure steady progress.

Week 1: Data Collection and Preprocessing
Day 1: Audit existing data and define schema

Review current dataset and map it to the target schema:

Columns: description, language, location, osm_tag_key, osm_tag_value, source, coordinates.

Identify missing fields and gaps.

Deliverable: data/processed/schema_map.csv (mapping existing data to the target schema).

Day 2: Define label space and Overpass queries

Finalize 30–60 OSM key–value pairs relevant to Pakistan.

Write Overpass API queries to collect data for these tags (nodes, ways, relations).

Deliverable: config/labels_pk.yaml (list of tags) and scripts/overpass_collect.py.

Day 3: Collect and enrich data

Run Overpass queries for 5–10 key tags (e.g., mosques, parks, bazaars).

Enrich data with Wikipedia/Wikidata summaries or geosearch by coordinates.

Deliverable: data/processed/descriptions_enriched.csv (with description_final column).

Day 4: Multilingual preprocessing

Detect languages (English, Urdu, Roman Urdu) and normalize text:

Lowercase, strip diacritics, normalize punctuation.

Add a language column and preprocess description_final.

Deliverable: utils/text_normalize.py and data/processed/descriptions_clean.csv.

Day 5: Thesis writing: Data collection and preprocessing

Write the Data Collection and Preprocessing sections of your thesis:

Sources (OSM, Wikipedia, blogs).

Schema and multilingual handling.

Challenges (e.g., Urdu/Roman Urdu normalization).

Deliverable: Draft of Chapter 3: Data Collection and Preprocessing.

Week 2: FP-Growth and Pattern Mining
Day 6: Adjective–noun pattern extraction

Extract adjective–noun and noun–noun patterns from description_final:

Use POS tagging for English.

Use rule-based extraction for Urdu/Roman Urdu.

Deliverable: notebooks/01_preprocess_patterns.ipynb and data/processed/itemsets_raw.csv.

Day 7: Synonym mapping and itemset creation

Map domain-specific synonyms to OSM concepts (e.g., mandir → place_of_worship).

Create FP-Growth-ready itemsets: patterns + normalized tokens.

Deliverable: data/processed/itemsets_clean.parquet.

Day 8: Guided Extended FP-Growth

Implement FP-Growth with guidance (OSM-relevant lexicon, minsup thresholds).

Compute support, confidence, and lift for patterns.

Deliverable: scripts/pattern_mining.py and data/processed/patterns_global.csv.

Day 9: Per-tag pattern mining

Mine patterns per tag and filter for discriminative patterns (e.g., high lift).

Deliverable: data/processed/patterns_per_tag.csv.

Day 10: Thesis writing: FP-Growth and pattern mining

Write the Pattern Mining section of your thesis:

Adjective–noun extraction.

FP-Growth methodology (global and per-tag).

Results: top patterns, support, lift.

Deliverable: Draft of Chapter 4: Pattern Mining.

Week 3: Bayesian Elastic Net and DistilBERT
Day 11: Feature selection with Bayesian Elastic Net

Build sparse bag-of-patterns features.

Run Bayesian Elastic Net (or ElasticNetCV as a proxy) to select features.

Deliverable: notebooks/02_feature_selection_ben.ipynb and selected_features.json.

Day 12: Baseline classifier (patterns only)

Train a simple classifier (e.g., Logistic Regression) using selected patterns.

Evaluate with micro/macro F1 and confusion matrix.

Deliverable: notebooks/03_baseline_patterns.ipynb and confusion_matrix.png.

Day 13: DistilBERT embeddings

Extract embeddings for description_final using DistilBERT or a multilingual variant.

Combine embeddings with selected patterns (feature fusion).

Deliverable: notebooks/04_fusion_model.ipynb and results_fusion.json.

Day 14: Fusion model training

Train a classifier on fused features (patterns + embeddings).

Compare performance to patterns-only baseline.

Deliverable: Updated results_fusion.json and evaluation plots.

Day 15: Thesis writing: Feature selection and classification

Write the Feature Selection and Classification sections of your thesis:

Bayesian Elastic Net methodology.

Baseline and fusion model results.

Deliverable: Draft of Chapter 5: Feature Selection and Classification.

Week 4: XAI, Evaluation, and Finalization
Day 16: Explainability (XAI)

For each prediction, show top contributing patterns and coefficients.

Create 5 qualitative case studies (e.g., why a description was tagged as amenity=mosque).

Deliverable: docs/explainability_cases.md with examples.

Day 17: Slice evaluations

Evaluate performance by:

Language (English, Urdu, Roman Urdu).

Region (city/province).

Tag categories (e.g., amenity, tourism, shop).

Deliverable: notebooks/05_slice_eval.ipynb and slice_metrics.csv.

Day 18: Pipeline documentation

Write detailed documentation for the pipeline:

Preprocessing, FP-Growth, feature selection, classification, and XAI.

Deliverable: docs/pipeline_overview.md.

Day 19: Thesis writing: XAI and evaluation

Write the Explainability and Evaluation sections of your thesis:

XAI methodology and case studies.

Evaluation metrics and slice analysis.

Deliverable: Draft of Chapter 6: Explainability and Evaluation.

Day 20: Finalization

Write the Introduction and Conclusion chapters.

Proofread the entire thesis and ensure all sections are complete.

Deliverable: Final thesis draft.

Daily Checklist Template

Use this template to track daily progress:

Goal: What you aim to achieve today.

Tasks:

Task 1 (acceptance: …)

Task 2 (acceptance: …)

Deliverables: Files, plots, or outputs to produce.

Risks/Blocks: Any challenges or dependencies.

Definition of Done: Clear criteria for completion.

This checklist ensures you stay on track and complete both the methodology and thesis writing within 4 weeks. Update it daily and commit progress to your GitHub repo.
