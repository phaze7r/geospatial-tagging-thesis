"""Step 3: extraction of nouns, adjectives and pairs with the unchanged thesis extractor (en_core_web_trf + PlaceInterpreter), TRAIN AND DEV ONLY.
The test rows are extracted in step 8. Chunked and resumable (Colab can drop the session): finished chunks are skipped on rerun. Needs a GPU runtime for speed."""
from v2lib import *
ensure_spacy_model()
CHUNK = 20000


def main():
    D = pd.read_parquet(P('corpus', 'osm_traindev.parquet')); assert not (D.split == 'test').any()
    parts = []; t0 = time.time()
    for a in range(0, len(D), CHUNK):
        f = P('extracted', f'part_{a // CHUNK:03d}.parquet'); parts.append(f)
        if os.path.exists(f): continue
        C = D.iloc[a:a + CHUNK].copy(); rows = extract(C.text.tolist(), batch=256)
        C['context_nouns'] = [json.dumps(r['context_nouns']) for r in rows]; C['adjectives'] = [json.dumps(r['adjectives']) for r in rows]
        C['transaction'] = [json.dumps(r['transaction']) for r in rows]; C.to_parquet(f)
        print(f'chunk {a // CHUNK}: {a + len(C):,}/{len(D):,} rows, {time.time()-t0:.0f}s')
    E = pd.concat([pd.read_parquet(f) for f in parts], ignore_index=True)
    out = P('extracted', 'osm_traindev_extracted.parquet'); E.to_parquet(out)
    has_adj = (E.adjectives.map(lambda s: len(json.loads(s))) > 0).mean()
    print(f'extracted {len(E):,} rows | rows with >=1 adjective {has_adj:.1%}')
    manifest('s03', [P('corpus', 'osm_traindev.parquet')], [out], rows=len(E), rows_with_adjective=float(has_adj), seconds=time.time() - t0)


if __name__ == '__main__': main()
