import os
import pandas as pd
import json
import logging
import numpy as np
import pickle
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegressionCV
from sklearn.preprocessing import LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_CSV = os.path.join(BASE_DIR, "data", "processed", "descriptions_cleaned.csv")
OUTPUT_RESULTS = os.path.join(BASE_DIR, "data", "processed", "bayesian_results.json")
OUTPUT_MODEL = os.path.join(BASE_DIR, "data", "processed", "bayesian_model.pkl")
OUTPUT_LE = os.path.join(BASE_DIR, "data", "processed", "label_encoder.pkl")
OUTPUT_EMBEDDINGS = os.path.join(BASE_DIR, "data", "processed", "X_test_embeddings.npy") # Save test data for XAI
OUTPUT_TEST_LABELS = os.path.join(BASE_DIR, "data", "processed", "y_test_labels.npy")     # Save test labels for XAI
LOG_FILE = os.path.join(BASE_DIR, "data", "processed", f"bayesian_net_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# --- Helper Functions ---

def get_embeddings(texts):
    """
    Generates embeddings. Similar to script 04.
    """
    try:
        from sentence_transformers import SentenceTransformer
        logging.info("Loading SentenceTransformer model (all-MiniLM-L6-v2)...")
        model = SentenceTransformer('all-MiniLM-L6-v2')
        embeddings = model.encode(texts, show_progress_bar=True)
        return embeddings, "SBERT"
    except Exception as e:
        logging.warning(f"SBERT generation failed: {e}. Falling back to TF-IDF.")
        tfidf = TfidfVectorizer(max_features=768)
        embeddings = tfidf.fit_transform(texts).toarray()
        return embeddings, "TF-IDF"

# --- Main Execution ---

def main():
    logging.info("Starting Bayesian Elastic Net Training (Autoscript 05)...")
    
    # 1. Load Data
    if not os.path.exists(INPUT_CSV):
        logging.error(f"Input file not found: {INPUT_CSV}")
        return

    df = pd.read_csv(INPUT_CSV, encoding='utf-8')
    df = df.dropna(subset=['description_final', 'osm_tag_value'])
    
    # Filter for valid classes (>=2 samples)
    class_counts = df['osm_tag_value'].value_counts()
    valid_classes = class_counts[class_counts >= 5].index # Need enough for CV
    df = df[df['osm_tag_value'].isin(valid_classes)]
    
    texts = df['description_final'].tolist()
    labels = df['osm_tag_value'].tolist()
    
    logging.info(f"Data loaded: {len(texts)} samples, {len(valid_classes)} classes.")

    # 2. Embeddings
    X, embed_type = get_embeddings(texts)
    
    # 3. Encode Labels
    le = LabelEncoder()
    y = le.fit_transform(labels)
    class_names = [str(c) for c in le.classes_]

    # 4. Train Bayesian Elastic Net (Approximation via SGDClassifier)
    # SGDClassifier with log_loss and elasticnet is essentially Elastic Net Logistic Regression
    logging.info("Training Elastic Net Classifier (SGD)...")
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    from sklearn.linear_model import SGDClassifier
    from sklearn.model_selection import GridSearchCV
    
    # Use GridSearch to find best alpha/l1_ratio roughly
    param_grid = {
        'alpha': [0.0001, 0.001, 0.01, 0.1],
        'l1_ratio': [0.15, 0.5, 0.85]
    }
    
    sgd = SGDClassifier(loss='log_loss', penalty='elasticnet', max_iter=1000, tol=1e-3, class_weight='balanced', random_state=42)
    clf = GridSearchCV(sgd, param_grid, cv=3, n_jobs=-1)
    
    clf.fit(X_train, y_train)
    best_model = clf.best_estimator_
    
    train_acc = best_model.score(X_train, y_train)
    test_acc = best_model.score(X_test, y_test)
    logging.info(f"Train Accuracy: {train_acc:.4f}, Test Accuracy: {test_acc:.4f}")
    logging.info(f"Best Params: {clf.best_params_}")

    # 5. Save Artifacts for XAI
    logging.info("Saving model and artifacts...")
    with open(OUTPUT_MODEL, "wb") as f:
        pickle.dump(best_model, f) # Save the best estimator
    
    with open(OUTPUT_LE, "wb") as f:
        pickle.dump(le, f)

    np.save(OUTPUT_EMBEDDINGS, X_test)
    np.save(OUTPUT_TEST_LABELS, y_test)
    
    # 6. Save Metrics
    results = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model": "ElasticNet SGDClassifier",
        "embedding": embed_type,
        "test_accuracy": test_acc,
        "best_params": clf.best_params_
    }
    
    with open(OUTPUT_RESULTS, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logging.info("Bayesian Net training complete.")

if __name__ == "__main__":
    main()
