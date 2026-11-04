"""Automatic checks on the reworded Pakistan candidates, then the review workbook for the annotator.

Checks per row: personal data (phone, e-mail, URL; reject), length, em dashes, words of the 227-tag
vocabulary or common type synonyms (flag: they may name another place, which the protocol allows),
words of the listing's own name (flag), and near-duplicates against the existing 199 rows and within
the new rows (token Jaccard >= 0.5; flag).

usage: python check_candidates.py EXISTING_pk_evalset_raw.json OUT.xlsx pk_translation_sheet.xlsx
"""
import glob, json, os, re, sys
import pandas as pd

SYN = """restaurant restaurants eatery diner dhaba cafe café cafes coffeehouse coffee-shop hotel hotels inn motel
hostel guesthouse guest-house resort lodge mosque mosques masjid shrine shrines mazar mazaar darbar durbar dargah
tomb tombs mausoleum fort forts fortress qila qilla museum museums gallery galleries park parks bagh garden gardens
zoo lake lakes beach beaches bakery bakeries market markets bazaar bazar mall malls plaza shop store church churches
cathedral temple temples mandir gurdwara monument memorial tower gate ruins valley peak mountain glacier waterfall
cinema stadium library college university school hospital bridge dam cemetery graveyard palace mahal haveli
stupa monastery minaret island river pass road street square club""".split()
WORD = re.compile(r"[a-zA-Zé'-]+")


def table_a1():
    tags = [t.strip() for t in open(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'tags_227.txt')) if t.strip()]
    assert len(tags) == len(set(tags)) == 227, len(tags)
    return set(tags)


TAGS = table_a1()


def vocab():
    tags = TAGS
    words = set()
    for tg in tags:
        words.add(tg.replace('-', ' ')); words.add(tg.replace('-', ' ') + 's')
    return words | {w.replace('-', ' ') for w in SYN}


def toks(s): return {w for w in re.findall(r'[a-z]{4,}', s.lower())}


def jac(a, b): return len(a & b) / max(1, len(a | b))


def main(existing, out):
    cand = {c['cid']: c for c in json.load(open('wv_candidates.json'))}
    rows = [json.loads(l) for f in sorted(glob.glob('para/b*.jsonl')) for l in open(f)]
    assert len({r['cid'] for r in rows}) == len(rows), 'duplicate cid'
    old = [(r['row'], toks(r['sentence'])) for r in json.load(open(existing))]
    V = vocab()
    out_rows, seen = [], []
    for i, r in enumerate(rows):
        c, t = cand[r['cid']], r['text']
        low = ' ' + ' '.join(WORD.findall(t.lower())) + ' '
        flags = []
        if re.search(r'\+?\d[\d\s-]{7,}\d|@|https?://|www\.', t): flags.append('REJECT personal data')
        n = len(t.split())
        if n < 5 or n > 60: flags.append(f'length {n}')
        if '—' in t: flags.append('em dash')
        tw = sorted(w for w in V if f' {w} ' in low)
        name = {w for w in toks(c['name']) if w not in {'hotel', 'restaurant', 'guest', 'house', 'park', 'lake', 'museum', 'shrine', 'tomb', 'fort', 'cafe', 'bazaar', 'market', 'mosque', 'masjid'}}
        nl = sorted(w for w in name if f' {w} ' in low)
        tk = toks(t)
        dup_old = [str(rid) for rid, s in old if jac(tk, s) >= 0.5]
        dup_new = [o for o, s in seen if jac(tk, s) >= 0.5]
        seen.append((f'PK{200 + i}', tk))
        out_rows.append({'id': f'PK{200 + i}', 'text': t, 'cid': r['cid'], 'article': c['article'], 'listing_name': c['name'],
                         'section': c['kind'], 'source_text': c['content'], 'source_url': c['url'], 'licence': 'CC BY-SA 4.0',
                         'type_words_in_text': ', '.join(tw), 'name_words_in_text': ', '.join(nl),
                         'near_dup_existing_rows': ', '.join(dup_old), 'near_dup_new_rows': ', '.join(dup_new),
                         'auto_flags': '; '.join(flags)})
    df = pd.DataFrame(out_rows)
    blind = df[['id', 'text']].assign(gold_tag='', alt_tags='', uncertain='', notes='')
    check = df[['id', 'text', 'source_text', 'source_url', 'article', 'listing_name', 'type_words_in_text', 'name_words_in_text',
                'near_dup_existing_rows', 'near_dup_new_rows', 'auto_flags']].assign(faithful_yes_no='', keep_yes_no='', check_notes='')
    # Roman Urdu drafts: 97 existing n>=3 rows without one, 143 new rows (keyed by cid so ids can move)
    ex = pd.read_excel(sys.argv[3], sheet_name='translate').set_index('row')
    new_rm = {json.loads(l)['id']: json.loads(l)['roman_urdu'] for l in open('roman/new_143.jsonl')}
    by_id = df.set_index('id')
    rm = [{'set': 'existing', 'id': f"row {r['row']}", 'cid': '', 'english': ex.loc[r['row'], 'sentence'], 'roman_urdu_draft': r['roman_urdu']}
          for r in map(json.loads, open('roman/existing_97.jsonl'))]
    rm += [{'set': 'new', 'id': i, 'cid': by_id.loc[i, 'cid'], 'english': by_id.loc[i, 'text'], 'roman_urdu_draft': t} for i, t in new_rm.items()]
    roman = pd.DataFrame(rm).assign(written_by='machine draft, to be checked by the author', ok_yes_no='', corrected_text='')
    assert len(roman) == 240 and not roman.roman_urdu_draft.str.contains('—').any()
    roman.to_csv('roman_urdu_drafts.csv', index=False)
    with pd.ExcelWriter(out) as xw:
        blind.to_excel(xw, sheet_name='1 Label (text only)', index=False)
        check.to_excel(xw, sheet_name='2 Source check', index=False)
        roman.to_excel(xw, sheet_name='3 Roman Urdu check', index=False)
        df.to_excel(xw, sheet_name='4 Provenance', index=False)
    # the closed tag vocabulary as its own sheet, and a drop-down on the gold_tag column of sheet 1
    import openpyxl
    from openpyxl.worksheet.datavalidation import DataValidation
    tags = sorted(TAGS)
    wb = openpyxl.load_workbook(out)
    ws = wb.create_sheet('Tags (227)', 1)
    ws.append(['tag'])
    for tg in tags: ws.append([tg])
    dv = DataValidation(type='list', formula1=f"='Tags (227)'!$A$2:$A${len(tags) + 1}", allow_blank=True)
    wb['1 Label (text only)'].add_data_validation(dv); dv.add(f'C2:C{len(df) + 1}')
    wb.save(out)
    df.to_csv(out.replace('.xlsx', '.csv'), index=False)
    print(len(df), 'rows |', 'rejects', int(df.auto_flags.str.contains('REJECT').sum()), '| type-word flags', int((df.type_words_in_text != '').sum()),
          '| name flags', int((df.name_words_in_text != '').sum()), '| dup existing', int((df.near_dup_existing_rows != '').sum()),
          '| dup new', int((df.near_dup_new_rows != '').sum()), '| length', int(df.auto_flags.str.contains('length').sum()))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
