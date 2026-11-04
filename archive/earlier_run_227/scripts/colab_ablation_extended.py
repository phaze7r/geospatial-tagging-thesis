# ============================================================================
# ABLATION on the EXTENDED Pakistan set (528 rows, extractor nouns) -- post-hoc, like the ablation itself.
# Same arms, helpers and lambda rule as 09_ablation_cells.py; every arm must reproduce ablation.json on
# OSM dev and the 106 set before its Pakistan figure is used. The OSM test split is never read.
# F arms (Wikivoyage tables) are not scored: the new rows' sources are in that training text.
# Writes osmfinal/ablation_pk_extended.json only (ablation.json is untouched).
# ============================================================================

# ---------------------------------------------------------------- CELL AX0 --
# 1. extractor output for the 592 rows, in a fresh process (spaCy trf registry), saved next to the set
import os, sys, json, time, pickle, re, gc, subprocess
import numpy as np, pandas as pd
from collections import Counter
from scipy import sparse
from scipy.stats import binomtest
ROOT = '/content/drive/MyDrive/geoproject'; OUT = f'{ROOT}/osmfinal'; RES = f'{ROOT}/pk_extension'
EXT = f'{RES}/pk_extended_extracted.json'
if not os.path.exists(EXT):
    open('/content/ext_dump.py', 'w').write(r'''
import json, sys, spacy
ROOT = '/content/drive/MyDrive/geoproject'; sys.path.insert(0, ROOT)
import pipeline_ranker as pr, adjective_extractor as ae
spacy.prefer_gpu(); PI = ae.PlaceInterpreter(model='en_core_web_trf')
X = json.load(open(f'{ROOT}/eval/pk_extended_raw.json'))
ex = pr.extract_rows([r['sentence'] for r in X], PI)
json.dump({r['id']: {k: e[k] for k in ('context_nouns', 'adjectives', 'transaction', 'tag_hints')} for r, e in zip(X, ex)},
          open(f'{ROOT}/pk_extension/pk_extended_extracted.json', 'w'), ensure_ascii=False)
''')
    r = subprocess.run([sys.executable, '/content/ext_dump.py'], capture_output=True, text=True); assert r.returncode == 0, r.stderr[-2000:]
EX = json.load(open(EXT)); print('extractor rows:', len(EX))
sys.path.insert(0, ROOT)
import pipeline_ranker as pr

# 2. restore + gates 1-3 (verbatim from AB0)
D = pd.read_parquet(f'{OUT}/osm_extracted.parquet')
for c in ('adjectives', 'transaction', 'context_nouns'): D[c] = D[c].map(json.loads)
D['adjs'] = D['adjectives'].map(lambda L: sorted({a.lower() for a in L if str(a).isalpha()}))
D['pit']  = D['transaction'].map(lambda L: [it for it in L if it.startswith('amod:')])
tr, dv = D[D.split == 'train'], D[D.split == 'dev']
meta = np.load(f'{OUT}/osm_feat_meta.npz', allow_pickle=True)
PV, CLASSES, NADJ, MIN_SUP = list(meta['patvocab']), list(meta['classes']), int(meta['n_adj']), float(meta['min_support'])
CIX = {c: k for k, c in enumerate(CLASSES)}; K = len(CLASSES)
ytr, ydv = tr.tag.map(CIX).values, dv.tag.map(CIX).values
assert (ytr == meta['ytr']).all() and (ydv == meta['ydv']).all(), 'labels differ from R3'
def _ok(p):
    body = p.split(':', 1)[1] if ':' in p else p
    return all(len(t) > 1 and t.isalnum() for t in body.split('_'))
def mine(train, min_sup):
    n_min = min_sup * len(train)
    c1 = Counter(a for L in train.adjs for a in L); c2 = Counter(p for L in train.pit for p in L)
    fa = sorted(a for a, c in c1.items() if c >= n_min and _ok(a))
    fp = sorted(p for p, c in c2.items() if c >= n_min and _ok(p))
    return fa + fp, len(fa)
def featurize(df, pv, nadj):
    pix = {p: j for j, p in enumerate(pv)}; A, P2 = set(pv[:nadj]), set(pv[nadj:])
    ri, ci = [], []
    for r, row in enumerate(df.itertuples(index=False)):
        seen = {pix[a] for a in row.adjs if a in A} | {pix[p] for p in row.pit if p in P2}
        ri += [r] * len(seen); ci += list(seen)
    return sparse.csr_matrix((np.ones(len(ri), np.float32), (ri, ci)), shape=(len(df), len(pv)))
