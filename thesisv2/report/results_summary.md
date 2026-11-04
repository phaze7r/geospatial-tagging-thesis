# thesisv2 results summary

Vocabulary: 408 tags (384 with corpus rows). Corpus rows 89,702; split {'train': 71784, 'dev': 9042, 'test': 8876}.
Min support 0.0001, 2916 patterns (1393 adjectives, 1523 pairs).

## Three methods, Hits@3 and Hits@5 (same vocabulary, same split)

| set | n | M1 base (nouns) H@3 | M2 adj-noun plain H@3 | M3 ours H@3 | M1 H@5 | M2 H@5 | M3 H@5 |
|---|---|---|---|---|---|---|---|
| osm_test | 8876 | 0.175 | 0.161 | 0.357 | 0.238 | 0.224 | 0.428 |
| osm_test_pakistan | 27 | 0.222 | 0.222 | 0.333 | 0.259 | 0.296 | 0.481 |
| eval_106 | 106 | 0.236 | 0.151 | 0.415 | 0.340 | 0.264 | 0.547 |
| eval_106_auto | 106 | 0.283 | 0.189 | 0.415 | 0.406 | 0.330 | 0.547 |
| pk528 | 528 | 0.286 | 0.244 | 0.509 | 0.386 | 0.371 | 0.585 |
| pk_second_round_357 | 357 | 0.266 | 0.224 | 0.529 | 0.373 | 0.331 | 0.599 |
| pk_first_round_rows_171 | 171 | 0.327 | 0.287 | 0.468 | 0.415 | 0.456 | 0.556 |
| pk_without_uncertain_395 | 395 | 0.337 | 0.284 | 0.577 | 0.441 | 0.420 | 0.653 |
| pk_without_type_word_525 | 525 | 0.284 | 0.244 | 0.507 | 0.385 | 0.370 | 0.583 |
| urdu_157_translated | 157 | 0.287 | 0.306 | 0.471 | 0.369 | 0.389 | 0.573 |
| roman_300_translated | 300 | 0.283 | 0.250 | 0.443 | 0.367 | 0.370 | 0.550 |
| roman_author_60_translated | 60 | 0.350 | 0.267 | 0.583 | 0.433 | 0.483 | 0.767 |
| roman_drafted_240_translated | 240 | 0.267 | 0.246 | 0.408 | 0.350 | 0.342 | 0.496 |
| urdu_157_english | 157 | 0.331 | 0.287 | 0.490 | 0.420 | 0.459 | 0.567 |
| roman_300_english | 300 | 0.287 | 0.247 | 0.473 | 0.373 | 0.373 | 0.553 |
| roman_author_60_english | 60 | 0.400 | 0.333 | 0.717 | 0.500 | 0.600 | 0.800 |
| roman_drafted_240_english | 240 | 0.258 | 0.225 | 0.412 | 0.342 | 0.317 | 0.492 |

## Comparisons (Hits@3; paired bootstrap 95% CI, exact McNemar, Holm within family)

