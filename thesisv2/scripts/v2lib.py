"""Shared helpers of thesisv2. Function bodies are copied from the finished notebooks; the source cell is named in each comment
(N11 = notebook 11 final run, N12 = notebook 12 ablation, PKS = pk_extension/colab_score_extended.py). Only the vocabulary,
paths and the sealed test handling are new."""
import os, re, sys, json, time, gc, pickle, subprocess, importlib.util
from collections import Counter
import numpy as np, pandas as pd
from scipy import sparse
from scipy.stats import binomtest
from common import *
from config import *
import pipeline_ranker as pr


# ------------------------------------------------------------------ tags, mapping
def get_lid():
    """py3langid across versions: 0.4.0 (thesis, Colab) has from_model_file(MODEL_FILE); 0.2.x has a module-level IDENTIFIER with the same classify()"""
    import py3langid.langid as L
    if hasattr(L.LanguageIdentifier, 'from_model_file'): return L.LanguageIdentifier.from_model_file(L.MODEL_FILE, norm_probs=True)
    return L.LanguageIdentifier.from_pickled_model(L.MODEL_FILE, norm_probs=True)


def norm_tag(v): return str(v).lower().replace('_', '-').replace(' ', '-')


def tag_of(key, value, religion=None):
    """(key, value[, religion]) -> tag name. N11 R1b rules (spelling variants, religion composite)."""
    if not isinstance(value, str): return None
    if key == 'amenity' and value == 'place_of_worship': return RELIGION.get(religion)
    return TAG_SPELLING.get((key, value)) or norm_tag(value)


def eff_value(key, value, religion):
    """place_of_worship is split by religion so that mosque, church and temple get their own counts and mapping rows"""
    return f'place_of_worship[{religion}]' if (key == 'amenity' and value == 'place_of_worship') else value


# ------------------------------------------------------------------ ranker with the stub tables (no old Wikivoyage table is loaded)
class StubTables:
    EN_CLS, PCLS = [], []


def build_ranker(vec_dict, lexicon): return pr.Ranker(pr.ladder(vec_dict), list(lexicon), StubTables())


# ------------------------------------------------------------------ scoring (N11 R5a, R7; N12 AB0)
def norm_rows(M):
    lo, hi = M.min(1, keepdims=True), M.max(1, keepdims=True)
    return np.where(hi > lo, (M - lo) / (hi - lo + 1e-9), M)


def sim_matrix(R, df, drop_abstract=True, naive=False):
    """M1 = nouns only (naive=False). M2 = nouns plus the extractor adjectives appended to the query (naive=True), N12 arm A2/B7."""
    out = []
    extra = list(df.adjectives) if naive else [[]] * len(df)
    for L, ex in zip(df.context_nouns, extra):
        terms = [t for t in L if not drop_abstract or t.lower() not in pr.ABSTRACT] + list(ex)
        out.append(R._norm(R.sim(terms)))
    return np.vstack(out).astype(np.float32)


def table_matrix(R, Xs, M, classes):
    agg = Xs @ M
    S = np.zeros((Xs.shape[0], len(R.TAGS)), np.float32)
    for k, c in enumerate(classes):
        if c in R.IX: S[:, R.IX[c]] = agg[:, k]
    has_ = Xs.getnnz(1) > 0
    S[has_] = norm_rows(S[has_]); S[~has_] = 0.0
    return S


def gold_idx(R, tags): return np.array([R.IX.get(t, -1) for t in tags])


def ranks(SIM, TBL, g, lam):
    """worst-case ties: rank = number of tags with score >= gold score; gold outside the vocabulary -> worst rank (N11 R7)"""
    s = SIM if TBL is None or lam == 0 else (1 - lam) * SIM + lam * TBL
    ok = g >= 0; r = np.full(len(g), SIM.shape[1] + 1)
    r[ok] = (s[ok] >= s[np.where(ok)[0], g[ok]][:, None]).sum(1); return r


