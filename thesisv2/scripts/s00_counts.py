"""Step 0: counts per key=value from the raw OSM harvest (read-only input). GATE: the user reads data/vocab_candidates.csv.
Raw file = notebook 11 R0e harvest: every OSM element with a description tag, 16 keys, 2.9M rows, `pakistan` flag.
n_en_est = n_desc * English share, the share measured with py3langid on a sample of LID_SAMPLE_PER_PAIR rows per pair (same classifier and
threshold as the corpus step). Exact numbers come from step 2."""
from v2lib import *


def main():
    path = raw_parquet_path(); t0 = time.time()
    D = pd.read_parquet(path, columns=['osm_id', 'key', 'value', 'description', 'religion', 'pakistan'])
    print(f'raw harvest: {len(D):,} rows, {D.osm_id.nunique():,} elements, Pakistan rows {int(D.pakistan.sum()):,}')
    D['ev'] = [eff_value(k, v, r) for k, v, r in zip(D.key, D['value'], D.religion)]
    g = D.groupby(['key', 'ev'])
    C = g.agg(n_desc=('osm_id', 'size'), n_elem=('osm_id', 'nunique'), n_pk=('pakistan', 'sum')).reset_index().rename(columns={'ev': 'value'})
    C['tag'] = [tag_of(k, 'place_of_worship', v[len('place_of_worship['):-1]) if v.startswith('place_of_worship[') else tag_of(k, v) for k, v in zip(C.key, C['value'])]
    lid = get_lid()
    rs = np.random.RandomState(0); share, share_pk = {}, {}
    for (k, v), idx in g.indices.items():
        if len(idx) < 5: continue
        take = idx if len(idx) <= LID_SAMPLE_PER_PAIR else rs.choice(idx, LID_SAMPLE_PER_PAIR, replace=False)
        sub = D.iloc[take]; txt = sub.description.fillna('').str.replace(r'\s+', ' ', regex=True).str.strip().tolist()
        en = np.array([(lid.classify(t)[0] == 'en' and lid.classify(t)[1] >= LANG_MIN_P) if t else False for t in txt])
        share[(k, v)] = float(en.mean()); pk = sub.pakistan.values.astype(bool)
        share_pk[(k, v)] = float(en[pk].mean()) if pk.any() else 0.0
    C['en_share'] = [share.get((k, v), 0.0) for k, v in zip(C.key, C['value'])]
    C['n_en_est'] = (C.n_desc * C.en_share).round().astype(int)
    C['n_en_pk_est'] = [int(round(n * share_pk.get((k, v), 0.0))) for k, v, n in zip(C.key, C['value'], C.n_pk)]
    C = C.sort_values('n_en_est', ascending=False)
    out = P('data', 'vocab_candidates.csv'); C.to_csv(out, index=False)
    print(f'{len(C):,} key=value pairs | with n_en_est >= {VOCAB_FLOOR_EN}: {(C.n_en_est >= VOCAB_FLOOR_EN).sum():,} | {time.time()-t0:.0f}s')
    print(C.groupby('key').agg(pairs=('value', 'size'), described=('n_desc', 'sum'), english_est=('n_en_est', 'sum')).sort_values('english_est', ascending=False).to_string())
    print(C.head(40)[['key', 'value', 'tag', 'n_desc', 'n_en_est', 'n_pk']].to_string(index=False))
    manifest('s00', [path], [out], pairs=len(C), rows=len(D))
    print(f'\nGATE: read {out}, then run s01_vocab_propose.py')


if __name__ == '__main__': main()
