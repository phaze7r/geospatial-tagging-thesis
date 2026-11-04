"""All switches and rules of thesisv2 in one place. Nothing here reads data.
Sources: protocol values come from notebook 11 (R-PROTOCOL, R1c, R3, R4b); vocabulary rules are new (written 2026-10-24)."""

# ---- corpus (notebook 11, R1c) ----
LANG_MIN_P = 0.6            # py3langid normalised probability for English
MIN_CONTENT_WORDS = 4
CAP_PER_TAG = 3000          # Pakistani rows are always kept
CORPUS_MIN_PER_TAG = 10     # tags below this stay in the vocabulary but get no table rows ("thin tags")
SPLIT_SALT = 'thesisv2-'    # new salt: the v2 split is independent of the old one
SPLIT_CUTS = (79, 89, 99)   # hash % 100 -> train 0-79, dev 80-89, test 90-99

# ---- mining and models (notebook 11, R3, R4a, R4b) ----
MIN_SUPPORT = 0.0005
FEN_C_GRID = (0.1, 0.5, 2.0)
BEN_WARMUP, BEN_SAMPLES, BEN_CHAINS, BEN_LAM2 = 500, 500, 2, 0.5
LAMS = [round(x * 0.05, 2) for x in range(0, 17)]          # 0.00 .. 0.80
SUPPORT_GRID = (0.002, 0.001, 0.0005, 0.0002, 0.0001)
LC_FRACTIONS_N = (5000, 10000, 20000, 40000, None)         # None = full train

# ---- vocabulary rules (new) ----
VOCAB_FLOOR_EN = 20         # estimated English descriptions per key=value for automatic inclusion
MUST_FLOOR = 10             # tourism/everyday must-have tags: below this they are flagged, not auto-dropped
MIN_TAGS, TARGET_TAGS = 400, 500
LID_SAMPLE_PER_PAIR = 400   # rows classified per key=value to estimate the English share

ALL = 'all'
KEY_RULES = {   # harvested keys (notebook 11, R0e) -> 'all' values, or an explicit set of place-type values
    'amenity': ALL, 'shop': ALL, 'tourism': ALL, 'leisure': ALL, 'historic': ALL, 'natural': ALL, 'office': ALL, 'craft': ALL,
    'man_made': {'tower', 'lighthouse', 'water_tower', 'windmill', 'watermill', 'observatory', 'pier', 'bridge', 'works', 'chimney'},
    'railway': {'station', 'halt', 'tram_stop', 'subway_entrance', 'platform'},
    'building': {'mosque', 'church', 'cathedral', 'chapel', 'temple', 'synagogue', 'shrine', 'hospital', 'school', 'university',
                 'college', 'hotel', 'retail', 'supermarket', 'stadium', 'train_station', 'castle', 'kindergarten', 'civic',
                 'government', 'public', 'house', 'apartments', 'dormitory', 'barn', 'farm', 'bungalow', 'cabin', 'hut', 'tower'},
    'place': {'city', 'town', 'village', 'hamlet', 'suburb', 'neighbourhood', 'island', 'square', 'locality', 'quarter', 'borough'},
    'landuse': {'farmland', 'forest', 'cemetery', 'residential', 'industrial', 'commercial', 'retail', 'meadow', 'orchard', 'vineyard',
                'farmyard', 'grass', 'military'},
    'aeroway': {'aerodrome', 'terminal', 'helipad'},
    'waterway': {'river', 'stream', 'canal', 'waterfall', 'dam', 'dock', 'weir'},
    'highway': {'bus_stop', 'pedestrian', 'footway', 'path', 'cycleway', 'living_street'},
}
EXCLUDE_VALUES = {   # not a place a person would describe
    '*': {'yes', 'no', 'vacant', 'outpost', 'unknown', 'other', 'fixme', 'disused'},
    'amenity': {'parking_space', 'parking_entrance', 'bench', 'waste_basket', 'waste_disposal', 'recycling', 'vending_machine',
                'bicycle_parking', 'motorcycle_parking', 'grit_bin', 'post_box', 'letter_box', 'telephone', 'clock', 'hunting_stand',
                'loading_dock', 'shelter', 'give_box', 'bbq', 'water_point', 'watering_place', 'parcel_locker', 'lounger'},
    'leisure': {'track', 'bleachers', 'fitness_station', 'outdoor_seating', 'firepit', 'slipway', 'common', 'picnic_table',
                'bird_hide', 'swimming_area'},
    'historic': {'boundary_stone', 'wayside_cross', 'charcoal_pile', 'bomb_crater', 'shieling', 'building', 'railway', 'heritage'},
    'natural': {'tree', 'tree_row', 'shrub', 'stone', 'bare_rock', 'scree', 'shingle', 'heath', 'fell', 'mud', 'sinkhole', 'stump'},
    'tourism': {'camp_pitch', 'checkpoint', 'trail_riding_station'},
    'shop': set(), 'office': set(), 'craft': set(),
}
# Tags the user wants covered (Pakistan tourism + everyday). key -> values. Missing or thin ones are reported, never silently dropped.
MUST_HAVE = {
    'tourism': ['viewpoint', 'guest_house', 'hostel', 'chalet', 'information', 'camp_site', 'caravan_site', 'alpine_hut', 'wilderness_hut',
                'museum', 'gallery', 'attraction', 'artwork', 'theme_park', 'zoo', 'aquarium', 'picnic_site', 'hotel', 'motel', 'apartment'],
    'historic': ['archaeological_site', 'fort', 'castle', 'monument', 'memorial', 'tomb', 'wayside_shrine', 'ruins', 'manor',
                 'city_gate', 'citywalls'],
    'natural': ['peak', 'glacier', 'waterfall', 'valley', 'lake', 'hot_spring', 'spring', 'beach', 'cave_entrance', 'cliff', 'hill'],
    'leisure': ['resort', 'nature_reserve', 'garden', 'park', 'golf_course', 'water_park', 'marina', 'swimming_pool', 'playground',
                'stadium', 'fitness_centre', 'sports_centre', 'horse_riding'],
    'amenity': ['marketplace', 'food_court', 'restaurant', 'cafe', 'fast_food', 'fountain', 'ferry_terminal', 'bus_station', 'fuel',
                'toilets', 'doctors', 'police', 'fire_station', 'community_centre', 'veterinary', 'pharmacy', 'hospital', 'clinic', 'bank',
                'atm', 'school', 'college', 'university', 'library', 'cinema', 'theatre', 'post_office', 'taxi', 'car_wash', 'car_rental'],
    'shop': ['convenience', 'clothes', 'hairdresser', 'beauty', 'car_repair', 'hardware', 'butcher', 'mobile_phone', 'furniture', 'kiosk',
             'jewelry', 'shoes', 'electronics', 'florist', 'laundry', 'tailor', 'gift', 'books', 'department_store', 'supermarket', 'mall',
             'bakery', 'greengrocer', 'chemist', 'optician', 'stationery', 'sports', 'toys', 'carpet', 'antiques', 'pet', 'travel_agency'],
}
RELIGION = {'muslim': 'mosque', 'christian': 'church', 'buddhist': 'temple', 'hindu': 'temple', 'jain': 'temple', 'sikh': 'temple',
            'shinto': 'temple', 'taoist': 'temple'}   # amenity=place_of_worship is resolved through the religion tag (notebook 11, R1b)