def assoc(Xt, yt, k):
    Cnt = np.zeros((Xt.shape[1], k)); r_, c_ = Xt.nonzero(); np.add.at(Cnt, (c_, yt[r_]), 1)
    Ntot = Cnt.sum(); rt = Cnt.sum(1, keepdims=True); ct = Cnt.sum(0, keepdims=True)
    conf = np.divide(Cnt, rt, out=np.zeros_like(Cnt), where=rt > 0)
    with np.errstate(divide='ignore', invalid='ignore'):
        lift = (Cnt / Ntot) / ((rt / Ntot) * (ct / Ntot))
    return conf.astype(np.float32), np.where(np.isfinite(lift) & (lift > 1), np.log(lift), 0.0).astype(np.float32)
pv_, nadj_ = mine(tr, MIN_SUP); assert pv_ == PV and nadj_ == NADJ
Xtr, Xdv = featurize(tr, PV, NADJ), featurize(dv, PV, NADJ)
for s, Xs in (('train', Xtr), ('dev', Xdv)): assert (Xs != sparse.load_npz(f'{OUT}/X_{s}.npz')).nnz == 0
T4 = dict(np.load(f'{OUT}/tables_r4a.npz'))
bz = np.load(f'{OUT}/tables_ben.npz'); T4['bayes_en'] = (bz['mean'] * bz['selected']).astype(np.float32)
CONF, LOGLIFT = assoc(Xtr, ytr, K); assert np.allclose(CONF, T4['conf']) and np.allclose(LOGLIFT, T4['loglift'])
print('gates 1-3 passed')

LEX = json.load(open(f'{ROOT}/eval/evalset_106.json'))['lexicon']
WVT = pr.Tables(f'{ROOT}/results_i/i3_elasticnet.npz', f'{ROOT}/results_p/p1_bayesian_en.npz', f'{ROOT}/results_p/p1_feat_meta.npz')
VEC = {'w2v': pickle.load(open(f'{OUT}/w2v_googlenews_osm.pkl', 'rb')), 'numberbatch': pickle.load(open(f'{OUT}/numberbatch_osm.pkl', 'rb'))}
RK = {bb: pr.Ranker(pr.ladder(v), LEX, WVT) for bb, v in VEC.items()}

# 3. query-side vectors for the new nouns (R5-cache recipe, as in colab_score_extended.py S1); tag vectors unchanged
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'gensim>=4.3.3'], check=True)
def parts(s): return [w for w in re.split(r'[\s\-_/]+', s) if w]
need = {p for e in EX.values() for n in e['context_nouns'] for p in [n] + parts(n)}
probe = {bb: {v for s in need for v in pr.variants(s)} - set(VEC[bb]) for bb in VEC}
import gensim.downloader as api
kv = api.load('word2vec-google-news-300'); NEW_W = {p: np.asarray(kv[p], np.float32) for p in probe['w2v'] if p in kv}; del kv; gc.collect()
kv = api.load('conceptnet-numberbatch-17-06-300'); key = lambda p: f'/c/en/{p.lower()}'
NEW_N = {p: np.asarray(kv[key(p)], np.float32) for p in probe['numberbatch'] if key(p) in kv}; del kv; gc.collect()
RK['w2v'].vec = pr.ladder({**VEC['w2v'], **NEW_W}); RK['numberbatch'].vec = pr.ladder({**VEC['numberbatch'], **NEW_N})
print(f'+{len(NEW_W)} w2v / +{len(NEW_N)} numberbatch query vectors')

# 4. helpers (verbatim) and the three sets
def norm_rows(M):
    lo, hi = M.min(1, keepdims=True), M.max(1, keepdims=True)
    return np.where(hi > lo, (M - lo) / (hi - lo + 1e-9), M)
def sim_matrix(R, df, drop_abstract=True, extra=None):
    out = []
    for i, L in enumerate(df.context_nouns):
        terms = [t for t in L if not drop_abstract or t.lower() not in pr.ABSTRACT]
        if extra is not None: terms = terms + list(extra[i])
        out.append(R._norm(R.sim(terms)))
    return np.vstack(out).astype(np.float32)
def table_matrix(R, Xs, M, classes=CLASSES):
    agg = Xs @ M
    S = np.zeros((Xs.shape[0], len(R.TAGS)), np.float32)
    for k, c in enumerate(classes):
        if c in R.IX: S[:, R.IX[c]] = agg[:, k]
    has_ = Xs.getnnz(1) > 0
    S[has_] = norm_rows(S[has_]); S[~has_] = 0.0
    return S
