"""Strip outputs, execution counts and Colab metadata (which holds the account name, id and photo URL)
from notebooks before they are committed. usage: python tools/strip_notebooks.py notebooks/*.ipynb"""
import json, sys

for path in sys.argv[1:]:
    nb = json.load(open(path))
    nb['metadata'] = {k: v for k, v in nb.get('metadata', {}).items() if k in ('kernelspec', 'language_info')}
    for c in nb['cells']:
        c['metadata'] = {}
        if c['cell_type'] == 'code': c['outputs'], c['execution_count'] = [], None
    json.dump(nb, open(path, 'w'), indent=1, ensure_ascii=False); open(path, 'a').write('\n')
    print('stripped', path)
