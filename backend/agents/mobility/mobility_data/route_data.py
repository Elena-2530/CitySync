"""
Pianificatore di percorsi del Mobility Agent.

Calcola itinerari sulla rete di trasporto pubblico (vedi transport_data.py)
combinando tratti a piedi, corse sulle linee e cambi.

Regole di onestà:
  - i tempi sono STIME sulla rete programmata (la frequenza reale non è nota:
    per ogni salita si somma un'attesa stimata, BOARD_WAIT_MIN);
  - la rete non contiene informazioni in tempo reale: ogni percorso riporta
    realtime_verified = False;
  - le linee segnalate come sospese vengono escluse, quelle in ritardo o con
    criticità vengono penalizzate e il percorso che le usa è marcato "disrupted".

I percorsi prodotti hanno lo stesso formato che route_planning_agent si
aspetta in context["route_options"] (source, updated_at, status, ...).
"""

import heapq
import itertools
from datetime import datetime, timezone

from agents.mobility.mobility_data import transport_data as td

BOARD_WAIT_MIN = 5                 # attesa stimata a ogni salita (frequenza ignota)
DEGRADED_PENALTY_WEIGHT = 15       # peso aggiuntivo per salire su una linea con criticità
WALK_BETWEEN_STOPS_M = 400         # distanza massima per un cambio a piedi tra fermate
MAX_WALK_TO_STOP_M = 1500          # distanza massima da/per una fermata
MAX_STOPS_NEAR = 4                 # fermate considerate vicino a partenza e arrivo
WALK_ONLY_MAX_M = 1500             # entro questa distanza è proposto anche il percorso a piedi

TRANSFER_PENALTY = {               # peso (non tempo) per ogni cambio
    "fastest": 0,
    "fewest_transfers": 15,
    "accessible": 8,
}

VALID_PROFILES = set(TRANSFER_PENALTY)


def _empty_disruptions():
    return {
        "disabled_lines": {},
        "degraded_lines": {},
        "blocked_hops": set(),
        "blocked_segments": [],
        "unmatched_services": [],
    }


def _search(origin, destination, network, banned_lines, disruptions, profile):
    """Dijkstra su stati (fermata, linea o None, ha già viaggiato)."""
    stops = network["stops"]
    lines = {lid: l for lid, l in network["lines"].items() if lid not in banned_lines}
    index = {lid: {sid: i for i, sid in enumerate(l["stops"])} for lid, l in lines.items()}
    serving = {}
    for lid, l in lines.items():
        for sid in l["stops"]:
            serving.setdefault(sid, []).append(lid)

    blocked = disruptions["blocked_hops"]
    degraded = disruptions["degraded_lines"]
    transfer_weight = TRANSFER_PENALTY.get(profile, 0)

    def walk_to_dest(stop):
        d = td.haversine_m(stop["lat"], stop["lon"], destination["lat"], destination["lon"])
        return d if d <= MAX_WALK_TO_STOP_M else None

    counter = itertools.count()
    heap = []
    best_weight = {}
    best_minutes = {}
    prev = {}

    def push(state, weight, minutes, before, edge):
        if state in best_weight and best_weight[state] <= weight:
            return
        best_weight[state] = weight
        best_minutes[state] = minutes
        prev[state] = (before, edge)
        heapq.heappush(heap, (weight, next(counter), state))

    start = ("O",)
    best_weight[start] = 0
    best_minutes[start] = 0
    prev[start] = None

    direct = td.haversine_m(origin["lat"], origin["lon"], destination["lat"], destination["lon"])
    if direct <= WALK_ONLY_MAX_M:
        m = td.walking_minutes(direct)
        push(("D",), m, m, start, ("walk_direct", round(direct), m))

    for near in td.stops_near(origin["lat"], origin["lon"], MAX_WALK_TO_STOP_M, network, MAX_STOPS_NEAR):
        m = td.walking_minutes(near["distance_m"])
        push((near["stop"]["id"], None, False), m, m, start,
             ("walk_origin", near["stop"]["id"], near["distance_m"], m))

    while heap:
        weight, _, state = heapq.heappop(heap)
        if weight > best_weight.get(state, float("inf")):
            continue
        if state == ("D",):
            break
        if state == start:
            continue

        stop_id, line_id, rode = state
        minutes = best_minutes[state]

        if line_id is not None:
            i = index[line_id][stop_id]
            line = lines[line_id]
            for j in (i - 1, i + 1):
                if 0 <= j < len(line["stops"]) and (line_id, min(i, j)) not in blocked:
                    hop = line["hop_minutes"][min(i, j)]
                    push((line["stops"][j], line_id, True), weight + hop, minutes + hop,
                         state, ("ride", line_id, stop_id, line["stops"][j], hop))
            push((stop_id, None, True), weight, minutes, state, ("alight", line_id, stop_id))
        else:
            for lid in serving.get(stop_id, []):
                extra = DEGRADED_PENALTY_WEIGHT if lid in degraded else 0
                extra += transfer_weight if rode else 0
                push((stop_id, lid, True), weight + BOARD_WAIT_MIN + extra,
                     minutes + BOARD_WAIT_MIN, state, ("board", lid, stop_id, BOARD_WAIT_MIN))

            here = stops[stop_id]
            for near in td.stops_near(here["lat"], here["lon"], WALK_BETWEEN_STOPS_M, network):
                other = near["stop"]["id"]
                if other == stop_id or other not in serving:
                    continue
                m = td.walking_minutes(near["distance_m"])
                push((other, None, rode), weight + m, minutes + m, state,
                     ("walk", stop_id, other, near["distance_m"], m))

            d = walk_to_dest(here)
            if d is not None and rode:
                m = td.walking_minutes(d)
                push(("D",), weight + m, minutes + m, state, ("walk_dest", stop_id, round(d), m))

    goal = ("D",)
    if goal not in best_weight:
        return None

    edges = []
    state = goal
    while prev[state] is not None:
        before, edge = prev[state]
        edges.append(edge)
        state = before
    edges.reverse()
    return _edges_to_option(edges, origin, destination, network, disruptions)


