"""Build one .ipynb per passed step: header, the exact script as it ran, the run command. Usage: python make_notebooks.py s02_corpus.py [more scripts]
Header facts come from STEPS below; add a line per step once it passes. Run cells assume Colab with Drive mounted."""
import json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
STEPS = {  # script: (title, runtime, flags, pass result recorded in STATE.md)
    'c0_smoke_colab.py': ('C0 Colab smoke test', 'T4 15 GB, host RAM 12 GB', '', 'all checks true'),
    's00_counts.py': ('Step 0 counts per key=value', 'CPU, 12 GB (T4 session); needs py3langid==0.4.0', '', '7,377 key=value rows, 2,875,608 harvest rows'),
    's01_vocab_propose.py': ('Step 1a propose vocabulary', 'local CPU', '', '408 tags (floor 20, parking and pitch allowed)'),
    's01b_vocab_freeze.py': ('Step 1b freeze vocabulary', 'local CPU', '', '408 tags, 9 aliases, sha256 388f9fe6a74c48f0'),
    's02_corpus.py': ('Step 2 mapping, corpus, sealed test', 'CPU, 12 GB; needs py3langid==0.4.0', '', '89,702 rows, train 71,784 / dev 9,042 / test 8,876, 384 of 408 tags'),
    's03_extract.py': ('Step 3 extraction train and dev', 'L4 23 GB, host RAM 52 GB, 305 s', '', '80,826 rows, 67.9% with an adjective'),
    's04_embeddings.py': ('Step 4 embeddings', 'CPU work on the L4 session, 52 GB RAM', '', '404/408 tags with a vector, 93.2% dev nouns embeddable'),
    's05_dev_m1_m2.py': ('Step 5 M1 and M2 on dev', 'CPU work on the L4 session', '', 'dev Hits@3 M1 w2v 0.176, M2 w2v 0.169, M1 numberbatch 0.207, M2 numberbatch 0.193'),
    's06_mine_weight.py': ('Step 6a mining and weighting (support 0.0001)', 'A100 40 GB for the 500-draw run; G4 96 GB for the 1,000-draw refit', '--min-support 0.0001 (refit: --ben-only --ben-warmup 1000 --ben-samples 1000)', '2,916 patterns; refit R-hat max 1.006, ESS 2,838, 0 divergences, credible 0.04%'),
    's06b_learning_curves.py': ('Step 6b learning curves', 'G4 96 GB, block sampling, about 5 h for the last 2 fits', '--ben-warmup 1000 --ben-samples 1000 --max-ben-minutes 3000', 'Bayesian R-hat max 1.103 / 1.998 / 1.936 / 5.500 / 1.010 at 5k/10k/20k/40k/full; conf and FEN curves complete'),
    's07_dev_select_freeze.py': ('Step 7 dev selection (support 0.0001)', 'CPU work on the G4 session', '', 'M3 dev Hits@3 0.365, Hits@5 0.442; support 0.0001 kept'),
    's08_test_and_sets.py': ('Step 8 sealed test and evaluation sets (one shot)', 'L4 GPU session', '', 'test Hits@3 M1 0.175, M2 0.161, M3 0.357; eval_106 0.236 / 0.151 / 0.415; pk528 0.286 / 0.244 / 0.509'),
    's09_basics_check.py': ('Step 9 everyday basics check (48 sentences)', 'L4 GPU session', '', 'Hits@3 M1 0.5625, M2 0.4167, M3 0.5625; Hits@5 0.604 / 0.542 / 0.750'),
    's10a_blind_labels.py': ('Step 10a blind labelling file', 'same session as step 9', '', '100 rows written to report/blind_label_file.csv'),
    's11_report.py': ('Step 11 report', 'local, result files only', '', 'report/results_summary.md, results_summary.json, NUMBERS_TO_UPDATE.md'),
    's07b_fpgrowth_check.py': ('Step 7b guided vs extended FP-Growth on the OSM training corpus', 'CPU high-RAM session (colab new --high-mem, 50 GB); sizes 5k-40k first, then the full size alone', '(full size only: 0)', 'support 0.0005; identical (pattern, tag) itemsets at 5,000 / 10,000 / 20,000 / 40,000 / 71,784; full size guided 3.22 s vs extended 2,403 s, 1,835 MB'),
    's12_explanations_and_tables.py': ('Step 12 explanation coverage and thesis tables (never opens the test)', 'L4 session, CPU work', '', 'coverage of the top-ranked tag 32.0% dev / 44.3% 106 / 52.8% pk528; M3 ranks reproduced exactly on dev, 106 and pk528'),
}
md = lambda s: {'cell_type': 'markdown', 'metadata': {}, 'source': s.splitlines(True)}
code = lambda s: {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': s.splitlines(True)}
for script in sys.argv[1:]:
    title, rt, flags, res = STEPS[script]
    src = open(os.path.join(ROOT, 'scripts', script)).read()
    cells = [md(f'# thesisv2 {title}\n\nRuntime: {rt}\n\nPassed: {res}\n\nSource below is the exact script that ran (helpers: scripts/v2lib.py, config.py, common.py). Outputs in Drive thesisv2/ and ~/thesisv2/results.'),
             code('# Colab: mount Drive, then run the step\nfrom google.colab import drive; drive.mount("/content/drive")'),
             code(f'!python /content/drive/MyDrive/thesisv2/scripts/{script} {flags}'),
             md('## Script source (read-only copy)'), code('# ' + script + '\n' + src)]
    nb = {'cells': cells, 'metadata': {'kernelspec': {'name': 'python3', 'display_name': 'Python 3'}}, 'nbformat': 4, 'nbformat_minor': 5}
    out = os.path.join(os.path.dirname(__file__), script.replace('.py', '.ipynb')); json.dump(nb, open(out, 'w'), indent=1); print(out)
