# ============================================================================
# EXTENDED PAKISTAN SET -- post-hoc evaluation of the FROZEN final OSM pipeline.
# The set was built after the final run, so nothing here is pre-registered and nothing
# is tuned: lambda, tables and vocabulary are the saved osmfinal artefacts.
# Arms: final (Numberbatch + OSM conf), Numberbatch + OSM Bayesian EN, base paper (w2v, Alg. 2).
# The Wikivoyage-trained arms are NOT scored: the overlap check found the source listings of
# 179 kept rows in results_i/weak_labelled.parquet.
# Before running: upload pk_extended_raw.json to Drive geoproject/eval/. Runtime: T4 GPU.
# Writes geoproject/pk_extension/pk_extended_results.json once (SCORED.flag).
# ============================================================================

# ---------------------------------------------------------------- CELL S0 --
# Restore + gates. Helpers copied verbatim from 09_ablation_cells.py (R3 / R4a / R5a / R6 / R7).
from google.colab import drive
drive.mount('/content/drive')
import os, sys, json, time, pickle, re, gc, subprocess
import numpy as np, pandas as pd
from collections import Counter
from scipy import sparse
from scipy.stats import binomtest
ROOT = '/content/drive/MyDrive/geoproject'; OUT = f'{ROOT}/osmfinal'; RES = f'{ROOT}/pk_extension'
os.makedirs(RES, exist_ok=True)
assert not os.path.exists(f'{RES}/SCORED.flag'), 'already scored once; read pk_extended_results.json instead'
sys.path.insert(0, ROOT)
import pipeline_ranker as pr

meta = np.load(f'{OUT}/osm_feat_meta.npz', allow_pickle=True)
PV, CLASSES, NADJ = list(meta['patvocab']), list(meta['classes']), int(meta['n_adj'])
T4 = dict(np.load(f'{OUT}/tables_r4a.npz'))
bz = np.load(f'{OUT}/tables_ben.npz'); T4['bayes_en'] = (bz['mean'] * bz['selected']).astype(np.float32)
ADO, FIN = json.load(open(f'{OUT}/adoption.json')), json.load(open(f'{OUT}/final.json'))
LAM = {'conf': ADO['dev']['numberbatch']['conf']['best_lambda'], 'bayes_en': ADO['dev']['numberbatch']['bayes_en']['best_lambda']}

def norm_rows(M):                                            # R5a, verbatim
    lo, hi = M.min(1, keepdims=True), M.max(1, keepdims=True)
    return np.where(hi > lo, (M - lo) / (hi - lo + 1e-9), M)
def featurize(df, pv, nadj):                                 # R3, verbatim
    pix = {p: j for j, p in enumerate(pv)}; A, P2 = set(pv[:nadj]), set(pv[nadj:])
    ri, ci = [], []
    for r, row in enumerate(df.itertuples(index=False)):
        seen = {pix[a] for a in row.adjs if a in A} | {pix[p] for p in row.pit if p in P2}
        ri += [r] * len(seen); ci += list(seen)
    return sparse.csr_matrix((np.ones(len(ri), np.float32), (ri, ci)), shape=(len(df), len(pv)))
def sim_matrix(R, df):                                       # R5a, abstract nouns dropped
    return np.vstack([R._norm(R.sim([t for t in L if t.lower() not in pr.ABSTRACT])) for L in df.context_nouns]).astype(np.float32)
def table_matrix(R, Xs, M, classes=CLASSES):                 # R5a, verbatim
    agg = Xs @ M
    S = np.zeros((Xs.shape[0], len(R.TAGS)), np.float32)
    for k, c in enumerate(classes):
        if c in R.IX: S[:, R.IX[c]] = agg[:, k]
    has_ = Xs.getnnz(1) > 0
    S[has_] = norm_rows(S[has_]); S[~has_] = 0.0
    return S
def ranks(SIM, TBL, g, lam):                                 # R7, verbatim
    s = SIM if TBL is None or lam == 0 else (1 - lam) * SIM + lam * TBL
    ok = g >= 0; r = np.full(len(g), SIM.shape[1] + 1)
    r[ok] = (s[ok] >= s[np.where(ok)[0], g[ok]][:, None]).sum(1); return r
