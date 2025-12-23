import pandas as pd
import numpy as np
import gensim.downloader as api
from sklearn.metrics.pairwise import cosine_similarity
import spacy
import os

def load_spacy_model(model_name):
    try:
        return spacy.load(model_name)
    except OSError:
        spacy.cli.download(model_name)
        return spacy.load(model_name)

def run_baseline():
    test_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\test_set.csv"
    osm_classes_file = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\final_osm_classes_pakistan.csv"
    output_csv = r"e:\Github\repo-phaze7r\geospatial-tagging-thesis\datareported\baseline_predictions.csv"

    if not os.path.exists(test_file) or not os.path.exists(osm_classes_file):
        print("Required files missing.")
        return

    # Load data
    test_df = pd.read_csv(test_file)
    osm_df = pd.read_csv(osm_classes_file)
    
    unique_classes = osm_df['target_label'].unique()
    print(f"Loaded {len(test_df)} test rows and {len(unique_classes)} unique OSM classes.")

    # Load Word2Vec (this will download ~1.6GB model if not present)
    print("Loading Word2Vec model (word2vec-google-news-300)...")
    try:
        model = api.load('word2vec-google-news-300')
    except Exception as e:
        print(f"Error loading Word2Vec: {e}. Trying a smaller model for demo if needed.")
        model = api.load('glove-twitter-25') # Fallback if news-300 fails

    nlp = load_spacy_model("en_core_web_sm")

    def get_vector(text):
        doc = nlp(text)
        # Baseline: Extract nouns and average their vectors
        vectors = []
        for token in doc:
            if token.pos_ == 'NOUN' and token.text in model:
                vectors.append(model[token.text])
        
        if not vectors:
            # Fallback to all words if no nouns found
            for token in doc:
                if token.text in model:
                    vectors.append(model[token.text])
        
        if vectors:
            return np.mean(vectors, axis=0)
        else:
            return np.zeros(model.vector_size)

    # Precompute class vectors (using the label string itself, e.g., "amenity restaurant")
    print("Computing OSM class vectors...")
    class_vectors = []
    for cls in unique_classes:
        clean_cls = cls.replace("__", " ")
        class_vectors.append(get_vector(clean_cls))
    class_vectors = np.array(class_vectors)

    # Predictions
    print("Generating baseline predictions...")
    results = []
    for idx, row in test_df.iterrows():
        query_vec = get_vector(row['sentence'])
        
        # Cosine similarity with all classes
        sims = cosine_similarity([query_vec], class_vectors)[0]
        
        # Get top 3 indices
        top_indices = sims.argsort()[-3:][::-1]
        top_classes = [unique_classes[i] for i in top_indices]
        top_scores = [sims[i] for i in top_indices]

        results.append({
            'sentence': row['sentence'],
            'actual_label': row['target_label'],
            'pred_1': top_classes[0],
            'score_1': top_scores[0],
            'pred_2': top_classes[1],
            'score_2': top_scores[1],
            'pred_3': top_classes[2],
            'score_3': top_scores[2]
        })

    # Save results
    res_df = pd.DataFrame(results)
    res_df.to_csv(output_csv, index=False)
    print(f"Saved baseline predictions to {output_csv}")

if __name__ == "__main__":
    run_baseline()
