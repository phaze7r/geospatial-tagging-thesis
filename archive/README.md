# Archive: building blocks, not part of the thesis

Everything in this folder is kept to record what was tried and why the work moved to the final approach.
**None of it produces a result reported in the thesis chapters on the final evaluation.** The thesis and its numbers
come from `thesisv2/` and `notebooks/thesisv2/` at the top of this repository.

| Folder | What it is | Status |
|---|---|---|
| `early_repo_2025/` | The first version of this repository (late 2025): Overpass collection for 12 Pakistani cities, a DistilBERT plus Bayesian-elastic-net feature classifier, a Flask dashboard. Its original README is `README_original.md`. | Superseded. Its claims were not evaluated under the frozen protocol of the final run and are not thesis results. The website it points to is offline. |
| `earlier_run_227/` | Notebooks 00 to 13 (preliminary study on Wikivoyage, then a full run on the base paper's 227-tag list), their result files, and the scoring scripts of the extended Pakistan set. | Superseded by `thesisv2/`. The thesis keeps it only as a consistency check (Section 6.6): Hits@3 0.189 to 0.380 on its own test split. |

## Why the work moved to the final approach

1. **The 227-tag list could not describe everyday places.** It has no clothes shop, convenience store, hairdresser
   or viewpoint, so a description of one of those could only receive a wrong tag. The final run builds a 408-tag
   vocabulary from OpenStreetMap by fixed rules.
2. **A classifier learned the label, not the place.** In the preliminary study a fine-tuned DistilBERT classifier
   reached 0.970 on its own weak labels and only 0.142 Hits@3 on paraphrased descriptions, because the weak labels
   came from the type word, which a paraphrase does not contain (thesis Sections 5.4 and 6.3). The final evaluation
   labels each description from its OpenStreetMap element and masks the tag words in the text.
3. **Settings were tuned on evaluation sets.** The preliminary study cross-validated the blend weight on the evaluation sets themselves. The final run fixes the
   vocabulary, splits, arms and settings on a development set, seals the test split, scores it once, and adds a
   control (M2: adjectives pasted into the query) next to the base method (M1) and this work (M3).
4. **The result held up.** The earlier run and the final run agree in direction and size (Hits@3 gain +0.191 on the
   227 tags, +0.182 on the 408 tags). The final numbers are 0.175, 0.161 and 0.357 for M1, M2 and M3 on the
   sealed OpenStreetMap test set, and the Pakistan primary subset goes from 0.286 to 0.509.

## One dependency of the final run

`thesisv2/scripts/s00_counts.py` reads the raw OpenStreetMap harvest (every element with a description tag, from
the QLever OSM planet endpoint). That harvest is made by cells R0a to R0e of
`earlier_run_227/notebooks/11_final_preregistered_run_osm.ipynb`, so that notebook is archived but not obsolete.

## How to read this folder

Notebooks here read and write Google Drive paths of the time (`/content/drive/MyDrive/geoproject/`) and are not
expected to run unchanged. They are kept as a record, with their outputs stripped.
