"""Paths, switches, manifests and the seal. Every step script starts with `from common import *`.
Colab: HOME is Drive My Drive/thesisv2. Local: ~/thesisv2 (override with THESISV2_HOME). --smoke (or THESISV2_SMOKE=1) writes to HOME/smoke
and uses tiny sizes, so the whole chain can be debugged in minutes before the real run."""
import os, sys, json, time, hashlib, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'src'))      # byte-identical pipeline_ranker.py and adjective_extractor.py
sys.path.insert(0, HERE)

ON_COLAB = os.path.isdir('/content/drive/MyDrive')
HOME = '/content/drive/MyDrive/thesisv2' if ON_COLAB else os.environ.get('THESISV2_HOME', os.path.abspath(os.path.join(HERE, '..')))
OLD = '/content/drive/MyDrive/geoproject' if ON_COLAB else os.environ.get('THESISV2_OLD', '')    # read-only inputs of the finished work
SMOKE = ('--smoke' in sys.argv) or os.environ.get('THESISV2_SMOKE') == '1'
WORK = os.path.join(HOME, 'smoke') if SMOKE else HOME
REPO = os.path.abspath(os.path.join(HERE, '..'))                                                    # the thesisv2 code folder (also Drive thesisv2/ after the push)
INPUTS = os.path.join(os.path.abspath(os.path.join(HERE, '..')), 'data', 'inputs')              # small read-only copies kept in the repo


def P(*a):
    """path under WORK; parent folder is created"""
    p = os.path.join(WORK, *a); os.makedirs(os.path.dirname(p), exist_ok=True); return p


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def sha256_text(s): return hashlib.sha256(s.encode()).hexdigest()


def jload(path):
    with open(path) as f: return json.load(f)


def jdump(obj, path, indent=1):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f: json.dump(obj, f, indent=indent, default=_jdefault)


def _jdefault(o):
    import numpy as np
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return float(o)
    if isinstance(o, np.ndarray): return o.tolist()
    if isinstance(o, set): return sorted(o)
    raise TypeError(type(o))


def manifest(step, inputs=(), outputs=(), **extra):
    """one JSON per step: inputs and outputs with sha256 and size, row counts or other facts in `extra`"""
    def rec(p): return {'path': p, 'bytes': os.path.getsize(p), 'sha256': sha256_file(p)} if os.path.isfile(p) else {'path': p, 'missing': True}
    m = {'step': step, 'utc': datetime.datetime.utcnow().isoformat() + 'Z', 'smoke': SMOKE, 'host': 'colab' if ON_COLAB else 'local',
         'inputs': [rec(p) for p in inputs], 'outputs': [rec(p) for p in outputs], **extra}
    out = P('manifests', f'{step}.json')
    with open(out, 'w') as f: json.dump(m, f, indent=1, default=_jdefault)
    print(f'[manifest] {out}')
    return m


# ---- the seal: the test rows live in their own file and only step 8 may open it ----
FLAG = P('protocol', 'TEST_SCORED.flag')
FROZEN = P('protocol', 'PROTOCOL_FROZEN.json')


def corpus_traindev():
    import pandas as pd
    return pd.read_parquet(P('corpus', 'osm_traindev.parquet'))


def open_test_once(step='s08'):
    """returns the sealed test rows. Refuses unless the protocol is frozen, the test hash matches, and the flag is absent; then writes the flag."""
    import pandas as pd
    assert step == 's08', 'only step s08 may open the test split'
    assert os.path.exists(FROZEN), 'protocol is not frozen (run s07 and confirm the gate)'
    assert not os.path.exists(FLAG), 'test set already scored once; read the results instead'
    te = pd.read_parquet(P('corpus', 'osm_test_sealed.parquet'))
    want = jload(P('corpus', 'split_stats.json'))['test_sha256_of_sorted_ids']
    assert sha256_text('\n'.join(sorted(te.osm_id))) == want, 'test set differs from the one hashed at split time'
    fz = jload(FROZEN)
    assert fz['test_sha256_of_sorted_ids'] == want, 'frozen protocol was written for a different test set'
    return te


def write_flag():
    with open(FLAG, 'w') as f: f.write(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))


def raw_parquet_path():
    if SMOKE: return P('data', 'synthetic_raw.parquet')
    p = os.path.join(OLD, 'osmfinal', 'raw', 'osm_descriptions.parquet')
    assert os.path.exists(p), f'raw harvest not found: {p} (mount Drive; this file is read-only input)'
    return p
