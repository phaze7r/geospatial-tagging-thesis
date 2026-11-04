import os
import pandas as pd
import json
import logging
import numpy as np
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_CSV = os.path.join(BASE_DIR, "data", "processed", "descriptions_cleaned.csv")
OUTPUT_RESULTS = os.path.join(BASE_DIR, "data", "processed", "classification_results.json")
LOG_FILE = os.path.join(BASE_DIR, "data", "processed", f"classification_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

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
    Generates embeddings.
    Tries to use SentenceTransformer (SBERT) first.
    Falls back to TF-IDF if SBERT is missing or fails.
    """
    try:
        from sentence_transformers import SentenceTransformer
        logging.info("Loading SentenceTransformer model (all-MiniLM-L6-v2)...")
        # Use a lightweight model
        model = SentenceTransformer('all-MiniLM-L6-v2')
        embeddings = model.encode(texts, show_progress_bar=True)
        logging.info(f"Generated SBERT embeddings: {embeddings.shape}")
        return embeddings, "SBERT"
    except ImportError:
        logging.warning("SentenceTransformer not found. Falling back to TF-IDF.")
    except Exception as e:
        logging.warning(f"SBERT generation failed: {e}. Falling back to TF-IDF.")
    
    # Fallback
    tfidf = TfidfVectorizer(max_features=768)
    embeddings = tfidf.fit_transform(texts).toarray()
    logging.info(f"Generated TF-IDF embeddings: {embeddings.shape}")
    return embeddings, "TF-IDF"

# --- Main Execution ---

def main():
    logging.info("Starting Embedding & Classification (Autoscript 04)...")
    
    if not os.path.exists(INPUT_CSV):
        logging.error(f"Input file not found: {INPUT_CSV}")
        return

    # Load Data
    df = pd.read_csv(INPUT_CSV, encoding='utf-8')
    logging.info(f"Loaded {len(df)} descriptions.")
    
    # Filter for valid descriptions
    df = df.dropna(subset=['description_final', 'osm_tag_value'])
    texts = df['description_final'].tolist()
    labels = df['osm_tag_value'].tolist() # Target class is the place type
    
    if len(texts) < 10:
        logging.error("Not enough data to train.")
        return

    # Generate Embeddings
    X, embed_type = get_embeddings(texts)
    
    # Encode Labels
    le = LabelEncoder()
    y = le.fit_transform(labels)
    class_names = [str(c) for c in le.classes_]
    
    # Filter rare classes (need at least 2 samples for split)
    class_counts = pd.Series(y).value_counts()
    valid_classes = class_counts[class_counts >= 2].index
    
    # Filter valid indices
    valid_mask = np.isin(y, valid_classes)
    X = X[valid_mask]
    y = y[valid_mask]
    
    if len(np.unique(y)) < 2:
        logging.error("Not enough classes to classify after filtering.")
        return

    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Train Classifier (Logistic Regression as robust baseline)
    logging.info(f"Training Logistic Regression (using {embed_type} features)...")
    clf = LogisticRegression(max_iter=1000, class_weight='balanced')
    clf.fit(X_train, y_train)
    
    # Evaluate
    y_pred = clf.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    # Get unique classes in test set for report
    unique_classes = np.unique(np.concatenate([y_test, y_pred]))
    target_names = [le.inverse_transform([c])[0] for c in unique_classes]
    
    report = classification_report(y_test, y_pred, labels=unique_classes, target_names=target_names, output_dict=True, zero_division=0)
    
    logging.info(f"Accuracy: {accuracy:.4f}")
    
    # Save Results
    results = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "embedding_type": embed_type,
        "model": "LogisticRegression",
        "accuracy": accuracy,
        "classification_report": report
    }
    
    with open(OUTPUT_RESULTS, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    logging.info(f"Results saved to {OUTPUT_RESULTS}")
    logging.info("Classification pipeline complete.")

if __name__ == "__main__":
    main()