def mets(r):
    r = np.asarray(r)
    o = {'n': int(len(r))}
    for k in (1, 2, 3, 5, 10, 20): o[f'Hits@{k}'] = float((r <= k).mean())
    o['nDCG@20'] = float(np.where(r <= 20, 1 / np.log2(r + 1), 0).mean()); o['MedR'] = float(np.median(r))
    return o


def pick_lambda(SIM, TBL, g, lams=LAMS):
    """N12 pick: Hits@3, then nDCG@20"""
    curve = {l: mets(ranks(SIM, TBL, g, l)) for l in lams}
    return max(lams, key=lambda l: (curve[l]['Hits@3'], curve[l]['nDCG@20'])), curve


def boot(a, b, n=10000, seed=0):
    rs = np.random.RandomState(seed); m = len(a); d = np.empty(n); a = a.astype(float); b = b.astype(float)
    for i in range(n):
        ix = rs.randint(0, m, m); d[i] = a[ix].mean() - b[ix].mean()
    return float(a.mean() - b.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def compare(ha, hb):
    """paired bootstrap CI and exact McNemar for two boolean hit vectors (PKS S4)"""
    d, lo, hi = boot(ha, hb); ao, bo = int((ha & ~hb).sum()), int((hb & ~ha).sum())
    p = binomtest(min(ao, bo), ao + bo, 0.5).pvalue if ao + bo else 1.0
    return {'delta_hits3': d, 'ci95': [lo, hi], 'a_only': ao, 'b_only': bo, 'p': float(p)}


def holm(ps):
    o = np.argsort(ps); adj = np.empty(len(ps)); run = 0.0
    for k, i in enumerate(o): run = max(run, (len(ps) - k) * ps[i]); adj[i] = min(1.0, run)
    return adj.tolist()


# ------------------------------------------------------------------ patterns (N11 R3, R4a; N12 AB0)
def prep(D):
    """json columns -> lists; adjs = alphabetic lowercase adjectives, pit = adjective-noun pair items (P1.1 rules)"""
    for c in ('adjectives', 'transaction', 'context_nouns'):
        if len(D) and isinstance(D[c].iloc[0], str): D[c] = D[c].map(json.loads)
    D['adjs'] = D['adjectives'].map(lambda L: sorted({a.lower() for a in L if str(a).isalpha()}))
    D['pit'] = D['transaction'].map(lambda L: [it for it in L if it.startswith('amod:')])
    return D


def _ok(p):
    body = p.split(':', 1)[1] if ':' in p else p
    return all(len(t) > 1 and t.isalnum() for t in body.split('_'))


def mine(train, min_sup):
    """guided frequent patterns: adjective 1-itemsets and adjective-noun 2-itemsets above min_sup (support is anti-monotone)"""
    n_min = min_sup * len(train)
    c1 = Counter(a for L in train.adjs for a in L); c2 = Counter(p for L in train.pit for p in L)
    fa = sorted(a for a, c in c1.items() if c >= n_min and _ok(a)); fp = sorted(p for p, c in c2.items() if c >= n_min and _ok(p))
    return fa + fp, len(fa)


def featurize(df, pv, nadj):
    pix = {p: j for j, p in enumerate(pv)}; A, P2 = set(pv[:nadj]), set(pv[nadj:])
    ri, ci = [], []
    for r, row in enumerate(df.itertuples(index=False)):
        seen = {pix[a] for a in row.adjs if a in A} | {pix[p] for p in row.pit if p in P2}
        ri += [r] * len(seen); ci += list(seen)
    return sparse.csr_matrix((np.ones(len(ri), np.float32), (ri, ci)), shape=(len(df), len(pv)))


def assoc(X, y, K):
    """confidence P(tag | pattern) and log-lift tables, patterns x classes (N11 R4a)"""
    Cnt = np.zeros((X.shape[1], K)); r_, c_ = X.nonzero(); np.add.at(Cnt, (c_, y[r_]), 1)
    Ntot = Cnt.sum(); rt = Cnt.sum(1, keepdims=True); ct = Cnt.sum(0, keepdims=True)
    conf = np.divide(Cnt, rt, out=np.zeros_like(Cnt), where=rt > 0)
    with np.errstate(divide='ignore', invalid='ignore'): lift = (Cnt / Ntot) / ((rt / Ntot) * (ct / Ntot))
    return conf.astype(np.float32), np.where(np.isfinite(lift) & (lift > 1), np.log(lift), 0.0).astype(np.float32)


def fit_fen(X, y, P, K, C=0.5):
    from sklearn.linear_model import LogisticRegression
    m = LogisticRegression(penalty='elasticnet', solver='saga', l1_ratio=0.5, C=C, max_iter=200, tol=1e-3, n_jobs=-1).fit(X, y)
    coef = np.zeros((P, K), np.float32); coef[:, m.classes_] = m.coef_.T
    return coef, {'iters': int(np.max(m.n_iter_)), 'nonzero': float((m.coef_ != 0).mean())}


def fit_ben(X, y, P, K, warmup=BEN_WARMUP, samples=BEN_SAMPLES, chains=BEN_CHAINS, seed=0, need_gpu=True):
    """Bayesian elastic net, scale-mixture model, NUTS (N11 R4b, unchanged). Fitted on the rows that carry at least one pattern.
    Returns mean, 94% HDI-like percentile bounds, selected mask and diagnostics. Memory: 3 sites x chains x samples x P x K floats on the device."""
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', 'numpyro', 'multipledispatch'], check=False)
    import jax, jax.numpy as jnp, numpyro, numpyro.distributions as dist
    from numpyro.infer import MCMC, NUTS
    from numpyro.diagnostics import gelman_rubin, effective_sample_size
    if need_gpu: assert jax.default_backend() == 'gpu', f'jax backend is {jax.default_backend()}; use a GPU runtime (or --smoke)'
    has = np.where(X.getnnz(1) > 0)[0]
    Xb = jnp.asarray(X[has].toarray(), jnp.float32); yb = jnp.asarray(y[has]); Nb = len(has)

    def model_sm(X_, y_=None):
        b = numpyro.sample('b', dist.HalfNormal(1.0))
        tau2 = numpyro.sample('tau2', dist.Exponential(1.0 / (2.0 * b ** 2)).expand([P, K]).to_event(2))
        z = numpyro.sample('z', dist.Normal(0.0, 1.0).expand([P, K]).to_event(2))
        beta = numpyro.deterministic('beta', z * jnp.sqrt(tau2))
        numpyro.factor('ridge', -BEN_LAM2 * jnp.sum(beta ** 2))
        alpha = numpyro.sample('alpha', dist.Normal(0.0, 2.0).expand([K]).to_event(1))
        with numpyro.plate('n', X_.shape[0]):
            numpyro.sample('y', dist.Categorical(logits=X_ @ beta + alpha), obs=y_)
    t0 = time.time()
    nblk = 4 if samples % 4 == 0 else 1               # same chains, draws taken in blocks and moved to host: device memory / nblk (1,000 draws ran out of GPU memory in one piece)
    mcmc = MCMC(NUTS(model_sm, max_tree_depth=10, target_accept_prob=0.8), num_warmup=warmup, num_samples=samples // nblk, num_chains=chains,
                chain_method='vectorized', progress_bar=False)
    Bs, bsc, div, steps = [], [], 0, []
    for i in range(nblk):
        if i: mcmc.post_warmup_state = mcmc.last_state      # continue the same chains, no new warmup
        mcmc.run(mcmc.post_warmup_state.rng_key if i else jax.random.PRNGKey(seed), Xb, yb, extra_fields=('diverging', 'num_steps'))
        S = mcmc.get_samples(group_by_chain=True); ex = mcmc.get_extra_fields()
        Bs.append(np.asarray(S['beta'])); bsc.append(float(np.asarray(S['b']).mean())); div += int(np.asarray(ex['diverging']).sum()); steps.append(float(np.asarray(ex['num_steps']).mean()))
        del S; gc.collect()
    secs = time.time() - t0; B = np.concatenate(Bs, axis=1) if nblk > 1 else Bs[0]; bscale = float(np.mean(bsc)); del Bs; gc.collect()
    top = np.argsort(-np.abs(B.mean((0, 1))).max(1))[:200]
    rh = np.asarray(gelman_rubin(B[:, :, top, :])) if chains > 1 else np.zeros(1); ess = np.asarray(effective_sample_size(B[:, :, top, :]))
    Bf = B.reshape(-1, P, K); mu = Bf.mean(0)
    lo = np.empty((P, K), np.float32); hi = np.empty((P, K), np.float32)
    for a in range(0, K, 50):                         # chunked percentiles: the full array would need several copies in memory
        blk = Bf[:, :, a:a + 50]; lo[:, a:a + 50] = np.percentile(blk, 3, 0); hi[:, a:a + 50] = np.percentile(blk, 97, 0)
    sel = (lo > 0) | (hi < 0)
    diag = {'rows': int(Nb), 'seconds': secs, 'divergences': div, 'mean_leapfrog': float(np.mean(steps)), 'b_mean': bscale,
            'rhat_top200_median': float(np.median(rh)), 'rhat_top200_max': float(rh.max()), 'ess_top200_median': float(np.median(ess)),
            'credible_share': float(sel.mean()), 'patterns_with_credible_tag': int(sel.any(1).sum()),
            'median_interval_width': float(np.median((hi - lo)[sel])) if sel.any() else None,
            'pass_p17b': bool(div == 0 and rh.max() <= 1.05), 'chains': chains, 'warmup': warmup, 'samples': samples}
    return mu.astype(np.float32), lo, hi, sel, diag


# ------------------------------------------------------------------ extraction and embeddings
def ensure_spacy_model(model='en_core_web_trf'):
    """install the model BEFORE spaCy is imported, then restart this process (spaCy registers factories at import; N11 R2-setup gotcha)"""
    if importlib.util.find_spec(model) is None:
        subprocess.run([sys.executable, '-m', 'spacy', 'download', model], check=True)
        os.execv(sys.executable, [sys.executable] + sys.argv)


_I = {}


def extract(texts, model='en_core_web_trf', batch=256):
    import spacy
    try: spacy.prefer_gpu()
    except Exception: pass
    import adjective_extractor as ae
    if model not in _I: _I[model] = ae.PlaceInterpreter(model=model)
    return pr.extract_rows(list(texts), _I[model], batch_size=batch)


def _first_existing(paths):
    for p in paths:
        if p and os.path.exists(p): return p
    return None


def load_vec_cache(backbone):
    """thesisv2 cache if it exists, else the old finished-work cache (read-only), else an empty dict (smoke/local override via THESISV2_VEC_*)"""
    name = {'w2v': 'w2v_v2.pkl', 'numberbatch': 'nb_v2.pkl'}[backbone]
    env = os.environ.get('THESISV2_VEC_' + backbone.upper())
    old = OLD_W2V_CACHES if backbone == 'w2v' else OLD_NB_CACHES
    p = _first_existing([env, P('embeddings', name)] + [os.path.join(OLD, o) for o in old] if OLD else [env, P('embeddings', name)])
    return pickle.load(open(p, 'rb')) if p else {}, p


def extend_vectors(VEC, backbone, strings):
    """add vectors for strings the cache lacks, with the N11 R5-cache recipe (gensim GoogleNews / ConceptNet Numberbatch)."""
    need = set(strings)
    for s in list(need): need.update(pr.parts(s))
    probe = {v for s in need for v in pr.variants(s)} - set(VEC)
    if not probe or SMOKE: return VEC, 0
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'gensim>=4.3.3'], check=True)
    import gensim.downloader as api
    if backbone == 'w2v':
        kv = api.load('word2vec-google-news-300'); new = {p: np.asarray(kv[p], np.float32) for p in probe if p in kv}
    else:
        kv = api.load('conceptnet-numberbatch-17-06-300'); key = lambda p: f'/c/en/{p.lower()}'
        new = {p: np.asarray(kv[key(p)], np.float32) for p in probe if key(p) in kv}
    del kv; gc.collect()
    return {**VEC, **new}, len(new)