# Spelling kept from the old lexicon so that the gold labels of the 106 and Pakistan sets stay valid (notebook 11, R1b EXTRA)
TAG_SPELLING = {('shop', 'books'): 'bookshop', ('amenity', 'arts_centre'): 'arts-center', ('highway', 'cycleway'): 'cycle-way',
                ('highway', 'footway'): 'foot-way', ('natural', 'wetland'): 'wet-land', ('natural', 'wood'): 'woods',
                ('natural', 'sinkhole'): 'sink-hole', ('building', 'greenhouse'): 'green-house', ('building', 'houseboat'): 'house-boat',
                ('man_made', 'wastewater_plant'): 'waste-water', ('amenity', 'ice_cream'): 'icecream'}
# Proposed merges (alias -> canonical). The user edits or removes lines at the vocabulary gate.
MERGE_PROPOSAL = {'grave-yard': 'cemetery', 'market': 'marketplace', 'apotheke': 'pharmacy', 'garten': 'garden', 'schloss': 'castle',
                  'rathaus': 'townhall', 'bakehouse': 'bakery', 'retail-area': 'retail', 'food-market': 'marketplace'}

# ---- reference numbers of the base paper (memory note base-papers-yousaf-osm-tagging; Yousaf, Schwartz and Wolter 2023, Tables 4 and 5) ----
# Measured on THEIR 227-tag list and THEIR 106 sentences. Shown as a reference row, never as a same-vocabulary comparison.
BASE_PAPER_PUBLISHED = {
    'W2V': {'Hits@1': 0.1604, 'Hits@5': 0.4717, 'Hits@10': 0.6509, 'Hits@20': 0.7075, 'nDCG@20': 0.3968},
    'W2V Clustered': {'Hits@1': 0.2264, 'Hits@5': 0.5283, 'Hits@10': 0.6509, 'Hits@20': 0.7075, 'nDCG@20': 0.4442},
}

# ---- input locations (read-only) ----
OLD_RAW_PARQUET = 'osmfinal/raw/osm_descriptions.parquet'     # under the old geoproject root
OLD_W2V_CACHES = ('osmfinal/w2v_googlenews_osm.pkl', 'models_cache/w2v_googlenews_subset_v2.pkl')
OLD_NB_CACHES = ('osmfinal/numberbatch_osm.pkl', 'models_cache/numberbatch_subset.pkl')