def gold_idx(R, df): return np.array([R.IX.get(t, -1) for t in df.tag])
def ranks(SIM, TBL, g, lam):
    s = SIM if TBL is None or lam == 0 else (1 - lam) * SIM + lam * TBL
    ok = g >= 0; r = np.full(len(g), SIM.shape[1] + 1)
    r[ok] = (s[ok] >= s[np.where(ok)[0], g[ok]][:, None]).sum(1); return r
def mets(r): return {'Hits@1': float((r <= 1).mean()), 'Hits@3': float((r <= 3).mean()), 'nDCG@20': float(np.where(r <= 20, 1 / np.log2(r + 1), 0).mean())}
LAMS = [round(x, 2) for x in np.arange(0.0, 0.85, 0.05)]
def pick(SIM, TBL, g):
    curve = {l: mets(ranks(SIM, TBL, g, l)) for l in LAMS}
    return max(LAMS, key=lambda l: (curve[l]['Hits@3'], curve[l]['nDCG@20']))
def boot(a, b, n=10000, seed=0):
    rs = np.random.RandomState(seed); m = len(a); d = np.empty(n); a = a.astype(float); b = b.astype(float)
    for i in range(n):
        ix = rs.randint(0, m, m); d[i] = a[ix].mean() - b[ix].mean()
    return float(a.mean() - b.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))
def as_df(rows):
    return pd.DataFrame({'context_nouns': [r['context_nouns'] for r in rows], 'tag': [r['gold_tag'] for r in rows],
                         'adjs': [sorted({a.lower() for a in r.get('adjectives', []) if str(a).isalpha()}) for r in rows],
                         'pit': [[it for it in r.get('transaction', []) if it.startswith('amod:')] for r in rows],
                         'adjectives': [r.get('adjectives', []) for r in rows], 'transaction': [r.get('transaction', []) for r in rows]})
ev106 = json.load(open(f'{ROOT}/eval/evalset_106_extracted.json')); ev106 = ev106['rows'] if isinstance(ev106, dict) else ev106
X = json.load(open(f'{ROOT}/eval/pk_extended_raw.json')); cnt = Counter(r['gold_tag'] for r in X)
pkx = [{**r, **{k: EX[r['id']][k] for k in ('context_nouns', 'adjectives', 'transaction')}} for r in X if cnt[r['gold_tag']] >= 3]
assert len(pkx) == 528
SETS = {'osm_dev': dv, 'eval_106': as_df(ev106), 'pk_ext': as_df(pkx)}

ARMS, RANKS, SIMC = {}, {}, {}
def sims(bb, s, mode):
    k = (bb, s, mode)
    if k not in SIMC:
        R, df = RK[bb], SETS[s]
        SIMC[k] = (sim_matrix(R, df, drop_abstract=False) if mode == 'keep_abstract' else
                   sim_matrix(R, df, extra=list(df.adjectives)) if mode == 'naive' else sim_matrix(R, df))
    return SIMC[k]
def osm_table(pv, nadj, M, cols=None):
    def f(R, df):
        Xs = featurize(df, pv, nadj)
        return table_matrix(R, Xs if cols is None else Xs[:, cols], M if cols is None else M[cols])
    return f
def arm(name, bb, mode='nouns', tbl=None, sets=None):
    sets = sets or SETS; R = RK[bb]
    g = {s: gold_idx(R, sets[s]) for s in sets}
    TB = {s: (tbl(R, sets[s]) if tbl else None) for s in sets}
    S = {s: (sims(bb, s, mode) if sets is SETS else sim_matrix(R, sets[s], drop_abstract=(mode != 'keep_abstract'))) for s in sets}
    lam = pick(S['osm_dev'], TB['osm_dev'], g['osm_dev']) if tbl else 0.0
    RANKS[name] = {s: ranks(S[s], TB[s], g[s], lam) for s in sets}
    ARMS[name] = {'backbone': bb, 'similarity': mode, 'lambda': lam, **{s: mets(RANKS[name][s]) for s in sets}}
    print(f'{name:44s} lam {lam:.2f} | ' + ' | '.join(f"{s} H@3 {ARMS[name][s]['Hits@3']:.3f}" for s in sets))
AB = json.load(open(f'{OUT}/ablation.json'))
def gate_arm(name):
    a, b = ARMS[name], AB['arms'][name]
    assert a['lambda'] == b['lambda'], (name, 'lambda')
    for s in ('osm_dev', 'eval_106'): assert abs(a[s]['Hits@3'] - b[s]['Hits@3']) < 1e-9, (name, s)

