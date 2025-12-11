import json
import os
import glob

def sync_dashboard():
    # Paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, 'docs')
    reports_dir = os.path.join(base_dir, 'archive', 'reports')
    data_json_path = os.path.join(docs_dir, 'data.json')
    data_js_path = os.path.join(docs_dir, 'data.js')
    
    # 1. Read data.json
    print(f"Reading {data_json_path}...")
    try:
        with open(data_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading data.json: {e}")
        data = {"config": {}, "progress": 0, "notes": []}

    # 2. Read all markdown reports
    print(f"Scanning reports in {reports_dir}...")
    reports = {}
    if os.path.exists(reports_dir):
        for report_path in glob.glob(os.path.join(reports_dir, '*.md')):
            filename = os.path.basename(report_path)
            # Web path should be relative to index.html, e.g., 'reports/filename.md'
            web_key = f"reports/{filename}"
            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    reports[web_key] = f.read()
                print(f"  Loaded {filename}")
            except Exception as e:
                print(f"  Error loading {filename}: {e}")
    
    # 3. Combine into final object
    data['reports'] = reports
    
    # 4. Write data.js
    print(f"Writing to {data_js_path}...")
    js_content = f"window.LOCAL_DATA = {json.dumps(data, indent=2)};"
    
    with open(data_js_path, 'w', encoding='utf-8') as f:
        f.write(js_content)
    
    print("Different 'data.js' generated successfully.")

if __name__ == "__main__":
    sync_dashboard()
