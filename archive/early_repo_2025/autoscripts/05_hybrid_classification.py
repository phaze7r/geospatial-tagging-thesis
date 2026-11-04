import os
import json
import logging
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import pickle
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression
from gensim.models import Word2Vec
from transformers import DistilBertTokenizer, DistilBertModel
from torch.utils.data import DataLoader, TensorDataset

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATAREPORTED_DIR = os.path.join(BASE_DIR, "datareported")
PROCESSED_DATA = os.path.join(DATAREPORTED_DIR, "preprocessed", "merged_dataset.csv")
BEN_FEATURES = os.path.join(DATAREPORTED_DIR, "ben_features", "ben_selected_features.json")
OUTPUT_DIR = os.path.join(DATAREPORTED_DIR, "classification")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_RESULTS = os.path.join(OUTPUT_DIR, "benchmark_results.json")
EMBEDDINGS_DIR = os.path.join(DATAREPORTED_DIR, "embeddings")
os.makedirs(EMBEDDINGS_DIR, exist_ok=True)
XAI_DIR = os.path.join(DATAREPORTED_DIR, "xai")
os.makedirs(XAI_DIR, exist_ok=True)

# Logging
log_filename = os.path.join(OUTPUT_DIR, f"classification_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()]
)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
logging.info(f"Using device: {device}")

def get_word2vec_embeddings(texts, embedding_dim=100):
    logging.info("Training Word2Vec Baseline...")
    tokenized_texts = [str(t).split() for t in texts]
    model = Word2Vec(sentences=tokenized_texts, vector_size=embedding_dim, window=5, min_count=1, workers=4)
    model.save(os.path.join(EMBEDDINGS_DIR, "word2vec_baseline.model"))
    
    embeddings = []
    for tokens in tokenized_texts:
        vecs = [model.wv[t] for t in tokens if t in model.wv]
        if vecs:
            embeddings.append(np.mean(vecs, axis=0))
        else:
            embeddings.append(np.zeros(embedding_dim))
            
    return np.array(embeddings)

