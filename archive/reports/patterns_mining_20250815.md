### Notebook 2 — Pattern Extraction & Guided Frequent Itemsets

- Timestamp: 2025-08-15 02:34:29 UTC
- Transactions: 3 (after pruning: 3)
- MIN_SUP: 0.05, MIN_CONF: 0.5, MAX_ITEMSET_LEN: 3
- Vocab kept: 3
- Frequent itemsets: 7; Rules: 8
- Guidance: Included domain synonyms (e.g., masjid->amenity=mosque) as osm_hint:* items to bias useful patterns.
- Top rules (by lift/conf): [{"antecedent": ["osm_hint:amenity=park"], "consequent": "amenity=park", "support": 0.3333, "confidence": 1.0, "lift": 3.0, "antecedent_len": 1}, {"antecedent": ["osm_hint:amenity=park", "osm_hint:shop=mall"], "consequent": "amenity=park", "support": 0.3333, "confidence": 1.0, "lift": 3.0, "antecedent_len": 2}, {"antecedent": ["city:islamabad", "osm_hint:amenity=park"], "consequent": "amenity=park", "support": 0.3333, "confidence": 1.0, "lift": 3.0, "antecedent_len": 2}, {"antecedent": ["city:islamabad", "osm_hint:amenity=park", "osm_hint:shop=mall"], "consequent": "amenity=park", "support": 0.3333, "confidence": 1.0, "lift": 3.0, "antecedent_len": 3}, {"antecedent": ["osm_hint:shop=mall"], "consequent": "amenity=park", "support": 0.3333, "confidence": 0.5, "lift": 1.5, "antecedent_len": 1}]
