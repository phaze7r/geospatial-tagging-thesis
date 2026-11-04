"""Step 4: word vectors for every vocabulary tag and every train/dev noun (Word2Vec GoogleNews and ConceptNet Numberbatch). Recipe of notebook 11
R5-cache-w2v / R5-cache-nb: start from the finished caches (read-only), add the missing strings from gensim, write new caches to thesisv2/embeddings.
Test and evaluation nouns are added later in step 8. Stops if a vocabulary tag has no vector in a backbone (the ranker would drop it)."""
from v2lib import *


def main():
    lex = [l.strip() for l in open(P('protocol', 'lexicon_v2.txt')) if l.strip()]
    D = prep(pd.read_parquet(P('extracted', 'osm_traindev_extracted.parquet')))
    nouns = nouns_of(D); out = {}; cov = {}
    for bb, name in (('w2v', 'w2v_v2.pkl'), ('numberbatch', 'nb_v2.pkl')):
        V, src = load_vec_cache(bb); print(f'{bb}: base cache {src} ({len(V):,} strings)')
        V, added = extend_vectors(V, bb, set(lex) | nouns); print(f'   +{added:,} vectors -> {len(V):,}')
        pickle.dump(V, open(P('embeddings', name), 'wb'), protocol=4); out[bb] = P('embeddings', name)
        R = build_ranker(V, lex); miss = sorted(set(lex) - set(R.TAGS))
        dv = D[D.split == 'dev']; toks = [t for L in dv.context_nouns for t in L if t.lower() not in pr.ABSTRACT]
        cov[bb] = {'tags_with_vector': len(R.TAGS), 'tags_missing': miss, 'dev_noun_tokens_embeddable': float(np.mean([R.vec(t) is not None for t in toks])) if toks else None}
        print(f'   tags with a vector {len(R.TAGS)}/{len(lex)} | missing: {miss[:30]} | dev noun tokens embeddable {cov[bb]["dev_noun_tokens_embeddable"]:.1%}')
    jdump(cov, P('results', 's04_vector_coverage.json'))
    bad = {bb: c['tags_missing'] for bb, c in cov.items() if len(c['tags_missing']) > max(2, 0.01 * len(lex))}
    manifest('s04', [P('extracted', 'osm_traindev_extracted.parquet')], list(out.values()) + [P('results', 's04_vector_coverage.json')], coverage=cov)
    if bad: raise SystemExit(f'too many vocabulary tags without a vector: {bad}. Merge or rename them at the vocabulary gate, then rerun steps 1b to 4.')


if __name__ == '__main__': main()