# ---------------------------------------------------------------- CELL AX1 --
# A, B and C arms, each gated against ablation.json on dev and the 106 set
arm('final: numberbatch + conf (657)', 'numberbatch', tbl=osm_table(PV, NADJ, T4['conf']))
arm('base Alg.2 + abstract removal (w2v)', 'w2v')
cols_adj, cols_pair = np.arange(NADJ), np.arange(NADJ, len(PV))
arm('A0 base Alg.2, abstract nouns kept (w2v)',        'w2v', mode='keep_abstract')
arm('A2 + adjectives appended to the query (w2v)',     'w2v', mode='naive')
arm('A3 + adjective patterns only, conf (w2v)',        'w2v', tbl=osm_table(PV, NADJ, T4['conf'], cols_adj))
arm('A4 + adjective-noun pairs = 657 patterns (w2v)',  'w2v', tbl=osm_table(PV, NADJ, T4['conf']))
arm('B1 final, adjective patterns only',               'numberbatch', tbl=osm_table(PV, NADJ, T4['conf'], cols_adj))
arm('B2 final, pair patterns only',                    'numberbatch', tbl=osm_table(PV, NADJ, T4['conf'], cols_pair))
arm('B3 final, log-lift instead of confidence',        'numberbatch', tbl=osm_table(PV, NADJ, T4['loglift']))
arm('B4 final, frequentist EN (C=0.5)',                'numberbatch', tbl=osm_table(PV, NADJ, T4['fen_C0.5']))
arm('B5 final, Bayesian EN',                           'numberbatch', tbl=osm_table(PV, NADJ, T4['bayes_en']))
arm('B6 final, nouns only (no table)',                 'numberbatch')
arm('B7 final, adjectives appended instead of table',  'numberbatch', mode='naive')
SUPPORT = {}
for ms in (0.002, 0.001, 0.0005, 0.0002, 0.0001):
    pv_s, nadj_s = mine(tr, ms); conf_s, _ = assoc(featurize(tr, pv_s, nadj_s), ytr, K)
    name = f'C support {ms:g}'; arm(name, 'numberbatch', tbl=osm_table(pv_s, nadj_s, conf_s))
    SUPPORT[name] = {'min_support': ms, 'patterns': len(pv_s), 'adjectives': nadj_s, 'pairs': len(pv_s) - nadj_s}
for name in ARMS: gate_arm(name)
print(f'gate: all {len(ARMS)} arms reproduce ablation.json on OSM dev and the 106 set exactly')

# ---------------------------------------------------------------- CELL AX2 --
# D small parser: OSM rows and the extended rows get nouns, adjectives and pairs from en_core_web_sm
# (the extended rows have no supplied nouns, so all three come from the parser); 106 rows as in AB3.
if subprocess.run([sys.executable, '-c', 'import en_core_web_sm'], capture_output=True).returncode:
    subprocess.run([sys.executable, '-m', 'spacy', 'download', 'en_core_web_sm', '-q'], check=True)
import spacy, adjective_extractor as ae
I_sm = ae.PlaceInterpreter(model='en_core_web_sm')
sub = D[D.split.isin(['train', 'dev'])].reset_index(drop=True)
t0 = time.time(); rows_sm = pr.extract_rows(list(sub.text), I_sm, batch_size=256); print(f'small parser: {len(rows_sm):,} OSM texts in {time.time()-t0:.0f}s')
SM = pd.DataFrame({'split': sub.split, 'tag': sub.tag, 'context_nouns': [r['context_nouns'] for r in rows_sm],
                   'adjectives': [r['adjectives'] for r in rows_sm], 'transaction': [r['transaction'] for r in rows_sm]})
SM['adjs'] = SM['adjectives'].map(lambda L: sorted({a.lower() for a in L if str(a).isalpha()}))
SM['pit']  = SM['transaction'].map(lambda L: [it for it in L if it.startswith('amod:')])
sm_tr, sm_dv = SM[SM.split == 'train'], SM[SM.split == 'dev']
pv_sm, nadj_sm = mine(sm_tr, MIN_SUP); conf_sm, _ = assoc(featurize(sm_tr, pv_sm, nadj_sm), sm_tr.tag.map(CIX).values, K)
ex106 = pr.extract_rows([r.get('sentence') or r.get('text') for r in ev106], I_sm)
expk = pr.extract_rows([r['sentence'] for r in pkx], I_sm)
SETS_SM = {'osm_dev': sm_dv,
           'eval_106': as_df([{**r, 'adjectives': e['adjectives'], 'transaction': e['transaction']} for r, e in zip(ev106, ex106)]),
           'pk_ext': as_df([{**r, 'context_nouns': e['context_nouns'], 'adjectives': e['adjectives'], 'transaction': e['transaction']} for r, e in zip(pkx, expk)])}