def mets(r): return {'n': int(len(r)), 'Hits@1': float((r <= 1).mean()), 'Hits@3': float((r <= 3).mean()), 'nDCG@20': float(np.where(r <= 20, 1 / np.log2(r + 1), 0).mean())}
def boot(a, b, n=10000, seed=0):                             # R6, verbatim
    rs = np.random.RandomState(seed); m = len(a); d = np.empty(n); a = a.astype(float); b = b.astype(float)
    for i in range(n):
        ix = rs.randint(0, m, m); d[i] = a[ix].mean() - b[ix].mean()
    return float(a.mean() - b.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))
def as_df(rows):                                             # R7
    return pd.DataFrame({'context_nouns': [r['context_nouns'] for r in rows], 'tag': [r['gold_tag'] for r in rows],
                         'adjs': [sorted({a.lower() for a in r['adjectives'] if str(a).isalpha()}) for r in rows],
                         'pit': [[it for it in r['transaction'] if it.startswith('amod:')] for r in rows]})

LEX = json.load(open(f'{ROOT}/eval/evalset_106.json'))['lexicon']
WVT = pr.Tables(f'{ROOT}/results_i/i3_elasticnet.npz', f'{ROOT}/results_p/p1_bayesian_en.npz', f'{ROOT}/results_p/p1_feat_meta.npz')
VEC = {'w2v': pickle.load(open(f'{OUT}/w2v_googlenews_osm.pkl', 'rb')), 'numberbatch': pickle.load(open(f'{OUT}/numberbatch_osm.pkl', 'rb'))}
RK = {bb: pr.Ranker(pr.ladder(v), LEX, WVT) for bb, v in VEC.items()}

ARMS = {'final: numberbatch + OSM conf': ('numberbatch', 'conf'), 'numberbatch + OSM Bayesian EN': ('numberbatch', 'bayes_en'),
        'base paper (w2v, Algorithm 2)': ('w2v', None)}
def score(rows):
    df, out = as_df(rows), {}
    for name, (bb, tb) in ARMS.items():
        R = RK[bb]; g = np.array([R.IX.get(t, -1) for t in df.tag])
        TBL = table_matrix(R, featurize(df, PV, NADJ), T4[tb]) if tb else None
        out[name] = ranks(sim_matrix(R, df), TBL, g, LAM[tb] if tb else 0.0)
    return out

X = json.load(open(f'{ROOT}/eval/pk_extended_raw.json'))
evpk = json.load(open(f'{ROOT}/eval/pk_evalset_extracted.json'))
c0 = Counter(r['gold_tag'] for r in evpk); pk3 = [r for r in evpk if c0[r['gold_tag']] >= 3]
orig = {r['id']: r for r in X if r['part'] == 'original'}
assert len(X) == 592 and len(orig) == 199 and len(pk3) == 157
assert all(orig[f"PK{int(r['row']):03d}"]['gold_tag'] == r['gold_tag'] and orig[f"PK{int(r['row']):03d}"]['context_nouns'] == r['context_nouns'] for r in evpk)
def gate(tag):
    S = score(pk3)
    for name in ARMS:
        assert abs(mets(S[name])['Hits@3'] - FIN['results']['pk_n3'][name]['Hits@3']) < 1e-9, (tag, name)
    print(f'gate ({tag}): all 3 arms reproduce final.json on the 157 rows exactly')
gate('saved caches')


# ---------------------------------------------------------------- CELL S1 --
# Extraction of all 592 English sentences with the same transformer extractor, then the embedding
# caches are extended for the new nouns (R5-cache recipe). Tag vectors are NOT rebuilt: only the
# query-side lookup gets the extra vectors, and the gate is re-run.
if subprocess.run([sys.executable, '-c', 'import en_core_web_trf'], capture_output=True).returncode:
    subprocess.run([sys.executable, '-m', 'spacy', 'download', 'en_core_web_trf', '-q'], check=True)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'gensim>=4.3.3'], check=True)
