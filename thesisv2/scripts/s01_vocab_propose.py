"""Step 1a: propose the vocabulary by rule and write protocol/lexicon_v2_draft.csv for the user to edit. GATE after step 1b.
Rules (config.py): allowed keys/values, excluded non-place values, floor on estimated English descriptions, must-have everyday and tourism
tags (flagged if thin or absent), and every gold tag of the 106 set and the Pakistan set (forced in, so those sets stay scorable).
The user edits the `include` (Y/N) and `canonical` (merge target) columns."""
from v2lib import *


def gold_tags():
    r106, _ = load_106(); X, _, _, _ = load_pk()
    return Counter([r['gold_tag'] for r in r106]), Counter([r['gold_tag'] for r in X])


def main():
    C = pd.read_csv(P('data', 'vocab_candidates.csv')); C['value'] = C['value'].astype(str)
    must = {(k, v) for k, vs in MUST_HAVE.items() for v in vs}
    tour_keys = {'tourism', 'historic', 'natural'}; tour_leisure = set(MUST_HAVE['leisure'])

    def decide(r):
        k, v = r.key, (r.value.split('[')[0] if r.value.startswith('place_of_worship[') else r.value)
        rule = KEY_RULES.get(k)
        ok_key = rule == ALL or (isinstance(rule, set) and v in rule) or (k == 'amenity' and v == 'place_of_worship')
        bad = v in EXCLUDE_VALUES['*'] or v in EXCLUDE_VALUES.get(k, set())
        is_must = (k, v) in must
        if not ok_key: return 'N', 'key/value not a place type', is_must
        if bad: return 'N', 'excluded value (not a place)', is_must
        if r.tag is None or (isinstance(r.tag, float)): return 'N', 'no tag (religion missing)', is_must
        if r.n_en_est >= VOCAB_FLOOR_EN: return 'Y', 'above floor', is_must
        if is_must and r.n_en_est >= MUST_FLOOR: return 'Y', 'must-have above must-floor', is_must
        if is_must: return 'N', 'MUST-HAVE BUT THIN: decide', is_must
        return 'N', f'below floor ({VOCAB_FLOOR_EN})', is_must
    dec = [decide(r) for r in C.itertuples()]
    C = C.assign(include=[d[0] for d in dec], reason=[d[1] for d in dec], must=[d[2] for d in dec])
    C['block'] = ['tourism' if (k in tour_keys or (k == 'leisure' and v in tour_leisure)) else 'everyday' for k, v in zip(C.key, C['value'])]
    C['canonical'] = [MERGE_PROPOSAL.get(t, t) if isinstance(t, str) else t for t in C.tag]
    D = C[C.include == 'Y'].copy()
    # must-haves that do not exist in the harvest at all
    found = {(k, v.split('[')[0] if v.startswith('place_of_worship[') else v) for k, v in zip(C.key, C['value'])}
    absent = sorted(f'{k}={v}' for k, v in must if (k, v) not in found)
    # gold tags: forced in
    g106, gpk = gold_tags(); gold = set(g106) | set(gpk)
    have = set(D.canonical) | set(D.tag)
    rows = []
    for t in sorted(gold):
        canon = MERGE_PROPOSAL.get(t, t)
        if canon in have or t in have: continue
        cand = C[(C.tag == t) | (C.canonical == canon)]
        if len(cand):   # exists in the harvest but below floor or excluded: include as gold-forced with its real counts
            c0 = cand.sort_values('n_en_est', ascending=False).iloc[0]
            rows.append({**c0.to_dict(), 'include': 'Y', 'reason': 'GOLD-FORCED (below floor or excluded)', 'block': 'gold-forced'})
        else:
            rows.append({'key': '(gold)', 'value': t, 'tag': t, 'canonical': canon, 'n_desc': 0, 'n_elem': 0, 'n_pk': 0, 'en_share': 0.0,
                         'n_en_est': 0, 'n_en_pk_est': 0, 'include': 'Y', 'reason': 'GOLD-FORCED (no OSM text: ranked by noun similarity)',
                         'must': False, 'block': 'gold-forced'})
    if rows:
        C = pd.concat([C, pd.DataFrame(rows)], ignore_index=True)
        # the forced rows replace nothing: duplicates by (key,value) keep the Y version
        C = C.sort_values('include', ascending=False).drop_duplicates(['key', 'value'], keep='first')
    C['gold_in_106'] = C.canonical.map(lambda t: g106.get(t, 0)); C['gold_in_pk'] = C.canonical.map(lambda t: gpk.get(t, 0))
    cols = ['include', 'key', 'value', 'tag', 'canonical', 'block', 'n_desc', 'n_en_est', 'n_pk', 'n_en_pk_est', 'must', 'gold_in_106', 'gold_in_pk', 'reason']
    C = C.sort_values(['include', 'n_en_est'], ascending=[False, False])[cols]
    out = P('protocol', 'lexicon_v2_draft.csv'); C.to_csv(out, index=False)
    Y = C[C.include == 'Y']; tags = sorted(set(Y.canonical))
    print(f'proposed vocabulary: {len(tags)} distinct tags from {len(Y)} key=value rows (target {MIN_TAGS}-{TARGET_TAGS})')
    print(Y.groupby('block').canonical.nunique().to_string())
    if len(tags) < MIN_TAGS: print(f'WARNING: fewer than {MIN_TAGS}. Lower VOCAB_FLOOR_EN in config.py or accept thin tags at the gate.')
    print('\nmust-have but thin (decide):', C[C.reason.str.contains('MUST-HAVE BUT THIN', na=False)][['key', 'value', 'n_en_est', 'n_pk']].to_dict('records'))
    print('must-have not in the harvest at all:', absent)
    thin_pk = Y[(Y.block == 'tourism') & (Y.n_pk > 0) & (Y.n_en_pk_est < 3)]
    print('tourism tags with almost no Pakistani text:', thin_pk.canonical.tolist()[:40])
    print('gold tags forced in:', C[C.block == 'gold-forced'].canonical.tolist())
    print('proposed merges:', {a: b for a, b in MERGE_PROPOSAL.items()})
    manifest('s01', [P('data', 'vocab_candidates.csv')], [out], n_tags=len(tags), absent_must=absent)
    print(f'\nGATE: edit {out} (include Y/N, canonical), then run s01b_vocab_freeze.py')


if __name__ == '__main__': main()
