"""Step 2: map the raw harvest to the new vocabulary, build the corpus and the sealed split. No re-harvest: same parquet as notebook 11.
Logic copied from notebook 11: R1b (mapping, one tag per element), R1c (English, masking, >= 4 words, template dedupe, cap, floor, place-name hash
split, test hash), R1d (near-duplicate check against the evaluation sentences). New: (key, value) -> tag through lexicon_v2_map.csv, new split salt,
and the test rows are written to their own file that only step 8 opens."""
from v2lib import *
import hashlib


def main():
    path = raw_parquet_path(); t0 = time.time()
    raw = pd.read_parquet(path)
    M = pd.read_csv(P('protocol', 'lexicon_v2_map.csv')); mp = {(k, str(v)): c for k, v, c in zip(M.key, M['value'], M.canonical)}
    lex = [l.strip() for l in open(P('protocol', 'lexicon_v2.txt')) if l.strip()]
    raw['ev'] = [eff_value(k, v, r) for k, v, r in zip(raw.key, raw['value'], raw.religion)]
    raw['tag'] = [mp.get((k, str(v))) for k, v in zip(raw.key, raw.ev)]
    m = raw[raw.tag.notna()]
    ntag = m.groupby('osm_id')['tag'].nunique(); keep = ntag[ntag == 1].index
    el = m[m.osm_id.isin(keep)].drop_duplicates('osm_id')[['osm_id', 'tag', 'key', 'value', 'description', 'name', 'pakistan']]
    print(f'mapped rows {len(m):,} | elements {m.osm_id.nunique():,} | ambiguous dropped {(ntag > 1).sum():,} | kept {len(el):,} | tags {el.tag.nunique()} of {len(lex)}')
    del raw, m

    lid = get_lid()
    d = el.copy(); d['description'] = d['description'].str.replace(r'\s+', ' ', regex=True).str.strip()
    pred = [lid.classify(t) for t in d['description'].tolist()]
    d['lang'] = [p[0] for p in pred]; d['lang_p'] = [float(p[1]) for p in pred]
    en = d[(d.lang == 'en') & (d.lang_p >= LANG_MIN_P)].copy()
    print(f'English (p>={LANG_MIN_P}): {len(en):,} of {len(d):,} | Pakistan {int(en.pakistan.sum()):,}')

    def mask_pattern(tag, value):
        phrases = {tag.replace('-', ' '), str(value).replace('_', ' ')}
        alts = sorted({re.escape(p).replace(r'\ ', r'[\s_-]?') for p in phrases if p}, key=len, reverse=True)
        return re.compile(r'\b(?:' + '|'.join(alts) + r')(?:e?s)?\b', re.I)
    PAT = {}
    def mask(row):
        k = (row.tag, row.value)
        if k not in PAT: PAT[k] = mask_pattern(*k)
        return PAT[k].sub(' ', row.description)
    en['text'] = [mask(r) for r in en.itertuples(index=False)]
    en['text'] = en['text'].str.replace(r'\s+', ' ', regex=True).str.strip()
    en['n_words'] = en['text'].str.count(r'\b[A-Za-z]{2,}\b'); en = en[en.n_words >= MIN_CONTENT_WORDS]
    print(f'>={MIN_CONTENT_WORDS} content words after masking: {len(en):,}')
    en['dedup_key'] = en['text'].str.lower().str.replace(r'\d+', '#', regex=True).str.replace(r'[^a-z# ]', '', regex=True)
    en = en.drop_duplicates('dedup_key'); print(f'after exact/template dedup: {len(en):,} | Pakistan {int(en.pakistan.sum()):,}')
    en = en.sample(frac=1.0, random_state=0)
    capped = pd.concat([pd.concat([g[g.pakistan], g[~g.pakistan].head(max(0, CAP_PER_TAG - int(g.pakistan.sum())))]) for _, g in en.groupby('tag')])
    vc = capped.tag.value_counts(); thin = sorted(set(lex) - set(vc[vc >= CORPUS_MIN_PER_TAG].index))
    capped = capped[capped.tag.isin(vc[vc >= CORPUS_MIN_PER_TAG].index)]
    print(f'capped at {CAP_PER_TAG}/tag, tags with >= {CORPUS_MIN_PER_TAG} rows: {len(capped):,} rows, {capped.tag.nunique()} tags | vocabulary tags without corpus rows: {len(thin)}')

    grp = capped['name'].fillna('').str.lower().str.strip(); grp = grp.where(grp != '', capped['osm_id'])
    h = grp.map(lambda s: int(hashlib.sha256((SPLIT_SALT + s).encode()).hexdigest()[:8], 16) % 100)
    capped['split'] = pd.cut(h, [-1, *SPLIT_CUTS], labels=['train', 'dev', 'test']).astype(str)
    for a, b in (('train', 'dev'), ('train', 'test'), ('dev', 'test')):
        assert not (set(grp[capped.split == a]) & set(grp[capped.split == b])), f'group overlap {a}/{b}'
    test_hash = sha256_text('\n'.join(sorted(capped.loc[capped.split == 'test', 'osm_id'])))
    cols = ['osm_id', 'tag', 'key', 'value', 'text', 'n_words', 'pakistan', 'split']
    td = capped[capped.split != 'test'][cols]; te = capped[capped.split == 'test'][cols]
    td.to_parquet(P('corpus', 'osm_traindev.parquet')); te.to_parquet(P('corpus', 'osm_test_sealed.parquet'))
    td.groupby(['tag', 'split']).size().unstack(fill_value=0).to_csv(P('corpus', 'tag_counts_traindev.csv'))   # train and dev only: the test is never counted by tag

    # R1d: near-duplicates of the evaluation sentences in the corpus (all splits; counts only, no model involved)
    tok = lambda s: set(re.findall(r'[a-z]{3,}', s.lower())); texts = [tok(t) for t in capped.text]; inv = {}
    for i, s in enumerate(texts):
        for w in s: inv.setdefault(w, []).append(i)
    def near(sentence):
        q_ = tok(sentence)
        if not q_: return 0
        cand = Counter(i for w in q_ for i in inv.get(w, []))
        return sum(1 for i, c in cand.items() if c / len(q_ | texts[i]) >= 0.6)
    r106, _ = load_106(); X, _, _, _ = load_pk()
    ov = {'eval_106': sum(1 for r in r106 if near(r['sentence'])), 'pakistan_592': sum(1 for r in X if near(r['sentence']))}
    print('evaluation sentences with a near-duplicate (Jaccard >= .6) in the corpus:', ov)
    stats = {'rows': len(capped), 'tags_in_corpus': int(capped.tag.nunique()), 'vocabulary_tags': len(lex), 'cap_per_tag': CAP_PER_TAG,
             'min_per_tag': CORPUS_MIN_PER_TAG, 'split_counts': capped.split.value_counts().to_dict(), 'split_salt': SPLIT_SALT,
             'test_sha256_of_sorted_ids': test_hash, 'tags_without_corpus_rows': thin, 'near_duplicates_of_eval': ov,
             'lang_filter': f'py3langid en, normalised p>={LANG_MIN_P}', 'min_content_words': MIN_CONTENT_WORDS,
             'funnel': {'mapped_elements': int(len(el)), 'english': int(len(d)), 'final_rows': len(capped)}}
    jdump(stats, P('corpus', 'split_stats.json')); print(json.dumps({k: v for k, v in stats.items() if k != 'tags_without_corpus_rows'}, indent=1))
    manifest('s02', [path, P('protocol', 'lexicon_v2_map.csv')], [P('corpus', 'osm_traindev.parquet'), P('corpus', 'osm_test_sealed.parquet'), P('corpus', 'split_stats.json')],
             rows=len(capped), seconds=time.time() - t0)


if __name__ == '__main__': main()
