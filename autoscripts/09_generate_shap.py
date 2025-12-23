import pandas as pd
import torch
import shap
import json
import os
import spacy
import matplotlib.pyplot as plt
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
from sklearn.preprocessing import LabelEncoder

def load_spacy_model(model_name):
    try:
        return spacy.load(model_name)
    except OSError:
        spacy.cli.download(model_name)
        return spacy.load(model_name)

def generate_shap():
    # Paths (Adjust if needed)
    train_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\train_set.csv"
    test_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\test_set.csv"
    features_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\selected_features.json"
    model_weights = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\autoscripts\hybrid_model.pt"
    output_dir = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported"

    if not os.path.exists(model_weights):
        print("Model weights missing. Please run training first.")
        return

    # 1. Load Resources
    print("Loading resources...")
    train_df = pd.read_csv(train_file)
    test_df = pd.read_csv(test_file)
    
    with open(features_file, 'r') as f:
        selected_features = json.load(f)
    print(f"Loaded {len(selected_features)} semantic features.")

    # 2. Setup Label Encoder (Must match training)
    le = LabelEncoder()
    le.fit(train_df['target_label'])
    class_names = list(le.classes_)
    print(f"Classes: {class_names}")

    # 3. Load Model & Tokenizer
    model_name = "distilbert-base-multilingual-cased"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=len(class_names))
    
    device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
    model.load_state_dict(torch.load(model_weights, map_location=device))
    model.to(device)
    model.eval()

    # 4. Define Augmentation Logic
    nlp = load_spacy_model("en_core_web_sm")

    def augment_text(sentence):
        doc = nlp(str(sentence))
        tokens = set([token.lemma_.lower() for token in doc])
        
        found = []
        for feat_items in selected_features:
            if set(feat_items).issubset(tokens):
                found.append("_".join(feat_items)) # e.g. "historic_mosque"
        
        feature_text = " ".join(found)
        return f"{sentence} [SEP] {feature_text}", found

    # 5. Create Explainer Pipeline
    clf = pipeline("text-classification", model=model, tokenizer=tokenizer, device=0 if torch.cuda.is_available() else -1, top_k=None)
    explainer = shap.Explainer(clf)

    # 6. Select Diverse Samples (Success Cases per Class)
    print("\nSelecting diverse success samples...")
    
    samples_to_explain = []
    classes_covered = set()
    
    # We want ~10-15 examples, ideally covering different classes
    for idx, row in test_df.iterrows():
        if len(samples_to_explain) >= 12:
            break
            
        original_text = row['sentence']
        true_label = row['target_label']
        
        # Augment
        augmented_input, features_found = augment_text(original_text)
        
        # Check Prediction
        inputs = tokenizer(augmented_input, return_tensors="pt", truncation=True, max_length=512).to(device)
        with torch.no_grad():
            logits = model(**inputs).logits
        pred_idx = logits.argmax().item()
        pred_label = le.inverse_transform([pred_idx])[0]
        
        # Heuristic: Prioritize Correct Predictions we haven't seen much of
        if pred_label == true_label:
            # Try to get 1-2 examples per class
            count_for_class = sum(1 for s in samples_to_explain if s['label'] == true_label)
            if count_for_class < 2:
                samples_to_explain.append({
                    'text': augmented_input,
                    'original': original_text,
                    'features': features_found,
                    'label': true_label,
                    'pred_idx': pred_idx,
                    'id': idx
                })

    print(f"Selected {len(samples_to_explain)} samples to explain.")

    # 7. Generate Plots
    for i, sample in enumerate(samples_to_explain):
        print(f"\n--- Processing Sample {i+1}/{len(samples_to_explain)} ---")
        print(f"Original: {sample['original']}")
        print(f"Features Added: {sample['features']}")
        print(f"Class: {sample['label']}")

        # Compute SHAP
        shap_values = explainer([sample['text']])
        
        # Visualize
        fig = plt.figure(figsize=(12, 6))
        
        # Plot the contribution for the predicted class
        shap.plots.waterfall(shap_values[0][:, sample['pred_idx']], show=False, max_display=15)
        
        # Save
        safe_label = sample['label'].replace("__", "_").replace(" ", "")
        file_name = f"shap_success_{sample['id']}_{safe_label}.png"
        save_path = os.path.join(output_dir, file_name)
        plt.savefig(save_path, bbox_inches='tight')
        plt.close(fig)
        print(f"Saved plot: {file_name}")

if __name__ == "__main__":
    generate_shap()