def nouns_of(D):
    return {n for L in D.context_nouns for n in L}


# ------------------------------------------------------------------ evaluation sets (N11 R7 as_df; PKS S2)
def as_df(rows, tag_key='gold_tag'):
    return pd.DataFrame({'context_nouns': [r['context_nouns'] for r in rows], 'tag': [r[tag_key] for r in rows],
                         'adjs': [sorted({a.lower() for a in r.get('adjectives', []) if str(a).isalpha()}) for r in rows],
                         'pit': [[it for it in r.get('transaction', []) if it.startswith('amod:')] for r in rows],
                         'adjectives': [r.get('adjectives', []) for r in rows], 'transaction': [r.get('transaction', []) for r in rows],
                         'id': [r.get('id', r.get('row', i)) for i, r in enumerate(rows)]})


def load_106():
    d = jload(os.path.join(INPUTS, 'evalset_106.json')); return d['rows'], d['lexicon']


def load_pk():
    X = jload(os.path.join(INPUTS, 'pk_extended_raw.json')); return X, jload(os.path.join(INPUTS, 'pk528_ids.json')), \
        jload(os.path.join(INPUTS, 'pk_subset_ids.json')), jload(os.path.join(INPUTS, 'pk_translations.json'))


def resolve_gold(lex, aliases):
    """gold tags of the 106 set and the Pakistan set that do not resolve (directly or through an alias) into the vocabulary"""
    r106, _ = load_106(); X, _, _, _ = load_pk(); L = set(lex)
    return sorted({r['gold_tag'] for r in r106 + X if r['gold_tag'] not in L and aliases.get(r['gold_tag']) not in L})


