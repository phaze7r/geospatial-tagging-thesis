
import pandas as pd
import random
import yaml
import os

# --- Config ---
OUTPUT_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../datareported/synthetic_volunteered_descriptions.csv'))
LABELS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../config/labels_pk.yaml'))
CITIES = ['Attock', 'Chitral', 'Islamabad', 'Karachi', 'Kohat', 'Lahore', 'Muzaffarabad', 'Peshawar', 'Quetta', 'Rawalpindi', 'Sialkot', 'Skardu']

# --- Templates ---
# Templates designed to act as a "Guide" or "Traveler"
# Emphasizing ADJ+NOUN pairs for the thesis task.
TEMPLATES = [
    "I visited this {adj} {noun} and was amazed by the {adj2} {noun2}.",
    "A {adj} {noun} located in the heart of the city, offering {adj2} {noun2}.",
    "If you are looking for a {adj} {noun}, this is the place to be. It has {adj2} {noun2}.",
    "This {adj} {noun} is popular among locals for its {adj2} {noun2}.",
    "We found a {adj} {noun} which was surprisingly {adj2}.",
    "The {adj} {noun} here is known for providing {adj2} {noun2}.",
    "As a traveler, I recommend this {adj} {noun} for its {adj2} {noun2}.",
    "A hidden gem! This {adj} {noun} features {adj2} {noun2}.",
    "The {adj} {noun} was closed, but the {adj2} {noun2} nearby was open.",
    "Locals say this {adj} {noun} is the best spot for {adj2} {noun2}.",
    "An iconic {adj} {noun} representing the culture of the city.",
    "This {adj} {noun} is a must-visit for anyone interested in {adj2} {noun2}.",
    "The {adj} {noun} offers a great view of the {adj2} {noun2}.",
    "I spent hours at this {adj} {noun} enjoying the {adj2} {noun2}.",
    "A very {adj} {noun} with excellent service and {adj2} {noun2}."
]

ADJECTIVES = [
    "beautiful", "historic", "ancient", "modern", "bustling", "quiet", "crowded", "peaceful", "scenic", "vibrant",
    "famous", "hidden", "local", "traditional", "luxury", "affordable", "clean", "dusty", "majestic", "small",
    "huge", "popular", "friendly", "spicy", "delicious", "fresh", "colorful", "busy", "calm", "safe"
]

NOUNS_GENERIC = [
    "place", "spot", "area", "location", "site", "view", "atmosphere", "environment", "experience", "service",
    "food", "staff", "building", "structure", "design", "architecture", "street", "road", "corner", "landmark"
]

def load_osm_tags():
    if not os.path.exists(LABELS_FILE):
        return ["park", "mosque", "shop", "restaurant", "hotel"] # Fallback
    
    with open(LABELS_FILE, 'r') as f:
        data = yaml.safe_load(f)
    
    tags = []
    # Recursively extract all list items
    def extract(d):
        if isinstance(d, dict):
            for k, v in d.items():
                extract(v)
        elif isinstance(d, list):
            tags.extend([str(x) for x in d])
    
    extract(data)
    return list(set(tags))

def main():
    print("[*] Generating Synthetic Volunteered Descriptions...")
    osm_nouns = load_osm_tags()
    print(f"    - Loaded {len(osm_nouns)} OSM tags as domain nouns.")
    
    data = []
    
    # Generate 500 descriptions
    for i in range(500):
        city = random.choice(CITIES)
        template = random.choice(TEMPLATES)
        
        # Fill template
        # Primary Subject (OSM Tag)
        noun = random.choice(osm_nouns).replace('_', ' ')
        adj = random.choice(ADJECTIVES)
        
        # Secondary Subject (Generic or OSM)
        if random.random() > 0.5:
            noun2 = random.choice(osm_nouns).replace('_', ' ')
        else:
            noun2 = random.choice(NOUNS_GENERIC)
        adj2 = random.choice(ADJECTIVES)
        
        description = template.format(adj=adj, noun=noun, adj2=adj2, noun2=noun2)
        
        data.append({
            'id': i + 100000, # Synthetic ID
            'city': city,
            'role': 'Volunteer Guide',
            'synthetic_description': description
        })
        
    df = pd.DataFrame(data)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"[+] Saved {len(df)} synthetic descriptions to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
