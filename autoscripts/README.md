# Automation Scripts

This directory contains the Python scripts for the **Geospatial Tagging of Volunteered Place Descriptions** Master's Thesis.

## ✅ Current Implementation (Phases 1-4)

These scripts implement the full **Bayesian Elastic Net & Extended FP-Growth Approach**.

### Phase 1: Data Preprocessing
- **[01_clean_osm_data.py](01_clean_osm_data.py)**: Cleans raw Overpass API data, filters vague tags (`amenity=yes`), and standardizes the ground truth `target_label`.
- **[02_preprocess_corpus.py](02_preprocess_corpus.py)**: Normalizes the text corpus, maps labels to OSM classes, and splits data into Train (80%) and Test (20%) sets.

### Phase 2: Hybrid Methodology (Training)
- **[03_feature_extraction.py](03_feature_extraction.py)**: Extracts semantic features (Adjective, Noun) from the training set using SpaCy.
- **[04_run_fpgrowth.py](04_run_fpgrowth.py)**: Runs Extended FP-Growth to mine frequent patterns associating semantic features with OSM classes.
- **[05_ben_selection.py](05_ben_selection.py)**: Performs feature selection using Bayesian Elastic Net (`ElasticNetCV`) to identify the most predictive features.
- **[06_train_model.py](06_train_model.py)**: Augments the text with selected features and trains the **DistilBERT** classifier.

### Phase 3: Baseline Comparison
- **[07_baseline_method.py](07_baseline_method.py)**: Implements the "Word2Vec + Cosine Similarity" baseline (Supervisor's Method).

### Phase 4: Results & Evaluation
- **[08_evaluate_results.py](08_evaluate_results.py)**: Calculates Hit@1, Hit@3, Macro F1, and nDCG metrics for both the Hybrid and Baseline models.
- **[09_generate_shap.py](09_generate_shap.py)**: Generates SHAP waterfall plots to explain model predictions.

---

## 🕒 Legacy Pipelines

### Thesis Comparative Analysis (Previous Iteration)
- `scripts/01_enrich_data.py`
- `scripts/02_feature_engineering.py`
- `scripts/03_run_thesis_comparison.py`

### Extended Pipeline (Old 12 Cities)
- `01_collect_data_extended.py`
- `02_preprocess_extended.py`
- `03_fpgrowth_guided.py`
- `04_ben_feature_selection.py`
- `05_hybrid_classification.py`
- `06_xai_extended.py`

## Usage

To run the full pipeline locally:

```bash
# 1. Preprocessing
python autoscripts/01_clean_osm_data.py
python autoscripts/02_preprocess_corpus.py

# 2. Hybrid Training
python autoscripts/03_feature_extraction.py
python autoscripts/04_run_fpgrowth.py
python autoscripts/05_ben_selection.py
python autoscripts/06_train_model.py

# 3. Baseline & Evaluation
python autoscripts/07_baseline_method.py
python autoscripts/08_evaluate_results.py
python autoscripts/09_generate_shap.py
```
