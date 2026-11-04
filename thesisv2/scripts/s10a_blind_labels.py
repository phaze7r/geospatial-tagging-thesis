"""Step 10a (optional): file for independent labelling. 100 random second-round rows of the Pakistan 528, sentence only, plus the vocabulary list.
Give report/blind_label_file.csv and report/blind_label_vocabulary.txt to one or two other annotators (they fill `your_tag`; they never see the gold tag).
The key stays in report/blind_label_key.json (do not share)."""
from v2lib import *


def main():
    X, ids528, subsets, _ = load_pk(); byid = {r['id']: r for r in X}
    second = [i for i in subsets['C extended n>=3, new rows only']]
    rs = np.random.RandomState(0); pick = sorted(rs.choice(second, min(100, len(second)), replace=False).tolist())
    pd.DataFrame({'id': pick, 'sentence': [byid[i]['sentence'] for i in pick], 'your_tag': '', 'unsure': '', 'notes': ''}).to_csv(P('report', 'blind_label_file.csv'), index=False)
    shutil_copy = open(P('protocol', 'lexicon_v2.txt')).read(); open(P('report', 'blind_label_vocabulary.txt'), 'w').write(shutil_copy)
    jdump({i: byid[i]['gold_tag'] for i in pick}, P('report', 'blind_label_key.json'))
    manifest('s10a', [P('protocol', 'lexicon_v2.txt')], [P('report', 'blind_label_file.csv'), P('report', 'blind_label_key.json')], rows=len(pick))
    print(f'wrote {len(pick)} rows to report/blind_label_file.csv')


if __name__ == '__main__': main()