def alias_map():
    """alias -> canonical tag, from the signed-off alias file (empty if none)"""
    p = P('protocol', 'lexicon_v2_aliases.csv')
    if not os.path.exists(p): return {}
    A = pd.read_csv(p); A = A[A['kind'] == 'merge'] if 'kind' in A else A
    return dict(zip(A['alias'], A['canonical']))


# ------------------------------------------------------------------ the arm runner (N12 AB0: arm, sims, pick), one place for dev, ablation and test sets
class Runner:
    """sets must contain 'osm_dev'; lambda is chosen on dev for every arm and applied unchanged to the other sets (N12 lambda_rule)."""

    def __init__(self, RK, sets, PV, NADJ, CLASSES, lam_fixed=None):
        self.RK, self.SETS, self.PV, self.NADJ, self.CLASSES = RK, sets, PV, NADJ, CLASSES
        self.LAM_FIXED = lam_fixed or {}                       # step 8 passes the lambdas frozen in the protocol
        self.ARMS, self.RANKS, self.SIMC = {}, {}, {}

    def sims(self, bb, s, mode):
        k = (bb, s, mode)
        if k not in self.SIMC:
            R, df = self.RK[bb], self.SETS[s]
            self.SIMC[k] = sim_matrix(R, df, drop_abstract=(mode != 'keep_abstract'), naive=(mode == 'naive'))
        return self.SIMC[k]

    def table(self, pv, nadj, M, cols=None):
        def f(R, df):
            Xs = featurize(df, pv, nadj)
            return table_matrix(R, Xs if cols is None else Xs[:, cols], M if cols is None else M[cols], self.CLASSES)
        return f

    def arm(self, name, bb, mode='nouns', tbl=None, sets=None, verbose=True):
        sets = sets or self.SETS; R = self.RK[bb]
        g = {s: gold_idx(R, sets[s].tag) for s in sets}
        TB = {s: (tbl(R, sets[s]) if tbl else None) for s in sets}
        S = {s: (self.sims(bb, s, mode) if sets is self.SETS else
                 sim_matrix(R, sets[s], drop_abstract=(mode != 'keep_abstract'), naive=(mode == 'naive'))) for s in sets}
        lam = (self.LAM_FIXED[name] if name in self.LAM_FIXED else pick_lambda(S['osm_dev'], TB['osm_dev'], g['osm_dev'])[0]) if tbl else 0.0
        self.RANKS[name] = {s: ranks(S[s], TB[s], g[s], lam) for s in sets}
        self.ARMS[name] = {'backbone': bb, 'similarity': mode, 'lambda': lam, **{s: mets(self.RANKS[name][s]) for s in sets}}
        if verbose: print(f'{name:48s} lam {lam:.2f} | ' + ' | '.join(f"{s} H@3 {self.ARMS[name][s]['Hits@3']:.3f} H@5 {self.ARMS[name][s]['Hits@5']:.3f}" for s in sets))
        return self.ARMS[name]


