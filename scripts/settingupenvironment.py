# Create requirements.txt with all necessary dependencies
requirements_content = """# Core Data Processing
pandas>=1.5.0
numpy>=1.21.0
requests>=2.28.0
beautifulsoup4>=4.11.0
lxml>=4.9.0

# NLP and ML Libraries
transformers>=4.21.0
torch>=1.12.0
scikit-learn>=1.1.0
nltk>=3.7
spacy>=3.4.0
sentence-transformers>=2.2.0

# Geospatial Libraries
shapely>=1.8.0
geopandas>=0.11.0
folium>=0.12.0

# OSM and Wikipedia APIs
overpy>=0.6
wikipedia>=1.4.0
osmnx>=1.2.0

# Web Framework (Optional)
flask>=2.2.0
flask-cors>=3.0.10

# Bayesian and Statistical Libraries
pymc>=4.0.0
arviz>=0.12.0
scipy>=1.9.0

# Pattern Mining (we'll implement Extended FP-Growth)
mlxtend>=0.20.0

# Utilities
tqdm>=4.64.0
python-dotenv>=0.20.0
jupyter>=1.0.0
matplotlib>=3.5.0
seaborn>=0.11.0

# Development Tools
pytest>=7.1.0
black>=22.0.0
flake8>=5.0.0
"""

with open('../requirements.txt', 'w', encoding='utf-8') as f:
    f.write(requirements_content)

print("✅ requirements.txt created")