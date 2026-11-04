"""Step 6b: learning curves on train fractions 5k / 10k / 20k / 40k / full for the confidence table, the frequentist elastic net and the Bayesian
elastic net. For each fit: Hits@3 on (a) up to 7,000 rows drawn from the rows it was fitted on and (b) dev, both at the dev-chosen lambda of the
full-train fit; gap = train - dev (converging curves with a small gap mean neither over- nor under-fitting). The Bayesian fits also record credible share,
interval width, R-hat, ESS, divergences and time. Notebook 11 R5b extended with the Bayesian arm and the new fractions.
Flags: --no-fen, --no-ben, --ben-samples N, --ben-warmup N, --max-ben-minutes M (default 150: larger fractions are skipped when the extrapolated time is over budget)."""
from v2lib import *
from s06_mine_weight import arg


def main():
    lex = [l.strip() for l in open(P('protocol', 'lexicon_v2.txt')) if l.strip()]
    D = prep(pd.read_parquet(P('extracted', 'osm_traindev_extracted.parquet'))); tr = D[D.split == 'train'].reset_index(drop=True); dv = D[D.split == 'dev'].reset_index(drop=True)
    meta = np.load(P('tables', 'feat_meta.npz'), allow_pickle=True); CLASSES, PV, NADJ = list(meta['classes']), list(meta['patvocab']), int(meta['n_adj']); P_, K = len(PV), len(CLASSES)
    Xtr, Xdv = sparse.load_npz(P('tables', 'X_train.npz')), sparse.load_npz(P('tables', 'X_dev.npz')); ytr = meta['ytr']
    R = build_ranker(pickle.load(open(P('embeddings', 'nb_v2.pkl'), 'rb')), lex)
    rng = np.random.RandomState(0); order = rng.permutation(len(tr))
    SIM_DV, G_DV = sim_matrix(R, dv), gold_idx(R, dv.tag)
    fr = [n if n is not None and n < len(tr) else len(tr) for n in LC_FRACTIONS_N]; fr = sorted(set(fr))
    if SMOKE: fr = sorted({max(50, len(tr) // 4), max(100, len(tr) // 2), len(tr)})
    warm, samp = int(arg('--ben-warmup', 50 if SMOKE else BEN_WARMUP)), int(arg('--ben-samples', 50 if SMOKE else BEN_SAMPLES)); budget = arg('--max-ben-minutes', 150.0) * 60
    models = {'conf': lambda idx: assoc(Xtr[idx], ytr[idx], K)[0]}
    if '--no-fen' not in sys.argv: models['fen_C0.5'] = lambda idx: fit_fen(Xtr[idx], ytr[idx], P_, K, 0.5)[0]
    LC = {a: [] for a in models}
    if '--no-ben' not in sys.argv: LC['bayes_en'] = []
    tabs = {a: {} for a in LC}; diag = {}; ben_secs = None
    for n in fr:
        idx = np.sort(order[:n])
        for a, fit in models.items(): t0 = time.time(); tabs[a][n] = fit(idx); print(f'{a:9s} n={n:6,} fit {time.time()-t0:.0f}s')
        if 'bayes_en' in LC:
            fb = P('tables', f'ben_lc_{P_}p_{warm}_{samp}_{n}.npz')   # one saved file per fit: a dropped session resumes here
            if os.path.exists(fb):
                z = np.load(fb, allow_pickle=True); tabs['bayes_en'][n] = z['t']; diag[n] = z['d'].item(); ben_secs = ben_secs or diag[n]['seconds']; print(f'bayes_en  n={n:6,} resumed from {fb}'); continue
            est = (ben_secs * n / fr[0]) if ben_secs else 0
            if ben_secs and est > budget: print(f'bayes_en n={n:,} skipped: extrapolated {est/60:.0f} min > budget'); continue
            mu, lo, hi, sel, bd = fit_ben(Xtr[idx], ytr[idx], P_, K, warmup=warm, samples=samp, need_gpu=not SMOKE)
            ben_secs = ben_secs or bd['seconds']; tabs['bayes_en'][n] = (mu * sel).astype(np.float32); diag[n] = bd; np.savez(fb, t=tabs['bayes_en'][n], d=np.array(bd, dtype=object))
            print(f'bayes_en  n={n:6,} fit {bd["seconds"]:.0f}s credible {bd["credible_share"]:.2%} R-hat max {bd["rhat_top200_max"]:.3f} div {bd["divergences"]}')
    full = max(fr)
    lam = {a: pick_lambda(SIM_DV, table_matrix(R, Xdv, tabs[a][full], CLASSES), G_DV)[0] for a in LC if full in tabs[a]}
    for a in LC:
        lam.setdefault(a, lam.get('conf', 0.5))        # a Bayesian fit skipped at full size borrows the confidence lambda
        for n in sorted(tabs[a]):
            idx = np.sort(order[:n]); ev = np.sort(rng.choice(idx, min(7000, len(idx)), replace=False))
            trs = tr.iloc[ev]; SIM_TR, G_TR = sim_matrix(R, trs), gold_idx(R, trs.tag)
            h_tr = (ranks(SIM_TR, table_matrix(R, Xtr[ev], tabs[a][n], CLASSES), G_TR, lam[a]) <= 3).mean()
            rk_dv = ranks(SIM_DV, table_matrix(R, Xdv, tabs[a][n], CLASSES), G_DV, lam[a]); h_dv = (rk_dv <= 3).mean()
            row = {'n_train': n, 'train_hits3': float(h_tr), 'dev_hits3': float(h_dv), 'dev_hits5': float((rk_dv <= 5).mean()), 'gap': float(h_tr - h_dv), 'lambda': lam[a]}
            if a == 'bayes_en': row.update({k: diag[n][k] for k in ('credible_share', 'median_interval_width', 'rhat_top200_max', 'ess_top200_median', 'divergences', 'seconds')})
            LC[a].append(row); print(f'{a:9s} n={n:6,} train H@3 {h_tr:.3f} dev H@3 {h_dv:.3f} gap {h_tr-h_dv:+.3f}')
    out = P('results', 'learning_curves.json'); jdump({'fractions': fr, 'curves': LC, 'lambda': lam}, out)
    try:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(10, 3.8)); sty = {'conf': ('-', 'o'), 'fen_C0.5': ('--', 's'), 'bayes_en': (':', '^')}
        for a, rows in LC.items():
            if not rows: continue
            x = [r['n_train'] for r in rows]
            ax[0].plot(x, [r['dev_hits3'] for r in rows], sty[a][0], marker=sty[a][1], color='black', label=f'{a} dev'); ax[0].plot(x, [r['train_hits3'] for r in rows], sty[a][0], marker=sty[a][1], color='grey', alpha=.6)
            ax[1].plot(x, [r['gap'] for r in rows], sty[a][0], marker=sty[a][1], color='black', label=a)
        ax[0].set_xscale('log'); ax[1].set_xscale('log'); ax[0].set_xlabel('training rows'); ax[1].set_xlabel('training rows'); ax[0].set_ylabel('Hits@3 (black dev, grey train)'); ax[1].set_ylabel('train - dev gap')
        ax[0].legend(frameon=False, fontsize=8); ax[1].legend(frameon=False, fontsize=8); ax[1].axhline(0, color='grey', lw=.5); fig.tight_layout(); fig.savefig(P('results', 'learning_curves.png'), dpi=200)
    except ImportError: print('matplotlib missing: figure skipped')
    manifest('s06b', [P('tables', 'X_train.npz'), P('tables', 'feat_meta.npz')], [out], fractions=fr)


if __name__ == '__main__': main()