def _edges_to_option(edges, origin, destination, network, disruptions):
    stops = network["stops"]
    lines = network["lines"]
    steps = []
    ride = None

    def finish():
        nonlocal ride
        if ride is not None:
            steps.append(ride)
            ride = None

    for edge in edges:
        kind = edge[0]
        if kind in {"walk_origin", "walk", "walk_dest"} and edge[-1] == 0:
            continue  # già sul posto: nessun passo a piedi da mostrare
        if kind == "walk_direct":
            _, dist, m = edge
            steps.append({"type": "walk", "from": origin["name"], "to": destination["name"],
                          "distance_m": dist, "minutes": m})
        elif kind == "walk_origin":
            _, sid, dist, m = edge
            steps.append({"type": "walk", "from": origin["name"], "to": stops[sid]["name"],
                          "distance_m": dist, "minutes": m})
        elif kind == "walk":
            _, a, b, dist, m = edge
            finish()
            steps.append({"type": "walk", "from": stops[a]["name"], "to": stops[b]["name"],
                          "distance_m": dist, "minutes": m})
        elif kind == "walk_dest":
            _, sid, dist, m = edge
            finish()
            steps.append({"type": "walk", "from": stops[sid]["name"], "to": destination["name"],
                          "distance_m": dist, "minutes": m})
        elif kind == "board":
            _, lid, sid, wait = edge
            finish()
            line = lines[lid]
            ride = {"type": "ride", "line_id": lid, "line": line["name"],
                    "operator": line.get("operator", ""), "mode": line.get("mode", ""),
                    "from": stops[sid]["name"], "to": stops[sid]["name"],
                    "stops_count": 0, "minutes": 0, "wait_estimate_min": wait}
        elif kind == "ride":
            _, lid, a, b, hop = edge
            ride["to"] = stops[b]["name"]
            ride["stops_count"] += 1
            ride["minutes"] += hop
        elif kind == "alight":
            finish()
    finish()

    rides = [s for s in steps if s["type"] == "ride"]
    total = sum(s["minutes"] for s in steps) + sum(s.get("wait_estimate_min", 0) for s in rides)
    walk_total = sum(s["minutes"] for s in steps if s["type"] == "walk")
    degraded = disruptions["degraded_lines"]
    degraded_used = [r["line"] for r in rides if r["line_id"] in degraded]

    warnings = [
        "Tempi stimati sulla rete programmata: nessun dato in tempo reale su "
        "frequenze, ritardi o soppressioni."
    ]
    for name in degraded_used:
        warnings.append(f"La linea {name} risulta in ritardo o con criticità.")

    return {
        "steps": steps,
        "lines": [r["line"] for r in rides],
        "line_ids": [r["line_id"] for r in rides],
        "transfers": max(0, len(rides) - 1),
        "total_minutes_estimate": int(total),
        "walking_minutes": int(walk_total),
        "status": "disrupted" if degraded_used else "available",
        "realtime_verified": False,
        "data_basis": network["meta"].get("data_type", "static"),
        "warnings": warnings,
    }


