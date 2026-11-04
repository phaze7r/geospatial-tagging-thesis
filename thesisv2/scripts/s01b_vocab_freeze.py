"""Step 1b: freeze the vocabulary the user signed off. Writes lexicon_v2.txt, lexicon_v2_map.csv (key,value -> tag, used by step 2) and
lexicon_v2_aliases.csv (alias -> canonical tag, used to relabel the gold tags of the 106 and Pakistan sets). Stops with an error if a gold tag
cannot be resolved or if there are fewer than MIN_TAGS tags (pass --allow-short to accept fewer, and say so in the thesis)."""
from v2lib import *


def main():
    C = pd.read_csv(P('protocol', 'lexicon_v2_draft.csv')); C['canonical'] = C['canonical'].fillna(C['tag'])
    Y = C[C.include.astype(str).str.upper() == 'Y']
    lex = sorted(set(Y.canonical))
    M = Y[Y.key != '(gold)'][['key', 'value', 'canonical']].drop_duplicates()
    amb = M.groupby(['key', 'value']).canonical.nunique(); assert (amb == 1).all(), f'a key=value maps to two canonical tags: {amb[amb > 1].index.tolist()}'
    aliases = {a: c for a, c in zip(Y.tag, Y.canonical) if a != c}
    aliases.update({a: c for a, c in MERGE_PROPOSAL.items() if c in lex and a not in lex})
    miss = resolve_gold(lex, aliases)
    assert not miss, f'gold tags that do not resolve into the vocabulary: {miss}. Add them (include=Y) or an alias, then rerun.'
    if len(lex) < MIN_TAGS and '--allow-short' not in sys.argv: raise SystemExit(f'only {len(lex)} tags (< {MIN_TAGS}); edit the draft or pass --allow-short')
    open(P('protocol', 'lexicon_v2.txt'), 'w').write('\n'.join(lex) + '\n')
    M.to_csv(P('protocol', 'lexicon_v2_map.csv'), index=False)
    pd.DataFrame([{'kind': 'merge', 'alias': a, 'canonical': c} for a, c in sorted(aliases.items())]).to_csv(P('protocol', 'lexicon_v2_aliases.csv'), index=False)
    sha = sha256_text('\n'.join(lex))
    print(f'vocabulary frozen: {len(lex)} tags, sha256 {sha[:16]}..., {len(M)} key=value mapping rows, {len(aliases)} aliases')
    manifest('s01b', [P('protocol', 'lexicon_v2_draft.csv')], [P('protocol', 'lexicon_v2.txt'), P('protocol', 'lexicon_v2_map.csv'), P('protocol', 'lexicon_v2_aliases.csv')],
             n_tags=len(lex), lexicon_sha256=sha)


if __name__ == '__main__': main()
