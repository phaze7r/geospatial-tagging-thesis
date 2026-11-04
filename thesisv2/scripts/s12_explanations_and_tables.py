"""Step 12 (thesis tables, CPU or GPU): everything the thesis needs that no earlier step stored. Reads the frozen models and results; NEVER opens the sealed test split.
Sets: osm_dev, eval_106 (supplied nouns), pk528 (extractor nouns); Numberbatch backbone only.
Writes results/s12_explanations_and_tables.json:
  coverage        share of rows whose top-ranked tag (and gold tag) has at least one credible Bayesian pattern; share with any pattern; mean credible patterns
  examples        three pk528 sentences with the top-3 tags and the credible patterns behind each (mean, 94% interval)
  worked          one pk528 sentence where the table moves the gold tag from outside the top 3 to rank 1
  top_rules       the 20 most frequent adjective-noun patterns with their best tag: support, confidence, lift (training split)
  strongest       the 25 strongest credible weights of the Bayesian elastic net with the frequentist coefficient
  agreement       Bayesian credible cells against frequentist non-zero cells: Jaccard and Spearman
  per_tag_pk528   Hits@3 per gold tag, M1 and M3
  fixed_broken    top-1 changes M1 -> M3 on pk528 and eval_106, with the strongest pattern weights
Uses results/ranks_final.npz (step 8) for M1 and M3 ranks."""
from v2lib import *
ensure_spacy_model()
from scipy.stats import spearmanr
M1, M3 = 'M1 base paper: nouns only (w2v)', 'M3 our pipeline: conf table + numberbatch'


