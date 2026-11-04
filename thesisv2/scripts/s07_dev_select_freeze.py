"""Step 7: everything that is decided on DEV, then the frozen protocol. Reads no test row.
1. lambda per arm (Hits@3 then nDCG@20), backbone, and the adoption gates (paired bootstrap on dev; notebook 11 R5a, R6).
2. ablation on dev (notebook 12 AB1, AB2): cumulative A-sequence, one-change B-swaps, minimum-support sensitivity, optional small parser.
3. minimum support is re-tuned on dev: if another support beats the one used by step 6 with a CI above zero, the script stops and says which
   --min-support to rerun steps 6a and 6b with.
4. with --freeze (after the user confirmed the gate): writes protocol/PROTOCOL_FROZEN.json with the configuration, lambdas, comparisons, Holm
   families and the test hash. Step 8 refuses to run without it."""
from v2lib import *

GATES = [('adjectives in the query vs nouns only (w2v): M2 vs M1', ('w2v', 'naive', None), ('w2v', 'nouns', None)),
         ('tables at all: M3 conf vs nouns only (numberbatch)', ('numberbatch', 'table', 'conf'), ('numberbatch', 'nouns', None)),
         ('tables vs adjectives in the query: M3 vs M2 (numberbatch)', ('numberbatch', 'table', 'conf'), ('numberbatch', 'naive', None)),
         ('backbone: numberbatch vs w2v (conf)', ('numberbatch', 'table', 'conf'), ('w2v', 'table', 'conf')),
         ('selection: frequentist EN vs conf (numberbatch)', ('numberbatch', 'table', 'fen_C0.5'), ('numberbatch', 'table', 'conf')),
         ('selection: Bayesian EN vs conf (numberbatch)', ('numberbatch', 'table', 'bayes_en'), ('numberbatch', 'table', 'conf'))]


