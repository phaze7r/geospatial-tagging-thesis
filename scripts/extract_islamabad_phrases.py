import requests
from bs4 import BeautifulSoup
import spacy
from spacy.matcher import Matcher
import pandas as pd
import os
from datetime import datetime
import time

# Load spaCy English model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Please install spaCy English model: python -m spacy download en_core_web_sm")
    exit()


def get_text_from_url(url):
    """Fetch and clean main text from a travel blog URL."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove unwanted elements
        for tag in soup(["script", "style", "header", "footer", "nav", "aside", "form", "button"]):
            tag.decompose()

        # Extract text from paragraphs, headings, and list items
        text_elements = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"])
        text = ' '.join([elem.get_text(separator=" ", strip=True) for elem in text_elements])

        # Clean up extra whitespace
        text = ' '.join(text.split())

        print(f"✓ Successfully extracted {len(text)} characters from {url}")
        return text

    except Exception as e:
        print(f"✗ Error fetching {url}: {str(e)}")
        return ""


def extract_adj_noun_phrases(text):
    """Extract adjective–noun and noun phrases from text using spaCy."""
    if not text.strip():
        return [], []

    doc = nlp(text)
    matcher = Matcher(nlp.vocab)

    # Pattern 1: Adjective(s) + Noun(s) (e.g., 'beautiful mosque', 'lush green hills')
    adj_noun_pattern = [
        {"POS": "ADJ", "OP": "+"},
        {"POS": "NOUN", "OP": "+"}
    ]

    # Pattern 2: Determiner + Adjective(s) + Noun(s) (e.g., 'the beautiful mosque')
    det_adj_noun_pattern = [
        {"POS": "DET", "OP": "?"},
        {"POS": "ADJ", "OP": "+"},
        {"POS": "NOUN", "OP": "+"}
    ]

    matcher.add("ADJ_NOUN", [adj_noun_pattern])
    matcher.add("DET_ADJ_NOUN", [det_adj_noun_pattern])

    adj_noun_phrases = []
    noun_phrases = []
    sentences = []

    for sent in doc.sents:
        sent_text = sent.text.strip()
        if len(sent_text) > 10:  # Filter out very short sentences
            sentences.append(sent_text)

            # Extract adj-noun patterns
            sent_doc = nlp(sent_text)
            matches = matcher(sent_doc)

            for match_id, start, end in matches:
                span = sent_doc[start:end]
                phrase = span.text.strip()
                if len(phrase) > 3 and phrase.lower() not in ['the', 'a', 'an']:
                    adj_noun_phrases.append((phrase, sent_text))

            # Extract noun chunks (noun phrases)
            for chunk in sent_doc.noun_chunks:
                phrase = chunk.text.strip()
                if len(phrase) > 2 and phrase.lower() not in ['the', 'a', 'an', 'this', 'that']:
                    noun_phrases.append((phrase, sent_text))

    return adj_noun_phrases, noun_phrases, sentences


def process_blog(url):
    """Process a single blog URL and return extracted phrases."""
    print(f"\n🔄 Processing: {url}")
    text = get_text_from_url(url)

    if not text:
        return [], [], []

    adj_noun, noun_phrases, sentences = extract_adj_noun_phrases(text)

    print(f"   📝 Extracted {len(sentences)} sentences")
    print(f"   🔤 Found {len(adj_noun)} adjective-noun phrases")
    print(f"   📋 Found {len(noun_phrases)} noun phrases")

    return adj_noun, noun_phrases, sentences


def main():
    """Main function to process all blogs and save results."""
    print("🚀 Starting Islamabad Travel Blog Phrase Extraction")
    print("=" * 60)

    # List of Islamabad travel blog URLs
    urls = [
        "https://travelwithmansoureh.com/blog/travel-guide-places-to-visit-in-islamabad-and-things-to-do",
        "https://travelpakistani.com/blogs/top-10-most-beautiful-places-in-islamabad-2024/125",
        "https://www.bucketlistly.blog/posts/6-best-places-visit-things-to-do-islamabad-pakistan",
        "https://www.pakistantravelblog.com/top-6-tourist-attractions-near-islamabad/"
    ]

    all_adj_noun = []
    all_noun_phrases = []
    all_sentences = []
    all_sources = []

    # Process each URL
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Processing blog...")
        adj_noun, noun_phrases, sentences = process_blog(url)

        # Add to collections with source info
        all_adj_noun.extend([(phrase, sentence, url) for phrase, sentence in adj_noun])
        all_noun_phrases.extend([(phrase, sentence, url) for phrase, sentence in noun_phrases])
        all_sentences.extend([(sentence, url) for sentence in sentences])

        # Small delay to be respectful to servers
        time.sleep(1)

    print(f"\n📊 EXTRACTION SUMMARY:")
    print(f"   Total sentences: {len(all_sentences)}")
    print(f"   Total adjective-noun phrases: {len(all_adj_noun)}")
    print(f"   Total noun phrases: {len(all_noun_phrases)}")

    # Always point to the repo's root data folder, even when running from scripts/
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    print(f"\n📁 Saving files to '{data_dir}' directory...")

    # Create DataFrames
    df_adj_noun = pd.DataFrame(all_adj_noun, columns=["adj_noun_phrase", "sentence", "source"])
    df_noun_phrases = pd.DataFrame(all_noun_phrases, columns=["noun_phrase", "sentence", "source"])
    df_sentences = pd.DataFrame(all_sentences, columns=["sentence", "source"])

    # Save individual files
    adj_noun_file = os.path.join(data_dir, "islamabad_adj_noun_phrases.csv")
    noun_phrases_file = os.path.join(data_dir, "islamabad_noun_phrases.csv")
    sentences_file = os.path.join(data_dir, "islamabad_sentences.csv")

    df_adj_noun.to_csv(adj_noun_file, index=False)
    df_noun_phrases.to_csv(noun_phrases_file, index=False)
    df_sentences.to_csv(sentences_file, index=False)

    # Create combined dataset matching your thesis structure
    combined_data = []

    # Add adjective-noun phrases
    for phrase, sentence, source in all_adj_noun:
        combined_data.append({
            'description': phrase,
            'sentence_context': sentence,
            'phrase_type': 'adjective_noun',
            'language': 'English',
            'location': 'Islamabad',
            'osm_tag_key': '',  # To be filled later
            'osm_tag_value': '',  # To be filled later
            'source': source,
            'coordinates': '',  # To be filled later
            'extracted_at': datetime.now().isoformat()
        })

    # Add noun phrases
    for phrase, sentence, source in all_noun_phrases:
        combined_data.append({
            'description': phrase,
            'sentence_context': sentence,
            'phrase_type': 'noun_phrase',
            'language': 'English',
            'location': 'Islamabad',
            'osm_tag_key': '',  # To be filled later
            'osm_tag_value': '',  # To be filled later
            'source': source,
            'coordinates': '',  # To be filled later
            'extracted_at': datetime.now().isoformat()
        })

    df_combined = pd.DataFrame(combined_data)
    combined_file = os.path.join(data_dir, "islamabad_extracted_phrases.csv")
    df_combined.to_csv(combined_file, index=False)

    print(f"✅ Files saved successfully:")
    print(f"   - {adj_noun_file} ({len(df_adj_noun)} rows)")
    print(f"   - {noun_phrases_file} ({len(df_noun_phrases)} rows)")
    print(f"   - {sentences_file} ({len(df_sentences)} rows)")
    print(f"   - {combined_file} ({len(df_combined)} rows)")

    # Display sample results
    print(f"\n🔍 SAMPLE ADJECTIVE-NOUN PHRASES:")
    print(df_adj_noun.head(10)[['adj_noun_phrase', 'source']].to_string(index=False))

    print(f"\n🔍 SAMPLE NOUN PHRASES:")
    print(df_noun_phrases.head(10)[['noun_phrase', 'source']].to_string(index=False))

    print(f"\n🎉 Extraction completed! Ready for your thesis pipeline.")


if __name__ == "__main__":
    main()