def _signature(option):
    return tuple(
        (s["type"], s.get("line_id", ""), s["from"], s["to"]) for s in option["steps"]
    )


def _main_line(option):
    rides = [s for s in option["steps"] if s["type"] == "ride"]
    if not rides:
        return None
    return max(rides, key=lambda s: s["minutes"])["line_id"]


def plan_routes(origin, destination, network=None, disruptions=None,
                profile="fastest", max_options=3, now=None):
    """
    Pianifica da `origin` a `destination` (testo o dict con name/lat/lon).

    Restituisce un dizionario con le opzioni ordinate (la prima è quella che
    meglio risponde al profilo richiesto), i luoghi non riconosciuti, le linee
    escluse e le note da riportare all'utente.
    """
    network = network or td.get_network()
    disruptions = disruptions or _empty_disruptions()
    profile = profile if profile in VALID_PROFILES else "fastest"
    now = now or datetime.now(timezone.utc)

    def resolve(value):
        if isinstance(value, dict) and "lat" in value and "lon" in value:
            return value
        return td.resolve_place(value, network)

    o, d = resolve(origin), resolve(destination)
    unresolved = []
    if o is None:
        unresolved.append(str(origin))
    if d is None:
        unresolved.append(str(destination))

    excluded = [
        {"line": network["lines"][lid]["name"], "status": status}
        for lid, status in disruptions["disabled_lines"].items()
        if lid in network["lines"]
    ] + [
        {"line": seg["line"], "status": seg["status"],
         "between": [seg["from"], seg["to"]]}
        for seg in disruptions["blocked_segments"]
    ]

    result = {
        "origin": o, "destination": d, "profile": profile,
        "unresolved": unresolved, "options": [],
        "excluded_lines": excluded,
        "unmatched_services": disruptions["unmatched_services"],
        "network": network["meta"], "notes": [],
    }
    if unresolved:
        return result

    if td.haversine_m(o["lat"], o["lon"], d["lat"], d["lon"]) < 150:
        result["notes"].append("Partenza e destinazione coincidono o sono molto vicine.")

    banned = set(disruptions["disabled_lines"])
    candidates = []

    def add(option, tag):
        if option is None:
            return
        sig = _signature(option)
        if all(_signature(c) != sig for c, _ in candidates):
            candidates.append((option, tag))

    order = [profile] + [p for p in ("fastest", "fewest_transfers") if p != profile]
    for prof in order:
        add(_search(o, d, network, banned, disruptions, prof), prof)

    if candidates:
        main = _main_line(candidates[0][0])
        if main:
            add(_search(o, d, network, banned | {main}, disruptions, profile), "alternative")

    # le opzioni restano nell'ordine di scoperta: la prima segue il profilo richiesto
    options = []
    for number, (option, tag) in enumerate(candidates[:max_options], start=1):
        option = dict(option)
        option.update({
            "id": f"R{number}",
            "profile": tag,
            "source": network["meta"].get("source", "network"),
            "updated_at": now.isoformat(),
            "from": o["name"],
            "to": d["name"],
        })
        if profile == "accessible":
            option["warnings"] = option["warnings"] + [
                "Accessibilità di stazioni e mezzi non verificata: controllare presso l'operatore."
            ]
        options.append(option)

    result["options"] = options
    if not options:
        result["notes"].append(
            "Nessun percorso trovato con la rete e le linee attualmente disponibili."
        )
    return result