import spacy; spacy.prefer_gpu()
import adjective_extractor as ae
PI = ae.PlaceInterpreter(model='en_core_web_trf')
def extract(texts):
    t0 = time.time(); ex = pr.extract_rows(list(texts), PI); print(f'   extracted {len(ex)} texts in {time.time()-t0:.0f}s'); return ex
EX = dict(zip([r['id'] for r in X], extract([r['sentence'] for r in X])))
same = np.mean([EX[i]['adjectives'] == orig[i]['adjectives'] for i in orig])
print(f'   original rows: re-extracted adjectives identical to the saved ones for {same:.1%}')

def parts(s): return [w for w in re.split(r'[\s\-_/]+', s) if w]
need = {p for e in EX.values() for n in e['context_nouns'] for p in [n] + parts(n)}
probe = {bb: {v for s in need for v in pr.variants(s)} - set(VEC[bb]) for bb in VEC}
import gensim.downloader as api
kv = api.load('word2vec-google-news-300'); NEW_W = {p: np.asarray(kv[p], np.float32) for p in probe['w2v'] if p in kv}; del kv; gc.collect()
kv = api.load('conceptnet-numberbatch-17-06-300'); key = lambda p: f'/c/en/{p.lower()}'
NEW_N = {p: np.asarray(kv[key(p)], np.float32) for p in probe['numberbatch'] if key(p) in kv}; del kv; gc.collect()
RK['w2v'].vec = pr.ladder({**VEC['w2v'], **NEW_W}); RK['numberbatch'].vec = pr.ladder({**VEC['numberbatch'], **NEW_N})
print(f'   +{len(NEW_W)} w2v and +{len(NEW_N)} numberbatch vectors for {len(need)} new noun strings')
gate('extended caches')
for bb, R in RK.items():
    cov = np.mean([R.vec(n) is not None for e in EX.values() for n in e['context_nouns']])
    print(f'   {bb:12s} extractor nouns embeddable {cov:.1%}')
miss = sorted({r['gold_tag'] for r in X} - set(RK['numberbatch'].IX) - set(RK['w2v'].IX)); print('   gold tags without a vector:', miss or 'none')


# ---------------------------------------------------------------- CELL S2 --
# English. A = the pre-registered 157 with supplied context nouns (= final.json);
# everything else uses extractor nouns for every row, since the new rows have no supplied nouns.
auto = lambda r: {**r, **{k: EX[r['id']][k] for k in ('context_nouns', 'adjectives', 'transaction')}}
cnt = Counter(r['gold_tag'] for r in X); n3 = [r for r in X if cnt[r['gold_tag']] >= 3]
pk3_ids = [f"PK{int(r['row']):03d}" for r in pk3]
SETS = {
    'A original 157, supplied nouns (final.json)':       [orig[i] for i in pk3_ids],
    'A2 original 157, extractor nouns':                 [auto(orig[i]) for i in pk3_ids],
    'B extended n>=3, extractor nouns':                 [auto(r) for r in n3],
    'C extended n>=3, new rows only':                   [auto(r) for r in n3 if r['part'] == 'extension'],
    'D extended n>=3, original rows only':              [auto(r) for r in n3 if r['part'] == 'original'],
    'S1 B without rows marked uncertain':               [auto(r) for r in n3 if not r['uncertain']],
    'S2 B without the 4 type-word rows':                [auto(r) for r in n3 if not r.get('type_word_in_text')],
}
RANKS, ROWS = {}, {}
for s, rows in SETS.items():
    RANKS[s] = score(rows); ROWS[s] = [r['id'] for r in rows]
    print(f'{s:46s} n={len(rows):3d} | ' + ' | '.join(f"{n.split(':')[0].split(' (')[0][:22]} H@3 {mets(RANKS[s][n])['Hits@3']:.3f}" for n in ARMS))


