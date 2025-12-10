window.LOCAL_DATA = {
  "progress": 43,
  "config": {
    "githubRepo": "phaze7r/geospatial-tagging-thesis",
    "backendApi": "https://osm-dynamic-api-0506da85fcea.herokuapp.com/api"
  },
  "notes": [
    {
      "id": 4,
      "date": "2025-06-28",
      "content": "Starting data preprocessing Phase for training data",
      "author": "phaze7r",
      "createdAt": "2024-01-15T10:00:00Z"
    },
    {
      "id": 3,
      "date": "2025-06-27",
      "content": "Completed Data Collection Phase for top 5 pakistani cities",
      "author": "phaze7r",
      "createdAt": "2025-01-15T10:00:00Z"
    },
    {
      "id": 2,
      "date": "2025-06-15",
      "content": "Started data collection phase",
      "author": "phaze7r",
      "createdAt": "2025-01-15T10:00:00Z"
    },
    {
      "id": 1,
      "date": "2025-05-20",
      "content": "Completed literature review",
      "author": "phaze7r",
      "createdAt": "2025-01-20T14:30:00Z"
    }
  ],
  "quotes": [
    "Keep exploring the geospatial frontier! \ud83c\udf0d",
    "Every commit brings you closer to success! \ud83d\ude80",
    "Data is the new oil, and you're the refiner! \u26fd",
    "Mapping the world, one tag at a time! \ud83d\uddfa\ufe0f",
    "Your research will change how we see places! \ud83d\udc41\ufe0f",
    "Geospatial intelligence is the future! \ud83d\udd2e",
    "Every dataset tells a story! \ud83d\udcca",
    "Innovation happens at the intersection of data and geography! \ud83c\udf10"
  ],
  "reports": {
    "reports/features_splits_20250815.md": "### Notebook 3 \u2014 Embeddings, Pattern Features, and Splits\n\n- Timestamp: 2025-08-15 04:07:26 UTC\n- Rows (valid labels): 3\n- Classes: 3\n- Pattern vocab size: 3\n- Embedding model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2\n- Embedding dim: 384\n- Split sizes: train=1, val=1, test=1\n",
    "reports/patterns_mining_20250815.md": "### Notebook 2 \u2014 Pattern Extraction & Guided Frequent Itemsets\n\n- Timestamp: 2025-08-15 02:34:29 UTC\n- Transactions: 3 (after pruning: 3)\n- MIN_SUP: 0.05, MIN_CONF: 0.5, MAX_ITEMSET_LEN: 3\n- Vocab kept: 3\n- Frequent itemsets: 7; Rules: 8\n- Guidance: Included domain synonyms (e.g., masjid->amenity=mosque) as osm_hint:* items to bias useful patterns.\n- Top rules (by lift/conf): [{\"antecedent\": [\"osm_hint:amenity=park\"], \"consequent\": \"amenity=park\", \"support\": 0.3333, \"confidence\": 1.0, \"lift\": 3.0, \"antecedent_len\": 1}, {\"antecedent\": [\"osm_hint:amenity=park\", \"osm_hint:shop=mall\"], \"consequent\": \"amenity=park\", \"support\": 0.3333, \"confidence\": 1.0, \"lift\": 3.0, \"antecedent_len\": 2}, {\"antecedent\": [\"city:islamabad\", \"osm_hint:amenity=park\"], \"consequent\": \"amenity=park\", \"support\": 0.3333, \"confidence\": 1.0, \"lift\": 3.0, \"antecedent_len\": 2}, {\"antecedent\": [\"city:islamabad\", \"osm_hint:amenity=park\", \"osm_hint:shop=mall\"], \"consequent\": \"amenity=park\", \"support\": 0.3333, \"confidence\": 1.0, \"lift\": 3.0, \"antecedent_len\": 3}, {\"antecedent\": [\"osm_hint:shop=mall\"], \"consequent\": \"amenity=park\", \"support\": 0.3333, \"confidence\": 0.5, \"lift\": 1.5, \"antecedent_len\": 1}]\n"
  }
};