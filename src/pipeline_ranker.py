"""Ranking stage of the pipeline: context nouns -> embedding similarity to the 227 OSM tags, blended with the mined adjective->tag table.
Identical to the evaluation code; loads the small result files from ROOT (or an assets dir)."""
import json, pickle, re, numpy as np
from collections import Counter
ABSTRACT = {'place','spot','location','area','site','position','thing','kind','sort','lot','bit','way','day','time'}
KS, LAM = (1, 2, 3, 5, 10, 20), 0.35
def parts(s): return [w for w in re.split(r'[\s\-_/]+', s) if w]
def variants(s):
    b = [s, s.lower(), s.title(), s.capitalize()]; o, seen = [], set()
    for v in b + [x.replace(' ', '_').replace('-', '_') for x in b] + [x.replace(' ', '').replace('-', '') for x in b]:
        if v and v not in seen: seen.add(v); o.append(v)
    return o
def ladder(VEC):
    def f(s):
        for v in variants(s):
            if v in VEC: return VEC[v]
        sub = [VEC[v] for w in parts(s) for v in variants(w) if v in VEC][:8]
        return np.mean(sub, 0) if sub else None
    return f
class Tables:
    """adjective->tag table (elastic net) + pattern->tag table (Bayesian elastic net posterior)"""
    def __init__(self, adj_npz, pat_npz, pat_meta_npz):
        e = np.load(adj_npz, allow_pickle=True); self.COEF, self.EN_CLS, self.EN_ADJ = e['coef'], list(e['classes']), list(e['adj_vocab']); self.AIX = {a: j for j, a in enumerate(self.EN_ADJ)}
        b = np.load(pat_npz, allow_pickle=True); m = np.load(pat_meta_npz, allow_pickle=True)
        self.PV, self.PCLS, self.NADJ = list(m['patvocab']), list(m['classes']), int(m['n_adj']); self.PIX = {p: j for j, p in enumerate(self.PV)}
        self.ADJ_SET, self.PAIR_SET = set(self.PV[:self.NADJ]), set(self.PV[self.NADJ:]); self.MU, self.SEL, self.LO, self.HI = b['mean'], b['selected'], b['hdi_lo'], b['hdi_hi']
    def pat_feats(self, r): return [self.PIX[a] for a in r['adjectives'] if a in self.ADJ_SET] + [self.PIX[p] for p in r['transaction'] if p in self.PAIR_SET]
class Ranker:
    def __init__(self, vec, lexicon, tables):
        self.vec, self.T = vec, tables; self.TAGS = [t for t in lexicon if vec(t) is not None]; self.IX = {t: i for i, t in enumerate(self.TAGS)}
        M = np.vstack([vec(t) for t in self.TAGS]); self.M = M / (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)
        self.c2w_adj = {c: self.IX[c] for c in tables.EN_CLS if c in self.IX}; self.c2w_pat = {c: self.IX[c] for c in tables.PCLS if c in self.IX}
    def sim(self, terms):
        s = np.zeros(len(self.TAGS), np.float32)
        for t in terms:
            v = self.vec(t)
            if v is None: continue
            sims = self.M @ (v / (np.linalg.norm(v) + 1e-9)); s += (sims - sims.min()) / (sims.max() - sims.min() + 1e-9)
        return s
    @staticmethod
    def _norm(s): lo, hi = s.min(), s.max(); return (s - lo) / (hi - lo + 1e-9) if hi > lo else s
    def en_adj(self, r):
        T = self.T; s = np.zeros(len(self.TAGS), np.float32); rc = [T.COEF[:, T.AIX[a]] for a in r['adjectives'] if a in T.AIX]
        if not rc: return s
        agg = np.sum(rc, 0)
        for c, w in self.c2w_adj.items(): s[w] = agg[T.EN_CLS.index(c)]
        return self._norm(s)
    def en_ben(self, r):
        T = self.T; s = np.zeros(len(self.TAGS), np.float32); f = T.pat_feats(r)
        if not f: return s
        agg = (T.MU * T.SEL)[f].sum(0)
        for c, w in self.c2w_pat.items(): s[w] = agg[T.PCLS.index(c)]
        return self._norm(s)
    def scores(self, r, lam=LAM, en='adj', noun_key='context_nouns', naive=False):
        terms = [t for t in r[noun_key] if t.lower() not in ABSTRACT] + (r['adjectives'] if naive else [])
        s = self._norm(self.sim(terms))
        if lam > 0 and en: s = (1 - lam) * s + lam * (self.en_adj(r) if en == 'adj' else self.en_ben(r))
        return s
    def rank(self, r, **kw):
        s = self.scores(r, **kw); g = r['gold_tag']; return int((s >= s[self.IX[g]]).sum()) if g in self.IX else len(self.TAGS) + 1
    def ranks(self, rows, **kw): return np.array([self.rank(r, **kw) for r in rows], float)
    def top(self, r, n=5, **kw):
        s = self.scores(r, **kw); return [(self.TAGS[j], float(s[j])) for j in np.argsort(-s)[:n]]
    def explain(self, r, topn=3, per_tag=3):
        """for each of the top tags: the credible contributing patterns (posterior mean, 94% interval)"""
        T = self.T; s = self.scores(r, en='ben'); f = T.pat_feats(r); out = []
        for j in np.argsort(-s)[:topn]:
            t = self.TAGS[j]; contrib = []
            if t in T.PCLS:
                k = T.PCLS.index(t); contrib = sorted([(T.PV[p], float(T.MU[p, k]), float(T.LO[p, k]), float(T.HI[p, k])) for p in f if T.SEL[p, k] and T.MU[p, k] > 0], key=lambda x: -x[1])[:per_tag]
            out.append((t, float(s[j]), contrib))
        return out
def metrics(ranks, ks=KS):
    r = np.asarray(ranks, float); o = {f'Hits@{k}': float((r <= k).mean()) for k in ks}; o['nDCG@20'] = float(np.where(r <= 20, 1 / np.log2(r + 1), 0).mean()); o['MedR'] = float(np.median(r)); return o
def extract_rows(texts, interpreter, batch_size=64):
    """run the extraction stage on raw sentences -> rows shaped like the evaluation files (context_nouns = extractor nouns)"""
    rows = []
    for it in interpreter.pipe(texts, batch_size=batch_size):
        nouns = sorted(set([e['head_lemma'] for e in it.entities] + list(it.context_nouns)))
        rows.append({'sentence': it.sentence, 'context_nouns': nouns, 'ours_nouns': nouns, 'adjectives': sorted({a for e in it.entities for a in e['adjectives']}), 'tag_hints': it.tag_hints, 'transaction': it.transaction})
    return rows
def load_default(ROOT, backbone='w2v'):
    lex = json.load(open(f'{ROOT}/eval/evalset_106.json'))['lexicon']
    T = Tables(f'{ROOT}/results_i/i3_elasticnet.npz', f'{ROOT}/results_p/p1_bayesian_en.npz', f'{ROOT}/results_p/p1_feat_meta.npz')
    cache = {'w2v': 'w2v_googlenews_subset_v2.pkl', 'numberbatch': 'numberbatch_subset.pkl'}[backbone]
    return Ranker(ladder(pickle.load(open(f'{ROOT}/models_cache/{cache}', 'rb'))), lex, T)