# ---------------------------------------------------------------- CELL S3 --
# Urdu and Roman Urdu through the translation front end (Phase N translators and prompt, verbatim),
# then the same extractor and arms. Each is paired with the English originals of the same rows.
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-U', 'bitsandbytes>=0.46.1'], check=True)
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, AutoModelForCausalLM, BitsAndBytesConfig
dev = 'cuda'; assert torch.cuda.is_available(), 'switch the runtime to a GPU (T4 is enough)'
nl_tok = AutoTokenizer.from_pretrained('facebook/nllb-200-distilled-600M', src_lang='urd_Arab'); nl = AutoModelForSeq2SeqLM.from_pretrained('facebook/nllb-200-distilled-600M', dtype=torch.float16).to(dev).eval()
def nllb(texts, bs=16):
    out = []
    for i in range(0, len(texts), bs):
        enc = nl_tok(texts[i:i+bs], return_tensors='pt', padding=True, truncation=True, max_length=256).to(dev)
        with torch.no_grad(): gen = nl.generate(**enc, forced_bos_token_id=nl_tok.convert_tokens_to_ids('eng_Latn'), max_new_tokens=160, num_beams=4)
        out += nl_tok.batch_decode(gen, skip_special_tokens=True)
    return out
qw_id = 'Qwen/Qwen2.5-7B-Instruct'
qw_tok = AutoTokenizer.from_pretrained(qw_id); qw = AutoModelForCausalLM.from_pretrained(qw_id, quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16, bnb_4bit_quant_type='nf4'), device_map='auto').eval()
def llm_translate(texts, lang, bs=8):
    out = []; qw_tok.padding_side = 'left'
    for i in range(0, len(texts), bs):
        msgs = [[{'role': 'system', 'content': 'You are a translator. Translate the user text into natural English. Keep place names as they are. Output only the translation.'}, {'role': 'user', 'content': f'{lang} text: {t}'}] for t in texts[i:i+bs]]
        enc = qw_tok([qw_tok.apply_chat_template(m, tokenize=False, add_generation_prompt=True) for m in msgs], return_tensors='pt', padding=True).to(dev)
        with torch.no_grad(): gen = qw.generate(**enc, max_new_tokens=120, do_sample=False)
        out += [s.strip().split('\n')[0] for s in qw_tok.batch_decode(gen[:, enc.input_ids.shape[1]:], skip_special_tokens=True)]
    return out

ur = [r for r in X if r['urdu']]; ru = [r for r in X if r['roman_urdu']]
assert len(ur) == 157 and len(ru) == 300
t0 = time.time()
TR = {'urdu_nllb': dict(zip([r['id'] for r in ur], nllb([r['urdu'] for r in ur]))),
      'roman_llm': dict(zip([r['id'] for r in ru], llm_translate([r['roman_urdu'] for r in ru], 'Roman Urdu (Urdu written in Latin letters, possibly mixed with English)')))}
print(f'translated {len(ur)} Urdu + {len(ru)} Roman Urdu in {time.time()-t0:.0f}s')
EXT = {k: dict(zip(v, extract(list(v.values())))) for k, v in TR.items()}
via = lambda k: (lambda r: {**r, **{f: EXT[k][r['id']][f] for f in ('context_nouns', 'adjectives', 'transaction')}})
ORIGINS = {'author': 'written by author', 'drafted': 'drafted, '}
LANG = {
    'U urdu 157 -> NLLB':                 [via('urdu_nllb')(r) for r in ur],
    'U-en same 157 rows, English':        [auto(r) for r in ur],
    'R roman 300 -> LLM':                 [via('roman_llm')(r) for r in ru],
    'R-en same 300 rows, English':        [auto(r) for r in ru],
    'R1 roman, author-written 60 -> LLM': [via('roman_llm')(r) for r in ru if r['roman_origin'] == ORIGINS['author']],
    'R1-en same 60 rows, English':        [auto(r) for r in ru if r['roman_origin'] == ORIGINS['author']],
    'R2 roman, drafted 240 -> LLM':       [via('roman_llm')(r) for r in ru if r['roman_origin'].startswith(ORIGINS['drafted'])],
    'R2-en same 240 rows, English':       [auto(r) for r in ru if r['roman_origin'].startswith(ORIGINS['drafted'])],
}
assert len(LANG['R1 roman, author-written 60 -> LLM']) == 60 and len(LANG['R2 roman, drafted 240 -> LLM']) == 240
for s, rows in LANG.items():
    RANKS[s] = score(rows); ROWS[s] = [r['id'] for r in rows]
    print(f'{s:46s} n={len(rows):3d} | ' + ' | '.join(f"{n.split(':')[0].split(' (')[0][:22]} H@3 {mets(RANKS[s][n])['Hits@3']:.3f}" for n in ARMS))


