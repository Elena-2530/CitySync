"""
Rete di trasporto pubblico usata dal Mobility Agent.

Questo modulo NON contiene informazioni in tempo reale: descrive la rete
"programmata" (fermate, linee, luoghi noti). Le interruzioni e i ritardi
arrivano dal chiamante (context["transport_data"]["services"]) e vengono
trasformati qui in vincoli per il pianificatore.

La rete può provenire da:
  1. un feed GTFS (cartella con stops.txt, routes.txt, trips.txt,
     stop_times.txt), indicata dalla variabile d'ambiente
     NEURAPOLIS_GTFS_DIR oppure passata a load_gtfs_directory();
  2. la rete dimostrativa network_demo.json, usata se non c'è un GTFS.
"""

import csv
import json
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
DEMO_NETWORK_FILE = DATA_DIR / "network_demo.json"

WALK_SPEED_M_PER_MIN = 80
WALK_DETOUR_FACTOR = 1.3

_FILLER_WORDS = {
    "napoli", "citta", "zona", "area", "piazza", "piazzale", "stazione",
    "di", "del", "della", "dello", "dell", "dei", "delle", "da", "a",
    "il", "lo", "la", "l", "i", "gli", "le", "un", "una", "al", "alla",
    "allo", "all", "in", "presso", "metro", "fermata"
}

_network_cache = {}


# ----------------------------------------------------------------------
# Utilità
# ----------------------------------------------------------------------

def normalize(text):
    """Minuscolo, senza accenti né punteggiatura."""
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(text.split())


def normalize_place(text):
    """Come normalize(), ma toglie anche articoli e parole generiche."""
    words = [w for w in normalize(text).split() if w not in _FILLER_WORDS]
    return " ".join(words)


def haversine_m(lat1, lon1, lat2, lon2):
    radius = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def walking_minutes(distance_m):
    """
    Tempo a piedi stimato (percorso reale ≈ 1,3 × distanza in linea d'aria).
    Sotto i 50 metri si considera di essere già sul posto.
    """
    if distance_m < 50:
        return 0
    return max(1, round(distance_m * WALK_DETOUR_FACTOR / WALK_SPEED_M_PER_MIN))


# ----------------------------------------------------------------------
# Caricamento della rete
# ----------------------------------------------------------------------

def _build_network(meta, stops, lines, places):
    for line in lines.values():
        line.setdefault("aliases", [])
        line["aliases"] = list(line["aliases"])
        line["_alias_norm"] = {normalize(line["name"]), normalize(line["id"])} | {
            normalize(a) for a in line["aliases"]
        }
    return {"meta": meta, "stops": stops, "lines": lines, "places": places}


def load_network(path=None):
    """Carica una rete da un file JSON (per default quella dimostrativa)."""
    path = Path(path) if path else DEMO_NETWORK_FILE
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)

    stops = {
        stop_id: {"id": stop_id, **info}
        for stop_id, info in raw["stops"].items()
    }
    lines = {
        line_id: {"id": line_id, **info}
        for line_id, info in raw["lines"].items()
    }

    for line in lines.values():
        hops = line.get("hop_minutes") or []
        if len(hops) != len(line["stops"]) - 1:
            raise ValueError(
                f"Linea {line['id']}: servono {len(line['stops']) - 1} tempi di tratta."
            )
        for stop_id in line["stops"]:
            if stop_id not in stops:
                raise ValueError(f"Linea {line['id']}: fermata sconosciuta {stop_id}.")

    return _build_network(raw.get("meta", {}), stops, lines, raw.get("places", []))


def _read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _time_to_minutes(value):
    """HH:MM:SS (anche oltre le 24) → minuti."""
    try:
        h, m, s = (int(x) for x in value.strip().split(":"))
        return h * 60 + m + s / 60
    except (ValueError, AttributeError):
        return None


