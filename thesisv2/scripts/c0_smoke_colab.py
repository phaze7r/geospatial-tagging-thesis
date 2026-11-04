"""Step C0: environment smoke test. Run first on a fresh Colab runtime. Prints GPU, host RAM, library versions, whether Drive and the read-only inputs are
reachable, and whether the copied src files are byte-identical to the originals. Writes manifests/c0.json (record the granted GPU and RAM in STATE.md)."""
import subprocess
from common import *


def sh(cmd):
    try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e: return f'ERR {e}'


def main():
    info = {'on_colab': ON_COLAB, 'home': HOME, 'gpu': sh('nvidia-smi --query-gpu=name,memory.total --format=csv,noheader'), 'ram': sh('free -g | head -2'), 'disk': sh('df -h /content | tail -1'), 'python': sys.version.split()[0]}
    for m in ('numpy', 'pandas', 'scipy', 'sklearn', 'spacy', 'torch', 'jax', 'numpyro', 'gensim', 'py3langid'):
        try: mod = __import__(m); info[m] = getattr(mod, '__version__', 'ok')
        except Exception as e: info[m] = f'MISSING ({type(e).__name__})'
    checks = {}
    if ON_COLAB:
        checks['raw_parquet'] = os.path.exists(os.path.join(OLD, 'osmfinal', 'raw', 'osm_descriptions.parquet'))
        checks['old_src_pipeline_ranker'] = os.path.exists(os.path.join(OLD, 'pipeline_ranker.py'))
        for f in ('pipeline_ranker.py', 'adjective_extractor.py'):
            old = os.path.join(OLD, f); mine = os.path.join(HERE, '..', 'src', f)
            checks[f'src_identical_{f}'] = os.path.exists(old) and sha256_file(old) == sha256_file(mine)
        checks['old_w2v_cache'] = os.path.exists(os.path.join(OLD, 'osmfinal', 'w2v_googlenews_osm.pkl')); checks['old_nb_cache'] = os.path.exists(os.path.join(OLD, 'osmfinal', 'numberbatch_osm.pkl'))
    for f in ('evalset_106.json', 'pk_extended_raw.json', 'pk_translations.json', 'pk528_ids.json', 'pk_subset_ids.json'): checks[f'input_{f}'] = os.path.exists(os.path.join(INPUTS, f))
    info['checks'] = checks; print(json.dumps(info, indent=1)); manifest('c0', [], [], **info)
    if not all(checks.values()): raise SystemExit('some checks failed: ' + str([k for k, v in checks.items() if not v]))


if __name__ == '__main__': main()
