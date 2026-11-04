#!/usr/bin/env python3
"""Fills the block between the results markers of README.md from thesisv2/report/tables/*.csv and thesisv2/results/*.json.
Run from anywhere: python tools/build_readme.py"""
import csv, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAB = ROOT / 'thesisv2/report/tables'
fpg = json.loads((ROOT / 'thesisv2/results/s07b_fpgrowth_check.json').read_text())


def md(name, align_from=1):
    with open(TAB / f'{name}.csv', newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    head, body = rows[0], rows[1:]
    sep = ['---' if i < align_from else '---:' for i in range(len(head))]
    return '\n'.join('| ' + ' | '.join(r) + ' |' for r in [head, sep] + body)


last = fpg[-1]
fp_rows = '\n'.join(f"| {x['transactions']:,} | {x['guided']['pattern_tag_itemsets']} | {x['extended']['pattern_tag_itemsets']} | {'yes' if x['identical'] else 'NO'} |" for x in fpg)

BLOCK = f'''<!-- results:start (written by tools/build_readme.py; edit the script, not this block) -->
## All results

Every number below is read from `thesisv2/results/` and `thesisv2/report/tables/`. Hits@3 is the headline metric; the thesis
gives the full tables and the statistics.

### All metrics, three methods

{md('main_results', 3)}

### Where the gain comes from (Hits@3, cumulative steps)

{md('ablation_stage')}

A2 is the control: the adjectives are pasted into the similarity query and nothing is mined. The jump at A3 is the contribution.

### Per tag on the Pakistan set

![Hits@3 per tag, M1 and M3, Pakistan primary subset](docs/fig_per_tag.png)

The pooled gain is not a gain for every tag: M3 is ahead on 13 of 37 tags, behind on 13 and level on 11. It loses on tags with no
training text (shrine, lake, hill) and where the nouns already said it.

### Guided against extended FP-Growth

Pattern-to-tag itemsets at minimum support {last['min_support']} (the pipeline itself uses 0.0001, where extended FP-Growth does not finish):

| Transactions | Guided | Extended | Identical |
|---:|---:|---:|---|
{fp_rows}

On the full {last['transactions']:,} transactions guided mining took {last['guided']['seconds']:.2f} s, extended FP-Growth {last['extended']['seconds']:,.0f} s and {last['extended']['peak_mb']:,.0f} MB: {last['extended']['seconds'] / last['guided']['seconds']:.0f} times slower. (Timings of the two smallest extended runs were inflated by a duplicate job and are not quoted.)

### The Bayesian elastic net

{md('bayes_diag')}

As the ranker it costs 0.075 Hits@3 on the test set, so it supplies the explanations while the confidence table ranks.

| Set | n | Gold-tag credible pattern | Top-ranked tag has a credible pattern |
|---|---:|---:|---:|
''' + '\n'.join(f"| {r['Set']} | {r['n']} | {r['Gold tag has a credible pattern']} | {r['Top-ranked tag has a credible pattern']} |" for r in csv.DictReader(open(TAB / 'coverage.csv', encoding='utf-8'))) + f'''

### Minimum support

{md('support')}

![Development Hits@3 against minimum support](docs/fig_support.png)

### Urdu and Roman Urdu, through translation

{md('multilingual', 2)}

### The earlier run on the base paper's 227 tags

{md('earlier_run')}

### Data

{md('corpus_funnel')}

{md('vocab_blocks')}

![Tags of the vocabulary by number of training descriptions](docs/fig_tag_distribution.png)
<!-- results:end -->'''

p = ROOT / 'README.md'
s = p.read_text(encoding='utf-8')
if '<!-- results:start' in s:
    s = re.sub(r'<!-- results:start.*?<!-- results:end -->', lambda m: BLOCK, s, flags=re.S)
else:
    s = s.replace('## Repository layout', BLOCK + '\n\n## Repository layout', 1)
p.write_text(s, encoding='utf-8')
print('README results block written,', len(BLOCK), 'chars')
