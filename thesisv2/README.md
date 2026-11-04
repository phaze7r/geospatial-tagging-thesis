# thesisv2: the final evaluation of the thesis (v20)

The final evaluation reported in the thesis (Chapter 5) and the journal draft. It reruns the whole pipeline
on the thesis's own vocabulary of 408 OpenStreetMap place tags, built from the map data, and compares three
methods on identical splits:

- **M1**, the base method of Yousaf et al. (2023): context nouns, Word2Vec similarity;
- **M2**, M1 with every extracted adjective added to the similarity query (no mining);
- **M3**, this thesis: guided FP-Growth, the confidence table, Numberbatch similarity, blend weight 0.45.

| Set | n | M1 | M2 | M3 | M3 − M1, Holm p |
|---|---|---|---|---|---|
| OSM test (sealed until step 8, scored once) | 8,876 | 0.175 | 0.161 | 0.357 | +0.182, < 0.0001 |
| Base paper's sentences | 106 | 0.236 | 0.151 | 0.415 | +0.179, 0.007 |
| Pakistan set, primary subset (post hoc) | 528 | 0.286 | 0.244 | 0.509 | +0.223, < 0.0001 |

Hits@3. All figures are in `results/final.json`; `report/results_summary.md` lists them in one place.

## Layout

```
scripts/     step scripts c0, s00 to s12 (one per step, run in order) and their helpers config.py, common.py, v2lib.py
protocol/    the vocabulary (lexicon_v2.txt, map, aliases, the reviewed draft) and PROTOCOL_FROZEN.json
results/     one JSON per step, including the FP-Growth check (s07b) and the explanation tables (s12)
report/      results summary, data and compute notes, the 100-row independent labelling files
RUNBOOK.md   step table, commands and pass criteria      PROVENANCE.md   where each function comes from
BAYESIAN_ATTEMPTS.md   every attempt to fit the Bayesian elastic net, including the failed ones
```

The step notebooks in `../notebooks/thesisv2/` hold the same scripts with their run commands and the result
each step passed with. The scripts import `pipeline_ranker.py` and `adjective_extractor.py` from `../src/`
(byte-identical copies). The corpus, the extracted features, the embedding caches and the fitted tables are
large and are not in this repository; `RUNBOOK.md` gives the command that rebuilds each of them, and every
step writes a manifest with the sha256 of its inputs and outputs.

Notebooks `../notebooks/00` to `13` are the earlier work (the preliminary Wikivoyage study and an earlier
run on the base paper's 227 tags) and are kept unchanged; the thesis reports that earlier run in Section 6.6.
