"""Step 8: the ONE-SHOT final run. Needs the frozen protocol (step 7 --freeze). Order inside the script:
 1. restore the frozen models and re-score DEV: every frozen arm must reproduce its recorded dev Hits@3 exactly (dry run, test still sealed);
 2. open the sealed test (hash checked), write TEST_SCORED.flag, extract the test rows;
 3. extract and score the evaluation sets: base-paper 106 (supplied nouns and extractor nouns), Pakistan 528 with subsets, Urdu and Roman Urdu
    through the STORED translations (nothing is retranslated), labels relabelled through the alias table;
 4. the pre-registered family (osm_test, eval_106) and the post hoc family (everything else) get separate Holm corrections;
 5. post hoc ablation on the 106 set and the Pakistan 528.
Notebook 11 R7 and pk_extension/colab_score_extended.py, with the three-method comparison and Hits@5 added."""
from v2lib import *
ensure_spacy_model()


def extend_ranker_vectors(RK, nouns):
    for bb in RK:
        V, _ = load_vec_cache(bb); V, added = extend_vectors(V, bb, nouns); RK[bb].vec = pr.ladder(V)
        print(f'   {bb}: +{added} vectors for {len(nouns):,} evaluation/test nouns')


def to_rows(texts, tags, ids, ex, supplied=None):
    return [{'context_nouns': (supplied[i] if supplied else e['context_nouns']), 'adjectives': e['adjectives'], 'transaction': e['transaction'], 'gold_tag': tags[i], 'id': ids[i]}
            for i, e in enumerate(ex)]


