import pandas as pd
import numpy as np
import torch
import json
import os
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import f1_score, accuracy_score
import spacy

def load_spacy_model(model_name):
    try:
        return spacy.load(model_name)
    except OSError:
        spacy.cli.download(model_name)
        return spacy.load(model_name)

def calculate_ndcg(actual, predicted_scores, k=3):
    # Simplified nDCG for Hit@k
    # predicted_scores is a list of (label, score) sorted by score
    relevance = [1 if p == actual else 0 for p, s in predicted_scores[:k]]
    dcg = sum([rel / np.log2(idx + 2) for idx, rel in enumerate(relevance)])
    idcg = 1.0 # Max possible DCG for 1 correct item is 1/log2(2) = 1
    return dcg / idcg

def evaluate():
    test_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\test_set.csv"
    features_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\selected_features.json"
    model_weights = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\autoscripts\hybrid_model.pt"
    baseline_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\baseline_predictions.csv"
    output_csv = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\final_results_comparison.csv"

    if not os.path.exists(test_file):
        print("Test set missing.")
        return

    test_df = pd.read_csv(test_file)
    actual_labels = test_df['target_label'].tolist()

    # --- 1. Evaluate Hybrid Model ---
    hybrid_metrics = {'Hit@1': 0, 'Hit@3': 0, 'Macro F1': 0, 'nDCG@3': 0}
    
    if os.path.exists(model_weights) and os.path.exists(features_file):
        print("Evaluating Hybrid Model...")
        with open(features_file, 'r') as f:
            selected_features = json.load(f)
        
        # Load Model
        model_name = "distilbert-base-multilingual-cased"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        # We need the same LabelEncoder used during training
        # For simplicity, we'll re-fit it here from the training set or assume sorted unique labels
        train_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\train_set.csv"
        train_df = pd.read_csv(train_file)
        le = LabelEncoder()
        le.fit(train_df['target_label'])
        
        model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=len(le.classes_))
        model.load_state_dict(torch.load(model_weights, map_location=torch.device('cpu')))
        model.eval()

        nlp = load_spacy_model("en_core_web_sm")
        
        preds_all = []
        hit1, hit3, ndcg = 0, 0, 0
        
        for idx, row in test_df.iterrows():
            # Augment
            doc = nlp(str(row['sentence']))
            tokens = set([token.lemma_.lower() for token in doc])
            found_features = [" ".join(feat) for feat in selected_features if set(feat).issubset(tokens)]
            augmented_text = f"{row['sentence']} [SEP] {' '.join(found_features)}"
            
            # Predict
            inputs = tokenizer(augmented_text, return_tensors="pt", truncation=True, padding=True, max_length=128)
            with torch.no_grad():
                outputs = model(**inputs)
            
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1).numpy()[0]
            top_indices = probs.argsort()[-3:][::-1]
            top_labels = le.inverse_transform(top_indices)
            
            preds_all.append(top_labels[0])
            
            if top_labels[0] == row['target_label']:
                hit1 += 1
            if row['target_label'] in top_labels:
                hit3 += 1
            
            # nDCG cache
            scores = [(label, probs[idx]) for idx, label in zip(top_indices, top_labels)]
            ndcg += calculate_ndcg(row['target_label'], scores, k=3)

        hybrid_metrics['Hit@1'] = hit1 / len(test_df)
        hybrid_metrics['Hit@3'] = hit3 / len(test_df)
        hybrid_metrics['Macro F1'] = f1_score(actual_labels, preds_all, average='macro')
        hybrid_metrics['nDCG@3'] = ndcg / len(test_df)
    else:
        print("Hybrid model weights not found. Skipping evaluation.")

    # --- 2. Evaluate Baseline ---
    baseline_metrics = {'Hit@1': 0, 'Hit@3': 0, 'Macro F1': 0, 'nDCG@3': 0}
    if os.path.exists(baseline_file):
        print("Evaluating Baseline Method...")
        b_df = pd.read_csv(baseline_file)
        hit1, hit3, ndcg = 0, 0, 0
        
        for idx, row in b_df.iterrows():
            top_labels = [row['pred_1'], row['pred_2'], row['pred_3']]
            if row['pred_1'] == row['actual_label']:
                hit1 += 1
            if row['actual_label'] in top_labels:
                hit3 += 1
            
            # For nDCG we use the scores from the file if available, or just rank
            scores = [(row['pred_1'], row['score_1']), (row['pred_2'], row['score_2']), (row['pred_3'], row['score_3'])]
            ndcg += calculate_ndcg(row['actual_label'], scores, k=3)
            
        baseline_metrics['Hit@1'] = hit1 / len(b_df)
        baseline_metrics['Hit@3'] = hit3 / len(b_df)
        baseline_metrics['Macro F1'] = f1_score(b_df['actual_label'], b_df['pred_1'], average='macro')
        baseline_metrics['nDCG@3'] = ndcg / len(b_df)
    else:
        print("Baseline results not found. Skipping evaluation.")

    # --- 3. Summary & Comparison ---
    comparison_df = pd.DataFrame([
        {'Metric': 'Hit@1', 'Hybrid Model': hybrid_metrics['Hit@1'], 'Baseline (Word2Vec)': baseline_metrics['Hit@1']},
        {'Metric': 'Hit@3', 'Hybrid Model': hybrid_metrics['Hit@3'], 'Baseline (Word2Vec)': baseline_metrics['Hit@3']},
        {'Metric': 'Macro F1', 'Hybrid Model': hybrid_metrics['Macro F1'], 'Baseline (Word2Vec)': baseline_metrics['Macro F1']},
        {'Metric': 'nDCG@3', 'Hybrid Model': hybrid_metrics['nDCG@3'], 'Baseline (Word2Vec)': baseline_metrics['nDCG@3']}
    ])

    comparison_df.to_csv(output_csv, index=False)
    print(f"Results Comparison:\n{comparison_df}")
    print(f"Saved final comparison to {output_csv}")

if __name__ == "__main__":
    evaluate()
