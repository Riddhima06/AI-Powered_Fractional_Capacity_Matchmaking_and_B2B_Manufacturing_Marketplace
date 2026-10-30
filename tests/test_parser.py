import json

import pytest

from ai import LLMParser, RuleBasedParser, parse_requirement

p = RuleBasedParser()


def test_spec_example_full_extraction():
    r = p.parse("I need 500 aluminium parts manufactured using CNC machining within 10 days near Delhi.")
    assert r.to_dict() == {"product": "aluminium parts", "process": "CNC Machining", "material": "Aluminium",
                           "quantity": 500, "deadline_days": 10, "location": "Delhi"}


@pytest.mark.parametrize("text,qty", [
    ("500 pieces of aluminium", 500), ("500 units CNC", 500), ("quantity 500 aluminium", 500),
    ("qty: 250 nylon", 250), ("need 1,000 steel parts", 1000), ("need 2k brass parts", 2000),
    ("order of 300 parts in 20 days", 300),
])
def test_quantity_extraction(text, qty):
    assert p.parse(text).quantity == qty


@pytest.mark.parametrize("text,material", [
    ("aluminium parts", "Aluminium"), ("aluminum parts", "Aluminium"),
    ("stainless steel sheets", "Stainless Steel"), ("SS304 brackets", "Stainless Steel"),
    ("mild steel gears", "Mild Steel"), ("ABS plastic cases", "ABS Plastic"), ("nylon gears", "Nylon"),
])
def test_material_extraction_and_normalization(text, material):
    assert p.parse(text).material == material


@pytest.mark.parametrize("text,process", [
    ("use CNC", "CNC Machining"), ("CNC machine work", "CNC Machining"), ("CNC machining", "CNC Machining"),
    ("injection moulding", "Injection Molding"), ("injection molding", "Injection Molding"),
    ("laser cutting", "Laser Cutting"), ("3D printing", "3D Printing"),
    ("additive manufacturing", "3D Printing"),
])
def test_process_extraction_and_normalization(text, process):
    assert p.parse(text).process == process


@pytest.mark.parametrize("text,days", [
    ("within 10 days", 10), ("in 10 days", 10), ("delivery in 10 days", 10),
    ("in 2 weeks", 14), ("within a week", 7), ("a 5-day turnaround", 5),
])
def test_deadline_extraction(text, days):
    assert p.parse("Need 100 parts " + text).deadline_days == days


def test_deadline_number_is_not_mistaken_for_quantity():
    r = p.parse("Need parts delivered within 10 days, quantity 500")
    assert (r.quantity, r.deadline_days) == (500, 10)


@pytest.mark.parametrize("text,city", [
    ("near Delhi", "Delhi"), ("around new delhi", "Delhi"), ("in Bangalore", "Bengaluru"),
    ("close to Mumbai", "Mumbai"),
])
def test_location_extraction(text, city):
    assert p.parse("Need 100 parts " + text).location == city


def test_missing_fields_are_none():
    r = p.parse("I need some parts made")
    assert r.quantity is None and r.process is None and r.deadline_days is None
    assert "process" in r.missing_fields()


def test_empty_text():
    assert parse_requirement("").quantity is None


def test_llm_parser_works_without_llm():
    r = LLMParser().parse("Need 500 aluminium parts using CNC within 10 days near Delhi")
    assert r.process == "CNC Machining" and r.quantity == 500


def test_llm_parser_uses_llm_and_normalizes():
    fake = lambda prompt: json.dumps({"product": "brackets", "process": "cnc machine", "material": "aluminum",
                                      "quantity": 42, "deadline_days": None, "location": "new delhi"})
    r = LLMParser(fake).parse("Need 99 parts in 5 days")
    assert (r.process, r.material, r.quantity, r.location) == ("CNC Machining", "Aluminium", 42, "Delhi")
    assert r.deadline_days == 5  # filled in by the rule-based fallback


def test_llm_parser_falls_back_on_error():
    def boom(prompt):
        raise RuntimeError("no network")
    assert LLMParser(boom).parse("Need 500 nylon parts").quantity == 500


@pytest.mark.parametrize("text,product", [
    ("200 ABS plastic components", "abs plastic components"),
    ("1000 stainless steel components", "stainless steel components"),
    ("300 aluminum parts", "aluminium parts"),
    ("100 pieces of nylon", "nylon parts"),
])
def test_product_extraction(text, product):
    assert p.parse(text).product == product