arm('D final, small parser (en_core_web_sm)', 'numberbatch', tbl=osm_table(pv_sm, nadj_sm, conf_sm), sets=SETS_SM)
gate_arm('D final, small parser (en_core_web_sm)')
print('gate: D reproduces ablation.json on dev and the 106 set')

# ---------------------------------------------------------------- CELL AX3 --
# comparisons on pk_ext (same pairs as AB6 minus the F corpus pairs), Holm within this set's family
F_, A1 = 'final: numberbatch + conf (657)', 'base Alg.2 + abstract removal (w2v)'
PAIRS = [('A1 abstract-noun removal',         A1, 'A0 base Alg.2, abstract nouns kept (w2v)'),
         ('A2 adjectives appended to query',  'A2 + adjectives appended to the query (w2v)', A1),
         ('A3 adjective patterns (table)',    'A3 + adjective patterns only, conf (w2v)', A1),
         ('A4 + pair patterns',               'A4 + adjective-noun pairs = 657 patterns (w2v)', 'A3 + adjective patterns only, conf (w2v)'),
         ('A5 Numberbatch backbone',          F_, 'A4 + adjective-noun pairs = 657 patterns (w2v)'),
         ('A total: final vs base Alg.2',     F_, 'A0 base Alg.2, abstract nouns kept (w2v)'),
         ('B1 drop pair patterns',            'B1 final, adjective patterns only', F_),
         ('B2 drop adjective patterns',       'B2 final, pair patterns only', F_),
         ('B3 log-lift weighting',            'B3 final, log-lift instead of confidence', F_),
         ('B4 frequentist EN selection',      'B4 final, frequentist EN (C=0.5)', F_),
         ('B5 Bayesian EN selection',         'B5 final, Bayesian EN', F_),
         ('B6 drop the table',                'B6 final, nouns only (no table)', F_),
         ('B7 naive adjectives, no table',    'B7 final, adjectives appended instead of table', F_),
         ('D small parser',                   'D final, small parser (en_core_web_sm)', F_)]
PAIRS += [(f'C {n[2:]} vs 0.0005', n, 'C support 0.0005') for n in SUPPORT if n != 'C support 0.0005']
CMP = []
for label, a, b in PAIRS:
    ha, hb = RANKS[a]['pk_ext'] <= 3, RANKS[b]['pk_ext'] <= 3
    d, lo, hi = boot(ha, hb); n01, n10 = int((~ha & hb).sum()), int((ha & ~hb).sum())
    CMP.append({'comparison': label, 'set': 'pk_ext', 'a': a, 'b': b, 'delta_hits3': d, 'ci95': [lo, hi], 'a_only': n10, 'b_only': n01,
                'p': float(binomtest(min(n01, n10), n01 + n10, 0.5).pvalue) if n01 + n10 else 1.0})
ps = np.array([c['p'] for c in CMP]); o = np.argsort(ps); m_ = len(ps); adj = np.empty(m_); run = 0.0
for rank_, i in enumerate(o): run = max(run, min(1.0, (m_ - rank_) * ps[i])); adj[i] = run
for c, pa in zip(CMP, adj): c['p_holm'] = float(pa)
for c in CMP: print(f"{c['comparison']:34s} dH@3 {c['delta_hits3']:+.3f} [{c['ci95'][0]:+.3f},{c['ci95'][1]:+.3f}] p_holm {c['p_holm']:.4f}")
json.dump({'status': 'post-hoc ablation on the extended Pakistan set (528 rows, extractor nouns); every arm reproduces ablation.json on OSM dev and the 106 set',
           'lambda_rule': 'per arm, chosen on OSM dev (as in ablation.json), applied unchanged to pk_ext',
           'sets': {s: len(v) for s, v in SETS.items()}, 'arms': {n: {'lambda': a['lambda'], 'pk_ext': a['pk_ext']} for n, a in ARMS.items()},
           'support_sensitivity': SUPPORT, 'comparisons': CMP, 'holm_family_size': m_, 'extra_query_vectors': {'w2v': len(NEW_W), 'numberbatch': len(NEW_N)},
           'not_scored': 'F arms (Wikivoyage tables): the extended rows\' source listings are in that training text'},
          open(f'{OUT}/ablation_pk_extended.json', 'w'), indent=1, default=str)
print('wrote', f'{OUT}/ablation_pk_extended.json')
