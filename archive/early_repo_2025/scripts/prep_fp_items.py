#!/usr/bin/env python3
"""
Prepare transactions from preprocessed OSM Islamabad data and mine frequent itemsets.

- Input: ./output/osm_isb_preprocessed.csv (columns: text, class_label, plus OSM keys)
- Outputs (default --out_dir ./output/fpg):
    - transactions.csv           (id, class_label, items_json)
    - vocab.csv                  (item, item_id, df)
    - fpg_global_itemsets.csv    (k, support, support_frac, items, items_readable)
    - fpg_by_class_itemsets.csv  (class_label, k, support, support_frac, items, items_readable)

Usage:
    cd geospatial-tagging-thesis/scripts
    python prepare_fp_items.py --input_csv ./output/osm_isb_preprocessed.csv --out_dir ./output/fpg

Optional flags:
    --min_support 0.02           # global min support fraction (default 2%)
    --class_min_support 0.05     # per-class min support fraction (default 5%)
    --min_count_floor 2          # absolute minimum support count
    --min_len 1 --max_len 3      # itemset size filters in outputs
    --ngram_max 2                # include unigrams and bigrams in tokens
    --min_token_len 2            # drop tokens shorter than this
    --min_df 2                   # drop tokens appearing in fewer than this many docs
    --max_vocab 8000             # cap vocab by highest document frequency
    --include_osm_keys amenity,shop,highway,leisure,natural,tourism,building,historic,place
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

import pandas as pd


# -----------------------------
# Tokenization / normalization
# -----------------------------
EN_STOP = {
    "a","an","the","and","or","but","if","then","else","for","with","without","to","from","of","on","in","at","by",
    "is","are","was","were","be","been","as","this","that","these","those","it","its","into","near","via","per",
    "around","about","over","under","within","between","across","next","nextto","opposite","behind","front","side",
    "road","rd","st","street","ave","avenue","phase","sector","block"
}
# Roman Urdu common stopwords (compact)
RU_STOP = {
    "hai","hain","tha","the","thi","ka","ki","ke","ko","se","mein","may","me","par","pe","per","tak","aur","ya",
    "k","kiye","liye","wala","wali","wale","gaya","gai","gaye","kar","kr","raha","rha","rahe","rhe","tha","thi",
    "tha","hogaya","yahan","wahan"
}
# Urdu script (subset)
UR_STOP = {"ہے","ہیں","تھا","تھی","تھے","کا","کی","کے","کو","سے","میں","پر","اور","یا","تک","کےلیے","کر","رہا","رہے","گیا","گئی","گئے"}

TOKEN_SPLIT = re.compile(r"[^\w\-\/]+", flags=re.UNICODE)  # keep hyphen and slash for sector-like tokens

def normalize_token(tok: str) -> str | None:
    if not tok:
        return None
    t = unicodedata.normalize("NFC", tok).strip().lower()
    # Normalize sector-like tokens: g-11/1 -> g111; f-7 -> f7
    t = t.replace("–", "-").replace("—", "-")
    t = t.replace("/", "")
    if t in EN_STOP or t in RU_STOP or t in UR_STOP:
        return None
    # drop if all punctuation or length < 2
    if all(ch in "-_" for ch in t) or len(t) < 2:
        return None
    # drop if token is mostly digits and punctuation (keep 'g11', 'f7' etc.)
    letters = sum(ch.isalpha() for ch in t)
    digits = sum(ch.isdigit() for ch in t)
    if letters == 0 and digits > 0 and digits >= len(t) - digits:
        return None
    return t


def tokenize_text(text: str, ngram_max: int = 2, min_token_len: int = 2) -> List[str]:
    if not isinstance(text, str):
        return []
    text = unicodedata.normalize("NFC", text)
    parts = [p for p in TOKEN_SPLIT.split(text) if p]
    toks = []
    for p in parts:
        nt = normalize_token(p)
        if nt and len(nt) >= min_token_len:
            toks.append(nt)

    # unigrams
    items = toks[:]
    # bigrams (within-sentence order; simple window of 2)
    if ngram_max >= 2 and len(toks) >= 2:
        for i in range(len(toks)-1):
            bi = f"{toks[i]}_{toks[i+1]}"
            items.append(bi)
    return items


# -----------------------------
# FP-Growth implementation (compact)
# -----------------------------
class FPNode:
    __slots__ = ("item", "count", "parent", "children", "node_link")
    def __init__(self, item: int | None, count: int, parent: "FPNode | None"):
        self.item = item
        self.count = count
        self.parent = parent
        self.children: Dict[int, FPNode] = {}
        self.node_link: FPNode | None = None


def build_fp_tree(transactions: List[List[int]], min_count: int):
    # 1) item frequency
    freq = Counter()
    for tx in transactions:
        # treat each item once per transaction
        for it in set(tx):
            freq[it] += 1
    freq = {it: c for it, c in freq.items() if c >= min_count}
    if not freq:
        return None, None, {}
    # order by frequency desc, then id asc
    order = {it: i for i, (it, _) in enumerate(sorted(freq.items(), key=lambda x: (-x[1], x[0])))}
    header: Dict[int, Tuple[int, FPNode | None]] = {it: [freq[it], None] for it in freq}
    root = FPNode(None, 0, None)
    # 2) insert
    for tx in transactions:
        filtered = [it for it in tx if it in freq]
        if not filtered:
            continue
        filtered.sort(key=lambda it: order[it])
        cur = root
        for it in filtered:
            if it in cur.children:
                child = cur.children[it]
                child.count += 1
            else:
                child = FPNode(it, 1, cur)
                cur.children[it] = child
                # link into header table
                if header[it][1] is None:
                    header[it][1] = child
                else:
                    n = header[it][1]
                    while n.node_link is not None:
                        n = n.node_link
                    n.node_link = child
            cur = child
    return root, header, freq


def ascend_to_root(node: FPNode) -> List[int]:
    path: List[int] = []
    while node.parent is not None and node.parent.item is not None:
        node = node.parent
        path.append(node.item)
    return path  # from parent upwards


def conditional_pattern_base(base_item: int, header) -> List[List[int]]:
    paths = []
    node = header[base_item][1]
    while node is not None:
        path = ascend_to_root(node)
        for _ in range(node.count):
            if path:
                paths.append(path[:])
        node = node.node_link
    return paths


def mine_tree(root: FPNode, header, min_count: int, suffix: List[int], out: Dict[Tuple[int, ...], int]):
    # items in ascending frequency for conditional mining
    items = sorted(header.keys(), key=lambda it: (header[it][0], it))
    for base in items:
        new_suffix = suffix + [base]
        support = header[base][0]
        out[tuple(sorted(new_suffix))] = support

        # Build conditional tree
        cond_transactions = conditional_pattern_base(base, header)
        cond = build_fp_tree(cond_transactions, min_count)
        if cond[0] is None or cond[1] is None:
            continue
        cond_root, cond_header, _ = cond
        if cond_header:
            mine_tree(cond_root, cond_header, min_count, new_suffix, out)


def fpgrowth(transactions: List[List[int]], min_count: int) -> Dict[Tuple[int, ...], int]:
    root, header, _ = build_fp_tree(transactions, min_count)
    if root is None or header is None:
        return {}
    results: Dict[Tuple[int, ...], int] = {}
    mine_tree(root, header, min_count, [], results)
    return results


# -----------------------------
# Pipeline helpers
# -----------------------------
def prune_vocab_by_df(doc_tokens: List[Set[str]], min_df: int, max_vocab: int) -> Set[str]:
    df = Counter()
    for toks in doc_tokens:
        for t in toks:
            df[t] += 1
    # Apply min_df
    kept = {t for t, c in df.items() if c >= min_df}
    # Limit vocab by highest df
    if max_vocab and len(kept) > max_vocab:
        kept = {t for t, _ in sorted(((t, df[t]) for t in kept), key=lambda x: (-x[1], x[0]))[:max_vocab]}
    return kept


def stringify_itemset(item_ids: Sequence[int], id2item: Dict[int, str]) -> Tuple[str, str]:
    items = [id2item[i] for i in sorted(item_ids)]
    return "|".join(items), ", ".join(items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_csv", default="./output/osm_isb_preprocessed.csv")
    ap.add_argument("--out_dir", default="./output/fpg")
    ap.add_argument("--text_col", default="text")
    ap.add_argument("--label_col", default="class_label")
    ap.add_argument("--include_osm_keys",
                    default="amenity,shop,highway,leisure,natural,tourism,building,historic,place")
    ap.add_argument("--ngram_max", type=int, default=2)
    ap.add_argument("--min_token_len", type=int, default=2)
    ap.add_argument("--min_df", type=int, default=2)
    ap.add_argument("--max_vocab", type=int, default=8000)
    ap.add_argument("--min_support", type=float, default=0.02)          # global
    ap.add_argument("--class_min_support", type=float, default=0.05)    # per-class
    ap.add_argument("--min_count_floor", type=int, default=2)
    ap.add_argument("--min_len", type=int, default=1)
    ap.add_argument("--max_len", type=int, default=3)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input_csv, encoding="utf-8")
    if args.text_col not in df.columns or args.label_col not in df.columns:
        raise RuntimeError(f"Expected columns '{args.text_col}' and '{args.label_col}' in {args.input_csv}")

    include_keys = [k.strip() for k in args.include_osm_keys.split(",") if k.strip()]

    # 1) Build raw per-document token sets and tag items
    doc_tokens: List[Set[str]] = []
    tag_items: List[Set[str]] = []
    labels: List[str] = []

    for _, r in df.iterrows():
        text = r.get(args.text_col, "")
        toks = set(tokenize_text(text, ngram_max=args.ngram_max, min_token_len=args.min_token_len))

        tagset: Set[str] = set()
        for k in include_keys:
            v = r.get(k)
            if isinstance(v, str) and v.strip():
                tagset.add(f"tag:{k}={v.strip()}")

        doc_tokens.append(toks)
        tag_items.append(tagset)
        labels.append(str(r.get(args.label_col)))

    n_docs = len(doc_tokens)

    # 2) Prune token vocab by document frequency; keep all tag items
    kept_tokens = prune_vocab_by_df(doc_tokens, min_df=args.min_df, max_vocab=args.max_vocab)

    # 3) Build final transactions and vocab
    items_all: Set[str] = set()
    transactions_str: List[List[str]] = []
    for toks, tags in zip(doc_tokens, tag_items):
        items = list((toks & kept_tokens) | tags)  # unique per doc
        transactions_str.append(items)
        items_all.update(items)

    # Map item -> id
    vocab_sorted = sorted(items_all)
    item2id = {item: i for i, item in enumerate(vocab_sorted)}
    id2item = {i: item for item, i in item2id.items()}

    # Convert to id transactions
    transactions_id: List[List[int]] = [[item2id[it] for it in tx] for tx in transactions_str]

    # 4) Save transactions and vocab
    tx_rows = []
    for i, (lbl, items) in enumerate(zip(labels, transactions_str)):
        tx_rows.append({"id": i, "class_label": lbl, "items_json": json.dumps(sorted(items), ensure_ascii=False)})
    pd.DataFrame(tx_rows).to_csv(out_dir / "transactions.csv", index=False, encoding="utf-8")

    # vocab with DF
    df_counter = Counter()
    for tx in transactions_str:
        for it in set(tx):
            df_counter[it] += 1
    vocab_rows = [{"item": it, "item_id": item2id[it], "df": df_counter[it]} for it in vocab_sorted]
    pd.DataFrame(vocab_rows).to_csv(out_dir / "vocab.csv", index=False, encoding="utf-8")

    # 5) Mine frequent itemsets (global)
    min_count_global = max(args.min_count_floor, int(math.ceil(args.min_support * n_docs)))
    global_itemsets = fpgrowth(transactions_id, min_count_global)

    # Filter by size and write
    global_rows = []
    for itemset, count in global_itemsets.items():
        k = len(itemset)
        if k < args.min_len or k > args.max_len:
            continue
        items_pipe, items_readable = stringify_itemset(itemset, id2item)
        global_rows.append({
            "k": k,
            "support": count,
            "support_frac": round(count / n_docs, 6),
            "items": items_pipe,
            "items_readable": items_readable,
        })
    global_df = pd.DataFrame(sorted(global_rows, key=lambda r: (-r["k"], -r["support"], r["items"])))
    global_df.to_csv(out_dir / "fpg_global_itemsets.csv", index=False, encoding="utf-8")

    # 6) Per-class mining
    by_class_rows = []
    labels_unique = sorted(set(labels))
    # index docs by class
    lbl_to_indices: Dict[str, List[int]] = defaultdict(list)
    for i, lbl in enumerate(labels):
        lbl_to_indices[lbl].append(i)

    for lbl in labels_unique:
        idxs = lbl_to_indices[lbl]
        if not idxs:
            continue
        sub_tx = [transactions_id[i] for i in idxs]
        min_count_class = max(args.min_count_floor, int(math.ceil(args.class_min_support * len(sub_tx))))
        itemsets = fpgrowth(sub_tx, min_count_class)
        for itemset, count in itemsets.items():
            k = len(itemset)
            if k < args.min_len or k > args.max_len:
                continue
            items_pipe, items_readable = stringify_itemset(itemset, id2item)
            by_class_rows.append({
                "class_label": lbl,
                "k": k,
                "support": count,
                "support_frac": round(count / len(sub_tx), 6),
                "items": items_pipe,
                "items_readable": items_readable,
            })

    by_class_df = pd.DataFrame(sorted(by_class_rows, key=lambda r: (r["class_label"], -r["k"], -r["support"], r["items"])))
    by_class_df.to_csv(out_dir / "fpg_by_class_itemsets.csv", index=False, encoding="utf-8")

    # Console summary
    print(f"[ok] Wrote transactions/vocab to: {out_dir.resolve()}")
    print(f"[ok] Global min_support={args.min_support} -> min_count={min_count_global} (N={n_docs})")
    print(f"[ok] Global itemsets kept (size in [{args.min_len},{args.max_len}]): {len(global_df)}")
    print(f"[ok] Per-class itemsets rows: {len(by_class_df)}")


if __name__ == "__main__":
    main()