def main():
    lex = [l.strip() for l in open(P('protocol', 'lexicon_v2.txt')) if l.strip()]
    D = prep(pd.read_parquet(P('extracted', 'osm_traindev_extracted.parquet'))); tr = D[D.split == 'train'].reset_index(drop=True); dv = D[D.split == 'dev'].reset_index(drop=True)
    assert 'test' not in set(D.split)
    lex_, RK, T = load_final_models()
    assert lex_ == lex
    PV, NADJ, CLASSES = T['PV'], T['NADJ'], T['CLASSES']; TB = T['tables']; run = Runner(RK, {'osm_dev': dv}, PV, NADJ, CLASSES); tb = run.table
    spec = {}
    for name, bb, mode, tk in [('M1 base paper: nouns only (w2v)', 'w2v', 'nouns', None), ('M2 adjective-noun plain (w2v)', 'w2v', 'naive', None),
                               ('M3 our pipeline: conf table + numberbatch', 'numberbatch', 'table', 'conf'), ('M3w M3 with word2vec', 'w2v', 'table', 'conf'),
                               ('M1n nouns only (numberbatch)', 'numberbatch', 'nouns', None), ('M2n adjective-noun plain (numberbatch)', 'numberbatch', 'naive', None),
                               ('X1 frequentist EN as ranker', 'numberbatch', 'table', 'fen_C0.5'), ('X2 Bayesian EN as ranker', 'numberbatch', 'table', 'bayes_en'),
                               ('X3 log-lift as ranker', 'numberbatch', 'table', 'loglift')]:
        if tk and tk not in TB: continue
        spec[name] = (bb, mode, tk); run.arm(name, bb, mode=('naive' if mode == 'naive' else 'nouns'), tbl=tb(PV, NADJ, TB[tk]) if tk else None)
    print('\n== adoption gates on dev (paired bootstrap on Hits@3)')
    ADOPT = []
    key = lambda s_: next(n for n, v in spec.items() if v == s_)
    for label, A, B in GATES:
        if (A not in spec.values()) or (B not in spec.values()): continue
        c = compare(run.RANKS[key(A)]['osm_dev'] <= 3, run.RANKS[key(B)]['osm_dev'] <= 3); lo, hi = c['ci95']
        verdict = 'KEEP first' if lo > 0 else ('KEEP second' if hi < 0 else 'NO DIFFERENCE: simpler/existing stays')
        ADOPT.append({'gate': label, **c, 'verdict': verdict}); print(f"{label:62s} dH@3 {c['delta_hits3']:+.3f} [{lo:+.3f},{hi:+.3f}] {verdict}")
    print('\n== ablation on dev'); ablation_arms(run, T)
    ABL = ablation_stats(run, ['osm_dev'])
    # minimum-support sensitivity (re-mines and rebuilds the conf table at each support)
    print('\n== minimum support (dev)'); SUP = {}
    ytr = tr.tag.map({c: k for k, c in enumerate(CLASSES)}).values
    for ms in sorted(set(SUPPORT_GRID) | {T['min_support']}, reverse=True):     # the support used by step 6 is always part of the grid
        pv_s, nadj_s = mine(tr, ms); conf_s, _ = assoc(featurize(tr, pv_s, nadj_s), ytr, len(CLASSES)); nm = f'C support {ms:g}'
        run.arm(nm, 'numberbatch', tbl=run.table(pv_s, nadj_s, conf_s)); SUP[nm] = {'min_support': ms, 'patterns': len(pv_s), 'adjectives': nadj_s, 'pairs': len(pv_s) - nadj_s}
    used = f"C support {T['min_support']:g}"
    better = []
    for nm in SUP:
        if nm == used: continue
        c = compare(run.RANKS[nm]['osm_dev'] <= 3, run.RANKS[used]['osm_dev'] <= 3); SUP[nm]['vs_used'] = c
        if c['ci95'][0] > 0: better.append((c['delta_hits3'], SUP[nm]['min_support']))
    out = {'dev_n': len(dv), 'arms': run.ARMS, 'gates': ADOPT, 'ablation_dev': ABL, 'support': SUP, 'support_used_in_step6': T['min_support']}
    if '--small-parser' in sys.argv:      # notebook 12 AB3: only the parser changes
        out['small_parser'] = small_parser_arm(run, tr, dv, lex, T)
    jdump(out, P('results', 's07_dev_selection.json'))
    lam = {n: a['lambda'] for n, a in run.ARMS.items() if n in spec and spec[n][2]}
    if better:
        best = max(better)[1]
        print(f'\nDEV prefers min_support {best} over {T["min_support"]} (CI above zero). Rerun: s06_mine_weight.py --min-support {best} ; s06b_learning_curves.py ; then s07 again.')
        manifest('s07', [P('tables', 'feat_meta.npz')], [P('results', 's07_dev_selection.json')], frozen=False, rerun_with_min_support=best)
        raise SystemExit(2)
    print('\nminimum support: no other value beats the one used (CI), keep', T['min_support'])
    if '--freeze' not in sys.argv:
        manifest('s07', [P('tables', 'feat_meta.npz')], [P('results', 's07_dev_selection.json')], frozen=False)
        print('\nGATE: read results/s07_dev_selection.json with the user; run again with --freeze to write the protocol and unlock step 8.'); return
    names = {'M1': 'M1 base paper: nouns only (w2v)', 'M2': 'M2 adjective-noun plain (w2v)', 'M3': 'M3 our pipeline: conf table + numberbatch'}
    sets_pre = ['osm_test', 'eval_106']; sets_post = ['osm_test_pakistan', 'eval_106_auto', 'pk528'] 
    comps = [('M3', 'M1'), ('M3', 'M2'), ('M2', 'M1'), ('M3', 'M3w'), ('X2', 'M3'), ('X1', 'M3')]
    fz = {'written_utc': datetime.datetime.utcnow().isoformat() + 'Z', 'primary_metric': 'Hits@3', 'also_reported': ['Hits@5', 'nDCG@20', 'Hits@1', 'Hits@2', 'Hits@10', 'Hits@20'],
          'tie_rule': 'worst case: rank = #{score >= gold score}', 'vocabulary_sha256': sha256_text('\n'.join(lex)), 'n_tags': len(lex),
          'min_support': T['min_support'], 'lambda': {n: lam[n] for n in lam}, 'arm_specs': {n: list(v) for n, v in spec.items()},
          'arm_names': names, 'comparisons': comps, 'prereg_sets': sets_pre, 'posthoc_sets': sets_post,
          'holm': 'prereg family = comparisons x prereg_sets (separate from the post hoc family)', 'test_sha256_of_sorted_ids': jload(P('corpus', 'split_stats.json'))['test_sha256_of_sorted_ids'],
          'dev_results': {n: a['osm_dev'] for n, a in run.ARMS.items() if n in spec}, 'split_salt': SPLIT_SALT, 'test_policy': 'scored exactly once, guarded by TEST_SCORED.flag',
          'adoption_gates': ADOPT}
    assert not os.path.exists(FROZEN), 'protocol already frozen; it is never overwritten'
    jdump(fz, FROZEN); print('PROTOCOL FROZEN:', FROZEN, '| sha256', sha256_file(FROZEN)[:16])
    manifest('s07', [P('tables', 'feat_meta.npz')], [P('results', 's07_dev_selection.json'), FROZEN], frozen=True, protocol_sha256=sha256_file(FROZEN))


def small_parser_arm(run, tr, dv, lex, T):
    """N12 AB3: final configuration with en_core_web_sm in place of the transformer parser (extracts train and dev again with the small model)"""
    subprocess.run([sys.executable, '-m', 'spacy', 'download', 'en_core_web_sm'], check=False)
    sub = pd.concat([tr, dv]).reset_index(drop=True); t0 = time.time(); rows = extract(sub.text.tolist(), model='en_core_web_sm')
    SM = pd.DataFrame({'split': sub.split, 'tag': sub.tag, 'context_nouns': [r['context_nouns'] for r in rows], 'adjectives': [r['adjectives'] for r in rows], 'transaction': [r['transaction'] for r in rows]})
    SM['adjs'] = SM.adjectives.map(lambda L: sorted({a.lower() for a in L if str(a).isalpha()})); SM['pit'] = SM.transaction.map(lambda L: [it for it in L if it.startswith('amod:')])
    s_tr, s_dv = SM[SM.split == 'train'], SM[SM.split == 'dev'].reset_index(drop=True); CIX = {c: k for k, c in enumerate(T['CLASSES'])}
    pv, nadj = mine(s_tr, T['min_support']); conf, _ = assoc(featurize(s_tr, pv, nadj), s_tr.tag.map(CIX).fillna(0).astype(int).values, len(T['CLASSES']))
    r2 = Runner(run.RK, {'osm_dev': s_dv}, pv, nadj, T['CLASSES']); r2.arm('D final, small parser (en_core_web_sm)', 'numberbatch', tbl=r2.table(pv, nadj, conf))
    return {'seconds': time.time() - t0, **r2.ARMS['D final, small parser (en_core_web_sm)']}


if __name__ == '__main__': main()
