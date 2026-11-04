# Provenance: where each piece of code comes from (for audit)
N11 = `adjective-aware-osm-tagging/notebooks/11_final_preregistered_run_osm.ipynb`, N12 = `12_ablation_osm.ipynb`, PKS = `thesis-writeup/pk_extension/colab_score_extended.py`.

| thesisv2 | Source | Change |
|---|---|---|
| src/pipeline_ranker.py, src/adjective_extractor.py | repo src/ (byte-identical to Drive; sha256 checked by C0) | none |
| v2lib.tag_of, eff_value | N11 R1b (EXTRA, RELIGION) | key+value mapping through the signed-off table |
| v2lib.sim_matrix, table_matrix, ranks, mets, boot, pick_lambda | N11 R5a, R6, R7; N12 AB0 | Hits@2/5/10/20 added; M2 = `naive=True` (N12 mode 'naive') |
| v2lib.mine, featurize, assoc, prep | N11 R3, R4a; N12 AB0 | none |
| v2lib.fit_fen, fit_ben | N11 R4a, R4b | percentiles chunked for K near 500; returns diagnostics |
| v2lib.Runner, ablation_arms, ABLATION_COMPARISONS | N12 AB0, AB1, comparisons of ablation.json | arm names kept; works on any set list |
| v2lib.compare, holm | PKS S4 | |
| v2lib.extend_vectors | N11 R5-cache-w2v, R5-cache-nb; PKS S1 | |
| s00, s01, s01b | new (vocabulary rules, written 2026-10-24) | |
| s02_corpus | N11 R1b, R1c, R1d | new salt, key+value mapping, test written to its own file |
| s03_extract | N11 R2 | chunked and resumable |
| s04_embeddings | N11 R5-pre, R5-cache | |
| s05_dev_m1_m2 | N12 arms A0, A2, base | |
| s06_mine_weight | N11 R3, R4a, R4b | |
| s06b_learning_curves | N11 R5b | fractions 5k to full; Bayesian arm and diagnostics added |
| s07_dev_select_freeze | N11 R5a, R6; N12 AB1, AB2, AB3 | support re-tuning rule, freeze written to protocol/PROTOCOL_FROZEN.json |
| s07b_fpgrowth_check | N12 AB4 | |
| s08_test_and_sets | N11 R7; PKS S0 to S4 | three-method comparison, Hits@5, Holm per family, stored translations |
| s09, s10a/b/c, s11 | new | s10c follows PKS S3 model loading |
Reference numbers of the base paper (config.BASE_PAPER_PUBLISHED) come from memory note base-papers-yousaf-osm-tagging (Tables 4 and 5 of the paper).
