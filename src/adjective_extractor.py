"""
adjective_extractor.py
======================
Adjective-enhanced place description interpreter.

Replaces the legacy parse.py + database.py pipeline (NLTK regex chunking +
hardcoded lookups) with a spaCy dependency-parse implementation of
Yousaf, Schwartz & Wolter (2023) Algorithm 1 ("Noun extraction"),
EXTENDED with the adjective layer their paper lists as future work:

  Paper (nouns only)                This module (nouns + adjectives)
  ---------------------------------------------------------------------
  named entities   (gazetteer)      same, via NER + gazetteer hook
  unnamed entities (OSM category)   same, via OSM category lexicon
  context nouns    (everything else) same
  -- adjectives discarded (fn. 6)   amod / acomp / conj adjectives kept,
                                    attached to their head noun, and
                                    mapped to OSM tag hints (cuisine=*,
                                    building:material=*, historic=*, ...)

Output per sentence:
  * entities:     [{phrase, head, category, osm_key}]
  * pairs:        [(adjective, noun, relation)]      -> FP-Growth items
  * context:      [context nouns]                    -> Word2Vec ranking
  * tag_hints:    [{key, value, evidence}]           -> direct OSM query
  * transaction:  flat item list                     -> one FP-Growth basket

Usage:
  from adjective_extractor import PlaceInterpreter
  pi = PlaceInterpreter()                    # loads spaCy once
  result = pi.interpret("This Persian place on Elizabeth Street makes "
                        "some of the best bread in the city")
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
import spacy

# --------------------------------------------------------------------------
# 1. OSM category lexicon
#    Same role as the legacy land/building/water dicts in database.py and the
#    Building/waterway/... lists in osmdb.py, merged, lemma-keyed, and mapped
#    to real OSM keys so Overpass queries can be generated directly.
#    Extend freely -- lemmas only (parser handles plurals/case).
# --------------------------------------------------------------------------
OSM_NOUN_LEXICON = {
    # noun lemma        (osm_key,      geometry hints)
    "city":       ("place",     ["region", "point"]),
    "town":       ("place",     ["region", "point"]),
    "village":    ("place",     ["region", "point"]),
    "country":    ("admin_level=2", ["region"]),
    "district":   ("admin_level",   ["region"]),
    "valley":     ("natural",   ["region", "point"]),
    "hill":       ("natural",   ["region", "point"]),
    "mountain":   ("natural",   ["region", "point"]),
    "plain":      ("natural",   ["region"]),
    "plateau":    ("natural",   ["region"]),
    "cliff":      ("natural",   ["line"]),
    "beach":      ("natural",   ["region"]),
    "glacier":    ("natural",   ["region"]),
    "wood":       ("natural",   ["region"]),
    "forest":     ("landuse",   ["region"]),
    "park":       ("leisure",   ["region", "point"]),
    "garden":     ("leisure",   ["region", "point"]),
    "market":     ("amenity",   ["region", "point"]),
    "bazaar":     ("amenity=marketplace", ["region", "point"]),
    "street":     ("highway",   ["line"]),
    "road":       ("highway",   ["line"]),
    "highway":    ("highway",   ["line"]),
    "bridge":     ("bridge",    ["line"]),
    "river":      ("waterway",  ["line"]),
    "stream":     ("waterway",  ["line"]),
    "canal":      ("waterway",  ["line"]),
    "lake":       ("water",     ["region"]),
    "pond":       ("water",     ["region"]),
    "sea":        ("water",     ["region"]),
    "ocean":      ("water",     ["region"]),
    "church":     ("building=church",   ["point", "region"]),
    "mosque":     ("building=mosque",   ["point", "region"]),
    "shrine":     ("historic=shrine",   ["point"]),
    "temple":     ("building=temple",   ["point", "region"]),
    "fort":       ("historic=fort",     ["point", "region"]),
    "castle":     ("historic=castle",   ["point", "region"]),
    "station":    ("railway=station",   ["point"]),
    "hotel":      ("tourism=hotel",     ["point", "region"]),
    "museum":     ("tourism=museum",    ["point", "region"]),
    "hospital":   ("amenity=hospital",  ["point", "region"]),
    "school":     ("amenity=school",    ["point", "region"]),
    "university": ("amenity=university",["point", "region"]),
    "office":     ("office",            ["point"]),
    "shop":       ("shop",              ["point"]),
    "house":      ("building=house",    ["point"]),
    "restaurant": ("amenity=restaurant",["point"]),
    "cafe":       ("amenity=cafe",      ["point"]),
    "bakery":     ("shop=bakery",       ["point"]),
    "stadium":    ("leisure=stadium",   ["region"]),
}

# --------------------------------------------------------------------------
# 2. Adjective -> OSM tag-hint lexicon  (the new layer)
#    Three classes of adjective, handled differently:
#      DIRECT   : adjective alone implies a key=value  ("Italian" -> cuisine)
#      MODIFIER : adjective refines the noun's tag     ("brick" -> material)
#      VAGUE    : subjective; no tag, but KEPT as an FP-Growth item because
#                 the Bayesian Elastic Net decides post-hoc whether e.g.
#                 "scenic" correlates with natural=* places. Never hardcode
#                 them away -- that is the whole point of the mining stage.
# --------------------------------------------------------------------------
ADJ_DIRECT = {
    # cuisine / ethnicity adjectives -> cuisine=* (nationality demonyms)
    "italian": ("cuisine", "italian"), "persian": ("cuisine", "persian"),
    "chinese": ("cuisine", "chinese"), "cantonese": ("cuisine", "chinese"),
    "afghan": ("cuisine", "afghan"),   "turkish": ("cuisine", "turkish"),
    "pakistani": ("cuisine", "pakistani"), "indian": ("cuisine", "indian"),
    "japanese": ("cuisine", "japanese"), "thai": ("cuisine", "thai"),
    "french": ("cuisine", "french"),   "mexican": ("cuisine", "mexican"),
    "vegan": ("diet:vegan", "yes"),    "vegetarian": ("diet:vegetarian", "yes"),
    "halal": ("diet:halal", "yes"),
}
ADJ_MODIFIER = {
    # material
    "brick": ("building:material", "brick"),
    "stone": ("building:material", "stone"),
    "wooden": ("building:material", "wood"),
    "marble": ("building:material", "marble"),
    # age / heritage
    "old": ("historic", "*"), "ancient": ("historic", "*"),
    "historic": ("historic", "*"), "colonial": ("historic", "*"),
    "medieval": ("historic", "*"), "mughal": ("historic", "*"),
    # access / status
    "abandoned": ("abandoned", "yes"), "ruined": ("ruins", "yes"),
    "pedestrian": ("highway", "pedestrian"),
    "residential": ("landuse", "residential"),
    "commercial": ("landuse", "commercial"),
    "industrial": ("landuse", "industrial"),
}
# everything else (nice, bustling, scenic, crowded, narrow ...) = VAGUE:
# emitted as pair items only, weighted later by FP-Growth + Elastic Net.

PLACE_HINT_NOUNS = {"place", "spot", "location", "area", "site", "position"}

# Heritage adjectives are only evidence of historic=* when the thing they modify
# can BE historic. Without this gate "old street" / "old friend" emit a heritage
# tag hint, which is noise: `old` is one of the commonest adjectives in the corpus.
HERITAGE_NOUNS = {
    "fort", "fortress", "citadel", "castle", "palace", "tomb", "monument", "ruin",
    "church", "mosque", "temple", "shrine", "cathedral", "chapel", "abbey",
    "monastery", "tower", "gate", "wall", "bridge", "mill", "manor", "building",
    "house", "quarter", "city", "town", "village", "district", "museum", "site",
}
HERITAGE_ADJ = {"old", "ancient", "historic", "colonial", "medieval", "mughal"}


def adj_form(tok):
    """Surface form to use for an adjective token.

    spaCy lemmatizes participial adjectives with their VERB lemma:
    'winding streets' -> 'wind', 'sprawling' -> 'sprawl', 'bustling' -> 'bustle'.
    Correct verb morphology, wrong descriptor -- the adjective is 'winding'. Keep
    the surface form for participles (VBG/VBN); lemma otherwise, so comparatives
    still normalize ('narrower' -> 'narrow').
    """
    if tok.tag_ in ("VBG", "VBN"):
        return tok.text.lower()
    return tok.lemma_.lower()


@dataclass
class Entity:
    phrase: str
    head_lemma: str
    category: str            # named | unnamed | context
    osm_key: str | None = None
    geometry: list = field(default_factory=list)
    adjectives: list = field(default_factory=list)


@dataclass
class Interpretation:
    sentence: str
    entities: list
    pairs: list              # (adj_lemma, noun_lemma, relation)
    context_nouns: list
    tag_hints: list          # [{key, value, evidence}]
    transaction: list        # FP-Growth basket

    def to_dict(self):
        return asdict(self)


class PlaceInterpreter:
    def __init__(self, model: str = "en_core_web_sm", gazetteer=None):
        """gazetteer: optional callable lemma->bool (GeoNames/OSM lookup).
        Falls back to spaCy NER (GPE/LOC/FAC) if None -- same role GeoText
        played in the legacy database.py, minus the hardcoded Bavaria hacks."""
        self.nlp = spacy.load(model)
        self.gazetteer = gazetteer

    # ---- adjective harvesting ------------------------------------------
    def _adjectives_for(self, noun_tok):
        """All adjectives modifying noun_tok:
        amod ('narrow street'), conj-expanded amod ('old and crowded bazaar'
        -> both), and predicative acomp/attr via copula ('the valley is
        breathtaking'). Legacy regex chunking captured none of these."""
        adjs = []
        for child in noun_tok.children:
            if child.dep_ == "amod":
                adjs.append(child)
                adjs += [c for c in child.conjuncts if c.pos_ == "ADJ"]
        # predicative: noun is nsubj of a copula whose acomp/attr is the
        # adjective. Handles 'the valley is breathtaking' including cases
        # where the adjective itself heads the clause ('valley' <-nsubj-
        # 'breathtaking' with 'is' as cop), which small models produce.
        if noun_tok.dep_ == "nsubj":
            head = noun_tok.head
            if head.pos_ == "ADJ":                       # adj-headed copula
                adjs.append(head)
                adjs += [c for c in head.conjuncts if c.pos_ == "ADJ"]
            elif head.lemma_ in ("be", "seem", "look", "feel", "remain"):
                found = [c for c in head.children
                         if c.dep_ in ("acomp", "attr") and c.pos_ == "ADJ"]
                adjs += found
                for a in found:
                    adjs += [c for c in a.conjuncts if c.pos_ == "ADJ"]
        # dedupe preserving order
        seen, out = set(), []
        for a in adjs:
            if a.i not in seen:
                seen.add(a.i); out.append(a)
        return out

    def _compound_phrase(self, noun_tok):
        """'art building' -> single unit, mirroring the paper's noun-merging
        rule, but via the parser's compound relation instead of adjacency."""
        parts = [t for t in noun_tok.children if t.dep_ == "compound"]
        toks = sorted(parts + [noun_tok], key=lambda t: t.i)
        return " ".join(t.text for t in toks), toks

    def _is_named(self, noun_tok):
        if self.gazetteer and self.gazetteer(noun_tok.text):
            return True
        return noun_tok.ent_type_ in ("GPE", "LOC", "FAC")

    # ---- Algorithm 1, extended -----------------------------------------
    @staticmethod
    def _evidence(adj_lemma, phrase):
        """'{adjective} {phrase}' without duplicating a word phrase already
        contains. Needed because a compound child reclassified as amod (e.g.
        'brick' in 'brick shops') is already inside `phrase`; naively
        prefixing it produced 'brick brick shops'."""
        if phrase.lower().split()[:1] == [adj_lemma]:
            return phrase
        return f"{adj_lemma} {phrase}"

    def interpret(self, sentence: str) -> Interpretation:
        """Single sentence -> Interpretation."""
        return self.interpret_doc(self.nlp(sentence))

    def pipe(self, texts, batch_size: int = 128):
        """Batched interpretation over many texts -- one spaCy pass per batch.

        Exists so corpus-scale callers (Block D) reuse THIS logic instead of
        re-inlining it; two copies drift the moment either is fixed.
        """
        for doc in self.nlp.pipe(texts, batch_size=batch_size):
            yield self.interpret_doc(doc)

    def interpret_doc(self, doc) -> Interpretation:
        """The actual Algorithm-1-plus-adjectives implementation."""
        sentence = doc.text
        entities, pairs, context, hints, basket = [], [], [], [], []

        for tok in doc:
            if tok.pos_ not in ("NOUN", "PROPN"):
                continue
            if tok.dep_ == "compound":       # consumed by its head noun
                continue

            phrase, phrase_toks = self._compound_phrase(tok)
            adjs = self._adjectives_for(tok)
            adj_lemmas = [adj_form(a) for a in adjs]

            # --- categorize noun (paper's Algorithm 1) ---
            lemma = tok.lemma_.lower()
            if self._is_named(tok):
                cat, key, geom = "named", None, []
            elif lemma in OSM_NOUN_LEXICON:
                key, geom = OSM_NOUN_LEXICON[lemma]
                cat = "unnamed"
            else:
                cat, key, geom = "context", None, []
                context.append(lemma)

            entities.append(Entity(phrase, lemma, cat, key, geom, adj_lemmas))

            # --- pair extraction (new) ---
            for a in adj_lemmas:
                pairs.append((a, lemma, "amod"))
                basket.append(f"amod:{a}_{lemma}")
            for c in phrase_toks[:-1]:       # noun-noun compounds
                cl = adj_form(c) if c.pos_ == "ADJ" else c.lemma_.lower()
                # Small parsers frequently mislabel adjectives as compounds
                # ("vegan cafe"). If the compound part is in an adjective
                # lexicon or POS-tagged ADJ, treat it as amod instead.
                if cl in ADJ_DIRECT or cl in ADJ_MODIFIER or c.pos_ == "ADJ":
                    pairs.append((cl, lemma, "amod"))
                    basket.append(f"amod:{cl}_{lemma}")
                    adj_lemmas.append(cl)
                else:
                    pairs.append((cl, lemma, "compound"))
                    basket.append(f"compound:{cl}_{lemma}")

            # --- adjective -> tag hints (new) ---
            for a in adj_lemmas:
                if a in ADJ_DIRECT:
                    k, v = ADJ_DIRECT[a]
                    hints.append({"key": k, "value": v,
                                  "evidence": self._evidence(a, phrase)})
                elif a in ADJ_MODIFIER:
                    # heritage adjectives need a heritage-capable head noun
                    if a in HERITAGE_ADJ and lemma not in HERITAGE_NOUNS:
                        continue
                    k, v = ADJ_MODIFIER[a]
                    hints.append({"key": k, "value": v,
                                  "evidence": self._evidence(a, phrase)})

            # abstract place nouns ('place', 'spot') flag a paraphrased
            # entity exactly as in the paper's running example
            if lemma in PLACE_HINT_NOUNS:
                basket.append("paraphrased_place")

        for cn in context:
            basket.append(f"ctx:{cn}")
        for e in entities:
            if e.category == "unnamed":
                basket.append(f"type:{e.head_lemma}")

        return Interpretation(sentence, [asdict(e) for e in entities],
                              pairs, context, hints, basket)


# --------------------------------------------------------------------------
# Overpass query hint assembly: combines the paper's type-based querying
# (osmdb.py's role) with the new adjective constraints. For "Persian place":
# noun gives nothing queryable, adjective gives cuisine=persian -- which is
# precisely the case the noun-only pipeline could not geo-reference.
# --------------------------------------------------------------------------
def overpass_filters(result: Interpretation):
    filters = []
    for h in result.tag_hints:
        filters.append(f'["{h["key"]}"' + (f'="{h["value"]}"]' if h["value"] != "*" else "]"))
    for e in result.entities:
        if e["category"] == "unnamed" and e["osm_key"]:
            k = e["osm_key"]
            filters.append(f'["{k}"]' if "=" not in k
                           else '["{}"="{}"]'.format(*k.split("=")))
    return filters


if __name__ == "__main__":
    pi = PlaceInterpreter()
    tests = [
        # paper's own hard cases
        "This Persian place on Elizabeth Street makes some of the best bread in the city",
        "Royal China is the place to be when you want dim sum, duck, and Cantonese dishes",
        "This place has great coffee",
        # your target register
        "The narrow winding streets of Raja Bazaar are lined with old brick shops",
        "The valley is breathtaking and the ancient fort overlooks a small vegan cafe",
    ]
    for s in tests:
        r = pi.interpret(s)
        print("=" * 70)
        print(s)
        print(" pairs:      ", r.pairs)
        print(" context:    ", r.context_nouns)
        print(" tag hints:  ", r.tag_hints)
        print(" transaction:", r.transaction)
        print(" overpass:   ", overpass_filters(r))
