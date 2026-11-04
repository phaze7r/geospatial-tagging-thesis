"""Step 11: hand-off report. Reads the result files and writes report/results_summary.json, report/results_summary.md and report/NUMBERS_TO_UPDATE.md.
Every number is copied from a result file. Updating the thesis, paper, decks, pages and app from this report is a separate task."""
from v2lib import *


def load(name):
    p = P('results', name); return jload(p) if os.path.exists(p) else None


def fmt(x, nd=3): return '' if x is None else f'{x:.{nd}f}'


def main():
    F, S07, S05, LC, S06, S09 = load('final.json'), load('s07_dev_selection.json'), load('s05_dev_m1_m2.json'), load('learning_curves.json'), load('s06_fit_diagnostics.json'), load('s09_basics.json')
    stats = jload(P('corpus', 'split_stats.json')); fz = jload(FROZEN) if os.path.exists(FROZEN) else None
    L = ['# thesisv2 results summary', '', f'Vocabulary: {stats["vocabulary_tags"]} tags ({stats["tags_in_corpus"]} with corpus rows). Corpus rows {stats["rows"]:,}; split {stats["split_counts"]}.',
         f'Min support {S06["min_support"]}, {S06["patterns"]} patterns ({S06["adjectives"]} adjectives, {S06["pairs"]} pairs).', '']
    if F:
        names = {k: v for k, v in (fz or {}).get('arm_names', {}).items()}
        L += ['## Three methods, Hits@3 and Hits@5 (same vocabulary, same split)', '', '| set | n | M1 base (nouns) H@3 | M2 adj-noun plain H@3 | M3 ours H@3 | M1 H@5 | M2 H@5 | M3 H@5 |', '|---|---|---|---|---|---|---|---|']
        for s in F['sizes']:
            if s == 'osm_dev': continue
            r = [F['arms'][names[k]][s] for k in ('M1', 'M2', 'M3') if names.get(k) in F['arms']]
            if len(r) == 3: L.append(f'| {s} | {r[0]["n"]} | ' + ' | '.join(fmt(x['Hits@3']) for x in r) + ' | ' + ' | '.join(fmt(x['Hits@5']) for x in r) + ' |')
        L += ['', '## Comparisons (Hits@3; paired bootstrap 95% CI, exact McNemar, Holm within family)', '', '| set | a | b | delta | 95% CI | p (Holm) | family |', '|---|---|---|---|---|---|---|']
        for c in F['comparisons']:
            if c['set'] in ('osm_test', 'eval_106', 'pk528', 'eval_106_auto', 'osm_test_pakistan'): L.append(f"| {c['set']} | {c['a']} | {c['b']} | {c['delta_hits3']:+.3f} | [{c['ci95'][0]:+.3f}, {c['ci95'][1]:+.3f}] | {c['p_holm']:.4f} | {c['family']} |")
        L += ['', '## Base paper, published (reference only: their list, their 106 sentences, no Hits@3)', '', json.dumps(F['reference_base_paper_published']['values'])]
        L += ['', '## Everyday vs tourism tags (Hits@3)', '', '```', json.dumps(F['breakdown'], indent=1), '```']
    if LC:
        L += ['', '## Learning curves (dev-chosen lambda)', '', '| model | n train | train H@3 | dev H@3 | gap |', '|---|---|---|---|---|']
        for a, rows in LC['curves'].items():
            for r in rows: L.append(f'| {a} | {r["n_train"]:,} | {fmt(r["train_hits3"])} | {fmt(r["dev_hits3"])} | {r["gap"]:+.3f} |')
    if S06 and 'ben' in S06: L += ['', '## Bayesian elastic net fit', '', '```', json.dumps(S06['ben'], indent=1), '```']
    if S09: L += ['', '## Everyday-basics check (48 sentences written before the test run)', '', '```', json.dumps(S09['summary'], indent=1), '```']
    for nm, f in (('Independent labels', 's10_independent_labels.json'), ('Open LLM comparator', 's10c_llm_comparator.json')):
        d = load(f)
        if d: L += ['', f'## {nm}', '', '```', json.dumps({k: v for k, v in d.items() if k != 'rows'}, indent=1)[:3000], '```']
    open(P('report', 'results_summary.md'), 'w').write('\n'.join(L) + '\n')
    jdump({'final': F, 'dev': S07, 'm1_m2_dev': S05, 'learning_curves': LC, 'fit': S06, 'basics': S09, 'corpus': stats, 'protocol_sha256': sha256_file(FROZEN) if fz else None}, P('report', 'results_summary.json'))
    todo = ['# Numbers and text to update later (separate task, after the user reviews report/results_summary.md)', '',
            '- Thesis draft (`~/thesis-writeup/finalosmdraft.md`, then build v20): abstract; 1.3 RQ wording unchanged; 4.2.4-4.2.7 (vocabulary, Pakistan = 528 only, 157 removed); 4.5.2 and a new learning-curve section;',
            '  4.9 corpus v2 (funnel, tags, split); Chapter 5 (3-method table, ablations, Pakistan 528, multilingual, basics check); 6.2, 6.4, 6.5 (limitations: vocabulary and learning curve resolved or restated); 7.1, 7.2; Appendix A (new vocabulary + aliases).',
            '- Tables: 4.4 (set statistics), 4.14 (baselines), 5.x results and ablation, A.1 vocabulary; figures: pipeline figure tag count, learning-curve figure (results/learning_curves.png).',
            '- Paper (`paper/paper_ijgi.md`), defence decks (HTML + PowerPoint), scroll page, Q&A page, repository README and results/, place-tagger (new tables, lexicon, tests, README, tag count in the UI text and About).',
            '- Every statement that says 227 tags, 165 tags, 0.189 to 0.380, 0.381 to 0.545, 2,489x (unchanged), 657 patterns, lambda 0.50.']
    open(P('report', 'NUMBERS_TO_UPDATE.md'), 'w').write('\n'.join(todo) + '\n')
    manifest('s11', [], [P('report', 'results_summary.md'), P('report', 'results_summary.json'), P('report', 'NUMBERS_TO_UPDATE.md')]); print('wrote report/')


if __name__ == '__main__': main()
