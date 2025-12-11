# scripts/sanity_test_on_patterns.py (optional)
import json, numpy as np, pandas as pd
from scipy.sparse import load_npz
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

X = load_npz("output/efpg/X_patterns.npz")
y = np.load("output/efpg/y.npy")
with open("scripts/output/efpg/label_map.json","r") as f:
    lbl = json.load(f)
id2lbl = {v:k for k,v in lbl.items()}
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
clf = LogisticRegression(penalty="elasticnet", solver="saga", l1_ratio=0.7, C=1.0, max_iter=3000, n_jobs=-1)
clf.fit(Xtr, ytr)
print(classification_report(yte, clf.predict(Xte), target_names=[id2lbl[i] for i in range(len(id2lbl))]))