def load_gtfs_directory(folder, max_lines=None):
    """
    Costruisce la rete da un feed GTFS già scaricato e decompresso.

    Per ogni linea (route) usa la corsa più frequente nella direzione 0
    (o, se manca, la prima direzione disponibile) come sequenza di fermate
    e calcola i tempi di tratta medi da stop_times.txt.
    Il GTFS contiene orari PROGRAMMATI: non sono dati in tempo reale.
    """
    folder = Path(folder)
    stops_rows = _read_csv(folder / "stops.txt")
    routes_rows = _read_csv(folder / "routes.txt")
    trips_rows = _read_csv(folder / "trips.txt")
    times_rows = _read_csv(folder / "stop_times.txt")

    stops = {}
    for row in stops_rows:
        try:
            stops[row["stop_id"]] = {
                "id": row["stop_id"],
                "name": row.get("stop_name") or row["stop_id"],
                "lat": float(row["stop_lat"]),
                "lon": float(row["stop_lon"]),
            }
        except (KeyError, ValueError):
            continue

    route_info = {r["route_id"]: r for r in routes_rows if r.get("route_id")}
    trip_route = {}
    trip_direction = {}
    for row in trips_rows:
        trip_route[row["trip_id"]] = row["route_id"]
        trip_direction[row["trip_id"]] = row.get("direction_id") or "0"

    by_trip = defaultdict(list)
    for row in times_rows:
        try:
            by_trip[row["trip_id"]].append(
                (int(row["stop_sequence"]), row["stop_id"],
                 _time_to_minutes(row.get("arrival_time") or row.get("departure_time")))
            )
        except (KeyError, ValueError):
            continue

    patterns = defaultdict(Counter)
    pattern_times = defaultdict(list)
    for trip_id, items in by_trip.items():
        route_id = trip_route.get(trip_id)
        if route_id is None:
            continue
        items.sort()
        seq = tuple(stop_id for _, stop_id, _ in items if stop_id in stops)
        if len(seq) < 2:
            continue
        key = (route_id, trip_direction.get(trip_id, "0"))
        patterns[key][seq] += 1
        pattern_times[(key, seq)].append([t for _, sid, t in items if sid in stops])

    chosen = {}
    for (route_id, direction), counter in patterns.items():
        best_seq = counter.most_common(1)[0][0]
        if route_id not in chosen or direction == "0":
            chosen[route_id] = ((route_id, direction), best_seq)

    lines = {}
    used_stops = set()
    for route_id, (key, seq) in chosen.items():
        samples = pattern_times[(key, seq)]
        hops = []
        for i in range(len(seq) - 1):
            diffs = [
                s[i + 1] - s[i] for s in samples
                if s[i] is not None and s[i + 1] is not None and s[i + 1] >= s[i]
            ]
            hops.append(max(1, round(sum(diffs) / len(diffs))) if diffs else 3)
        info = route_info.get(route_id, {})
        short = info.get("route_short_name") or route_id
        lines[route_id] = {
            "id": route_id,
            "name": info.get("route_long_name") or short,
            "operator": info.get("agency_id") or "",
            "mode": "rail" if str(info.get("route_type")) in {"1", "2", "12"} else "bus",
            "aliases": [short],
            "stops": list(seq),
            "hop_minutes": hops,
        }
        used_stops.update(seq)
        if max_lines and len(lines) >= max_lines:
            break

    stops = {sid: info for sid, info in stops.items() if sid in used_stops}
    meta = {
        "name": f"GTFS: {folder.name}",
        "source": f"gtfs:{folder.name}",
        "data_type": "static_gtfs",
        "verified": False,
        "realtime": False,
        "notes": "Orari programmati da GTFS: non indicano ritardi o soppressioni in corso.",
    }
    return _build_network(meta, stops, lines, [])


def get_network(force_reload=False):
    """Rete in uso: GTFS se indicato da NEURAPOLIS_GTFS_DIR, altrimenti demo."""
    gtfs_dir = os.environ.get("NEURAPOLIS_GTFS_DIR")
    key = gtfs_dir or "demo"
    if force_reload or key not in _network_cache:
        _network_cache[key] = (
            load_gtfs_directory(gtfs_dir) if gtfs_dir else load_network()
        )
    return _network_cache[key]


# ----------------------------------------------------------------------
# Luoghi, fermate e linee
# ----------------------------------------------------------------------

