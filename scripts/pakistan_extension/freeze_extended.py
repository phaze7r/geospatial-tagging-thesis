"""Freeze the extended Pakistan set: the 199 adjudicated rows + the new rows the author kept.

Gold labels = file 2 (Appendix C mapping applied); file 1 (blind, no sources) kept as `blind_tag`.
Roman Urdu: 60 author-written + 240 drafts the author checked (17 corrected) + 21 extra drafts the
author approved = 300. Urdu: the author's 157. Writes pk_extended_raw.json; nothing is scored here.

usage: python freeze_extended.py PK_EXTRACTED.json TRANSLATION_SHEET.xlsx FILE1.xlsx FILE2.xlsx OUT.json
"""
import json, sys
from collections import Counter
import pandas as pd

ext, sheet, f1, f2, out = sys.argv[1:6]
TYPE_WORD_KEPT = {'PK284': 'road', 'PK351': 'buildings', 'PK356': 'buildings', 'PK670': 'ruins'}   # author chose to keep

s = lambda v: '' if pd.isna(v) else str(v).strip()
old = json.load(open(ext))
tr = pd.read_excel(sheet, sheet_name='translate').set_index('row')
b1, b2 = pd.read_excel(f1, sheet_name=None), pd.read_excel(f2, sheet_name=None)
lab, blind = b2['1 Label (text only)'].set_index('id'), b1['1 Label (text only)'].set_index('id')
chk, prov = b2['2 Source check'].set_index('id'), b2['4 Provenance'].set_index('id')
cand = {c['cid']: c for c in json.load(open('wv_candidates.json'))}

# Roman Urdu, keyed 'row N' (existing) or 'PKnnn' (new)
roman = {}
for r in b2['3 Roman Urdu check'].itertuples():
    ok = s(r.ok_yes_no).lower() == 'yes'
    roman[r.id] = (s(r.roman_urdu_draft) if ok else s(r.corrected_text), 'drafted, checked by author' if ok else 'drafted, corrected by author')
for l in open('roman/new_extra_21.jsonl'):
    d = json.loads(l); roman[d['id']] = (d['roman_urdu'], 'drafted, checked by author')
for row, v in tr.roman_urdu.dropna().items(): roman[f'row {row}'] = (s(v), 'written by author')

rows = []
for r in old:
    rm, org = roman.get(f"row {r['row']}", ('', ''))
    ur = s(tr.urdu.get(int(r['row']), ''))
    rows.append({**r, 'id': f"PK{int(r['row']):03d}", 'part': 'original', 'urdu': ur, 'roman_urdu': rm, 'roman_origin': org})
for i in lab.index:
    if s(chk.loc[i, 'keep_yes_no']).lower() != 'yes': continue
    c = cand[prov.loc[i, 'cid']]; rm, org = roman.get(i, ('', ''))
    rows.append({'id': i, 'part': 'extension', 'sentence': s(lab.loc[i, 'text']), 'gold_tag': s(lab.loc[i, 'gold_tag']),
                 'alt_tags': [t.strip() for t in s(lab.loc[i, 'alt_tags']).split(',') if t.strip()],
                 'uncertain': s(lab.loc[i, 'uncertain']).lower() == 'yes', 'notes': s(lab.loc[i, 'notes']),
                 'blind_tag': s(blind.loc[i, 'gold_tag']), 'type_word_in_text': TYPE_WORD_KEPT.get(i, ''),
                 'source': 'wikivoyage', 'source_url': c['url'], 'source_revid': c['revid'], 'article': c['article'],
                 'listing_name': c['name'], 'source_text': c['content'], 'license': 'CC-BY-SA-4.0',
                 'annotator': 'author', 'urdu': '', 'roman_urdu': rm, 'roman_origin': org})

# checks
assert len({r['id'] for r in rows}) == len(rows)
assert all(r['gold_tag'] for r in rows)
assert not any(('—' in r['roman_urdu'] and r['roman_origin'] != 'written by author') or (r['part'] == 'extension' and '—' in r['sentence']) for r in rows)   # author-written data stays verbatim
assert (lab.loc[[r['id'] for r in rows if r['part'] == 'extension'], 'text'] == chk.loc[[r['id'] for r in rows if r['part'] == 'extension'], 'text']).all()
n_rm, n_ur = sum(bool(r['roman_urdu']) for r in rows), sum(bool(r['urdu']) for r in rows)
cnt = Counter(r['gold_tag'] for r in rows); n3 = [r for r in rows if cnt[r['gold_tag']] >= 3]
cnt_o = Counter(r['gold_tag'] for r in rows if r['part'] == 'original')
print(f"rows {len(rows)} (original {len(old)}, extension {len(rows) - len(old)}) | tags {len(cnt)}")
print(f"n>=3 subset {len(n3)} rows / {sum(c >= 3 for c in cnt.values())} tags (original {sum(r['part'] == 'original' for r in n3)}, extension {sum(r['part'] == 'extension' for r in n3)})")
print(f"pre-registered original n>=3: {sum(1 for r in old if cnt_o[r['gold_tag']] >= 3)} rows")
print(f"Roman Urdu {n_rm} ({Counter(r['roman_origin'] for r in rows if r['roman_urdu'])}) | Urdu {n_ur}")
assert n_rm == 300 and n_ur == 157
json.dump(rows, open(out, 'w'), ensure_ascii=False, indent=1)
print('wrote', out)
