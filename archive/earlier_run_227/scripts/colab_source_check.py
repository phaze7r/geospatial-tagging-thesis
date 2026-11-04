# ============================================================================
# SOURCE CHECK of the first-round (original 199) Pakistan rows, and EXTRACTION STATISTICS of the full set.
# Post hoc; nothing is refitted. Writes pk_extension/original_source_check.{csv,json} and
# pk_extension/extended_extraction_stats.json.
# ============================================================================

# ---------------------------------------------------------------- CELL SC0 --
# the two training corpora and the first-round rows
import json, sys, subprocess, pandas as pd
from collections import Counter
ROOT = '/content/drive/MyDrive/geoproject'
wv = pd.read_parquet(f'{ROOT}/results_i/weak_labelled.parquet')
osm = pd.read_parquet(f'{ROOT}/osmfinal/osm_extracted.parquet')
print('weak:', wv.shape, list(wv.columns)); print(wv[['source', 'place_name', 'split']].head(3).to_string())
print('osm:', osm.shape, list(osm.columns))
evpk = json.load(open(f'{ROOT}/eval/pk_evalset_extracted.json'))
print(Counter(r['source'] for r in evpk))

# ---------------------------------------------------------------- CELL SC1 --
# OSM rows: is the element itself in the final OSM corpus?  Wikivoyage rows: is the venue's own listing
# in the weakly labelled Wikivoyage corpus (Pakistani pages only, matched on the venue name)?
import re, numpy as np
sys.path.insert(0, ROOT)
pk_rows = pd.read_parquet(f'{ROOT}/results_m/pk_from_corpus.parquet'); print('pk_from_corpus:', pk_rows.shape, list(pk_rows.columns))
norm = lambda s: re.sub(r'[^a-z0-9]+', ' ', str(s).lower()).strip()
tok = lambda s: set(re.findall(r'[a-z]{4,}', str(s).lower()))
key = 'sent_id' if 'sent_id' in pk_rows.columns else None
wpk = wv[wv.sent_id.isin(pk_rows.sent_id)] if key else wv[wv.place_name.map(norm).isin({norm(r['venue']) for r in evpk})]
print('weak-labelled rows on Pakistani pages:', len(wpk), Counter(wpk.split))
by_name = {n: g for n, g in wpk.groupby(wpk.place_name.map(norm))}
osm_ids = dict(zip(osm.osm_id, osm.split))
c3 = Counter(r['gold_tag'] for r in evpk)
REC = []
for r in evpk:
    rec = {'row': r['row'], 'source': r['source'], 'gold': r['gold_tag'], 'n3': c3[r['gold_tag']] >= 3}
    if r['source'] == 'osm':
        rec['in_corpus'] = osm_ids.get(r['source_id'].replace('osm:', ''), '')
    elif r['source'] == 'wikivoyage':
        g = by_name.get(norm(r['venue']))
        if g is not None:
            rec['in_corpus'] = ','.join(sorted(set(g.split)))
            rec['same_weak_tag'] = bool((g.weak_tag == r['gold_tag']).any())
            rec['max_jaccard'] = round(max(len(tok(r['sentence']) & tok(t)) / max(1, len(tok(r['sentence']) | tok(t))) for t in g.text), 3)
            rec['n_sent'] = len(g)
    REC.append(rec)
S = pd.DataFrame(REC).fillna({'in_corpus': ''})
for src in ('wikivoyage', 'osm'):
    s = S[S.source == src]
    print(f"{src}: {len(s)} rows | source in corpus: {int((s.in_corpus != '').sum())} (train: {int(s.in_corpus.str.contains('train').sum())}) | "
          f"n>=3 rows with source in train: {int((s.n3 & s.in_corpus.str.contains('train')).sum())}"
          + (f" | weak tag = gold for {int(s.same_weak_tag.fillna(False).sum())}" if src == 'wikivoyage' else ''))
S.to_csv(f'{ROOT}/pk_extension/original_source_check.csv', index=False)
print(S[S.in_corpus != ''].head(12).to_string())

# ---------------------------------------------------------------- CELL SC2 --
# Effect on the PRELIMINARY (Wikivoyage-trained) Pakistan results of Section 5.4.9: rescore the 157 rows
# without the rows whose source is in the weakly labelled TRAIN split. Gate first: full 157 must give
# the published 0.618 (W2V + table) and 0.510 (W2V nouns only).
import pipeline_ranker as pr
from scipy.stats import binomtest
print('weak corpus sources:', Counter(wv.source))
for r in evpk:                                                     # OSM eval rows: also look for their name on Pakistani pages
    if r['source'] == 'osm':
        g = by_name.get(norm(r['venue']))
        if g is not None: S.loc[S.row == r['row'], 'weak_split'] = ','.join(sorted(set(g.split)))
