"""Individual scoring rules and the weighted final score. All scores are 0-100."""
from __future__ import annotations

from typing import Dict, Optional

WEIGHTS: Dict[str, float] = {
    "capability": 0.40,
    "material": 0.20,
    "capacity": 0.20,
    "location": 0.10,
    "lead_time": 0.10,
}

# A field the buyer did not mention is not a constraint, so it scores full marks.


def _norm(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def capability_score(required_process: Optional[str], capabilities) -> int:
    if not required_process:
        return 100
    return 100 if _norm(required_process) in {_norm(c) for c in capabilities} else 0


def material_score(required_material: Optional[str], materials) -> int:
    if not required_material:
        return 100
    return 100 if _norm(required_material) in {_norm(m) for m in materials} else 0


def capacity_score(quantity: Optional[int], daily_capacity: int) -> int:
    """Compare required quantity with daily capacity.

    ratio = daily_capacity / quantity
      ratio >= 1.5 -> 100 (comfortable)
      ratio >= 1.0 -> 90  (sufficient)
      ratio <  1.0 -> ratio * 70 (e.g. half the needed quantity per day -> 35)
    """
    if not quantity:
        return 100
    ratio = daily_capacity / quantity
    if ratio >= 1.5:
        return 100
    if ratio >= 1.0:
        return 90
    return round(ratio * 70)


def capacity_is_sufficient(quantity: Optional[int], daily_capacity: int, deadline_days: Optional[int]) -> bool:
    """Can the factory physically make `quantity` units within the deadline?
    Without a deadline we require that one day's output covers the order."""
    if not quantity:
        return True
    days = deadline_days if deadline_days else 1
    return daily_capacity * days >= quantity


def lead_time_score(deadline_days: Optional[int], lead_time_days: int) -> int:
    """Lead time within 80% of the deadline -> 100; within the deadline -> 85;
    late: 60 minus 1 point per 1% overshoot (30% late -> 30, 60%+ late -> 0)."""
    if not deadline_days:
        return 100
    if lead_time_days <= 0.8 * deadline_days:
        return 100
    if lead_time_days <= deadline_days:
        return 85
    overshoot = (lead_time_days - deadline_days) / deadline_days
    return max(0, round(60 - overshoot * 100))


def final_score(scores: Dict[str, float], weights: Optional[Dict[str, float]] = None) -> float:
    """Weighted sum of the five component scores (keys as in WEIGHTS)."""
    w = weights or WEIGHTS
    return round(sum(scores[k] * w[k] for k in w), 1)