# ------------------------------------------------------------------ ablation arms (N12 AB1; cumulative A-sequence and one-change B-swaps), shared by step 7 (dev) and step 8 (post hoc sets)
def ablation_arms(run, T, verbose=True):
    """T = {'PV','NADJ','tables': {'conf','loglift','fen_C0.5','bayes_en'}}. Arm names follow notebook 12 so the thesis tables keep their labels."""
    PV, NADJ, TB = T['PV'], T['NADJ'], T['tables']
    ca, cp = np.arange(NADJ), np.arange(NADJ, len(PV)); tb = run.table
    run.arm('final: numberbatch + conf', 'numberbatch', tbl=tb(PV, NADJ, TB['conf']), verbose=verbose)
    run.arm('base Alg.2 + abstract removal (w2v)', 'w2v', verbose=verbose)
    run.arm('A0 base Alg.2, abstract nouns kept (w2v)', 'w2v', mode='keep_abstract', verbose=verbose)
    run.arm('A2 + adjectives appended to the query (w2v)', 'w2v', mode='naive', verbose=verbose)
    run.arm('A3 + adjective patterns only, conf (w2v)', 'w2v', tbl=tb(PV, NADJ, TB['conf'], ca), verbose=verbose)
    run.arm('A4 + adjective-noun pairs = all patterns (w2v)', 'w2v', tbl=tb(PV, NADJ, TB['conf']), verbose=verbose)
    run.arm('B1 final, adjective patterns only', 'numberbatch', tbl=tb(PV, NADJ, TB['conf'], ca), verbose=verbose)
    run.arm('B2 final, pair patterns only', 'numberbatch', tbl=tb(PV, NADJ, TB['conf'], cp), verbose=verbose)
    run.arm('B3 final, log-lift instead of confidence', 'numberbatch', tbl=tb(PV, NADJ, TB['loglift']), verbose=verbose)
    if 'fen_C0.5' in TB: run.arm('B4 final, frequentist EN (C=0.5)', 'numberbatch', tbl=tb(PV, NADJ, TB['fen_C0.5']), verbose=verbose)
    if 'bayes_en' in TB: run.arm('B5 final, Bayesian EN', 'numberbatch', tbl=tb(PV, NADJ, TB['bayes_en']), verbose=verbose)
    run.arm('B6 final, nouns only (no table)', 'numberbatch', verbose=verbose)
    run.arm('B7 final, adjectives appended instead of table', 'numberbatch', mode='naive', verbose=verbose)


