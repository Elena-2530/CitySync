"""
Accesso ai dati dei luoghi turistici di Napoli.

I dati stanno in places_napoli.json. Il modulo cerca luoghi per nome, per
categoria e per vicinanza; non inventa mai un luogo che non è nel file.
"""

import json
import math
import re
import unicodedata
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "places_napoli.json"

_cache = {}


def normalize(text):
    """Minuscolo, senza accenti né punteggiatura."""
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(text.split())


def load(path=None):
    """Carica (e tiene in memoria) il file dei luoghi."""
    path = Path(path) if path else DATA_FILE
    key = str(path)
    if key not in _cache:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
        for place in raw["places"]:
            place["_names"] = {normalize(place["name"])} | {
                normalize(a) for a in place.get("aliases", [])
            }
        for area in raw.get("areas", []):
            area["_names"] = {normalize(area["name"])} | {
                normalize(a) for a in area.get("aliases", [])
            }
        _cache[key] = raw
    return _cache[key]


def all_places(data=None):
    return (data or load())["places"]


def get_place(place_id, data=None):
    for place in all_places(data):
        if place["id"] == place_id:
            return place
    return None


def _find_longest(text, items):
    """Elemento il cui nome compare nel testo (vince il nome più lungo)."""
    text = normalize(text)
    if not text:
        return None
    best = None
    for item in items:
        for name in item["_names"]:
            if name and re.search(rf"\b{re.escape(name)}\b", text):
                if best is None or len(name) > best[0]:
                    best = (len(name), item)
    return best[1] if best else None


def find_place(text, data=None):
    """Luogo citato nel testo, oppure None."""
    return _find_longest(text, all_places(data))


def find_area(text, data=None):
    """Zona della città citata nel testo (per le ricerche 'vicino a')."""
    return _find_longest(text, (data or load()).get("areas", []))


def haversine_m(lat1, lon1, lat2, lon2):
    radius = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def nearby(lat, lon, radius_m=1000, data=None, exclude_id=None, limit=None):
    """Luoghi entro radius_m metri, dal più vicino."""
    found = []
    for place in all_places(data):
        if place["id"] == exclude_id:
            continue
        distance = haversine_m(lat, lon, place["lat"], place["lon"])
        if distance <= radius_m:
            found.append((distance, place))
    found.sort(key=lambda item: item[0])
    if limit:
        found = found[:limit]
    return [{"place": place, "distance_m": round(distance)} for distance, place in found]


def by_category(category, data=None):
    return [p for p in all_places(data) if category in p.get("categories", [])]