def main():
    fz = jload(FROZEN); lam = fz['lambda']; spec = {n: tuple(v) for n, v in fz['arm_specs'].items()}; short = {n.split()[0]: n for n in spec}
    lex, RK, T = load_final_models(); PV, NADJ, CLASSES, TB = T['PV'], T['NADJ'], T['CLASSES'], T['tables']
    assert sha256_text('\n'.join(lex)) == fz['vocabulary_sha256'], 'vocabulary changed since the freeze'
    D = prep(pd.read_parquet(P('extracted', 'osm_traindev_extracted.parquet'))); dv = D[D.split == 'dev'].reset_index(drop=True)
    alias = alias_map(); fix = lambda t: alias.get(t, t)

    def run_specs(run):
        for name, (bb, mode, tk) in spec.items():
            run.arm(name, bb, mode='naive' if mode == 'naive' else 'nouns', tbl=run.table(PV, NADJ, TB[tk]) if tk else None, verbose=False)
    dry = Runner(RK, {'osm_dev': dv}, PV, NADJ, CLASSES, lam_fixed=lam); run_specs(dry)
    for n in spec:
        assert abs(dry.ARMS[n]['osm_dev']['Hits@3'] - fz['dev_results'][n]['Hits@3']) < 1e-9, f'dry run mismatch: {n}'
    print(f'dry run passed: {len(spec)} frozen arms reproduce their dev Hits@3 exactly'); del dry

    te = open_test_once('s08'); write_flag(); print(f'TEST OPENED ONCE: {len(te):,} rows; flag written'); t0 = time.time()
    ex_te = extract(te.text.tolist()); te_rows = to_rows(None, te.tag.tolist(), te.osm_id.tolist(), ex_te)
    df_te = as_df(te_rows); df_te['pakistan'] = te.pakistan.values
    SETS = {'osm_dev': dv, 'osm_test': df_te, 'osm_test_pakistan': df_te[df_te.pakistan].reset_index(drop=True)}

    r106, _ = load_106(); e106 = extract([r['sentence'] for r in r106]); g106 = [fix(r['gold_tag']) for r in r106]
    SETS['eval_106'] = as_df(to_rows(None, g106, list(range(len(r106))), e106, supplied=[r['context_nouns'] for r in r106]))
    SETS['eval_106_auto'] = as_df(to_rows(None, g106, list(range(len(r106))), e106))
    X, ids528, subsets, TR = load_pk(); byid = {r['id']: r for r in X}
    lim = (lambda L: list(L)[:40]) if SMOKE else (lambda L: list(L))              # --smoke: 40 rows per Pakistan set
    subsets = {k: lim(v) for k, v in subsets.items()}; ids528 = lim(ids528)
    need = set(ids528).union(*[set(v) for v in subsets.values()]); EXP = dict(zip(sorted(need), extract([byid[i]['sentence'] for i in sorted(need)])))
    pk = lambda ids: as_df([{'context_nouns': EXP[i]['context_nouns'], 'adjectives': EXP[i]['adjectives'], 'transaction': EXP[i]['transaction'], 'gold_tag': fix(byid[i]['gold_tag']), 'id': i} for i in ids])
    SETS['pk528'] = pk(ids528)
    for nm, key in (('pk_second_round_357', 'C extended n>=3, new rows only'), ('pk_first_round_rows_171', 'D extended n>=3, original rows only'),
                    ('pk_without_uncertain_395', 'S1 B without rows marked uncertain'), ('pk_without_type_word_525', 'S2 B without the 4 type-word rows')):
        SETS[nm] = pk(subsets[key])
    trids = {src: sorted(set(subsets[key]) & set(TR[src])) for src, key in (('urdu_nllb', 'U urdu 157 -> NLLB'), ('roman_llm', 'R roman 300 -> LLM'))}
    EXT = {src: dict(zip(ids, extract([TR[src][i] for i in ids]))) for src, ids in trids.items()}
    mk = lambda ids, src: as_df([{'context_nouns': EXT[src][i]['context_nouns'], 'adjectives': EXT[src][i]['adjectives'], 'transaction': EXT[src][i]['transaction'], 'gold_tag': fix(byid[i]['gold_tag']), 'id': i} for i in ids if i in EXT[src]])
    for nm, key, src in (('urdu_157_translated', 'U urdu 157 -> NLLB', 'urdu_nllb'), ('roman_300_translated', 'R roman 300 -> LLM', 'roman_llm'),
                         ('roman_author_60_translated', 'R1 roman, author-written 60 -> LLM', 'roman_llm'), ('roman_drafted_240_translated', 'R2 roman, drafted 240 -> LLM', 'roman_llm')):
        SETS[nm] = mk(subsets[key], src)
    for nm, key in (('urdu_157_english', 'U-en same 157 rows, English'), ('roman_300_english', 'R-en same 300 rows, English'),
                    ('roman_author_60_english', 'R1-en same 60 rows, English'), ('roman_drafted_240_english', 'R2-en same 240 rows, English')):
        SETS[nm] = pk(subsets[key])
    print(f'extraction of test + evaluation sets: {time.time()-t0:.0f}s | sets: ' + ', '.join(f'{k} {len(v):,}' for k, v in SETS.items()))
    extend_ranker_vectors(RK, set().union(*[nouns_of(v) for k, v in SETS.items() if k != 'osm_dev']))

    run = Runner(RK, SETS, PV, NADJ, CLASSES, lam_fixed=lam); run_specs(run)
    sets_out = [s for s in SETS if s != 'osm_dev']
    for n in spec: print(f'{n:44s} ' + ' | '.join(f"{s} H@3 {run.ARMS[n][s]['Hits@3']:.3f}" for s in ('osm_test', 'eval_106', 'pk528')))
    comps = []
    for s in sets_out:
        for a, b in fz['comparisons']:
            if short[a] not in run.RANKS or short[b] not in run.RANKS: continue
            ra, rb = run.RANKS[short[a]][s], run.RANKS[short[b]][s]
            c3, c5 = compare(ra <= 3, rb <= 3), compare(ra <= 5, rb <= 5)
            comps.append({'set': s, 'a': short[a], 'b': short[b], 'family': 'prereg' if s in fz['prereg_sets'] else 'posthoc', **c3, 'hits5': {'delta': c5['delta_hits3'], 'ci95': c5['ci95'], 'p': c5['p'], 'a_only': c5['a_only'], 'b_only': c5['b_only']}})
    for fam in ('prereg', 'posthoc'):
        idx = [i for i, c in enumerate(comps) if c['family'] == fam]
        for i, ph in zip(idx, holm([comps[i]['p'] for i in idx])): comps[i]['p_holm'] = ph
    print('\n== comparisons (Hits@3), Holm within family')
    for c in comps:
        if c['set'] in ('osm_test', 'eval_106', 'pk528'): print(f"  {c['set']:12s} {c['a'][:30]:30s} vs {c['b'][:30]:30s} dH@3 {c['delta_hits3']:+.3f} [{c['ci95'][0]:+.3f},{c['ci95'][1]:+.3f}] p_holm {c['p_holm']:.4f} ({c['family']})")
    # blocks (everyday vs tourism) and thin tags
    draft = pd.read_csv(P('protocol', 'lexicon_v2_draft.csv')); blk = dict(zip(draft.canonical, draft.block))
    breakdown = {}
    for s in ('osm_test', 'pk528'):
        t = SETS[s].tag.map(lambda x: blk.get(x, 'gold-forced')); has = SETS[s].tag.isin(CLASSES)
        breakdown[s] = {n: {'by_block': {b: float((run.RANKS[n][s][(t == b).values] <= 3).mean()) for b in sorted(set(t)) if (t == b).sum() >= 5}, 'tags_with_table_rows': float((run.RANKS[n][s][has.values] <= 3).mean()) if has.any() else None,
                            'tags_without_table_rows': float((run.RANKS[n][s][~has.values] <= 3).mean()) if (~has).any() else None} for n in (short['M1'], short['M2'], short['M3'])}
    print('\n== post hoc ablation on 106 and Pakistan 528'); ab = Runner(RK, {'osm_dev': dv, 'eval_106': SETS['eval_106'], 'pk528': SETS['pk528']}, PV, NADJ, CLASSES)
    ablation_arms(ab, T); ABL = ablation_stats(ab, ['eval_106', 'pk528'])
    final = {'protocol_sha256': sha256_file(FROZEN), 'n_tags': len(lex), 'sizes': {s: len(SETS[s]) for s in SETS}, 'arms': {n: {s: run.ARMS[n][s] for s in sets_out} for n in spec},
             'lambda': lam, 'comparisons': comps, 'breakdown': breakdown, 'ablation_posthoc': {'arms': {n: {s: a[s] for s in ('eval_106', 'pk528')} for n, a in ab.ARMS.items()}, 'stats': ABL},
             'reference_base_paper_published': {'values': BASE_PAPER_PUBLISHED, 'note': 'measured by Yousaf, Schwartz and Wolter (2023) on THEIR 227-tag list and THEIR 106 sentences; Hits@3 was not published; reference only'},
             'gold_relabelled_through_aliases': {k: v for k, v in alias.items()}, 'seconds': time.time() - t0}
    jdump(final, P('results', 'final.json'))
    np.savez_compressed(P('results', 'ranks_final.npz'), **{f'{s}|{n}': run.RANKS[n][s] for n in spec for s in sets_out})
    manifest('s08', [FROZEN, P('corpus', 'osm_test_sealed.parquet')], [P('results', 'final.json'), P('results', 'ranks_final.npz'), FLAG], sizes=final['sizes'])
    print('\nwrote results/final.json')


if __name__ == '__main__': main()
