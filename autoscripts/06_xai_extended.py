import os
import logging
import numpy as np
import shap
import torch
import torch.nn as nn
import matplotlib.pyplot as plt
import pickle
import json
from datetime import datetime

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATAREPORTED_DIR = os.path.join(BASE_DIR, "datareported")
CLASSIFICATION_DIR = os.path.join(DATAREPORTED_DIR, "classification")
XAI_DIR = os.path.join(DATAREPORTED_DIR, "xai")
os.makedirs(XAI_DIR, exist_ok=True)
BEN_FEATURES_FILE = os.path.join(DATAREPORTED_DIR, "ben_features", "ben_selected_features.json")

# Logging
log_filename = os.path.join(XAI_DIR, f"xai_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()]
)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

class HybridClassifier(nn.Module):
    def __init__(self, input_dim, num_classes):
        super(HybridClassifier, self).__init__()
        self.fc1 = nn.Linear(input_dim, 256)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.3)
        self.fc2 = nn.Linear(256, num_classes)
        
    def forward(self, x):
        out = self.fc1(x)
        out = self.relu(out)
        out = self.dropout(out)
        out = self.fc2(out)
        return out

def main():
    logging.info("Starting Explainable AI (SHAP) (Autoscript 06)...")
    
    # 1. Load Artifacts
    if not os.path.exists(os.path.join(CLASSIFICATION_DIR, "hybrid_model.pth")):
         logging.error("Hybrid model not found. Run Step 5 first.")
         return
         
    with open(os.path.join(CLASSIFICATION_DIR, "label_encoder.pkl"), "rb") as f:
        le = pickle.load(f)
        
    X_test = np.load(os.path.join(XAI_DIR, "X_test_hybrid.npy"))
    y_test = np.load(os.path.join(XAI_DIR, "y_test_labels.npy"))
    
    # Load Feature Names
    # DistilBERT (768 dims) + BEN Features (N dims)
    with open(BEN_FEATURES_FILE, "r") as f:
        ben_data = json.load(f)
    ben_features = ben_data["features"]
    
    feature_names = [f"distilbert_{i}" for i in range(768)] + ben_features
    
    logging.info(f"Loaded Test Data: {X_test.shape}")
    logging.info(f"Total Features: {len(feature_names)}")

    # 2. Rebuild Model
    model = HybridClassifier(input_dim=X_test.shape[1], num_classes=len(le.classes_)).to(device)
    model.load_state_dict(torch.load(os.path.join(CLASSIFICATION_DIR, "hybrid_model.pth")))
    model.eval()

    # 3. SHAP Wrapper
    # SHAP DeepExplainer or KernelExplainer. 
    # DeepExplainer works with PyTorch batches.
    
    # Use a small background sample (e.g. 100 random samples from test)
    background_indices = np.random.choice(X_test.shape[0], 100, replace=False)
    background = torch.from_numpy(X_test[background_indices]).to(device)
    
    explainer = shap.DeepExplainer(model, background)
    
    # Explain a few examples (e.g. 10)
    test_indices = np.random.choice(X_test.shape[0], 10, replace=False)
    test_samples = torch.from_numpy(X_test[test_indices]).to(device)
    
    logging.info("Calculating SHAP values (this may take a minute)...")
    shap_values = explainer.shap_values(test_samples)
    
    # Check type of shap_values
    if isinstance(shap_values, list):
        logging.info(f"SHAP values is a list of length {len(shap_values)}")
        logging.info(f"Shape of first element: {shap_values[0].shape}")
    else:
        logging.info(f"SHAP values is array of shape {shap_values.shape}")

    # 4. Visualization
    plt.figure(figsize=(12, 10))
    # shap.summary_plot handles multiclass logic (lists of arrays) automatically
    # feature_names must align with columns of test_samples
    shap.summary_plot(shap_values, test_samples, feature_names=feature_names, show=False)
    plt.tight_layout()
    
    plot_path = os.path.join(XAI_DIR, "shap_summary_plot.png")
    plt.savefig(plot_path)
    logging.info(f"Saved SHAP summary plot to {plot_path}")
    
    logging.info("XAI Complete.")

if __name__ == "__main__":
    main()
