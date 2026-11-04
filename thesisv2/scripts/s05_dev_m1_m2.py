"""Step 5: the two methods without mining and without Bayesian, on DEV only.
M1 = base paper: context nouns only, Word2Vec similarity, abstract-noun removal (Algorithm 2). M2 = M1 plus the extractor adjectives appended to the
embedding query. Numberbatch versions are reported as well so that backbone and adjectives can be told apart."""
from v2lib import *


def main():
    lex = [l.strip() for l in open(P('protocol', 'lexicon_v2.txt')) if l.strip()]
    D = prep(pd.read_parquet(P('extracted', 'osm_traindev_extracted.parquet'))); dv = D[D.split == 'dev'].reset_index(drop=True)
    RK = {bb: build_ranker(pickle.load(open(P('embeddings', n), 'rb')), lex) for bb, n in (('w2v', 'w2v_v2.pkl'), ('numberbatch', 'nb_v2.pkl'))}
    run = Runner(RK, {'osm_dev': dv}, [], 0, [])
    run.arm('M1 base paper: nouns only (w2v)', 'w2v')
    run.arm('M2 adjective-noun plain (w2v)', 'w2v', mode='naive')
    run.arm('M1 nouns only (numberbatch)', 'numberbatch')
    run.arm('M2 adjective-noun plain (numberbatch)', 'numberbatch', mode='naive')
    run.arm('A0 abstract nouns kept (w2v)', 'w2v', mode='keep_abstract')
    h = {k: v['osm_dev'] for k, v in run.ARMS.items()}
    cmp_ = compare(run.RANKS['M2 adjective-noun plain (w2v)']['osm_dev'] <= 3, run.RANKS['M1 base paper: nouns only (w2v)']['osm_dev'] <= 3)
    print('M2 - M1 (w2v) dev Hits@3:', f"{cmp_['delta_hits3']:+.3f} [{cmp_['ci95'][0]:+.3f}, {cmp_['ci95'][1]:+.3f}]")
    out = P('results', 's05_dev_m1_m2.json'); jdump({'dev_n': len(dv), 'arms': h, 'm2_vs_m1_w2v': cmp_}, out)
    manifest('s05', [P('extracted', 'osm_traindev_extracted.parquet')], [out], dev_rows=len(dv))


if __name__ == '__main__': main()