def resolve_place(text, network=None):
    """
    Trasforma un testo ("Piazza Garibaldi, Napoli") in un luogo con coordinate.

    Cerca prima tra i luoghi noti, poi tra le fermate. Restituisce None se non
    riconosce nulla: l'agente non deve inventare una posizione.
    """
    network = network or get_network()
    query = normalize_place(text)
    if not query:
        return None

    candidates = []

    for place in network.get("places", []):
        names = [place["name"]] + list(place.get("aliases", []))
        for name in names:
            alias = normalize_place(name)
            if alias:
                candidates.append((alias, 0, {
                    "name": place["name"], "lat": place["lat"], "lon": place["lon"],
                    "kind": "place", "approximate": True,
                }))

    for stop in network["stops"].values():
        alias = normalize_place(stop["name"])
        if alias:
            candidates.append((alias, 1, {
                "name": stop["name"], "lat": stop["lat"], "lon": stop["lon"],
                "kind": "stop", "stop_id": stop["id"], "approximate": True,
            }))

    best = None
    for alias, priority, info in candidates:
        if query == alias:
            score = (3, len(alias), -priority)
        elif re.search(rf"\b{re.escape(alias)}\b", query):
            score = (2, len(alias), -priority)
        elif re.search(rf"\b{re.escape(query)}\b", alias) and len(query) >= 4:
            score = (1, len(query), -priority)
        else:
            continue
        if best is None or score > best[0]:
            best = (score, info)

    return dict(best[1]) if best else None


def stops_near(lat, lon, radius_m, network=None, limit=None):
    """Fermate entro radius_m metri, dalla più vicina."""
    network = network or get_network()
    found = []
    for stop in network["stops"].values():
        d = haversine_m(lat, lon, stop["lat"], stop["lon"])
        if d <= radius_m:
            found.append((d, stop))
    found.sort(key=lambda item: item[0])
    found = found[:limit] if limit else found
    return [{"stop": stop, "distance_m": round(d)} for d, stop in found]


def lines_serving(stop_id, network=None):
    network = network or get_network()
    return [line for line in network["lines"].values() if stop_id in line["stops"]]


def line_for_service(service, network=None):
    """Associa un servizio ricevuto (dict) a una linea della rete, se possibile."""
    network = network or get_network()
    if not isinstance(service, dict):
        return None

    line_id = service.get("line_id")
    if line_id in network["lines"]:
        return network["lines"][line_id]

    name = normalize(service.get("name") or "")
    if not name:
        return None

    best = None
    for line in network["lines"].values():
        for alias in line["_alias_norm"]:
            if alias and re.search(rf"\b{re.escape(alias)}\b", name):
                if best is None or len(alias) > best[0]:
                    best = (len(alias), line)
    return best[1] if best else None


def _stop_index(line, stop_ref, network):
    """Indice di una fermata sulla linea, da id o da nome."""
    if stop_ref in line["stops"]:
        return line["stops"].index(stop_ref)
    wanted = normalize_place(stop_ref)
    for i, stop_id in enumerate(line["stops"]):
        if wanted and wanted == normalize_place(network["stops"][stop_id]["name"]):
            return i
    return None


def disruptions_from_services(services, network=None):
    """
    Trasforma i servizi ricevuti in vincoli per il pianificatore.

    - suspended / cancelled → linea esclusa (anche se il dato è vecchio:
      per prudenza non si manda nessuno su una linea segnalata sospesa);
      se il servizio indica "between": [fermata_a, fermata_b] sono escluse
      solo le tratte comprese tra le due fermate;
    - delayed / disrupted → linea mantenuta ma penalizzata.
    """
    network = network or get_network()
    result = {
        "disabled_lines": {},
        "degraded_lines": {},
        "blocked_hops": set(),
        "blocked_segments": [],
        "unmatched_services": [],
    }

    for service in services or []:
        if not isinstance(service, dict):
            continue
        status = service.get("status")
        if status not in {"suspended", "cancelled", "delayed", "disrupted"}:
            continue
        line = line_for_service(service, network)
        if line is None:
            result["unmatched_services"].append(service.get("name", "servizio sconosciuto"))
            continue

        between = service.get("between")
        if status in {"suspended", "cancelled"}:
            if isinstance(between, (list, tuple)) and len(between) == 2:
                a = _stop_index(line, between[0], network)
                b = _stop_index(line, between[1], network)
                if a is not None and b is not None:
                    lo, hi = sorted((a, b))
                    for hop in range(lo, hi):
                        result["blocked_hops"].add((line["id"], hop))
                    result["blocked_segments"].append({
                        "line": line["name"],
                        "from": network["stops"][line["stops"][lo]]["name"],
                        "to": network["stops"][line["stops"][hi]]["name"],
                        "status": status,
                    })
                    continue
            result["disabled_lines"][line["id"]] = status
        else:
            result["degraded_lines"][line["id"]] = status

    return result
