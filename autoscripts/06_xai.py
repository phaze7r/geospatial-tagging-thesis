import os
import pandas as pd
import json
import logging
import numpy as np
import pickle
import matplotlib.pyplot as plt
from datetime import datetime
from sklearn.linear_model import SGDClassifier
from sklearn.calibration import CalibratedClassifierCV

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_MODEL = os.path.join(BASE_DIR, "data", "processed", "bayesian_model.pkl")
OUTPUT_LE = os.path.join(BASE_DIR, "data", "processed", "label_encoder.pkl")
INPUT_EMBEDDINGS = os.path.join(BASE_DIR, "data", "processed", "X_test_embeddings.npy")
INPUT_TEST_LABELS = os.path.join(BASE_DIR, "data", "processed", "y_test_labels.npy")
OUTPUT_PLOT = os.path.join(BASE_DIR, "data", "processed", "shap_summary.png")
LOG_FILE = os.path.join(BASE_DIR, "data", "processed", f"xai_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def main():
    logging.info("Starting Explainable AI (XAI) (Autoscript 06)...")
    
    # 1. Load Artifacts
    if not os.path.exists(OUTPUT_MODEL):
        logging.error("Model not found. Run autoscripts/05_bayesian_net.py first.")
        return

    logging.info("Loading model and data...")
    with open(OUTPUT_MODEL, "rb") as f:
        clf = pickle.load(f)
    
    with open(OUTPUT_LE, "rb") as f:
        le = pickle.load(f)

    X_test = np.load(INPUT_EMBEDDINGS)
    y_test = np.load(INPUT_TEST_LABELS)
    
    class_names = [str(c) for c in le.classes_]
    
    logging.info(f"Loaded model: {type(clf)}")
    logging.info(f"Test Data Shape: {X_test.shape}")

    # 2. SHAP Explanations
    logging.info("Generating SHAP explanations...")
    try:
        import shap
        
        # LinearExplainer is fast for linear models.
        # SGDClassifier coefficients are in clf.coef_
        # We need to construct a masker or background.
        
        # For simple linear models, LinearExplainer works well.
        # Check if clf is SGDClassifier directly or wrapped in GridSearchCV
        if hasattr(clf, 'best_estimator_'):
            model = clf.best_estimator_
        else:
            model = clf
            
        logging.info(f"Explaining model type: {type(model)}")
        
        # Calculate background (mean) for masking
        masker = shap.maskers.Independent(data=X_test)
        
        explainer = shap.LinearExplainer(model, masker=masker)
        shap_values = explainer(X_test)
        
        logging.info(f"SHAP values generated. Shape: {shap_values.shape if hasattr(shap_values, 'shape') else 'list'}")
        
        # Plotting Summary
        plt.figure()
        # Summary plot for all classes (or top class)
        shap.summary_plot(shap_values, X_test, class_names=class_names, show=False)
        plt.tight_layout()
        plt.savefig(OUTPUT_PLOT)
        logging.info(f"SHAP plot saved to {OUTPUT_PLOT}")
        
    except ImportError:
        logging.warning("SHAP library not found. Skipping XAI visualization.")
    except Exception as e:
        logging.error(f"SHAP generation failed: {e}")
        import traceback
        traceback.print_exc()

    logging.info("XAI pipeline complete.")

if __name__ == "__main__":
    main()
