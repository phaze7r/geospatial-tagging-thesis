# RUNBOOK: how to run thesisv2 (the code is complete; run it, debug it, do not redesign it)

All commands run from `~/thesisv2`. Local driver: `python scripts/colab_step.py ...` (wraps the Colab CLI; untested until C0).
Compute: Colab Pro. Heavy steps use the best GPU the account grants (A100, then L4, then T4); counts, mapping, tables and the report run on CPU.
`colab stop` right after each heavy step. Record the granted GPU/RAM and the units used in STATE.md.

## Before anything: local smoke (5 to 15 minutes, CPU, no Colab)
```
source .venv-smoke/bin/activate
python tests/smoke_local.py            # whole chain on synthetic data -> smoke/ ; must end with SMOKE RUN COMPLETE
THESISV2_SMOKE=1 pytest tests/test_v2lib.py
```
The smoke run needs the place-tagger venv for spaCy (already wired through PYTHONPATH in the script). Same chain on Colab CPU: add `--smoke` to any step.

## Step table
| Step | Script (+ flags) | Runtime | Reads | Writes (Drive thesisv2/) | Pass looks like |
|---|---|---|---|---|---|
| C0 | `c0_smoke_colab.py` | any | Drive inputs | manifests/c0.json | all checks true; note GPU, RAM |
| 0 | `s00_counts.py` | CPU, high RAM | old Drive `osmfinal/raw/osm_descriptions.parquet` | data/vocab_candidates.csv | pairs listed, per-key table printed. **GATE: user reads it** |
| 1a | `s01_vocab_propose.py` | CPU | vocab_candidates.csv | protocol/lexicon_v2_draft.csv | prints tag count, thin must-haves, gold coverage. User edits `include`, `canonical` |
| 1b | `s01b_vocab_freeze.py` (`--allow-short` only if the user accepts fewer than 400) | CPU | draft | protocol/lexicon_v2.txt, lexicon_v2_map.csv, lexicon_v2_aliases.csv | vocabulary frozen, every gold tag resolves. **GATE: user signed off** |
| 2 | `s02_corpus.py` | CPU, high RAM | raw parquet, map | corpus/osm_traindev.parquet, osm_test_sealed.parquet, split_stats.json | funnel printed, no group overlap, test hash stored |
| 3 | `s03_extract.py` | GPU | traindev | extracted/osm_traindev_extracted.parquet | rows extracted; resumable by chunks |
| 4 | `s04_embeddings.py` | CPU, high RAM (gensim ~4 GB) | extracted, old caches | embeddings/w2v_v2.pkl, nb_v2.pkl, results/s04_vector_coverage.json | tags with vector ~100% |
| 5 | `s05_dev_m1_m2.py` | CPU | extracted, embeddings | results/s05_dev_m1_m2.json | M1, M2 dev numbers |
| 6a | `s06_mine_weight.py` (`--fen-grid`, `--skip-ben`, `--ben-only` (same support only), `--ben-samples N`) | GPU for the Bayesian fit | extracted | tables/*.npz, results/s06_fit_diagnostics.json | patterns counted; BEN: 0 divergences, R-hat <= 1.05 |
| 6b | `s06b_learning_curves.py` (`--no-fen`, `--no-ben`, `--max-ben-minutes M`) | GPU | tables, X | results/learning_curves.json + .png | train and dev curves, gaps |
| 7 | `s07_dev_select_freeze.py` (`--small-parser` optional) | CPU | all dev inputs | results/s07_dev_selection.json | adoption gates; if it exits 2 it names `--min-support X`: rerun 6a, 6b, 7 |
| 7b | `s07b_fpgrowth_check.py` (REQUIRED: guided vs extended FP-Growth, thesis claim) | CPU | extracted | results/s07b_fpgrowth_check.json | guided = extended itemsets |
| 7f | `s07_dev_select_freeze.py --freeze` | CPU | same | protocol/PROTOCOL_FROZEN.json | **GATE: only after the user confirms** |
| 8 | `s08_test_and_sets.py` | GPU | frozen protocol, sealed test | results/final.json, ranks_final.npz, protocol/TEST_SCORED.flag | dry run passed, test opened once, comparisons printed |
| 9 | `s09_basics_check.py` | GPU or CPU | basics_test.json | results/s09_basics.json | top-5 per sentence, hits |
| 10a/b | `s10a_blind_labels.py`, `s10b_kappa.py file.csv` (optional) | CPU | | report/blind_label_file.csv, results/s10_independent_labels.json | |
| 10c | `s10c_llm_comparator.py` (optional) | GPU | | results/s10c_llm_comparator.json | |
| 12 | `s12_explanations_and_tables.py` (thesis v20 helper; never opens the test) | CPU or GPU, high RAM (Numberbatch ~4 GB) | frozen models, ranks_final.npz | results/s12_explanations_and_tables.json | coverage of credible patterns, examples, top rules, strongest weights, fixed/broken, per-tag |
| 11 | `s11_report.py` | CPU | all results | report/results_summary.md/json, NUMBERS_TO_UPDATE.md | |

## Colab commands (per step)
```
python scripts/colab_step.py new A100         # or L4 / T4; no argument = CPU. Mounts Drive.
python scripts/colab_step.py push             # copies scripts, src, data/inputs, basics_test.json into Drive thesisv2/ (repeat after any local fix)
python scripts/colab_step.py launch c0_smoke_colab.py
python scripts/colab_step.py tail c0_smoke_colab     # wait for EXIT_CODE 0
python scripts/colab_step.py launch s03_extract.py
python scripts/colab_step.py tail s03_extract 30
python scripts/colab_step.py pull results/final.json # copy a result file to ~/thesisv2/results/
python scripts/colab_step.py stop
```
Requirements on a fresh VM (the scripts install what they need at run time: gensim, numpyro, mlxtend, spaCy model). If a library is missing: `colab install pandas pyarrow scikit-learn py3langid==0.4.0 matplotlib`.
Fallback if the CLI cannot mount Drive headless: colab-mcp in the browser, paste `bootstrap_thesisv2.py` into a cell, then `!python /content/drive/MyDrive/thesisv2/scripts/<step>.py`.

## Rules for debugging
- Fix the smallest thing. Do not change the method, the metrics, the arms, the seal or the protocol logic. Log every fix in STATE.md (file, line, why).
- A step that fails midway can be rerun: manifests and chunked outputs are overwritten or resumed. Never delete `protocol/TEST_SCORED.flag` or `PROTOCOL_FROZEN.json`.
- If a number cannot be reproduced or a gate fails, stop and tell the user.
- If step 7 asks for a lower `--min-support` (the old dev run preferred 0.0002 to 0.0001, which gives about 1,500 to 3,000 patterns), the Bayesian fit grows with patterns x tags: check device memory first (`colab_step.py status`), use `--ben-samples 250` if needed and record it.
- Memory: the Bayesian fit stores 3 sites x chains x draws x patterns x tags floats on the device. If it runs out of memory: `--ben-samples 250`, or a larger GPU, and say so in STATE.md.
