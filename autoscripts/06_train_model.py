import pandas as pd
import numpy as np
import json
import os
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments, Trainer
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, f1_score
import spacy
import matplotlib.pyplot as plt

def load_spacy_model(model_name):
    try:
        return spacy.load(model_name)
    except OSError:
        spacy.cli.download(model_name)
        return spacy.load(model_name)

class CustomDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item['labels'] = torch.tensor(self.labels[idx])
        return item

    def __len__(self):
        return len(self.labels)

def compute_metrics(pred):
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)
    f1 = f1_score(labels, preds, average='macro')
    acc = accuracy_score(labels, preds)
    return {'accuracy': acc, 'f1': f1}

def train_model():
    train_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\train_set.csv"
    features_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\selected_features.json"
    model_output = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\autoscripts\hybrid_model.pt"
    plot_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\plot_training_curve.png"

    if not os.path.exists(train_file) or not os.path.exists(features_file):
        print("Required files missing.")
        return

    # Load data
    df = pd.read_csv(train_file)
    with open(features_file, 'r') as f:
        selected_features = json.load(f)
    print(f"Loaded {len(df)} rows and {len(selected_features)} features.")

    # Augment Input
    nlp = load_spacy_model("en_core_web_sm")
    augmented_sentences = []
    for idx, row in df.iterrows():
        doc = nlp(str(row['sentence']))
        tokens = set([token.lemma_.lower() for token in doc])
        
        found_features = []
        for feat_items in selected_features:
            if set(feat_items).issubset(tokens):
                found_features.append(" ".join(feat_items))
        
        feature_text = " ".join(found_features)
        augmented_text = f"{row['sentence']} [SEP] {feature_text}"
        augmented_sentences.append(augmented_text)
    
    df['augmented_sentence'] = augmented_sentences

    # Encode Labels
    le = LabelEncoder()
    df['labels'] = le.fit_transform(df['target_label'])
    num_labels = len(le.classes_)
    print(f"Number of classes: {num_labels}")

    # Split for validation
    train_df = df.sample(frac=0.8, random_state=42)
    val_df = df.drop(train_df.index)

    # Tokenization
    model_name = "distilbert-base-multilingual-cased"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    train_encodings = tokenizer(train_df['augmented_sentence'].tolist(), truncation=True, padding=True, max_length=128)
    val_encodings = tokenizer(val_df['augmented_sentence'].tolist(), truncation=True, padding=True, max_length=128)

    train_dataset = CustomDataset(train_encodings, train_df['labels'].tolist())
    val_dataset = CustomDataset(val_encodings, val_df['labels'].tolist())

    # Training Arguments
    training_args = TrainingArguments(
        output_dir='./results',
        num_train_epochs=3,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        warmup_steps=100,
        weight_decay=0.01,
        logging_dir='./logs',
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True
    )

    # Train
    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=num_labels)
    device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
    model.to(device)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics
    )

    print(f"Starting training on {device}...")
    train_result = trainer.train()
    
    # Save Model Weights
    torch.save(model.state_dict(), model_output)
    print(f"Saved model to {model_output}")

    # Plot Training Curve (simplified)
    history = trainer.state.log_history
    train_loss = [x['loss'] for x in history if 'loss' in x]
    eval_loss = [x['eval_loss'] for x in history if 'eval_loss' in x]
    
    plt.figure(figsize=(10, 5))
    plt.plot(train_loss, label='Train Loss')
    plt.plot(np.linspace(0, len(train_loss), len(eval_loss)), eval_loss, label='Eval Loss')
    plt.xlabel('Steps')
    plt.ylabel('Loss')
    plt.legend()
    plt.title('Training and Evaluation Loss')
    plt.savefig(plot_file)
    print(f"Saved training curve to {plot_file}")

if __name__ == "__main__":
    train_model()