def main():
    fz = jload(FROZEN); lam = fz['lambda'][M3]
    lex, RK, T = load_final_models(); PV, NADJ, CLASSES, TB = T['PV'], T['NADJ'], T['CLASSES'], T['tables']
    assert sha256_text('\n'.join(lex)) == fz['vocabulary_sha256']
    bz = np.load(P('tables', 'tables_ben.npz')); SEL, MU, LO, HI = bz['selected'], bz['mean'], bz['hdi_lo'], bz['hdi_hi']
    D = prep(pd.read_parquet(P('extracted', 'osm_traindev_extracted.parquet'))); dv = D[D.split == 'dev'].reset_index(drop=True)
    alias = alias_map(); fix = lambda t: alias.get(t, t)
    r106, _ = load_106(); e106 = extract([r['sentence'] for r in r106])
    X, ids528, _, _ = load_pk(); byid = {r['id']: r for r in X}; ids528 = ids528[:40] if SMOKE else ids528; e528 = extract([byid[i]['sentence'] for i in ids528])
    S106 = as_df([{'context_nouns': r['context_nouns'], 'adjectives': e['adjectives'], 'transaction': e['transaction'], 'gold_tag': fix(r['gold_tag']), 'id': i} for i, (r, e) in enumerate(zip(r106, e106))])
    S528 = as_df([{'context_nouns': e['context_nouns'], 'adjectives': e['adjectives'], 'transaction': e['transaction'], 'gold_tag': fix(byid[i]['gold_tag']), 'id': i} for i, e in zip(ids528, e528)])
    SETS = {'osm_dev': dv, 'eval_106': S106, 'pk528': S528}
    V, _ = load_vec_cache('numberbatch'); V, _ = extend_vectors(V, 'numberbatch', set(lex) | nouns_of(S106) | nouns_of(S528)); R = RK['numberbatch']; R.vec = pr.ladder(V)
    cls_ix = {c: k for k, c in enumerate(CLASSES)}; TAGS = list(R.TAGS)
    ranks_final = np.load(P('results', 'ranks_final.npz'))

    cov, ex_rows, per_row = {}, {}, {}
    for s, df in SETS.items():
        Xs = featurize(df, PV, NADJ).tocsr(); S = sim_matrix(R, df, drop_abstract=True, naive=False); Tm = table_matrix(R, Xs, TB['conf'], CLASSES)
        sc = (1 - lam) * S + lam * Tm; top3 = np.argsort(-sc, axis=1)[:, :3]
        cred = lambda r, t: [j for j in Xs[r].indices if TAGS[t] in cls_ix and SEL[j, cls_ix[TAGS[t]]]]
        tc = [cred(r, top3[r, 0]) for r in range(len(df))]; gi = gold_idx(R, df.tag)
        rk = ranks(S, Tm, gi, lam)      # dry run: the recomputed M3 must reproduce the frozen figures exactly, or the coverage below would not describe the reported system
        if s == 'osm_dev': assert abs(mets(rk)['Hits@3'] - fz['dev_results'][M3]['Hits@3']) < 1e-9, 'M3 dev Hits@3 differs from the frozen protocol'
        else: assert np.array_equal(rk, ranks_final[f'{s}|{M3}']), f'recomputed M3 ranks differ from ranks_final on {s}'
        gc = [cred(r, gi[r]) if gi[r] >= 0 else [] for r in range(len(df))]
        cov[s] = {'n': len(df), 'any_pattern': float((Xs.getnnz(1) > 0).mean()), 'top_has_credible': float(np.mean([len(c) > 0 for c in tc])),
                  'gold_has_credible': float(np.mean([len(c) > 0 for c in gc])), 'mean_credible_top': float(np.mean([len(c) for c in tc])),
                  'top1_correct': float((top3[:, 0] == gi).mean())}
        per_row[s] = (Xs, sc, top3, tc)
        print(s, cov[s])

    def explain(s, r, k=3):
        Xs, sc, top3, _ = per_row[s]; df = SETS[s]; out = []
        for t in top3[r][:k]:
            pats = [{'pattern': PV[j], 'mean': float(MU[j, cls_ix[TAGS[t]]]), 'lo': float(LO[j, cls_ix[TAGS[t]]]), 'hi': float(HI[j, cls_ix[TAGS[t]]])}
                    for j in Xs[r].indices if TAGS[t] in cls_ix and SEL[j, cls_ix[TAGS[t]]]]
            out.append({'tag': TAGS[t], 'credible_patterns': sorted(pats, key=lambda d: -abs(d['mean']))[:4]})
        return {'id': str(df.id.iloc[r]), 'gold': df.tag.iloc[r], 'nouns': df.context_nouns.iloc[r], 'adjectives': df.adjs.iloc[r], 'top3': out}
    s, df = 'pk528', S528; correct = [r for r in range(len(df)) if per_row[s][2][r, 0] == gold_idx(R, [df.tag.iloc[r]])[0]]
    ok = [r for n in (2, 1, 0) for r in correct if len(per_row[s][3][r]) >= n]; ok = list(dict.fromkeys(ok))   # prefer rows with credible patterns, then any correct top-1
    examples = []
    for r in ok[:3]:
        e = explain(s, r); e['sentence'] = byid[df.id.iloc[r]]['sentence']; examples.append(e)

    r1, r3 = ranks_final[f'{s}|{M1}'], ranks_final[f'{s}|{M3}']
    wk = [r for lo, npat in ((4, 2), (2, 1), (2, 0)) for r in range(len(df)) if r3[r] == 1 and r1[r] >= lo and len(per_row[s][0][r].indices) >= npat]   # strongest case first, then weaker
    worked = None
    if wk:
        r = wk[0]; Xs, sc, top3, _ = per_row[s]; gk = cls_ix.get(df.tag.iloc[r])
        worked = {**explain(s, r, 3), 'sentence': byid[df.id.iloc[r]]['sentence'], 'rank_M1': int(r1[r]), 'rank_M3': int(r3[r]),
                  'weights': sorted([{'pattern': PV[j], 'conf_to_gold': float(TB['conf'][j, gk]) if gk is not None else 0.0} for j in Xs[r].indices], key=lambda d: -d['conf_to_gold'])[:5]}

    # frequent adjective-noun rules, training split
    Xt = sparse.load_npz(P('tables', 'X_train.npz')).tocsc(); meta = np.load(P('tables', 'feat_meta.npz'), allow_pickle=True); ytr = meta['ytr']; N = len(ytr)
    tag_n = np.bincount(ytr, minlength=len(CLASSES)); rules = []
    for j in range(NADJ, len(PV)):
        rows_ = Xt[:, j].indices
        if len(rows_) < 2: continue
        cnt = np.bincount(ytr[rows_], minlength=len(CLASSES)); k = int(cnt.argmax())
        rules.append({'pattern': PV[j], 'tag': CLASSES[k], 'support': len(rows_) / N, 'count': int(len(rows_)), 'confidence': float(cnt[k] / len(rows_)),
                      'lift': float((cnt[k] / len(rows_)) / (tag_n[k] / N))})
    top_rules = sorted(rules, key=lambda d: -d['count'])[:20]
    rules_summary = {'pair_patterns_with_a_rule': len(rules), 'lift_above_one': float(np.mean([r['lift'] > 1 for r in rules])) if rules else None}

    FEN = TB['fen_C0.5']; cred_mask = SEL; fen_nz = FEN != 0
    jac = float((cred_mask & fen_nz).sum() / max(1, (cred_mask | fen_nz).sum()))
    both = cred_mask | fen_nz; rho = float(spearmanr(np.abs(MU[both]), np.abs(FEN[both])).statistic) if both.sum() > 2 else None
    idx = np.argwhere(SEL); strongest = sorted([{'pattern': PV[j], 'tag': CLASSES[k], 'mean': float(MU[j, k]), 'lo': float(LO[j, k]), 'hi': float(HI[j, k]), 'fen': float(FEN[j, k])} for j, k in idx],
                                               key=lambda d: -abs(d['mean']))[:25]
    agreement = {'credible_cells': int(SEL.sum()), 'fen_nonzero_cells': int(fen_nz.sum()), 'jaccard': jac, 'spearman_abs': rho}

    per_tag = {}
    for t in sorted(set(df.tag)):
        m = (df.tag == t).values; per_tag[t] = {'n': int(m.sum()), 'M1': float((r1[m] <= 3).mean()), 'M3': float((r3[m] <= 3).mean())}

    def fb(s):
        df = SETS[s]; r1_, r3_ = ranks_final[f'{s}|{M1}'], ranks_final[f'{s}|{M3}']; Xs, sc, top3, _ = per_row[s]
        fixed = [r for r in range(len(df)) if r3_[r] == 1 and r1_[r] > 1]; broken = [r for r in range(len(df)) if r1_[r] == 1 and r3_[r] > 1]
        def item(r):
            t = top3[r, 0]; k = cls_ix.get(TAGS[t])
            w = sorted([(PV[j], float(TB['conf'][j, k])) for j in Xs[r].indices], key=lambda x: -x[1])[:3] if k is not None else []
            return {'id': str(df.id.iloc[r]), 'gold': df.tag.iloc[r], 'top1_M3': TAGS[t], 'rank_M1': int(r1_[r]), 'rank_M3': int(r3_[r]), 'strongest_patterns_for_top1': w}
        return {'fixed': len(fixed), 'broken': len(broken), 'fixed_examples': [item(r) for r in fixed[:10]], 'broken_examples': [item(r) for r in broken[:10]],
                'top1_M1': float((r1_ == 1).mean()), 'top1_M3': float((r3_ == 1).mean())}
    out = {'lambda': lam, 'coverage': cov, 'examples': examples, 'worked': worked, 'top_rules': top_rules, 'rules_summary': rules_summary, 'strongest': strongest, 'agreement': agreement,
           'per_tag_pk528': per_tag, 'fixed_broken': {'pk528': fb('pk528'), 'eval_106': fb('eval_106')}}
    jdump(out, P('results', 's12_explanations_and_tables.json'))
    manifest('s12', [P('tables', 'tables_ben.npz'), P('tables', 'tables_r4a.npz'), P('results', 'ranks_final.npz')], [P('results', 's12_explanations_and_tables.json')])


if __name__ == '__main__': main()
