"""Step 10b (optional): Cohen's kappa between the independent annotator(s) and the gold tags. Usage: s10b_kappa.py report/blind_label_filled_A.csv [more files]"""
from v2lib import *


def main():
    from sklearn.metrics import cohen_kappa_score
    key = jload(P('report', 'blind_label_key.json')); alias = alias_map(); fix = lambda t: alias.get(str(t).strip().lower(), str(t).strip().lower())
    out = {}
    for f in [a for a in sys.argv[1:] if a.endswith('.csv')]:
        A = pd.read_csv(f).dropna(subset=['your_tag']); A = A[A['your_tag'].astype(str).str.strip() != '']
        gold = [fix(key[i]) for i in A.id]; ann = [fix(t) for t in A.your_tag]
        out[os.path.basename(f)] = {'n': len(A), 'agreement': float(np.mean([a == b for a, b in zip(gold, ann)])), 'kappa': float(cohen_kappa_score(gold, ann)),
                                    'top_disagreements': Counter((g, a) for g, a in zip(gold, ann) if g != a).most_common(10)}
        print(os.path.basename(f), out[os.path.basename(f)])
    jdump(out, P('results', 's10_independent_labels.json')); manifest('s10b', [], [P('results', 's10_independent_labels.json')])


if __name__ == '__main__': main()
