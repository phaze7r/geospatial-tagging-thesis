"""Step 9: everyday-basics check. The sentences in protocol/basics_test.json were written BEFORE step 8 and are not edited afterwards. Scores the frozen
M1, M2 and M3 and prints the top five tags of M3 for every sentence. Gold tags missing from the vocabulary are reported, never added afterwards.
The sentence from the app screenshot that triggered the vocabulary work is B01."""
from v2lib import *
ensure_spacy_model()


def main():
    fz = jload(FROZEN); spec = {n: tuple(v) for n, v in fz['arm_specs'].items()}; short = {n.split()[0]: n for n in spec}
    BASICS = os.path.join(REPO, 'protocol', 'basics_test.json'); B = jload(BASICS); alias = alias_map()
    ex = extract([b['sentence'] for b in B])
    lex, RK, T = load_final_models(extra_nouns={n for e in ex for n in e['context_nouns']})
    for bb in RK:                                          # query-side vectors for the new nouns
        V, _ = load_vec_cache(bb); V, _ = extend_vectors(V, bb, {n for e in ex for n in e['context_nouns']} | set(lex)); RK[bb].vec = pr.ladder(V)
    PV, NADJ, CLASSES, TB = T['PV'], T['NADJ'], T['CLASSES'], T['tables']
    gold = [alias.get(b['gold_tag'], b['gold_tag']) for b in B]; inv = [g in set(lex) for g in gold]
    rows = [{'context_nouns': e['context_nouns'], 'adjectives': e['adjectives'], 'transaction': e['transaction'], 'gold_tag': g, 'id': b['id']} for e, g, b in zip(ex, gold, B)]
    df = as_df(rows); run = Runner(RK, {'osm_dev': df}, PV, NADJ, CLASSES, lam_fixed=fz['lambda'])
    out = {}
    for key in ('M1', 'M2', 'M3'):
        name = short[key]; bb, mode, tk = spec[name]
        run.arm(name, bb, mode='naive' if mode == 'naive' else 'nouns', tbl=run.table(PV, NADJ, TB[tk]) if tk else None, verbose=False)
        r = run.RANKS[name]['osm_dev']; out[key] = {k: float((r[np.array(inv)] <= k).mean()) for k in (1, 3, 5)}; out[key]['n_scored'] = int(sum(inv))
    M3 = short['M3']; bb, mode, tk = spec[M3]; R = RK[bb]; SIM = run.sims(bb, 'osm_dev', 'nouns'); TBL = run.table(PV, NADJ, TB[tk])(R, df)
    s = (1 - fz['lambda'][M3]) * SIM + fz['lambda'][M3] * TBL; detail = []
    for i, b in enumerate(B):
        top = [R.TAGS[j] for j in np.argsort(-s[i])[:5]]
        detail.append({'id': b['id'], 'group': b['group'], 'sentence': b['sentence'], 'gold': gold[i], 'gold_in_vocabulary': inv[i], 'top5_M3': top, 'rank_M3': int(run.RANKS[M3]['osm_dev'][i]),
                       'rank_M1': int(run.RANKS[short['M1']]['osm_dev'][i]), 'rank_M2': int(run.RANKS[short['M2']]['osm_dev'][i])})
        print(f"{b['id']} {gold[i]:20s} {'in-vocab' if inv[i] else 'NOT IN VOCABULARY':17s} M3 top5 {top}")
    print('\nHits (sentences whose gold tag is in the vocabulary):', json.dumps(out)); print('gold tags not in the vocabulary:', sorted({g for g, v in zip(gold, inv) if not v}))
    jdump({'summary': out, 'detail': detail}, P('results', 's09_basics.json')); manifest('s09', [BASICS, FROZEN], [P('results', 's09_basics.json')], **out)


if __name__ == '__main__': main()