# ---------------------------------------------------------------- CELL S4 --
# Comparisons (paired bootstrap 95% CI on the Hits@3 difference, exact McNemar, Holm over this file)
# and the one write.
def holm(ps):
    o = np.argsort(ps); adj = np.empty(len(ps)); run = 0.0
    for k, i in enumerate(o): run = max(run, (len(ps) - k) * ps[i]); adj[i] = min(1.0, run)
    return adj.tolist()
F, BEN, B0 = list(ARMS)
CMP = []
for s in RANKS:
    for a, b in ((F, B0), (BEN, F)):
        ha, hb = RANKS[s][a] <= 3, RANKS[s][b] <= 3
        d, lo, hi = boot(ha, hb); ao, bo = int((ha & ~hb).sum()), int((hb & ~ha).sum())
        CMP.append({'set': s, 'a': a, 'b': b, 'delta_hits3': d, 'ci95': [lo, hi], 'a_only': ao, 'b_only': bo,
                    'p': float(binomtest(min(ao, bo), ao + bo, 0.5).pvalue) if ao + bo else 1.0})
for c, p in zip(CMP, holm([c['p'] for c in CMP])): c['p_holm'] = p
for s, (en, tr) in {'urdu': ('U-en same 157 rows, English', 'U urdu 157 -> NLLB'), 'roman': ('R-en same 300 rows, English', 'R roman 300 -> LLM'),
                    'roman_author': ('R1-en same 60 rows, English', 'R1 roman, author-written 60 -> LLM'),
                    'roman_drafted': ('R2-en same 240 rows, English', 'R2 roman, drafted 240 -> LLM')}.items():
    d, lo, hi = boot(RANKS[tr][F] <= 3, RANKS[en][F] <= 3)
    CMP.append({'set': f'translation loss, {s}', 'a': tr, 'b': en, 'arm': F, 'delta_hits3': d, 'ci95': [lo, hi]})
for c in CMP:
    print(f"{c['set'][:40]:40s} {c['a'][:28]:28s} vs {c['b'][:28]:28s} d {c['delta_hits3']:+.3f} [{c['ci95'][0]:+.3f}, {c['ci95'][1]:+.3f}]" + (f"  p {c['p']:.4f} holm {c['p_holm']:.4f}" if 'p' in c else ''))

OUTJ = {'note': ('Post-hoc evaluation of the frozen final OSM pipeline on the extended Pakistan set (built after the final run). '
                 'Set A reproduces final.json; all other sets use extractor nouns. Wikivoyage-trained arms are not scored (source overlap).'),
        'lambda': LAM, 'sets': {s: {'n': len(ROWS[s]), 'ids': ROWS[s], **{n: mets(RANKS[s][n]) for n in ARMS}} for s in RANKS},
        'ranks': {s: {n: RANKS[s][n].tolist() for n in ARMS} for s in RANKS}, 'comparisons': CMP,
        'translations': TR, 'models': {'nllb': 'facebook/nllb-200-distilled-600M (urd_Arab->eng_Latn, 4 beams)', 'llm': qw_id + ' (4-bit, greedy)'},
        'extractor': 'en_core_web_trf via adjective_extractor.PlaceInterpreter', 'extra_vectors': {'w2v': len(NEW_W), 'numberbatch': len(NEW_N)},
        'input': 'eval/pk_extended_raw.json', 'n3_tags': sorted(t for t, c in cnt.items() if c >= 3)}
json.dump(OUTJ, open(f'{RES}/pk_extended_results.json', 'w'), ensure_ascii=False, indent=1)
open(f'{RES}/SCORED.flag', 'w').write(time.strftime('%Y-%m-%d %H:%M:%S'))
print('wrote', f'{RES}/pk_extended_results.json', '+ SCORED.flag')
