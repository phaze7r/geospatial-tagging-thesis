# Bayesian elastic net at min_support 0.0001: attempts, fixes, results

Setting: 2,916 patterns x 384 classes, NUTS, 2 chains. Each stored draw array is patterns x classes x chains x draws x 4 bytes (8.96 GB at 1,000 draws). Facts below come from logs in Drive thesisv2/logs and STATE.md.

| # | Date | Step | Hardware | Settings | Result | Cost |
|---|---|---|---|---|---|---|
| 1 | 2026-10-25 | 6a | A100 40 GB | 500 warmup, 500 draws | Ran. FAILED the gate: R-hat max 1.079 (limit 1.05), ESS median 310, 0 divergences, 9,360 s | about 2.6 h |
| 2 | 2026-10-25 | 6a refit | A100 40 GB | 1,000 warmup, 1,000 draws | GPU OUT OF MEMORY at the final copy (jit_swapaxes, 8.34 GiB) | minutes |
| 3 | 2026-10-25 | 6a refit | A100 40 GB | same, plus XLA_PYTHON_CLIENT_MEM_FRACTION=0.95 | FAILED at start: XLA allocator abort "spatial partitioning expects one central gap". Setting removed | minutes |
| 4 | 2026-10-25 | 6a refit | A100 40 GB | 1,000 warmup, 700 draws | Started, then stopped by me: a pass at 700 would not answer the 1,000-draw question | about 15 min |
| 5 | 2026-10-25 | 6a refit | G4 (RTX PRO 6000, 96 GB) | 1,000 warmup, 1,000 draws | VM dropped by Colab about 28 min in (my 10-minute polling gap, detached process counted as idle). Run lost | about 4 to 5 units |
| 6 | 2026-10-25 | 6a refit | G4 | 1,000 warmup, 1,000 draws, checks every 4 min | PASSED: R-hat max 1.006, ESS median 2,838, 0 divergences, credible 0.04%, 8,803 s | about 22 units |
| 7 | 2026-10-25 | 6b learning curves | G4 | 1,000/1,000, all 5 sizes | 5k fit PASSED to run (4,768 s, R-hat max 1.103, not converged, saved). 5k fit completed and saved (4,768 s, R-hat max 1.103). The 2nd fit (10k) then ran out of GPU memory at its final copy (8.34 GiB) after 1h28 | about 13 units |
| 8 | 2026-10-25 | 6b | G4 | same, on-demand GPU allocation (XLA_PYTHON_CLIENT_PREALLOCATE=false), 5k reused | 10k fit completed and saved (5,220 s, R-hat max 1.998, 0 div). The 2nd fit (20k) then ran out of GPU memory, same error, after 1h28 | about 13 units |
| 9 | 2026-10-26 | 6b | G4 | same, XLA_PYTHON_CLIENT_MEM_FRACTION=0.90 plus PREALLOCATE=false (cap 85.5 GiB) | 20k fit completed and saved (6,147 s, R-hat max 1.936, 0 div). The 2nd fit (40k) then ran out of GPU memory, same error, after 1h45. GPU memory reached 88 GB in the final phase | about 16 units |

## Code change made along the way
scripts/s06b_learning_curves.py: each Bayesian fit is saved to tables/ben_lc_<patterns>p_<warmup>_<draws>_<n>.npz and reused on rerun, so a dropped session costs one fit, not the whole run. Smoke test passed and the resume path was checked. No change to the method or the numbers.

## Code change 2 (approved by the user after attempt 9)
scripts/v2lib.py fit_ben: the 1,000 draws are taken in 4 blocks of 250 on the same chains and each block is moved to host memory. Tests: pytest 9 passed, smoke_local SMOKE RUN COMPLETE.

## Attempt 10 final result (2026-10-26 08:24): SUCCESS
6b finished with exit 0 on the G4 with block sampling. Bayesian fits at 5k, 10k, 20k, 40k and 71,784 rows are all present in results/learning_curves.json. Full-size fit with block sampling: 8,831 s, R-hat max 1.010, 0 divergences, credible share 0.04%, matching the unblocked 6a refit (1.006, 0.04%): the control passes, block sampling is sound. Slice R-hat max: 1.103 (5k), 1.998 (10k), 1.936 (20k), 5.500 (40k), 1.010 (full). Train-dev gap of the Bayesian net stays within 0.002 at all sizes. The stop rule (cap 08:45) was not needed.

## Stop rule set by the user (2026-10-26 06:00)
Do not spend the compute budget on this. Final 6b fit (71,784 rows, started 05:52): hard cap 08:45; on any failure or after the cap, stop, rerun s06b with --max-ben-minutes 600 (reloads the saved 5k, 10k, 20k and 40k fits, skips the full-size Bayesian fit, writes learning_curves.json), use the converged 6a refit as the full-size Bayesian point, stop the VM, and continue the pipeline.

## Attempt 10 result so far
40k fit completed with block sampling: 9,060 s, R-hat max 5.500, 0 divergences, credible 0.01%. Slice R-hats so far: 1.103 (5k), 1.998 (10k), 1.936 (20k), 5.500 (40k); the full-size 6a refit was 1.006. The last 6b fit (71,784 rows, same data and seed as that refit) is the control for the block sampling.

## Correction (2026-10-26, found in the log)
Attempts 7 to 9 were first described as failing again at the 10k fit. The log shows each completed one new fit before failing: 5k, 10k and 20k are saved. The real pattern: the SECOND Bayesian fit in a process always ran out of GPU memory, the FIRST always passed (also the 6a refit, a single fit). So device memory from the first fit is not released. Attempt 10 relaunched with block sampling; 5k, 10k, 20k reused, 40k is the first fit of the new process.

## What we learned
- Memory cap: JAX limits itself to 71.2 GiB on the 96 GB card (default fraction 0.75), even with on-demand allocation. A scratch test at real size (384 classes, 1,000 draws, tree depth 2) peaked at 50 GiB and passed at fraction 0.90 (cap 85.5 GiB).
- The out-of-memory happens only at the end of a fit, so every failed attempt costs the whole fit time.
- With 500 draws the Bayesian fit does not converge at 2,916 patterns. With 1,000 draws the full-size fit converges (attempt 6). The 5,000-row slice does not converge even at 1,000 draws (R-hat 1.103).
- Colab drops a VM that shows no kernel activity for about 30 minutes while a detached job runs. Poll every 4 minutes.

## Attempt 9 failed: options for the user (none applied yet)
Why the scratch test misled: it passed at 50 GiB peak with a shallow sampler (tree depth 2). The real run (depth 10) sits at about 67 GB during sampling, and the end-of-fit copy needs about 20 GB more than the larger cap allows. The cause of the extra memory during real sampling is not identified.

0. Recommended: sample in blocks. After warmup, run 4 blocks of 250 draws with the same chains (numpyro post_warmup_state), move each block to host memory, and join them. Same sampler, same chains, same 1,000 draws, one quarter of the device memory. A change inside fit_ben, so it needs approval. Check it first with a short scratch run.
1. Keep the saved fits (5k, and the 6a full-size refit) and report the Bayesian learning curve with the sizes that completed, plus the confidence-table and frequentist curves at all 5 sizes (they finished in seconds).
2. Reduce what is stored: keep only the weights array on the device (a change inside fit_ben), or run the two chains one after the other. This changes memory handling, not the model, and needs approval.
3. Report the Bayesian net at the earlier support of 0.0005, where 500 draws converged (R-hat 1.016, 680 patterns). This mixes two supports and needs approval.
4. Skip the Bayesian learning curve and state it plainly in the thesis as not run because of GPU memory limits at this model size.
