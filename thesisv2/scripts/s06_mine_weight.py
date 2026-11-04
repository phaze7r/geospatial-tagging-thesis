"""Step 6a: mining and weighting on TRAIN only. Guided FP-Growth patterns (support rule), pattern x tag tables: confidence and log-lift, frequentist
elastic net, Bayesian elastic net (NUTS, scale mixture). Copy of notebook 11 R3, R4a, R4b with the new vocabulary.
Flags: --min-support X (default config.MIN_SUPPORT), --fen-grid (fit C in 0.1, 0.5, 2.0; default only 0.5), --skip-ben, --ben-only (reuse saved X and tables),
--ben-samples N / --ben-warmup N (shorter run for timing). GPU needed for the Bayesian fit (not in --smoke)."""
from v2lib import *


def arg(name, default, cast=float):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def main():
    ms = arg('--min-support', 0.01 if SMOKE else MIN_SUPPORT)     # smoke: few patterns so the CPU Bayesian fit stays short
    D = prep(pd.read_parquet(P('extracted', 'osm_traindev_extracted.parquet'))); tr = D[D.split == 'train']; dv = D[D.split == 'dev']
    CLASSES = sorted(tr.tag.unique()); CIX = {c: k for k, c in enumerate(CLASSES)}; K = len(CLASSES)
    pv, nadj = mine(tr, ms); P_ = len(pv)
    print(f'MIN_SUPPORT {ms} (>= {ms*len(tr):.0f} of {len(tr):,} train rows): {nadj} adjectives + {P_-nadj} pairs = {P_} patterns | {K} classes | {tr.tag.nunique()} tags in train')
    X = {'train': featurize(tr, pv, nadj), 'dev': featurize(dv, pv, nadj)}
    y = {'train': tr.tag.map(CIX).values, 'dev': dv.tag.map(CIX).fillna(-1).astype(int).values}
    for s in X:
        sparse.save_npz(P('tables', f'X_{s}.npz'), X[s]); print(f'{s:5s} {X[s].shape} rows with >=1 pattern {(X[s].getnnz(1) > 0).mean():.1%}')
    np.savez(P('tables', 'feat_meta.npz'), patvocab=np.array(pv), classes=np.array(CLASSES), n_adj=nadj, ytr=y['train'], ydv=y['dev'], min_support=ms)
    diag = {'min_support': ms, 'patterns': P_, 'adjectives': nadj, 'pairs': P_ - nadj, 'classes': K, 'train_rows': len(tr), 'dev_rows': len(dv),
            'rows_with_pattern': {s: float((X[s].getnnz(1) > 0).mean()) for s in X}}
    if '--ben-only' in sys.argv:
        T4 = dict(np.load(P('tables', 'tables_r4a.npz')))
        assert T4['conf'].shape == (P_, K), f'--ben-only needs the tables of the same --min-support (saved {T4["conf"].shape}, now {(P_, K)}); rerun without --ben-only'
    else:
        conf, loglift = assoc(X['train'], y['train'], K); T4 = {'conf': conf, 'loglift': loglift}; diag['fen'] = {}
        for C in (FEN_C_GRID if '--fen-grid' in sys.argv else (0.5,)):
            t0 = time.time(); T4[f'fen_C{C}'], st = fit_fen(X['train'], y['train'], P_, K, C); st['seconds'] = time.time() - t0; diag['fen'][str(C)] = st
            print(f'frequentist EN C={C}: {st["seconds"]:.0f}s, {st["iters"]} iters, nonzero {st["nonzero"]:.1%}')
        np.savez(P('tables', 'tables_r4a.npz'), **T4)
    if '--skip-ben' not in sys.argv:
        warm, samp = int(arg('--ben-warmup', 50 if SMOKE else BEN_WARMUP)), int(arg('--ben-samples', 50 if SMOKE else BEN_SAMPLES))
        mu, lo, hi, sel, bd = fit_ben(X['train'], y['train'], P_, K, warmup=warm, samples=samp, need_gpu=not SMOKE)
        print(f'NUTS {bd["rows"]:,} rows x {P_} x {K}: {bd["seconds"]:.0f}s | divergences {bd["divergences"]} | R-hat max {bd["rhat_top200_max"]:.3f} | ESS median {bd["ess_top200_median"]:.0f} | credible {bd["credible_share"]:.2%} | {"PASS" if bd["pass_p17b"] else "FAIL"}')
        np.savez(P('tables', 'tables_ben.npz'), mean=mu, hdi_lo=lo, hdi_hi=hi, selected=sel, patvocab=np.array(pv), classes=np.array(CLASSES)); diag['ben'] = bd
    jdump(diag, P('results', 's06_fit_diagnostics.json'))
    outs = [P('tables', f) for f in ('feat_meta.npz', 'X_train.npz', 'X_dev.npz', 'tables_r4a.npz', 'tables_ben.npz') if os.path.exists(P('tables', f))] + [P('results', 's06_fit_diagnostics.json')]
    manifest('s06', [P('extracted', 'osm_traindev_extracted.parquet')], outs, **{k: v for k, v in diag.items() if k != 'fen'})


if __name__ == '__main__': main()