ABLATION_COMPARISONS = [   # (label, arm a, arm b) as in N12 / ablation.json: a minus b on Hits@3
    ('A1 abstract-noun removal', 'base Alg.2 + abstract removal (w2v)', 'A0 base Alg.2, abstract nouns kept (w2v)'),
    ('A2 adjectives appended to query', 'A2 + adjectives appended to the query (w2v)', 'base Alg.2 + abstract removal (w2v)'),
    ('A3 adjective patterns (table)', 'A3 + adjective patterns only, conf (w2v)', 'A2 + adjectives appended to the query (w2v)'),
    ('A4 + pair patterns', 'A4 + adjective-noun pairs = all patterns (w2v)', 'A3 + adjective patterns only, conf (w2v)'),
    ('A5 Numberbatch backbone', 'final: numberbatch + conf', 'A4 + adjective-noun pairs = all patterns (w2v)'),
    ('A total: final vs base Alg.2', 'final: numberbatch + conf', 'base Alg.2 + abstract removal (w2v)'),
    ('B1 drop pair patterns', 'B1 final, adjective patterns only', 'final: numberbatch + conf'),
    ('B2 drop adjective patterns', 'B2 final, pair patterns only', 'final: numberbatch + conf'),
    ('B3 log-lift weighting', 'B3 final, log-lift instead of confidence', 'final: numberbatch + conf'),
    ('B4 frequentist EN selection', 'B4 final, frequentist EN (C=0.5)', 'final: numberbatch + conf'),
    ('B5 Bayesian EN selection', 'B5 final, Bayesian EN', 'final: numberbatch + conf'),
    ('B6 drop the table', 'B6 final, nouns only (no table)', 'final: numberbatch + conf'),
    ('B7 naive adjectives, no table', 'B7 final, adjectives appended instead of table', 'final: numberbatch + conf'),
]


