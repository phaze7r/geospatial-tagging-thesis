# Colab cell (CPU is enough). Checks the new Pakistan rows against both training corpora before they are used.
# 1. Upload pk_extension_review.csv to Drive geoproject/eval/ first.
# 2. Run. Writes geoproject/eval/pk_extension_overlap.csv and prints the flagged rows.
# A row is flagged when its text, or the source listing it was reworded from, shares >= 50% of its
# content words (token Jaccard, words of 4+ letters) with any training sentence, or when the source
# listing appears verbatim in a training sentence.
import re, collections
import pandas as pd

ROOT = '/content/drive/MyDrive/geoproject'
new = pd.read_csv(f'{ROOT}/eval/pk_extension_review.csv')
tok = lambda s: frozenset(re.findall(r'[a-z]{4,}', str(s).lower()))

def text_col(df):
    for c in ('text', 'sentence', 'description', 'desc', 'content'):
        if c in df.columns: return c
    raise KeyError(f'no text column in {list(df.columns)}')

corpora = {}
osm = pd.read_parquet(f'{ROOT}/osmfinal/osm_extracted.parquet')
corpora['osm_final'] = osm[text_col(osm)].astype(str).tolist()
wv = pd.read_parquet(f'{ROOT}/results_i/weak_labelled.parquet')
corpora['wikivoyage_weak'] = wv[text_col(wv)].astype(str).tolist()
print({k: len(v) for k, v in corpora.items()}, '| text columns:', text_col(osm), text_col(wv))

rows = []
for name, sents in corpora.items():
    T = [tok(s) for s in sents]
    inv = collections.defaultdict(list)
    for i, t in enumerate(T):
        for w in t: inv[w].append(i)
    big = '\n'.join(sents).lower()                                   # one string: substring search runs in C
    for _, r in new.iterrows():
        for field in ('text', 'source_text'):
            q = tok(r[field])
            if not q: continue
            hits = collections.Counter(i for w in q if len(inv[w]) < 5000 for i in inv[w])   # skip very common words
            best = max((len(q & T[i]) / len(q | T[i]), i) for i in hits) if hits else (0.0, -1)
            verbatim = field == 'source_text' and len(str(r[field])) > 40 and str(r[field]).lower()[:80] in big
            if best[0] >= 0.5 or verbatim:
                rows.append({'id': r['id'], 'field': field, 'corpus': name, 'jaccard': round(best[0], 3),
                             'verbatim_source': verbatim, 'train_sentence': sents[best[1]][:200] if best[1] >= 0 else ''})
out = pd.DataFrame(rows)
out.to_csv(f'{ROOT}/eval/pk_extension_overlap.csv', index=False)
print(len(out), 'flags over', out['id'].nunique() if len(out) else 0, 'rows')
print(out.to_string()[:6000] if len(out) else 'no overlap found')