| set | a | b | delta | 95% CI | p (Holm) | family |
|---|---|---|---|---|---|---|
| osm_test | M3 our pipeline: conf table + numberbatch | M1 base paper: nouns only (w2v) | +0.182 | [+0.172, +0.192] | 0.0000 | prereg |
| osm_test | M3 our pipeline: conf table + numberbatch | M2 adjective-noun plain (w2v) | +0.196 | [+0.186, +0.206] | 0.0000 | prereg |
| osm_test | M2 adjective-noun plain (w2v) | M1 base paper: nouns only (w2v) | -0.014 | [-0.019, -0.010] | 0.0000 | prereg |
| osm_test | M3 our pipeline: conf table + numberbatch | M3w M3 with word2vec | +0.028 | [+0.022, +0.034] | 0.0000 | prereg |
| osm_test | X2 Bayesian EN as ranker | M3 our pipeline: conf table + numberbatch | -0.075 | [-0.083, -0.068] | 0.0000 | prereg |
| osm_test | X1 frequentist EN as ranker | M3 our pipeline: conf table + numberbatch | -0.018 | [-0.024, -0.011] | 0.0000 | prereg |
| osm_test_pakistan | M3 our pipeline: conf table + numberbatch | M1 base paper: nouns only (w2v) | +0.111 | [-0.111, +0.333] | 1.0000 | posthoc |
| osm_test_pakistan | M3 our pipeline: conf table + numberbatch | M2 adjective-noun plain (w2v) | +0.111 | [-0.111, +0.333] | 1.0000 | posthoc |
| osm_test_pakistan | M2 adjective-noun plain (w2v) | M1 base paper: nouns only (w2v) | +0.000 | [+0.000, +0.000] | 1.0000 | posthoc |
| osm_test_pakistan | M3 our pipeline: conf table + numberbatch | M3w M3 with word2vec | -0.037 | [-0.222, +0.148] | 1.0000 | posthoc |
| osm_test_pakistan | X2 Bayesian EN as ranker | M3 our pipeline: conf table + numberbatch | -0.037 | [-0.222, +0.148] | 1.0000 | posthoc |
| osm_test_pakistan | X1 frequentist EN as ranker | M3 our pipeline: conf table + numberbatch | +0.111 | [+0.000, +0.222] | 1.0000 | posthoc |
| eval_106 | M3 our pipeline: conf table + numberbatch | M1 base paper: nouns only (w2v) | +0.179 | [+0.075, +0.283] | 0.0066 | prereg |
| eval_106 | M3 our pipeline: conf table + numberbatch | M2 adjective-noun plain (w2v) | +0.264 | [+0.170, +0.358] | 0.0000 | prereg |
| eval_106 | M2 adjective-noun plain (w2v) | M1 base paper: nouns only (w2v) | -0.085 | [-0.151, -0.019] | 0.0851 | prereg |
| eval_106 | M3 our pipeline: conf table + numberbatch | M3w M3 with word2vec | +0.028 | [-0.009, +0.075] | 0.7500 | prereg |
| eval_106 | X2 Bayesian EN as ranker | M3 our pipeline: conf table + numberbatch | -0.094 | [-0.170, -0.019] | 0.0851 | prereg |
| eval_106 | X1 frequentist EN as ranker | M3 our pipeline: conf table + numberbatch | -0.009 | [-0.075, +0.066] | 1.0000 | prereg |
| eval_106_auto | M3 our pipeline: conf table + numberbatch | M1 base paper: nouns only (w2v) | +0.132 | [+0.019, +0.245] | 1.0000 | posthoc |
| eval_106_auto | M3 our pipeline: conf table + numberbatch | M2 adjective-noun plain (w2v) | +0.226 | [+0.113, +0.340] | 0.0182 | posthoc |
| eval_106_auto | M2 adjective-noun plain (w2v) | M1 base paper: nouns only (w2v) | -0.094 | [-0.160, -0.038] | 0.3618 | posthoc |
| eval_106_auto | M3 our pipeline: conf table + numberbatch | M3w M3 with word2vec | +0.019 | [-0.047, +0.085] | 1.0000 | posthoc |
| eval_106_auto | X2 Bayesian EN as ranker | M3 our pipeline: conf table + numberbatch | -0.123 | [-0.208, -0.047] | 0.3959 | posthoc |
| eval_106_auto | X1 frequentist EN as ranker | M3 our pipeline: conf table + numberbatch | +0.009 | [-0.066, +0.085] | 1.0000 | posthoc |
| pk528 | M3 our pipeline: conf table + numberbatch | M1 base paper: nouns only (w2v) | +0.223 | [+0.174, +0.273] | 0.0000 | posthoc |
| pk528 | M3 our pipeline: conf table + numberbatch | M2 adjective-noun plain (w2v) | +0.265 | [+0.214, +0.314] | 0.0000 | posthoc |
| pk528 | M2 adjective-noun plain (w2v) | M1 base paper: nouns only (w2v) | -0.042 | [-0.072, -0.011] | 0.5994 | posthoc |
| pk528 | M3 our pipeline: conf table + numberbatch | M3w M3 with word2vec | +0.034 | [+0.008, +0.062] | 1.0000 | posthoc |
| pk528 | X2 Bayesian EN as ranker | M3 our pipeline: conf table + numberbatch | -0.072 | [-0.106, -0.040] | 0.0030 | posthoc |
| pk528 | X1 frequentist EN as ranker | M3 our pipeline: conf table + numberbatch | -0.019 | [-0.047, +0.009] | 1.0000 | posthoc |

## Base paper, published (reference only: their list, their 106 sentences, no Hits@3)

{"W2V": {"Hits@1": 0.1604, "Hits@5": 0.4717, "Hits@10": 0.6509, "Hits@20": 0.7075, "nDCG@20": 0.3968}, "W2V Clustered": {"Hits@1": 0.2264, "Hits@5": 0.5283, "Hits@10": 0.6509, "Hits@20": 0.7075, "nDCG@20": 0.4442}}

## Everyday vs tourism tags (Hits@3)

```
{
 "osm_test": {
  "M1 base paper: nouns only (w2v)": {
   "by_block": {
    "everyday": 0.1724082421120412,
    "tourism": 0.1816816816816817
   },
   "tags_with_table_rows": 0.17519152771518703,
   "tags_without_table_rows": null
  },
  "M2 adjective-noun plain (w2v)": {
   "by_block": {
    "everyday": 0.15920798454603993,
    "tourism": 0.16516516516516516
   },
   "tags_with_table_rows": 0.1609959441189725,
   "tags_without_table_rows": null
  },
  "M3 our pipeline: conf table + numberbatch": {
   "by_block": {
    "everyday": 0.3557630392788152,
    "tourism": 0.359984984984985
   },
   "tags_with_table_rows": 0.35703019378098244,
   "tags_without_table_rows": null
  }
 },
 "pk528": {
  "M1 base paper: nouns only (w2v)": {
   "by_block": {
    "everyday": 0.21908127208480566,
    "gold-forced": 0.2,
    "tourism": 0.36666666666666664
   },
   "tags_with_table_rows": 0.2791164658634538,
   "tags_without_table_rows": 0.4
  },
  "M2 adjective-noun plain (w2v)": {
   "by_block": {
    "everyday": 0.20141342756183744,
    "gold-forced": 0.0,
    "tourism": 0.3
   },
   "tags_with_table_rows": 0.2429718875502008,
   "tags_without_table_rows": 0.26666666666666666
  },
  "M3 our pipeline: conf table + numberbatch": {
   "by_block": {
    "everyday": 0.43109540636042404,
    "gold-forced": 0.0,
    "tourism": 0.6125
   },
   "tags_with_table_rows": 0.5341365461847389,
   "tags_without_table_rows": 0.1
  }
 }
}
```

