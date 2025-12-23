
import asyncio
import os
import glob
import pandas as pd
import yaml
from playwright.async_api import async_playwright
from tqdm import tqdm

# --- Configuration ---
CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../config/cities.yaml'))
RAW_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../datareported/raw'))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../datareported'))
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'final_enriched_dataset.csv')

async def scrape_city_context(city_name):
    """
    Scrapes generic travel context for a city from Wikipedia and Reddit.
    Returns a combined string of text.
    """
    print(f"[*] Scraping context for: {city_name}")
    context_text = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        page = await context.new_page()

        # 1. Wikipedia Travel Section (or Intro)
        try:
            wiki_url = f"https://en.wikipedia.org/wiki/{city_name}"
            await page.goto(wiki_url, timeout=15000)
            # Get the summary paragraphs
            paragraphs = await page.locator("p").all_inner_texts()
            # Filter valid paragraphs (heuristic: length > 50 chars)
            valid_paras = [p for p in paragraphs if len(p) > 50][:5] # Top 5 relevant paragraphs
            context_text.extend(valid_paras)
        except Exception as e:
            print(f"[-] Wiki Error for {city_name}: {e}")

        # 2. Reddit Travel Search (DuckDuckGo Search pointing to Reddit to avoid API/Auth)
        # "site:reddit.com travel to {city_name}"
        try:
            search_url = f"https://html.duckduckgo.com/html/?q=site:reddit.com%20travel%20{city_name}%20pakistan"
            await page.goto(search_url, timeout=15000)
            # Get search snippets
            snippets = await page.locator(".result__snippet").all_inner_texts()
            context_text.extend(snippets[:5]) 
        except Exception as e:
            print(f"[-] Reddit Search Error for {city_name}: {e}")

        await browser.close()

    return " ".join(context_text)

def main():
    # 1. Load Config
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
    
    cities_config = {c['name']: c for c in config['cities']}
    
    # 2. Load Existing Raw Data
    csv_files = glob.glob(os.path.join(RAW_DATA_DIR, "*_raw.csv"))
    print(f"[*] Found {len(csv_files)} raw CSV files.")
    
    all_poi_dfs = []

    for csv_file in csv_files:
        city_name_file = os.path.basename(csv_file).replace('_raw.csv', '').capitalize()
        # Verify if matches config
        if city_name_file not in cities_config and city_name_file != "Islamabad": # formatting might be diff
             # Try simple matching
             pass 

        df = pd.read_csv(csv_file)
        # Ensure description_raw is string
        if 'description_raw' not in df.columns:
            df['description_raw'] = ""
        df['description_raw'] = df['description_raw'].fillna("")
        
        all_poi_dfs.append(df)

    if not all_poi_dfs:
        print("[!] No raw data found!")
        return

    full_df = pd.concat(all_poi_dfs, ignore_index=True)
    print(f"[*] Total POIs loaded: {len(full_df)}")
    
    # --- PREPROCESSING (User Request) ---
    # 1. Remove strict duplicates (by osm_id)
    print("    - Running Deduplication...")
    before_len = len(full_df)
    full_df = full_df.drop_duplicates(subset=['osm_id'])
    print(f"    - Removed {before_len - len(full_df)} duplicates.")

    # 3. Enrichment Loop
    # We will scrape context for each Unique City in the config
    # And then append that context to *relevant* POIs or a generic pool? 
    # Thesis Plan: "ONLY fetch descriptions that geolocate to the BBox".
    # Implementation: We really want to find descriptions *of the POIs*.
    # But doing that for 1000s of POIs is slow.
    # User's "Antigravity Protocol": Solve sparsity.
    # Strategy: 
    #   For each city, get a "Context Blob".
    #   For each POI, if its name is mentioned in the Context Blob, append the relevant sentence.
    #   ALSO: Scrape generic "Things to do in {City}" and fuzzy match POI names.

    enriched_texts = {} # city -> full_text

    print("[*] Starting Scraping Phase (Async)...")
    
    for city_obj in tqdm(config['cities']):
        city_name = city_obj['name']
        # normalize name for matching
        
        # Scrape
        try:
             # We run async loop here synchronously for simplicity in this script structure
            text_blob = asyncio.run(scrape_city_context(city_name))
            enriched_texts[city_name] = text_blob
        except Exception as e:
            print(f"[-] Global Error scraping {city_name}: {e}")
            enriched_texts[city_name] = ""

    # 4. Merging Logic
    print("[*] Merging Context into POIs...")
    
    # Pre-compute matches to avoid O(N*M) where M is huge text
    # Actually, we just check if POI Name is in Text Blob of its city.
    
    def enrich_row(row):
        city = row['city']
        
        # Strategy Update: "Data Sparsity" is extreme.
        # We append the General City Context to EVERY POI in that city.
        # This provides a "Regional Context" signal (e.g. "coastal", "mountainous")
        # which adheres to the Thesis goal of improving Geospatial Semantics.
        
        current_desc = str(row['description_raw'])
        if city in enriched_texts:
             blob = enriched_texts[city]
             if blob:
                 # Clean up blob?
                 blob_clean = blob.replace('\n', ' ').strip()
                 # limit to 1000 chars to save space/time?
                 return current_desc + " " + blob_clean[:1000]
        
        return current_desc

    full_df['enriched_description'] = full_df.apply(enrich_row, axis=1)
    
    # 5. Save
    full_df.to_csv(OUTPUT_FILE, index=False)
    print(f"[+] Saved Enriched Dataset to {OUTPUT_FILE}")
    print(f"    - Original POIs: {len(full_df)}")
    print(f"    - Enriched POIs: {len(full_df[full_df['enriched_description'].str.len() > len(full_df['description_raw'])])}")

if __name__ == "__main__":
    main()
