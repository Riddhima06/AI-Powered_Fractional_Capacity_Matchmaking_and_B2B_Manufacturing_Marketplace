"""Match a structured requirement against manufacturers and rank them."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from . import scoring
from .location import city_coordinates, haversine_km, location_score
from .requirement_parser import Requirement

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "manufacturers.json"


def load_manufacturers(path: Union[str, Path] = DEFAULT_DATA) -> List[Dict]:
    """Load the (fictional demo) manufacturers from JSON."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)["manufacturers"]


def _distance_km(req: Requirement, m: Dict) -> Optional[float]:
    coords = city_coordinates(req.location)
    if coords is None:
        return None
    return haversine_km(coords[0], coords[1], m["latitude"], m["longitude"])


def explain(req: Requirement, m: Dict, r: Dict) -> str:
    """Build a short human-readable explanation from the score breakdown."""
    s = []
    cap, mat = r["capability_score"] == 100, r["material_score"] == 100
    if cap and mat:
        s.append("Strong capability and material compatibility.")
    elif cap:
        s.append(f"Offers {req.process} but does not work with {req.material}.")
    elif mat:
        s.append(f"Works with {req.material} but does not offer {req.process}.")
    else:
        s.append(f"Offers neither {req.process} nor {req.material}.")

    if req.quantity:
        if r["capacity_score"] >= 90:
            s.append("Has sufficient capacity for the order.")
        elif r["_capacity_ok"]:
            s.append(f"Capacity ({m['daily_capacity']}/day) is tight but workable within the deadline.")
        else:
            s.append(f"Capacity ({m['daily_capacity']}/day) is insufficient for {req.quantity} units.")

    if req.deadline_days:
        lt = m["lead_time_days"]
        if lt <= req.deadline_days:
            s.append(f"Can meet the requested deadline (lead time {lt} days vs {req.deadline_days}).")
        else:
            s.append(f"Lead time of {lt} days exceeds the {req.deadline_days}-day deadline.")

    d = r["distance_km"]
    if d is not None:
        if d <= 25:
            s.append("Located very close to the buyer.")
        elif d <= 100:
            s.append(f"Location is close (~{d:.0f} km).")
        elif d <= 200:
            s.append(f"Location is moderately close (~{d:.0f} km).")
        else:
            s.append(f"Location is far (~{d:.0f} km).")
    return " ".join(s)


def score_manufacturer(req: Requirement, m: Dict) -> Dict:
    """Score a single manufacturer and return the full breakdown."""
    dist = _distance_km(req, m)
    if req.location is None:
        loc = 100  # no location preference
    elif dist is None:
        loc = 50  # buyer city unknown to the demo -> neutral
    else:
        loc = location_score(dist)

    parts = {
        "capability": scoring.capability_score(req.process, m["capabilities"]),
        "material": scoring.material_score(req.material, m["materials"]),
        "capacity": scoring.capacity_score(req.quantity, m["daily_capacity"]),
        "location": loc,
        "lead_time": scoring.lead_time_score(req.deadline_days, m["lead_time_days"]),
    }
    cap_ok = scoring.capacity_is_sufficient(req.quantity, m["daily_capacity"], req.deadline_days)

    reasons = []
    if parts["capability"] == 0:
        reasons.append(f"missing capability: {req.process}")
    if parts["material"] == 0:
        reasons.append(f"missing material: {req.material}")
    if not cap_ok:
        reasons.append("insufficient capacity")

    result = {
        "manufacturer": m["company_name"],
        "manufacturer_id": m["id"],
        "location": m["location"],
        "distance_km": None if dist is None else round(dist, 1),
        "final_score": scoring.final_score(
            {k: v for k, v in parts.items()}
        ),
        "capability_score": parts["capability"],
        "material_score": parts["material"],
        "capacity_score": parts["capacity"],
        "location_score": parts["location"],
        "lead_time_score": parts["lead_time"],
        "eligible": not reasons,
        "ineligible_reasons": reasons,
        "_capacity_ok": cap_ok,
    }
    result["explanation"] = explain(req, m, result)
    del result["_capacity_ok"]
    return result


def match_manufacturers(
    requirement: Union[Requirement, Dict],
    manufacturers: Sequence[Dict],
    include_ineligible: bool = True,
) -> List[Dict]:
    """Score and rank manufacturers.

    Eligible manufacturers (right process + material + enough capacity) come first, each group sorted
    by final_score DESC. Ineligible ones are kept as clearly-marked alternatives unless
    include_ineligible=False.
    """
    req = requirement if isinstance(requirement, Requirement) else Requirement.from_dict(requirement)
    results = [score_manufacturer(req, m) for m in manufacturers]
    if not include_ineligible:
        results = [r for r in results if r["eligible"]]
    results.sort(key=lambda r: (not r["eligible"], -r["final_score"], r["manufacturer"]))
    return results