S['weak_train'] = (S.source == 'wikivoyage') & S.in_corpus.str.contains('train') | S.get('weak_split', pd.Series('', index=S.index)).fillna('').str.contains('train')
pk3 = [r for r in evpk if c3[r['gold_tag']] >= 3]
drop = set(S[S.weak_train & S.n3].row)
RKP = {'W2V': pr.load_default(ROOT, 'w2v'), 'Numberbatch': pr.load_default(ROOT, 'numberbatch')}
def h3(rk, rows, lam): return float((rk.ranks(rows, lam=lam) <= 3).mean())
full = {'W2V + table': h3(RKP['W2V'], pk3, 0.35), 'W2V nouns only': h3(RKP['W2V'], pk3, 0), 'Numberbatch + table': h3(RKP['Numberbatch'], pk3, 0.35)}
print('full 157:', {k: round(v, 3) for k, v in full.items()})
assert abs(full['W2V + table'] - 0.6178343949044586) < 1e-9 and abs(full['W2V nouns only'] - 0.5095541401273885) < 1e-9, 'gate failed'
rest = [r for r in pk3 if r['row'] not in drop]
cut = {'W2V + table': h3(RKP['W2V'], rest, 0.35), 'W2V nouns only': h3(RKP['W2V'], rest, 0), 'Numberbatch + table': h3(RKP['Numberbatch'], rest, 0.35)}
print(f'without the {len(drop)} rows whose source is in weak train ({len(rest)} left):', {k: round(v, 3) for k, v in cut.items()})
a, b = RKP['W2V'].ranks(rest, lam=0.35) <= 3, RKP['W2V'].ranks(rest, lam=0) <= 3
ao, bo = int((a & ~b).sum()), int((b & ~a).sum())
print('transfer vs base on the rest: d', round(a.mean() - b.mean(), 3), '| improved/worsened', ao, bo, '| McNemar p', round(binomtest(min(ao, bo), ao + bo, .5).pvalue, 4))
osm_in = S[(S.source == 'osm') & (S.in_corpus != '')]; print('OSM eval rows in the final OSM corpus:', osm_in[['row', 'gold', 'n3', 'in_corpus']].to_dict('records'))
json.dump({'wikivoyage_rows': 164, 'wikivoyage_source_in_weak': int((S[S.source == 'wikivoyage'].in_corpus != '').sum()),
           'wikivoyage_source_in_weak_train': int(((S.source == 'wikivoyage') & S.in_corpus.str.contains('train')).sum()),
           'n3_rows_dropped': len(drop), 'dropped_rows': sorted(int(x) for x in drop), 'full_157': full, 'without_dropped': cut,
           'transfer_vs_base_rest': {'delta': float(a.mean() - b.mean()), 'improved': ao, 'worsened': bo, 'p': float(binomtest(min(ao, bo), ao + bo, .5).pvalue)},
           'osm_rows_in_final_corpus': osm_in[['row', 'gold', 'n3', 'in_corpus']].to_dict('records'),
           'method': 'venue name matched (normalised) against place_name of weak-labelled rows on Pakistani pages (results_m/pk_from_corpus); OSM by element id. Name matching is a lower bound.'},
          open(f'{ROOT}/pk_extension/original_source_check.json', 'w'), indent=1, default=str)
print('wrote pk_extension/original_source_check.json')

# ---------------------------------------------------------------- CELL SC3 --
# Tables 4.2 / 4.4 / 4.8: extraction statistics for the full set (extractor only, nothing is scored).
# Runs in a fresh Python process (a kernel whose spaCy was imported before the trf install cannot load it).
# Gate: the same statistics on the SAVED first-round extraction must reproduce Table 4.8's first-round column.
SRC = r'''
import json, sys, numpy as np, spacy
ROOT = '/content/drive/MyDrive/geoproject'; sys.path.insert(0, ROOT)
import pipeline_ranker as pr, adjective_extractor as ae
spacy.prefer_gpu(); PI = ae.PlaceInterpreter(model='en_core_web_trf')
X = json.load(open(f'{ROOT}/eval/pk_extended_raw.json')); evpk = json.load(open(f'{ROOT}/eval/pk_evalset_extracted.json'))
EX = dict(zip([r['id'] for r in X], pr.extract_rows([r['sentence'] for r in X], PI)))
def stats(rows):
    pit = [[t for t in r['transaction'] if t.startswith('amod:')] for r in rows]
    return {'Sentences': len(rows), 'Nouns per sentence (this work)': round(float(np.mean([len(r['ours_nouns']) for r in rows])), 2),
            'Adjectives found (total)': int(sum(len(r['adjectives']) for r in rows)),
            'Adjectives per sentence': round(float(np.mean([len(r['adjectives']) for r in rows])), 2),
            'Sentences with ≥1 adjective': f"{100 * np.mean([len(r['adjectives']) > 0 for r in rows]):.1f}%",
            'Adjective–noun pairs per sentence': round(float(np.mean([len(p) for p in pit])), 2),
            'Sentences where a direct tag hint fires': f"{100 * np.mean([len(r['tag_hints']) > 0 for r in rows]):.1f}%"}
out = {'saved_original_199': stats(evpk), 'fresh_original_199': stats([EX[f"PK{int(r['row']):03d}"] for r in evpk]),
       'fresh_new_393': stats([EX[r['id']] for r in X if r['part'] == 'extension']), 'fresh_extended_592': stats(list(EX.values())),
       'samples': {i: {'gold': next(x for x in X if x['id'] == i)['gold_tag'], 'sentence': next(x for x in X if x['id'] == i)['sentence'],
                       'nouns': EX[i]['ours_nouns'], 'adjectives': EX[i]['adjectives'],
                       'pairs': [t[5:] for t in EX[i]['transaction'] if t.startswith('amod:')]} for i in ('PK249', 'PK262', 'PK300', 'PK430')}}
json.dump(out, open(f'{ROOT}/pk_extension/extended_extraction_stats.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
'''
open('/content/ext_stats.py', 'w').write(SRC)
r = subprocess.run([sys.executable, '/content/ext_stats.py'], capture_output=True, text=True)
print(r.stdout[-6000:]); print(r.stderr[-1500:] if r.returncode else '')
