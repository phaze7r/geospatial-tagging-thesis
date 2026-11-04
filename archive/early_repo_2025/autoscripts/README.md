# Automation Scripts

This directory contains the Python scripts for the Geospatial Tagging Pipeline.

## Scripts

### Extended Pipeline (12 Cities)
- **01_collect_data_extended.py**: Collects OSM data for 12 cities.
- **02_preprocess_extended.py**: Normalizes Roman Urdu, extracts POS tags, merges data.
- **03_fpgrowth_guided.py**: Runs Guided FP-Growth mining.
- **04_ben_feature_selection.py**: Selects features using Bayesian Elastic Net.
- **05_hybrid_classification.py**: Trains Hybrid (DistilBERT+BEN) & Word2Vec Baseline.
- **06_xai_extended.py**: Generates SHAP explanations.

### Previous Versions (Legacy)
- 01_collect_data.py
- 02_preprocess_data.py
- ...

## Usage
Run scripts from the project root:
```bash
python autoscripts/01_collect_data_extended.py
```
