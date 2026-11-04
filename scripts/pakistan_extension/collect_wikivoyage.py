"""Collect candidate Pakistani place descriptions from English Wikivoyage listings (CC BY-SA 4.0).

Walks Category:Pakistan recursively, reads every article's wikitext at its current revision and keeps
the `content` of each listing template (see/do/buy/eat/drink/sleep/listing). Every row keeps the
article, revision id and listing name so it can be traced back to its source.

usage: python collect_wikivoyage.py OUT.jsonl
"""
import json, os, re, sys, time, urllib.parse, urllib.request
import mwparserfromhell as mw

API = 'https://en.wikivoyage.org/w/api.php'
UA = {'User-Agent': os.environ.get('WIKI_UA', 'adjective-aware-osm-tagging/0.1 (set WIKI_UA to a contact address, per the Wikimedia user-agent policy)')}
KINDS = {'see', 'do', 'buy', 'eat', 'drink', 'sleep', 'listing'}


def api(**p):
    p['format'] = 'json'
    for attempt in range(5):
        try:
            req = urllib.request.Request(API + '?' + urllib.parse.urlencode(p), headers=UA)
            return json.load(urllib.request.urlopen(req, timeout=60))
        except Exception:
            time.sleep(2 ** attempt)
    raise RuntimeError(f'API failed: {p}')


def walk(cat, seen_cats, pages):
    cont = {}
    while True:
        r = api(action='query', list='categorymembers', cmtitle=cat, cmlimit=500, **cont)
        for m in r['query']['categorymembers']:
            if m['ns'] == 14 and m['title'] not in seen_cats:
                seen_cats.add(m['title']); walk(m['title'], seen_cats, pages)
            elif m['ns'] == 0:
                pages.add(m['title'])
        if 'continue' not in r: return
        cont = {'cmcontinue': r['continue']['cmcontinue']}


def text_of(node):
    return mw.parse(str(node)).strip_code().strip() if node is not None else ''


def main(out):
    pages = set(); walk('Category:Pakistan', {'Category:Pakistan'}, pages)
    pages = sorted(pages)
    print(len(pages), 'articles', file=sys.stderr)
    n = 0
    with open(out, 'w') as f:
        for i in range(0, len(pages), 20):
            r = api(action='query', prop='revisions', rvprop='content|ids', rvslots='main',
                    titles='|'.join(pages[i:i + 20]))
            for p in r['query']['pages'].values():
                if 'revisions' not in p: continue
                rev = p['revisions'][0]
                code = mw.parse(rev['slots']['main']['*'])
                for tpl in code.filter_templates():
                    kind = str(tpl.name).strip().lower()
                    if kind not in KINDS: continue
                    get = lambda k: text_of(tpl.get(k).value) if tpl.has(k) else ''
                    content = get('content')
                    if not content: continue
                    f.write(json.dumps({'article': p['title'], 'revid': rev['revid'], 'kind': kind if kind != 'listing' else get('type') or 'listing',
                                        'name': get('name'), 'alt': get('alt'), 'content': content,
                                        'url': 'https://en.wikivoyage.org/w/index.php?oldid=%d' % rev['revid']},
                                       ensure_ascii=False) + '\n')
                    n += 1
                # older articles list places as plain bullets: * '''Name''' - description
                for sec in code.get_sections(levels=[2]):
                    head = sec.filter_headings()[0].title.strip_code().strip().lower()
                    if head not in KINDS: continue
                    for line in str(sec).split('\n'):
                        m = re.match(r"^\*+\s*'''(.+?)'''(.*)$", line)
                        if not m or '{{' in line: continue
                        content = mw.parse(m.group(2)).strip_code().strip(' -–:,.')
                        if not content: continue
                        f.write(json.dumps({'article': p['title'], 'revid': rev['revid'], 'kind': head,
                                            'name': mw.parse(m.group(1)).strip_code().strip(), 'alt': '', 'content': content,
                                            'url': 'https://en.wikivoyage.org/w/index.php?oldid=%d' % rev['revid'], 'format': 'bullet'},
                                           ensure_ascii=False) + '\n')
                        n += 1
            time.sleep(1)
    print(n, 'listings with content', file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv[1])
