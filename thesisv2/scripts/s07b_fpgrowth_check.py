"""Step 7b (optional, CPU): guided versus extended FP-Growth on the v2 training transactions at growing sizes. Notebook 12 AB4 logic: guided counts only
{pattern, tag} itemsets; extended = FP-Growth first scan + mlxtend fpgrowth over every remaining item (60 minute timeout per size). Reports time, peak
memory and whether the {pattern, tag} itemsets are identical."""
from v2lib import *
import tracemalloc, signal, warnings; warnings.filterwarnings('ignore')


class _Timeout(Exception): pass


def _alarm(*_): raise _Timeout()


def main():
    try: from mlxtend.frequent_patterns import fpgrowth
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'mlxtend'], check=True); from mlxtend.frequent_patterns import fpgrowth
    from mlxtend.preprocessing import TransactionEncoder
    D = prep(pd.read_parquet(P('extracted', 'osm_traindev_extracted.parquet'))); tr = D[D.split == 'train'].sample(frac=1.0, random_state=0).reset_index(drop=True)
    # support of the earlier check: at the final run's 0.0001 the count threshold is below one row at 5,000 transactions and extended FP-Growth does not finish
    MIN_SUP = 0.02 if SMOKE else 0.0005; KEEP = ('amod:', 'compound:', 'type:'); is_pat = lambda it: it.startswith(('adj:', 'amod:'))
    sizes = [n for n in (5000, 10000, 20000, 40000) if n < len(tr)] + [len(tr)]
    if SMOKE: sizes = [min(500, len(tr)), len(tr)]
    only = [int(x) for x in sys.argv[1:] if x.isdigit()]   # rerun just these sizes, keep the stored records of the others
    if only: sizes = [n if n > 0 else len(tr) for n in only]; out = [r for r in (jload(P('results', 's07b_fpgrowth_check.json')) or []) if r['transactions'] not in sizes]
    else: out = []
    signal.signal(signal.SIGALRM, _alarm)
    for n in sizes:
        sub = tr.iloc[:n]
        TX = [sorted(set([f'adj:{a}' for a in A] + [it for it in T_ if it.startswith(KEEP)] + [f'tag:{y}'])) for A, T_, y in zip(sub.adjs, sub.transaction, sub.tag)]
        MIN_CNT = MIN_SUP * len(TX); rec = {'transactions': len(TX), 'min_support': MIN_SUP}
        tracemalloc.start(); t0 = time.perf_counter(); c1, c12 = Counter(), Counter()
        for items in TX:
            tag = next(i for i in items if i.startswith('tag:'))
            for it in items:
                if is_pat(it): c1[it] += 1; c12[(it, tag)] += 1
        G = {k for k, c in c12.items() if c >= MIN_CNT and c1[k[0]] >= MIN_CNT}
        rec['guided'] = {'seconds': time.perf_counter() - t0, 'peak_mb': tracemalloc.get_traced_memory()[1] / 2**20, 'pattern_tag_itemsets': len(G)}; tracemalloc.stop()
        tracemalloc.start(); t0 = time.perf_counter(); signal.alarm(0 if SMOKE else 60 * 60)
        try:
            ic = Counter(it for items in TX for it in items); fset = {it for it, c in ic.items() if c >= MIN_CNT}; TXf = [[it for it in items if it in fset] for items in TX]
            te_ = TransactionEncoder(); DF_ = pd.DataFrame.sparse.from_spmatrix(te_.fit(TXf).transform(TXf, sparse=True), columns=te_.columns_);   # sparse, as in the earlier check (09_ablation_cells.py)
            FI = fpgrowth(DF_, min_support=MIN_SUP, use_colnames=True); signal.alarm(0)
            E = set()
            for its in FI.itemsets:
                if len(its) == 2:
                    a_, b_ = sorted(its, key=lambda x: x.startswith('tag:'))
                    if is_pat(a_) and b_.startswith('tag:'): E.add((a_, b_))
            rec['extended'] = {'seconds': time.perf_counter() - t0, 'peak_mb': tracemalloc.get_traced_memory()[1] / 2**20, 'frequent_itemsets': int(len(FI)), 'pattern_tag_itemsets': len(E)}
            rec['identical'] = bool(E == G)
        except (_Timeout, MemoryError) as e: signal.alarm(0); rec['extended'] = {'failed': type(e).__name__, 'seconds': time.perf_counter() - t0}
        tracemalloc.stop(); out.append(rec); print(rec, flush=True); jdump(out, P('results', 's07b_fpgrowth_check.json'))
    jdump(out, P('results', 's07b_fpgrowth_check.json')); manifest('s07b', [P('extracted', 'osm_traindev_extracted.parquet')], [P('results', 's07b_fpgrowth_check.json')])


if __name__ == '__main__': main()
