"""Public copy of the extended Pakistan set. Reddit-derived rows keep their id, label and post id but not
their text (Reddit user content is not ours to relicense); everything else is kept with its per-row licence.
usage: python tools/make_public_dataset.py pk_extended_raw.json data/pakistan/pk_extended.json"""
import json, sys
from collections import Counter

src, out = sys.argv[1:3]
KEEP = ['id', 'part', 'sentence', 'gold_tag', 'alt_tags', 'uncertain', 'source', 'source_id', 'source_url', 'source_revid',
        'article', 'listing_name', 'source_text', 'venue', 'city', 'license', 'collection_tag', 'annotator_b_tag', 'blind_tag',
        'type_word_in_text', 'urdu', 'roman_urdu', 'roman_origin']
TEXT = ['sentence', 'source_text', 'urdu', 'roman_urdu']
rows = []
for r in json.load(open(src)):
    o = {k: r[k] for k in KEEP if k in r}
    if r.get('source') == 'reddit':
        for k in TEXT: o[k] = None
        o['license'] = 'text withheld (Reddit user content); rehydrate from source_id'
    rows.append(o)
cnt = Counter(r['gold_tag'] for r in rows)
for o in rows: o['primary_subset'] = cnt[o['gold_tag']] >= 3
assert len(rows) == 592 and sum(o['primary_subset'] for o in rows) == 528
json.dump(rows, open(out, 'w'), ensure_ascii=False, indent=1)
print(len(rows), 'rows |', sum(o['source'] == 'reddit' for o in rows), 'reddit rows without text |', Counter(o['license'] for o in rows))