## Learning curves (dev-chosen lambda)

| model | n train | train H@3 | dev H@3 | gap |
|---|---|---|---|---|
| conf | 5,000 | 0.615 | 0.294 | +0.321 |
| conf | 10,000 | 0.562 | 0.320 | +0.242 |
| conf | 20,000 | 0.507 | 0.339 | +0.168 |
| conf | 40,000 | 0.458 | 0.356 | +0.103 |
| conf | 71,784 | 0.428 | 0.365 | +0.063 |
| fen_C0.5 | 5,000 | 0.388 | 0.276 | +0.112 |
| fen_C0.5 | 10,000 | 0.397 | 0.294 | +0.103 |
| fen_C0.5 | 20,000 | 0.398 | 0.316 | +0.082 |
| fen_C0.5 | 40,000 | 0.401 | 0.332 | +0.069 |
| fen_C0.5 | 71,784 | 0.398 | 0.343 | +0.055 |
| bayes_en | 5,000 | 0.206 | 0.207 | -0.001 |
| bayes_en | 10,000 | 0.221 | 0.221 | +0.000 |
| bayes_en | 20,000 | 0.232 | 0.230 | +0.001 |
| bayes_en | 40,000 | 0.254 | 0.254 | +0.000 |
| bayes_en | 71,784 | 0.289 | 0.290 | -0.001 |

## Bayesian elastic net fit

```
{
 "rows": 46443,
 "seconds": 8803.2213037014,
 "divergences": 0,
 "mean_leapfrog": 383.0,
 "b_mean": 0.06940052658319473,
 "rhat_top200_median": 0.9996620416641235,
 "rhat_top200_max": 1.0061430931091309,
 "ess_top200_median": 2837.533170357723,
 "credible_share": 0.0003902677754915409,
 "patterns_with_credible_tag": 286,
 "median_interval_width": 1.1683179140090942,
 "pass_p17b": true,
 "chains": 2,
 "warmup": 1000,
 "samples": 1000
}
```

## Everyday-basics check (48 sentences written before the test run)

```
{
 "M1": {
  "1": 0.20833333333333334,
  "3": 0.5625,
  "5": 0.6041666666666666,
  "n_scored": 48
 },
 "M2": {
  "1": 0.10416666666666667,
  "3": 0.4166666666666667,
  "5": 0.5416666666666666,
  "n_scored": 48
 },
 "M3": {
  "1": 0.2916666666666667,
  "3": 0.5625,
  "5": 0.75,
  "n_scored": 48
 }
}
```

## Independent labels

```
{
 "blind_label_filled_A.csv": {
  "n": 100,
  "agreement": 0.81,
  "kappa": 0.7834757834757835,
  "top_disagreements": [
   [
    [
     "ruins",
     "archaeological-site"
    ],
    4
   ],
   [
    [
     "hotel",
     "guest-house"
    ],
    2
   ],
   [
    [
     "retail",
     "clothes"
    ],
    2
   ],
   [
    [
     "village",
     "hill"
    ],
    1
   ],
   [
    [
     "park",
     "nature-reserve"
    ],
    1
   ],
   [
    [
     "retail",
     "handicraft"
    ],
    1
   ],
   [
    [
     "house",
     "manor"
    ],
    1
   ],
   [
    [
     "cave-entrance",
     "shrine"
    ],
    1
   ],
   [
    [
     "hill",
     "viewpoint"
    ],
    1
   ],
   [
    [
     "ruins",
     "building"
    ],
    1
   ]
  ]
 },
 "blind_label_filled_B.csv": {
  "n": 100,
  "agreement": 0.81,
  "kappa": 0.7829563628055746,
  "top_disagreements": [
   [
    [
     "ruins",
     "archaeological-site"
    ],
    4
   ],
   [
    [
     "hotel",
     "guest-house"
    ],
    2
   ],
   [
    [
     "retail",
     "clothes"
    ],
    2
   ],
   [
    [
     "village",
     "hill"
    ],
    1
   ],
   [
    [
     "park",
     "nature-reserve"
    ],
    1
   ],
   [
    [
     "retail",
     "handicraft"
    ],
    1
   ],
   [
    [
     "street",
     "quarter"
    ],
    1
   ],
   [
    [
     "house",
     "manor"
    ],
    1
   ],
   [
    [
     "cave-entrance",
     "shrine"
    ],
    1
   ],
   [
    [
     "hill",
     "viewpoint"
    ],
    1
   ]
  ]
 }
}
```
