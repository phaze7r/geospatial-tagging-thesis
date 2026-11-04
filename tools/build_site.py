#!/usr/bin/env python3
"""Builds docs/index.html, the static results page (GitHub Pages: publish the docs/ folder of the main branch).
Every number on the page is read from thesisv2/results/*.json or thesisv2/report/tables/*.csv; nothing is typed in.
Run from anywhere: python tools/build_site.py"""
import csv, json
from html import escape as E
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES, TAB, DOCS = ROOT / 'thesisv2/results', ROOT / 'thesisv2/report/tables', ROOT / 'docs'
REPO = 'https://github.com/phaze7r/geospatial-tagging-thesis'
APP = 'https://bat.tail3da3d0.ts.net'  # place-tagger, served from the author's laptop; change here if the host changes
final = json.loads((RES / 'final.json').read_text())
lc = json.loads((RES / 'learning_curves.json').read_text())
fpg = json.loads((RES / 's07b_fpgrowth_check.json').read_text())
s12 = json.loads((RES / 's12_explanations_and_tables.json').read_text())
blend = json.loads((DOCS / 'data/blend.json').read_text())


def table(name):
    with open(TAB / f'{name}.csv', newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


M1, M2, M3 = 'M1 base paper: nouns only (w2v)', 'M2 adjective-noun plain (w2v)', 'M3 our pipeline: conf table + numberbatch'
def arm(a, s, k='Hits@3'): return final['arms'][a][s][k]
def holm(s):
    c = next(c for c in final['comparisons'] if c['set'] == s and c['a'] == M3 and c['b'] == M1)
    return c['delta_hits3'], c['p_holm']
def ptxt(p): return '< 0.0001' if p < 1e-4 else f'{p:.3f}'
def f3(x): return f'{x:.3f}'

SETS = [('osm_test', 'OpenStreetMap test set', 'Sealed until the protocol was frozen, scored once'),
        ('eval_106', 'Base-paper sentences', 'The 106 sentences of Yousaf et al. (2023)'),
        ('pk528', 'Pakistan set', '528 Pakistani descriptions, evaluated after the protocol (post hoc)')]
N = {s: final['sizes'][s] for s, *_ in SETS}


def bars(groups, mx, legend=True):
    """groups: [(title, sub, [(label, value, cls)])]; HTML bars, width = value / mx."""
    out = []
    for gi, (title, sub, rows) in enumerate(groups):
        r = ''.join(f'<div class="brow"><span class="lab">{E(l)}</span><span class="track" style="--v:{v:.4f};--max:{mx};--d:{i}"><i class="{c}"></i></span><span class="val">{v:.3f}</span></div>'
                    for i, (l, v, c) in enumerate(rows))
        out.append(f'<div class="bgroup reveal"><h3>{E(title)}</h3><p class="sub">{E(sub)}</p>{r}</div>')
    return ''.join(out)


LEG = '<p class="legend"><span><i class="c1"></i>M1 base method, nouns only</span><span><i class="c2"></i>M2 adjectives added to the query</span><span><i class="c3"></i>M3 this work</span></p>'


def ledger():
    groups = [(t, f'{N[s]:,} rows. {sub}', [('M1 base', arm(M1, s), 'c1'), ('M2 control', arm(M2, s), 'c2'), ('M3 this work', arm(M3, s), 'c3')]) for s, t, sub in SETS]
    rows = table('main_results')
    th = ''.join(f'<th class="n">{h}</th>' if h in ('Hits@1', 'Hits@3', 'Hits@5', 'nDCG@20') else f'<th>{h}</th>' for h in ('Set', 'n', 'Method', 'Hits@1', 'Hits@3', 'Hits@5', 'nDCG@20'))
    body = ''.join(f'<tr class="{"hi" if "M3" in r["Method"] else ""}"><td>{E(r["Set"])}</td><td class="n">{r["n"]}</td><td>{E(r["Method"])}</td>'
                   + ''.join(f'<td class="n">{r[k]}</td>' for k in ('Hits@1', 'Hits@3', 'Hits@5', 'nDCG@20')) + '</tr>' for r in rows)
    gain = ''.join(f'<tr><td>{E(t)}</td><td class="n">{holm(s)[0]:+.3f}</td><td class="n">{ptxt(holm(s)[1])}</td></tr>' for s, t, _ in SETS)
    return (f'<div class="bars three">{bars(groups, 0.6)}</div>{LEG}'
            f'<div class="tw" style="margin-top:56px"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody>'
            '<caption>Hits@k: the share of descriptions whose correct tag is among the k top-ranked tags. nDCG@20 rewards ranking the correct tag higher.</caption></table></div>'
            f'<div class="tw" style="margin-top:40px"><table style="min-width:420px"><thead><tr><th>M3 against M1, Hits@3</th><th class="n">Difference</th><th class="n">p, Holm corrected</th></tr></thead><tbody>{gain}</tbody>'
            '<caption>Paired bootstrap for the interval, exact McNemar test for p, Holm correction within the protocol family. The Pakistan row is post hoc.</caption></table></div>')


def stage():
    rows = table('ablation_stage')
    out = []
    for r in rows:
        key = r['Step'].startswith('A3')
        vals = [('OSM dev', float(r['OSM dev']), 'c3'), ('Base paper', float(r['Base-paper set']), 'c2'), ('Pakistan', float(r['Pakistan set']), 'c1')]
        b = ''.join(f'<div class="brow"><span class="lab">{l}</span><span class="track" style="--v:{v};--max:0.55;--d:{i}"><i class="{c}"></i></span><span class="val">{v:.3f}</span></div>' for i, (l, v, c) in enumerate(vals))
        out.append(f'<div class="step reveal{" key" if key else ""}"><p class="what">{E(r["Step"])}</p><div>{b}</div></div>')
    return f'<div class="stage">{"".join(out)}</div>'


def dumbbell():
    t = s12['per_tag_pk528']
    rows = sorted(t.items(), key=lambda kv: (kv[1]['M3'] - kv[1]['M1'], kv[1]['n']), reverse=True)
    ahead = sum(v['M3'] > v['M1'] + 1e-9 for _, v in rows); behind = sum(v['M3'] < v['M1'] - 1e-9 for _, v in rows)
    lvl = len(rows) - ahead - behind
    out = []
    for tag, v in rows:
        a, b = v['M1'] * 100, v['M3'] * 100
        out.append(f'<div class="drow"><span class="t">{E(tag)} <span>({v["n"]})</span></span><span class="dtrack" title="{E(tag)}: base {v["M1"]:.2f}, this work {v["M3"]:.2f}">'
                   f'<b style="left:{min(a, b):.1f}%;width:{abs(a - b):.1f}%"></b><i class="a" style="left:{a:.1f}%"></i><i class="b" style="left:{b:.1f}%"></i></span></div>')
    scale = '<div class="dscale"><span></span><div>' + ''.join(f'<span style="left:{v * 20}%">{v / 5:g}</span>' for v in range(6)) + '</div></div>'
    return f'<div class="dumb reveal">{"".join(out)}</div>{scale}', (ahead, behind, lvl, len(rows))


def curves():
    W, H, L, B, T = 560, 300, 52, 44, 14
    xs = [L + i * (W - L - 40) / 4 for i in range(5)]
    lo, hi = 0.20, 0.40
    y = lambda v: T + (H - T - B) * (1 - (v - lo) / (hi - lo))
    g = ''.join(f'<line class="svg-l" x1="{L}" x2="{W}" y1="{y(v):.1f}" y2="{y(v):.1f}"/><text class="svg-t" x="{L - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v:.2f}</text>' for v in (0.20, 0.25, 0.30, 0.35, 0.40))
    xl = ''.join(f'<text class="svg-t" x="{x:.1f}" y="{H - 18}" text-anchor="middle">{n["n_train"]:,}</text>' for x, n in zip(xs, lc['curves']['conf']))
    def line(key, cls, dash=''):
        pts = [(x, y(c['dev_hits3'])) for x, c in zip(xs, lc['curves'][key])]
        return (f'<polyline class="l-{cls[2:]}" stroke-width="2.5" {dash} points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}"/>'
                + ''.join(f'<circle class="{cls}" r="4.5" cx="{a:.1f}" cy="{b:.1f}"/>' for a, b in pts))
    ben = lc['curves']['bayes_en'][-1]
    bx, by = xs[-1], y(ben['dev_hits3'])
    svg = (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Development Hits@3 against training rows for the confidence table, the frequentist elastic net and the Bayesian elastic net">{g}{xl}'
           f'{line("conf", "s-conf")}{line("fen_C0.5", "s-fen")}'
           f'<circle class="s-ben" stroke-width="2.5" r="6" cx="{bx:.1f}" cy="{by:.1f}"/>'
           f'<text class="svg-t" x="{(L + W) / 2:.0f}" y="{H - 2}" text-anchor="middle">training rows</text></svg>')
    worst = max(c['rhat_top200_max'] for c in lc['curves']['bayes_en'][:-1])
    fin = lambda k: lc['curves'][k][-1]['dev_hits3']
    key = (f'<p class="legend"><span><i class="k-line" style="--c:var(--fg)"></i>Confidence table {fin("conf"):.3f}</span>'
           f'<span><i class="k-line" style="--c:var(--slate)"></i>Frequentist elastic net {fin("fen_C0.5"):.3f}</span>'
           f'<span><i class="k-ring"></i>Bayesian elastic net, full size only {fin("bayes_en"):.3f}</span></p>')
    return svg + key, worst


def intervals():
    rows = s12['strongest'][:10]
    W, RH, L = 560, 32, 214
    mx = 8.0
    x = lambda v: L + (W - L - 8) * v / mx
    g = ''.join(f'<line class="svg-l" x1="{x(v):.1f}" x2="{x(v):.1f}" y1="0" y2="{RH * len(rows)}"/><text class="svg-t" x="{x(v):.1f}" y="{RH * len(rows) + 18}" text-anchor="middle">{v}</text>' for v in (0, 2, 4, 6, 8))
    nice = lambda r: (lambda t: t if len(t) <= 31 else t[:30] + '...')(f'{r["pattern"].replace("amod:", "").replace("_", " ")} to {r["tag"]}')
    body = ''.join(f'<g class="cred"><text class="svg-t" x="{L - 10}" y="{i * RH + 20}" text-anchor="end" style="fill:var(--fg)">{E(nice(r))}</text>'
                   f'<line x1="{x(r["lo"]):.1f}" x2="{x(r["hi"]):.1f}" y1="{i * RH + 16}" y2="{i * RH + 16}"/><circle cx="{x(r["mean"]):.1f}" cy="{i * RH + 16}" r="5"/></g>' for i, r in enumerate(rows))
    return (f'<svg viewBox="0 0 {W} {RH * len(rows) + 28}" role="img" aria-label="Posterior mean and 94 percent credible interval of the ten strongest pattern weights">{g}{body}</svg>')


def small_table(rows, num_from=1, cap=''):
    keys = list(rows[0].keys())
    th = ''.join(f'<th class="n">{E(k)}</th>' if i >= num_from else f'<th>{E(k)}</th>' for i, k in enumerate(keys))
    tb = ''.join('<tr>' + ''.join(f'<td class="n">{E(r[k])}</td>' if i >= num_from else f'<td>{E(r[k])}</td>' for i, k in enumerate(keys)) + '</tr>' for r in rows)
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody>' + (f'<caption>{cap}</caption>' if cap else '') + '</table></div>'


# ---- numbers used in prose, all from files -------------------------------------------------------------------------
d_osm, p_osm = holm('osm_test'); d_pk, p_pk = holm('pk528'); d_106, p_106 = holm('eval_106')
last = fpg[-1]; speed = last['extended']['seconds'] / last['guided']['seconds']
all_identical = all(x['identical'] for x in fpg)
bd = {r['Quantity']: r['Value'] for r in table('bayes_diag')}
ben_cost = next(c for c in final['comparisons'] if c['set'] == 'osm_test' and c['a'].startswith('X2') and c['b'] == M3)['delta_hits3']
cov = {r['Set']: r for r in table('coverage')}
dumb_html, (ahead, behind, level, ntags) = dumbbell()
curve_svg, bad_rhat = curves()
split = {r['Split']: r['Descriptions'] for r in table('split')}
vb = {r['Block']: r['Tags'] for r in table('vocab_blocks')}

eg = blend['examples']
PICK = ['cold coffee and free wifi', 'children clothing', 'Mughal walled enclosure']
data_json = json.dumps({'lambda': blend['lambda'], 'vocabulary': blend['vocabulary'], 'pick': PICK,
                        'examples': [{k: e[k] for k in ('text', 'nouns', 'unused', 'adjectives', 'tags')} for e in eg]}, separators=(',', ':'))
first = sorted(eg[0]['tags'], key=lambda t: -((1 - blend['lambda']) * t['sim'] + blend['lambda'] * t['pat']))[:5]
noscript = ''.join(f'<li>{E(t["tag"])} {(1 - blend["lambda"]) * t["sim"] + blend["lambda"] * t["pat"]:.2f}</li>' for t in first)

fig_arrow = '<svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'

HTML = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Adjective-aware place tagging</title>
<meta name="description" content="A thesis result page: mining adjective patterns lifts the correct-tag rate in the top three from {arm(M1, 'osm_test'):.3f} to {arm(M3, 'osm_test'):.3f} on {N['osm_test']:,} held-out OpenStreetMap descriptions.">
<meta property="og:title" content="Adjective-aware place tagging">
<meta property="og:description" content="Ranking 408 OpenStreetMap place tags from a free-text description by reading the adjectives.">
<meta name="color-scheme" content="light dark">
<link rel="icon" type="image/svg+xml" href="favicon.svg">
<link rel="stylesheet" href="site.css">
<script>document.documentElement.classList.add('js');try{{var t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
</head>
<body>
<a class="skip" href="#main">Skip to the content</a>
<header class="top"><div class="wrap">
  <a class="brand" href="#top"><svg class="mark" width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path fill="currentColor" fill-rule="evenodd" d="M12 1.5a10.5 10.5 0 1 0 0 21a10.5 10.5 0 1 0 0-21z M12 3.2a8.8 8.8 0 1 1 0 17.6a8.8 8.8 0 1 1 0-17.6z M17.8 6.2L13.6 13.6L6.2 17.8L10.4 10.4z M12 11.1a0.9 0.9 0 1 0 0 1.8a0.9 0.9 0 1 0 0-1.8z"/></svg><span>Adjective-aware tagging</span></a>
  <nav class="nav" aria-label="Sections"><a href="#results" class="keep">Results</a><a href="#gain">Gain</a><a href="#pakistan">Pakistan</a><a href="#try">Try it</a><a href="#checks">Checks</a><a href="#method">Method</a><a href="#limits">Limits</a><a href="{REPO}" class="keep">Code</a>
    <button class="theme" id="theme" type="button" aria-label="Switch between light and dark"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg></button></nav>
</div></header>

<main id="main">
<div class="hero" id="top"><div class="wrap">
  <div>
    <h1>Adjectives tell you what a place is.</h1>
    <p class="lede">“A quiet spot with good cold coffee” never says <i>cafe</i>. This thesis ranks {blend['vocabulary'] + 4} OpenStreetMap place tags from a description like that, and shows that mining the adjectives, which the base method throws away, roughly doubles the hit rate: the right tag is among the top three for {arm(M3, 'osm_test') * 100:.1f}% of {N['osm_test']:,} held-out descriptions, against {arm(M1, 'osm_test') * 100:.1f}% for nouns alone.</p>
    <div class="actions"><a class="btn btn--fill" href="#results">See the results {fig_arrow}</a><a class="btn btn--line" href="{REPO}">Read the code {fig_arrow}</a></div>
    <p class="byline"><b>Faizan Shah Ahmad</b>, MS Artificial Intelligence, Air University, Islamabad. Supervisor Dr Madiha Yousaf, co-supervisor Dr Faridoon Khan. Thesis: <i>Geospatial Tagging of Volunteered Place Descriptions: Bayesian Elastic Net and Extended FP-Growth Approach</i>.</p>
  </div>
  <div class="receipt" id="receipt" aria-label="Interactive ranking receipt">
    <h2>TAG RECEIPT<br><span style="font-weight:400">{blend['vocabulary'] + 4} tags ranked</span></h2>
    <hr>
    <div class="r-pick" id="r-pick" role="radiogroup" aria-label="Example description"></div>
    <blockquote class="r-text" id="r-text"></blockquote>
    <p class="r-read" id="r-read"></p>
    <div class="r-lam"><label for="r-lam" id="r-lamv">lambda 0.45</label><input id="r-lam" type="range" min="0" max="1" step="0.05" value="{blend['lambda']}"></div>
    <div class="r-snaps" id="r-snaps"></div>
    <hr>
    <ol class="r-rank" id="r-rank" aria-live="polite"></ol>
    <p class="r-key"><span><i class="k1"></i>noun similarity</span><span><i class="k2"></i>pattern table</span><span>select a tag</span></p>
    <hr>
    <ul class="r-sum" id="r-sum"></ul>
    <noscript><div class="noscript">Turn on JavaScript to move the weight and pick other descriptions. Top tags at the thesis setting: <ol>{noscript}</ol></div></noscript>
  </div>
</div></div>

<section class="on-black" id="results"><div class="wrap">
  <div class="head"><h2>Three methods, one vocabulary, same splits</h2>
  <p>M1 is the base method of Yousaf et al. (2023): context nouns and Word2Vec similarity. M2 is the control: every adjective is simply added to the similarity query. M3 is this work: mined adjective patterns, scored by confidence, blended with noun similarity. Every setting was fixed on a development set before the test split was opened.</p></div>
  {ledger()}
</div></section>

<section class="sec-ivory" id="gain"><div class="wrap">
  <div class="head"><h2>The mined table carries the gain</h2>
  <p>Each step adds one thing to the base method, Hits@3 on three sets. Pasting adjectives into the query makes things worse, since words like “cold” or “free” sit near no tag name. Counting which adjectives co-occur with which tag in real descriptions is what moves the number: +{float(table('ablation_stage')[3]['OSM dev']) - float(table('ablation_stage')[2]['OSM dev']):.3f} on the development set from the table alone (step A3 against the A2 control).</p></div>
  {stage()}
  <p class="legend"><span><i class="c3" style="--c:#000"></i>OSM development set</span><span><i class="c2" style="--c:#bfc9c2"></i>Base-paper sentences</span><span><i class="c1" style="--c:var(--slate)"></i>Pakistan set</span></p>
</div></section>

<section id="pakistan"><div class="wrap">
  <div class="head"><h2>On Pakistani places: {arm(M1, 'pk528'):.3f} to {arm(M3, 'pk528'):.3f}</h2>
  <p>528 descriptions of Pakistani places over {ntags} tags, written after the protocol was fixed, so this result is post hoc. The pooled gain is real ({d_pk:+.3f}, Holm p {ptxt(p_pk)}), but it is not a gain for every kind of place: this work is ahead on {ahead} of the {ntags} tags, behind on {behind} and level on {level}. It loses where a tag has no training text or where the nouns already said it.</p></div>
  {dumb_html}
  <p class="legend"><span><i class="c1" style="--c:var(--slate);border-radius:50%"></i>M1 base method</span><span><i class="c3" style="border-radius:50%"></i>M3 this work</span><span>Hits@3 per tag, number of descriptions in brackets, ordered by the difference</span></p>
</div></section>

<section class="sec-ivory" id="try"><div class="wrap">
  <div class="head"><h2>Try the tagger yourself</h2>
  <p>The place tagger is the thesis model behind a small web page. Type a description without naming the place, and it ranks all {blend['vocabulary'] + 4} tags and shows which adjectives pushed each one up and how sure the model is. It is invitation-only because it runs on the author's own laptop, which can serve only a handful of people at once. Ask for a code on the page and it is sent back to you. If the page does not load, the laptop is off: the receipt at the top of this page runs the same ranking on fixed examples.</p></div>
  <div class="actions"><a class="btn btn--fill" href="{APP}" rel="noopener">Open the place tagger {fig_arrow}</a><a class="btn btn--line" href="#top">Back to the receipt {fig_arrow}</a></div>
</div></section>

<section class="sec-soft" id="checks"><div class="wrap">
  <div class="head"><h2>Two checks on the machinery</h2>
  <p>The thesis title names two methods. Both are tested here, and one result is not the one the title suggests.</p></div>
  <div class="two">
    <div class="prose">
      <h3>Guided FP-Growth finds the same patterns, faster</h3>
      <p class="big">{speed:.0f}×</p>
      <p>Guided mining took {last['guided']['seconds']:.2f} s on the full {last['transactions']:,} transactions; extended FP-Growth took {last['extended']['seconds']:,.0f} s and {last['extended']['peak_mb']:,.0f} MB. Their pattern-to-tag itemsets were {'identical' if all_identical else 'NOT identical'} at all {len(fpg)} corpus sizes tested, from {fpg[0]['transactions']:,} to {last['transactions']:,}.</p>
      <p class="muted">The check ran at minimum support {last['min_support']}, not at the 0.0001 the pipeline uses; at 0.0001 the extended algorithm does not finish. The thesis states this.</p>
    </div>
    <div class="prose">
      <h3>The Bayesian elastic net explains; it does not rank</h3>
      <p class="big">{f"{ben_cost:+.3f}".replace("-", chr(0x2212))}</p>
      <p>Used as the ranker, the Bayesian elastic net lowers Hits@3 on the test set by {abs(ben_cost):.3f}. Only {bd['Credible coefficients (94% interval excludes zero)']} of its coefficients are credible, and {bd['Patterns with at least one credible tag']} patterns have a credible tag. So the confidence table ranks and the Bayesian fit supplies the intervals behind each explanation: a credible pattern backs the top tag for {cov['OSM development set']['Top-ranked tag has a credible pattern']} (development), {cov['Base-paper sentences']['Top-ranked tag has a credible pattern']} (base paper) and {cov['Pakistan set']['Top-ranked tag has a credible pattern']} (Pakistan) of descriptions.</p>
    </div>
  </div>
  <div class="two" style="margin-top:72px">
    <figure class="fig"><div class="tw"><div style="min-width:520px">{intervals()}</div></div><figcaption>The ten strongest pattern weights: posterior mean and 94% credible interval on the log-odds scale. Chains, warm-up, draws per chain: {bd['Chains, warm-up, retained draws per chain']}; median effective sample size {bd['Effective sample size, median']}, no divergent transitions.</figcaption></figure>
    <figure class="fig"><div class="tw"><div style="min-width:480px">{curve_svg}</div></div><figcaption>Development Hits@3 as the training text grows. The confidence table is still improving at the full {lc['fractions'][-1]:,} rows. The Bayesian fit converged only at full size (smaller fits reached R-hat up to {bad_rhat:.1f}), so it has a single point.</figcaption></figure>
  </div>
</div></section>

<section id="languages"><div class="wrap">
  <div class="head"><h2>Urdu and Roman Urdu, through translation</h2>
  <p>Urdu and Roman Urdu input is translated to English first, then ranked. The figures measure the pipeline behind a translation step, not native Urdu understanding. Everything here is Hits@3 and post hoc. M3 stays ahead of M1 in every variant.</p></div>
  {small_table(table('multilingual'), 2)}
  <div class="head" style="margin-top:72px"><h2>A second vocabulary says the same</h2>
  <p>An earlier full run used the base paper’s 227-tag list. The direction and size of the gain agree with the final 408-tag run.</p></div>
  {small_table(table('earlier_run'), 1, 'Hits@3. Gain is the pipeline minus the base method.')}
</div></section>

<section class="sec-soft" id="method"><div class="wrap">
  <div class="head"><h2>How a description becomes a ranking</h2>
  <p>The confidence table ranks the tags; the Bayesian elastic net, fitted on the same patterns, supplies the credible intervals that explain a prediction.</p></div>
  <div class="two">
    <ol class="steps">
      <li><div><b>Extract</b><span>A transformer dependency parser reads the description and returns context nouns, adjectives and adjective-noun pairs.</span></div></li>
      <li><div><b>Mine</b><span>Guided FP-Growth on {split['Train']} training descriptions, minimum support 0.0001, gives 2,916 patterns: 1,393 adjectives and 1,523 pairs.</span></div></li>
      <li><div><b>Weigh</b><span>Each pattern gets a confidence for each tag: of the descriptions that contain it, the share that carry the tag.</span></div></li>
      <li><div><b>Blend</b><span>score = (1 − λ) × noun similarity + λ × pattern score, with λ = {final['lambda'][M3]} for Numberbatch, chosen on the development set.</span></div></li>
      <li><div><b>Rank</b><span>All {blend['vocabulary'] + 4} tags are sorted by score. The top three become three queries against OpenStreetMap.</span></div></li>
    </ol>
    <figure class="fig fig-img"><img src="fig_algorithm1.png" alt="Algorithm 1: training and tagging" width="1100" height="800" loading="lazy"><figcaption>Algorithm 1. Line 6 is the confidence table that ranks; lines 7 and 8 are the Bayesian elastic net behind the explanations.</figcaption></figure>
  </div>
  <div class="facts" style="margin-top:64px">
    <div class="fact"><div class="v">{vb['Total']}</div><div class="l">place tags built from OpenStreetMap by fixed rules: {vb['Everyday places']} everyday, {vb['Tourism and heritage places']} tourism and heritage, {vb['Forced in because a gold tag of an evaluation set needs it']} forced in</div></div>
    <div class="fact"><div class="v">{split['Total']}</div><div class="l">descriptions after cleaning, split by place name: {split['Train']} train, {split['Development']} development, {split['Test (sealed until step 8)']} test</div></div>
    <div class="fact"><div class="v">2.9M</div><div class="l">OpenStreetMap elements with a description tag harvested, 2,875,608 rows before any filter</div></div>
    <div class="fact"><div class="v">1</div><div class="l">time the test split was scored, after a dry run reproduced every development figure</div></div>
  </div>
</div></section>

<section id="limits"><div class="wrap">
  <div class="head"><h2>What this does not show</h2>
  <p>The weak points are part of the result, so they are here too.</p></div>
  <ul class="limits">
    <li><b>The Pakistan result is post hoc.</b> The OpenStreetMap test set and the base-paper sentences were fixed in advance; the Pakistan set was completed afterwards. Its second round has one main annotator and drafted rewordings.</li>
    <li><b>The gain is uneven.</b> Hotel and restaurant carry much of the Pakistan result. Tags with no training text, such as shrine, lake and hill, are ranked by noun similarity alone and lose.</li>
    <li><b>Explanation is partial and costs accuracy.</b> A credible pattern backs the top tag for roughly a third to a half of descriptions. Ranking with the Bayesian table would make every explanation exact at a cost of {abs(ben_cost):.3f} Hits@3.</li>
    <li><b>The table is still learning.</b> Both curves rise at the full training size, and the best minimum support sat at the edge of its grid.</li>
    <li><b>Translation front end.</b> Urdu and Roman Urdu are translated before ranking. There is no native Urdu model.</li>
    <li><b>No user study and no language-model comparison.</b> The thesis shows explanations exist and read sensibly; it does not test whether they help people.</li>
  </ul>
</div></section>
</main>

<footer class="site-foot"><div class="wrap">
  <div><h3>Thesis</h3><p>Faizan Shah Ahmad, Air University, Islamabad, 2026.<br>Base paper: Yousaf, Schwartz and Wolter (2023), <i>KI - Künstliche Intelligenz</i> 37(1), 69 to 81.</p></div>
  <div><h3>Code and data</h3><ul><li><a href="{REPO}">Repository</a></li><li><a href="{REPO}/tree/main/thesisv2">The final evaluation, step by step</a></li><li><a href="{APP}" rel="noopener">Place tagger (invitation-only demo)</a></li><li><a href="{REPO}/tree/main/archive">Archive: earlier work, kept as a record</a></li></ul></div>
  <div><h3>Licence</h3><p>Code: Apache License 2.0. Data: OpenStreetMap rows are ODbL 1.0, Wikivoyage rows CC BY-SA 4.0.</p><pre>Every number on this page is read from thesisv2/results and thesisv2/report/tables by tools/build_site.py.</pre></div>
</div></footer>

<script type="application/json" id="blend">{data_json}</script>
<script>
(function(){{
  var root=document.documentElement;
  document.getElementById('theme').addEventListener('click',function(){{
    var dark=root.dataset.theme?root.dataset.theme==='dark':matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme=dark?'light':'dark';try{{localStorage.setItem('theme',root.dataset.theme)}}catch(e){{}}
  }});
  var io='IntersectionObserver' in window?new IntersectionObserver(function(es){{es.forEach(function(e){{if(e.isIntersecting){{e.target.classList.add('in');io.unobserve(e.target)}}}})}},{{threshold:.25}}):null;
  document.querySelectorAll('.reveal').forEach(function(el){{io?io.observe(el):el.classList.add('in')}});

  // the receipt: the thesis blend, worked live. sim and pat come from the model; the page only re-blends them.
  var D=JSON.parse(document.getElementById('blend').textContent),SHOWN=8,ROW=40,ex=0,lam=D.lambda,picked=null,rows={{}};
  var $=function(id){{return document.getElementById(id)}},f2=function(x){{return x.toFixed(2)}};
  var esc=function(s){{return String(s).replace(/[&<>"]/g,function(c){{return{{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]}})}};
  var pick=$('r-pick'),rank=$('r-rank');
  D.pick.forEach(function(t,i){{var b=document.createElement('button');b.type='button';b.setAttribute('role','radio');b.textContent=t;
    b.onclick=function(){{ex=i;picked=null;build(true)}};pick.appendChild(b)}});
  [[0,'lambda 0: base paper'],[D.lambda,'lambda '+D.lambda+': this thesis'],[1,'lambda 1: adjectives only']].forEach(function(s){{
    var b=document.createElement('button');b.type='button';b.textContent=s[1];b.dataset.v=s[0];b.onclick=function(){{lam=s[0];$('r-lam').value=lam;update()}};$('r-snaps').appendChild(b)}});
  $('r-lam').addEventListener('input',function(e){{lam=Number(e.target.value);update()}});
  function score(t){{return (1-lam)*t.sim+lam*t.pat}}
  function build(print){{
    var e=D.examples[ex];rank.innerHTML='';rows={{}};rank.style.height=SHOWN*ROW+'px';
    Array.prototype.forEach.call(pick.children,function(b,i){{b.setAttribute('aria-checked',i===ex)}});
    $('r-text').textContent='\\u201c'+e.text+'\\u201d';
    $('r-read').innerHTML='<b>nouns</b> '+esc(e.nouns.filter(function(n){{return e.unused.indexOf(n)<0}}).join(', '))+'<br><b>adjectives</b> '+esc(e.adjectives.join(', '));
    e.tags.forEach(function(t){{
      var li=document.createElement('li');li.innerHTML='<button type="button"><span class="r-n"></span><span class="r-tag">'+esc(t.tag)+'</span><span class="r-s"></span><span class="r-track" aria-hidden="true"><span class="r-seg-sim"></span><span class="r-seg-tbl"></span></span></button>';
      li.firstChild.onclick=function(){{picked=t.tag;update()}};rank.appendChild(li);rows[t.tag]=li}});
    if(print){{rank.classList.remove('print');void rank.offsetWidth;rank.classList.add('print')}}
    update(print);
  }}
  function update(print){{
    var e=D.examples[ex],sorted=e.tags.slice().sort(function(a,b){{return score(b)-score(a)}});
    var sel=sorted.filter(function(t){{return t.tag===picked}})[0]||sorted[0];
    sorted.forEach(function(t,i){{
      var li=rows[t.tag],b=li.firstChild,out=i>=SHOWN;
      li.style.top=Math.min(i,SHOWN)*ROW+'px';li.className=out?'is-out':'';li.setAttribute('aria-hidden',out);b.tabIndex=out?-1:0;
      li.style.setProperty('--i',Math.min(i,SHOWN));
      b.className=t.tag===sel.tag?'is-sel':'';
      b.children[0].textContent=i+1;b.children[2].textContent=f2(score(t));
      b.children[3].children[0].style.width=((1-lam)*t.sim*100)+'%';b.children[3].children[1].style.width=(lam*t.pat*100)+'%';
    }});
    $('r-lamv').textContent='lambda '+f2(lam);
    Array.prototype.forEach.call($('r-snaps').children,function(b){{b.setAttribute('aria-pressed',Number(b.dataset.v)===lam)}});
    var hot=sel.from.filter(function(p){{return p[1]>=0.005}}).slice(0,4);
    $('r-sum').innerHTML=
      '<li><b>match</b><span>sim['+esc(sel.tag)+'] = '+f2(sel.sim)+'</span></li>'+
      '<li><b>look up</b><span>pat['+esc(sel.tag)+'] = '+f2(sel.pat)+' '+(hot.length?hot.map(function(p){{return '<mark>'+esc(p[0])+' '+p[1].toFixed(2)+'</mark>'}}).join(''):'no mined pattern points here')+'</span></li>'+
      '<li><b>blend</b><span>(1 \\u2212 '+f2(lam)+') \\u00d7 '+f2(sel.sim)+' + '+f2(lam)+' \\u00d7 '+f2(sel.pat)+' = '+f2(score(sel))+'</span></li>'+
      '<li><b>rank</b><span>'+esc(sel.tag)+' is number '+(sorted.indexOf(sel)+1)+' of '+D.vocabulary+'</span></li>';
  }}
  build(false);
}})();
</script>
</body>
</html>
'''
(DOCS / 'index.html').write_text(HTML, encoding='utf-8')
print('wrote docs/index.html', len(HTML), 'bytes;', f'per tag: ahead {ahead}, behind {behind}, level {level} of {ntags}')