def ablation_stats(run, sets):
    """paired bootstrap + exact McNemar per comparison and set, Holm over all of them (N12)"""
    out = []
    for s in sets:
        for label, a, b in ABLATION_COMPARISONS:
            if a in run.RANKS and b in run.RANKS:
                out.append({'comparison': label, 'set': s, 'a': a, 'b': b, **compare(run.RANKS[a][s] <= 3, run.RANKS[b][s] <= 3)})
    for c, ph in zip(out, holm([c['p'] for c in out])): c['p_holm'] = ph
    return out


# ------------------------------------------------------------------ restore everything the frozen pipeline needs (steps 8, 9, 10c)
def load_final_models(extra_nouns=()):
    """lexicon, rankers (both backbones, vectors extended for extra_nouns), tables and the frozen protocol"""
    lex = [l.strip() for l in open(P('protocol', 'lexicon_v2.txt')) if l.strip()]
    VEC = {}
    for bb in ('w2v', 'numberbatch'):
        V, _ = load_vec_cache(bb)
        V, added = extend_vectors(V, bb, set(lex) | set(extra_nouns)); VEC[bb] = V
        if added: print(f'   +{added} {bb} vectors')
    RK = {bb: build_ranker(VEC[bb], lex) for bb in VEC}
    meta = np.load(P('tables', 'feat_meta.npz'), allow_pickle=True)
    PV, NADJ, CLASSES = list(meta['patvocab']), int(meta['n_adj']), list(meta['classes'])
    TB = dict(np.load(P('tables', 'tables_r4a.npz')))
    if os.path.exists(P('tables', 'tables_ben.npz')):
        bz = np.load(P('tables', 'tables_ben.npz')); TB['bayes_en'] = (bz['mean'] * bz['selected']).astype(np.float32)
    return lex, RK, {'PV': PV, 'NADJ': NADJ, 'CLASSES': CLASSES, 'tables': TB, 'min_support': float(meta['min_support'])}