def get_distilbert_embeddings(texts):
    logging.info("Generating DistilBERT Embeddings (PyTorch)...")
    tokenizer = DistilBertTokenizer.from_pretrained('distilbert-base-uncased')
    model = DistilBertModel.from_pretrained('distilbert-base-uncased').to(device)
    model.eval()
    
    all_embeddings = []
    batch_size = 32
    
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            inputs = tokenizer(batch_texts, return_tensors='pt', padding=True, truncation=True, max_length=64).to(device)
            outputs = model(**inputs)
            # CLS token
            cls_embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
            all_embeddings.append(cls_embeddings)
            
            if i % 320 == 0:
                logging.info(f"Processed {i}/{len(texts)} samples...")
                
    return np.concatenate(all_embeddings, axis=0)

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
    logging.info("Starting Hybrid Classification & Benchmarking (Autoscript 05)...")
    
    # 1. Load Data
    df = pd.read_csv(PROCESSED_DATA)
    # Filter
    class_counts = df['osm_tag_value'].value_counts()
    valid_classes = class_counts[class_counts >= 10].index
    df = df[df['osm_tag_value'].isin(valid_classes)]
    df = df.dropna(subset=['clean_text', 'osm_tag_value'])
    
    texts = df['clean_text'].astype(str).tolist()
    labels = df['osm_tag_value'].tolist()
    
    le = LabelEncoder()
    y = le.fit_transform(labels)
    
    logging.info(f"Data Loaded: {len(texts)} samples, {len(le.classes_)} classes.")

    # 2. Baseline: Word2Vec + Logistic Regression
    X_w2v = get_word2vec_embeddings(texts)
    
    X_train_w, X_test_w, y_train, y_test = train_test_split(X_w2v, y, test_size=0.2, random_state=42, stratify=y)
    
    logging.info("Training Baseline Classifier (Logistic Regression on W2V)...")
    clf_w2v = LogisticRegression(max_iter=1000, class_weight='balanced')
    clf_w2v.fit(X_train_w, y_train)
    y_pred_w = clf_w2v.predict(X_test_w)
    
    w2v_acc = accuracy_score(y_test, y_pred_w)
    logging.info(f"Baseline Word2Vec Accuracy: {w2v_acc:.4f}")

    # 3. Hybrid: DistilBERT + BEN Features
    with open(BEN_FEATURES, "r") as f:
        ben_data = json.load(f)
    selected_features = ben_data["features"]
    
    logging.info("Constructing BEN Feature Matrix...")
    feature_matrix = np.zeros((len(texts), len(selected_features)))
    
    for idx, text in enumerate(texts):
        for f_idx, feat in enumerate(selected_features):
            if feat in text:
                feature_matrix[idx, f_idx] = 1
                
    # Get Transformer Embeddings
    bert_cache = os.path.join(EMBEDDINGS_DIR, "distilbert_embeddings.npy")
    if os.path.exists(bert_cache):
        logging.info("Loading cached DistilBERT embeddings...")
        X_bert = np.load(bert_cache)
    else:
        X_bert = get_distilbert_embeddings(texts)
        np.save(bert_cache, X_bert)
        
    logging.info("Fusing Embeddings with BEN Features...")
    X_hybrid = np.hstack((X_bert, feature_matrix))
    X_hybrid = X_hybrid.astype(np.float32) # Ensure float32 for PyTorch
    
    X_train_h, X_test_h, y_train_h, y_test_h = train_test_split(X_hybrid, y, test_size=0.2, random_state=42, stratify=y)
    
    # Train Hybrid Classifier (PyTorch)
    logging.info("Training Hybrid Model (PyTorch MLP)...")
    
    model = HybridClassifier(input_dim=X_hybrid.shape[1], num_classes=len(le.classes_)).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    
    # DataLoader
    train_dataset = TensorDataset(torch.from_numpy(X_train_h), torch.from_numpy(y_train_h))
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    
    epochs = 10
    model.train()
    for epoch in range(epochs):
        epoch_loss = 0
        correct = 0
        total = 0
        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device).long()
            
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total += targets.size(0)
            correct += (predicted == targets).sum().item()
            
        if (epoch+1) % 2 == 0:
            logging.info(f"Epoch {epoch+1}/{epochs}, Loss: {epoch_loss/len(train_loader):.4f}, Acc: {correct/total:.4f}")
            
    # Evaluate
    model.eval()
    with torch.no_grad():
        inputs_test = torch.from_numpy(X_test_h).to(device)
        targets_test = torch.from_numpy(y_test_h).to(device).long()
        outputs_test = model(inputs_test)
        _, predicted_test = torch.max(outputs_test.data, 1)
        hybrid_acc = (predicted_test == targets_test).sum().item() / targets_test.size(0)
        
    logging.info(f"Hybrid Model Accuracy: {hybrid_acc:.4f}")
    
    # Save Model & Artifacts
    torch.save(model.state_dict(), os.path.join(OUTPUT_DIR, "hybrid_model.pth"))
    
    with open(os.path.join(OUTPUT_DIR, "label_encoder.pkl"), "wb") as f:
        pickle.dump(le, f)
    
    np.save(os.path.join(DATAREPORTED_DIR, "xai", "X_test_hybrid.npy"), X_test_h)
    np.save(os.path.join(DATAREPORTED_DIR, "xai", "y_test_labels.npy"), y_test_h)

    # 4. Results
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "baseline_word2vec_accuracy": w2v_acc,
        "hybrid_model_accuracy": hybrid_acc,
        "improvement": hybrid_acc - w2v_acc,
        "classes": len(le.classes_)
    }
    
    with open(OUTPUT_RESULTS, "w") as f:
        json.dump(results, f, indent=2)
        
    logging.info(f"Comparison Results saved to {OUTPUT_RESULTS}")

if __name__ == "__main__":
    main()
