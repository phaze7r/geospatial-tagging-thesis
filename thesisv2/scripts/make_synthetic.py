"""Smoke-test data: a tiny synthetic stand-in for the raw OSM harvest (same columns as notebook 11 R0e). Only for --smoke runs; not data of the thesis.
Values are chosen from tags whose vectors exist in the finished-work caches, so the whole chain can run locally and on a CPU Colab runtime."""
from common import *
import random
import pandas as pd

TAGS = {  # (key, value, religion): nouns
    ('amenity', 'cafe', None): ['coffee', 'tea', 'cake', 'sandwiches', 'wifi', 'espresso'],
    ('amenity', 'restaurant', None): ['karahi', 'naan', 'kebab', 'curry', 'menu', 'dishes'],
    ('tourism', 'hotel', None): ['rooms', 'breakfast', 'pool', 'lobby', 'staff', 'beds'],
    ('tourism', 'museum', None): ['exhibits', 'galleries', 'artifacts', 'tickets', 'sculptures', 'history'],
    ('leisure', 'park', None): ['lawns', 'trees', 'playground', 'benches', 'paths', 'lake'],
    ('amenity', 'place_of_worship', 'muslim'): ['minarets', 'dome', 'prayer', 'courtyard', 'carpet', 'imam'],
    ('amenity', 'place_of_worship', 'christian'): ['bells', 'altar', 'pews', 'choir', 'tower', 'service'],
    ('shop', 'bakery', None): ['bread', 'cakes', 'cookies', 'pastries', 'oven', 'counter'],
    ('amenity', 'pharmacy', None): ['medicine', 'pharmacist', 'tablets', 'prescriptions', 'counter', 'syrups'],
    ('shop', 'books', None): ['books', 'novels', 'magazines', 'shelves', 'authors', 'textbooks'],
    ('amenity', 'school', None): ['classrooms', 'teachers', 'pupils', 'playground', 'library', 'exams'],
    ('amenity', 'bank', None): ['accounts', 'cashiers', 'loans', 'machine', 'counter', 'queue'],
}
ADJ = ['cheap', 'quiet', 'cozy', 'fresh', 'historic', 'ancient', 'spacious', 'busy', 'clean', 'friendly', 'old', 'modern', 'popular', 'small', 'large', 'beautiful']
FILL = ['near the market', 'on the main road', 'in the old town', 'close to the station', 'next to the river', 'opposite the park', 'behind the mall', 'by the bridge']


def main():
    rs = random.Random(0); rows = []; n = 0
    per = 160 if not os.environ.get('SYNTH_ROWS') else int(os.environ['SYNTH_ROWS'])
    for (k, v, rel), nouns in TAGS.items():
        for i in range(per):
            a1, a2 = rs.sample(ADJ, 2); n1, n2 = rs.sample(nouns, 2); name = f'{rs.choice(["Al", "Royal", "Green", "City", "New"])} {rs.choice(["Point", "House", "Corner", "Palace", "Garden"])} {n}'
            text = f'A {a1} place {rs.choice(FILL)} with {a2} {n1} and {n2}, ' + rs.choice(['open every day', 'loved by locals', 'worth the visit', 'easy to find']) + f' {rs.randint(1, 900)}'
            n += 1; rows.append({'osm_id': f'node/{n}', 'key': k, 'value': v, 'description': text, 'name': name, 'religion': rel, 'pakistan': rs.random() < 0.12})
    for j in range(80):    # rows that must be dropped: non-English and excluded values
        n += 1; rows.append({'osm_id': f'node/{n}', 'key': 'amenity', 'value': 'bench', 'description': f'Eine schöne Bank am Fluss {j}', 'name': None, 'religion': None, 'pakistan': False})
    df = pd.DataFrame(rows); out = P('data', 'synthetic_raw.parquet'); df.to_parquet(out); print(f'wrote {out}: {len(df)} rows')


if __name__ == '__main__': main()
