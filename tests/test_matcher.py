import pytest

from ai import Requirement, haversine_km, load_manufacturers, match_manufacturers, parse_requirement
from ai.location import DISTANCE_BANDS, location_score
from ai.matcher import score_manufacturer
from ai.scoring import (WEIGHTS, capability_score, capacity_score, final_score, lead_time_score,
                        material_score)

MANUFACTURERS = load_manufacturers()


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_dataset_is_marked_fictional():
    assert len(MANUFACTURERS) >= 10
    assert all(m["demo_data"] for m in MANUFACTURERS)


def test_capability_scoring():
    assert capability_score("CNC Machining", ["CNC Machining", "Laser Cutting"]) == 100
    assert capability_score("cnc machining", ["CNC Machining"]) == 100
    assert capability_score("Welding", ["CNC Machining"]) == 0


def test_material_scoring():
    assert material_score("Aluminium", ["Aluminium"]) == 100
    assert material_score("Titanium", ["Aluminium"]) == 0


def test_capacity_scoring():
    assert capacity_score(500, 1000) == 100   # comfortable
    assert capacity_score(500, 500) == 90     # just enough
    assert capacity_score(500, 250) == 35     # insufficient
    assert capacity_score(500, 50) < capacity_score(500, 250)


def test_haversine_known_distance():
    # Delhi -> Mumbai is roughly 1150 km in a straight line
    assert haversine_km(28.6139, 77.2090, 19.0760, 72.8777) == pytest.approx(1150, abs=30)
    assert haversine_km(28.6, 77.2, 28.6, 77.2) == 0


@pytest.mark.parametrize("km,score", [(0, 100), (25, 100), (40, 90), (75, 75), (150, 50), (300, 30), (1500, 10)])
def test_location_scoring_bands(km, score):
    assert location_score(km) == score


def test_location_bands_are_configurable():
    assert location_score(10, [(5, 100), (float("inf"), 20)]) == 20
    assert DISTANCE_BANDS[0] == (25, 100)  # default untouched


def test_lead_time_scoring():
    assert lead_time_score(10, 7) == 100
    assert lead_time_score(10, 10) == 85
    assert lead_time_score(10, 12) == 40
    assert lead_time_score(10, 30) == 0
    assert lead_time_score(None, 30) == 100


def test_final_weighted_score():
    s = {"capability": 100, "material": 100, "capacity": 90, "location": 80, "lead_time": 90}
    assert final_score(s) == 40 + 20 + 18 + 8 + 9


def test_ranking_cnc_aluminium_delhi():
    req = parse_requirement("Need 500 aluminium parts using CNC machining within 10 days near Delhi.")
    res = match_manufacturers(req, MANUFACTURERS)
    assert res[0]["manufacturer"] == "Alpha Precision Works"
    assert res[0]["final_score"] == 100
    scores = [r["final_score"] for r in res if r["eligible"]]
    assert scores == sorted(scores, reverse=True)
    assert set(res[0]) >= {"final_score", "capability_score", "material_score", "capacity_score",
                           "location_score", "lead_time_score", "eligible", "explanation"}


def test_eligibility_flags():
    req = Requirement(process="CNC Machining", material="Aluminium", quantity=500, deadline_days=10, location="Delhi")
    by_name = {r["manufacturer"]: r for r in match_manufacturers(req, MANUFACTURERS)}
    assert by_name["Alpha Precision Works"]["eligible"]
    assert not by_name["Deccan Polymers"]["eligible"]
    assert "missing capability: CNC Machining" in by_name["Deccan Polymers"]["ineligible_reasons"]
    # eligible results are listed before ineligible ones
    flags = [r["eligible"] for r in match_manufacturers(req, MANUFACTURERS)]
    assert flags == sorted(flags, reverse=True)


def test_exclude_ineligible():
    req = parse_requirement("Need 500 aluminium parts using CNC machining within 10 days near Delhi.")
    assert all(r["eligible"] for r in match_manufacturers(req, MANUFACTURERS, include_ineligible=False))


@pytest.mark.parametrize("text,expected_top", [
    ("I need 200 ABS plastic components manufactured by injection molding in 15 days.", {"Deccan Polymers", "Mumbai Moulding Co"}),
    ("Need 1000 stainless steel components using laser cutting within 7 days.", {"Laser Craft Industries", "Jaipur Metal Works", "Alpha Precision Works"}),
    ("Need 300 nylon parts using 3D printing within 20 days.", {"Chennai Additive Labs", "Rapid Proto Bengaluru", "Mumbai Moulding Co"}),
])
def test_demo_requirements_have_sensible_top_match(text, expected_top):
    res = match_manufacturers(parse_requirement(text), MANUFACTURERS)
    assert res[0]["eligible"] and res[0]["manufacturer"] in expected_top


def test_no_perfect_match_is_handled_gracefully():
    req = parse_requirement("Need 5000 titanium parts using CNC machining within 3 days near Chennai.")
    res = match_manufacturers(req, MANUFACTURERS)
    assert len(res) == len(MANUFACTURERS)
    assert not any(r["eligible"] for r in res)
    assert all(r["final_score"] < 100 and r["explanation"] for r in res)


def test_missing_fields_do_not_crash():
    res = match_manufacturers({}, MANUFACTURERS)
    assert all(r["final_score"] == 100 for r in res)


def test_accepts_dict_requirement():
    res = match_manufacturers({"process": "Welding", "material": "Brass", "quantity": 10}, MANUFACTURERS)
    assert res[0]["eligible"]


def test_unknown_city_gets_neutral_location_score():
    m = MANUFACTURERS[0]
    assert score_manufacturer(Requirement(location="Atlantis"), m)["location_score"] == 50
