"""Turn a buyer's natural-language requirement into structured data.

    RequirementParser (abstract interface)
    |-- RuleBasedParser   local regex/keyword parser (default, no API key needed)
    `-- LLMParser         optional; wraps any function that calls an LLM, falls back to rules
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .location import CITY_ALIASES, resolve_city

# --------------------------------------------------------------------------- vocabulary
PROCESS_SYNONYMS: Dict[str, List[str]] = {
    "CNC Machining": ["cnc", "cnc machining", "cnc machine", "cnc machined", "cnc milling",
                      "cnc turning", "machining", "machined"],
    "Injection Molding": ["injection molding", "injection moulding", "injection mold",
                          "injection mould", "plastic injection"],
    "Laser Cutting": ["laser cutting", "laser cut", "laser cutter"],
    "3D Printing": ["3d printing", "3d print", "3d printed", "additive manufacturing", "fdm", "sla", "sls"],
    "Sheet Metal Fabrication": ["sheet metal", "sheet metal fabrication", "sheet metal bending"],
    "Welding": ["welding", "welded", "weld"],
    "Die Casting": ["die casting", "die cast"],
}

MATERIAL_SYNONYMS: Dict[str, List[str]] = {
    "Aluminium": ["aluminium", "aluminum", "al6061", "al 6061"],
    "Stainless Steel": ["stainless steel", "stainless", "ss304", "ss316", "ss 304", "ss 316"],
    "Mild Steel": ["mild steel", "carbon steel", "steel"],
    "Brass": ["brass"],
    "Copper": ["copper"],
    "Titanium": ["titanium"],
    "ABS Plastic": ["abs plastic", "abs"],
    "Nylon": ["nylon", "polyamide"],
    "Polycarbonate": ["polycarbonate"],
    "Polypropylene": ["polypropylene"],
}

UNIT_WORDS = ["pieces", "piece", "pcs", "pc", "units", "unit", "items", "nos"]
PRODUCT_NOUNS = ["parts", "components", "brackets", "housings", "gears", "shafts", "enclosures",
                 "panels", "plates", "sheets", "prototypes", "fittings", "covers"]


def _phrase_regex(phrase: str) -> "re.Pattern[str]":
    words = [re.escape(w) for w in phrase.split()]
    return re.compile(r"(?<![a-z0-9])" + r"[\s-]+".join(words) + r"(?![a-z0-9])")


def _compile(table: Dict[str, List[str]]) -> List[Tuple["re.Pattern[str]", str]]:
    pairs = [(syn, canon) for canon, syns in table.items() for syn in syns]
    pairs.sort(key=lambda p: len(p[0]), reverse=True)  # longest phrase wins ("stainless steel" > "steel")
    return [(_phrase_regex(syn), canon) for syn, canon in pairs]


_PROCESS_RE = _compile(PROCESS_SYNONYMS)
_MATERIAL_RE = _compile(MATERIAL_SYNONYMS)
_CITY_TABLE: Dict[str, List[str]] = {}
for _alias, _city in CITY_ALIASES.items():
    _CITY_TABLE.setdefault(_city, []).append(_alias)
_CITY_RE = _compile(_CITY_TABLE)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _find(text: str, compiled) -> Optional[str]:
    for rx, canon in compiled:
        if rx.search(text):
            return canon
    return None


def normalize_process(value: Optional[str]) -> Optional[str]:
    return _find(_clean(value), _PROCESS_RE) if value else None


def normalize_material(value: Optional[str]) -> Optional[str]:
    return _find(_clean(value), _MATERIAL_RE) if value else None


# --------------------------------------------------------------------------- data class
FIELDS = ["product", "process", "material", "quantity", "deadline_days", "location"]


@dataclass
class Requirement:
    product: Optional[str] = None
    process: Optional[str] = None
    material: Optional[str] = None
    quantity: Optional[int] = None
    deadline_days: Optional[int] = None
    location: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "Requirement":
        return cls(**{k: data.get(k) for k in FIELDS})

    def missing_fields(self) -> List[str]:
        return [f for f in FIELDS if getattr(self, f) is None]


# --------------------------------------------------------------------------- parsers
class RequirementParser(ABC):
    @abstractmethod
    def parse(self, text: str) -> Requirement:
        """Convert free text into a Requirement."""


_NUM = r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)(?:\s?(k))?(?=\s|$|pcs\b|pc\b)"
_DEADLINE_RE = re.compile(r"(?<![\w.])(\d+)\s*-?\s*(day|week)s?\b")
_A_WEEK_RE = re.compile(r"\b(?:a|one)\s+week\b")
_QTY_KEYWORD_RE = re.compile(r"\b(?:quantity|qty)\s*(?:of\s*)?[:=]?\s*(?:of\s+)?" + _NUM)
_QTY_NOUN_RE = re.compile(
    _NUM + r"\s*((?:[a-z][a-z0-9-]*\s+){0,3}?(?:" + "|".join(PRODUCT_NOUNS + UNIT_WORDS) + r"))\b"
)
_ANY_NUM_RE = re.compile(_NUM)


def _to_int(num: str, k: Optional[str]) -> int:
    value = int(num.replace(",", ""))
    return value * 1000 if k else value


class RuleBasedParser(RequirementParser):
    """Keyword matching + regular expressions. Fully local, no API key."""

    def parse(self, text: str) -> Requirement:
        t = _clean(text or "")
        process = _find(t, _PROCESS_RE)
        material = _find(t, _MATERIAL_RE)
        location = _find(t, _CITY_RE)

        deadline, t_no_deadline = self._deadline(t)
        quantity, product = self._quantity_and_product(t_no_deadline, material)
        return Requirement(product, process, material, quantity, deadline, location)

    @staticmethod
    def _deadline(t: str) -> Tuple[Optional[int], str]:
        m = _DEADLINE_RE.search(t)
        if m:
            days = int(m.group(1)) * (7 if m.group(2) == "week" else 1)
            return days, t[: m.start()] + " " + t[m.end():]
        m = _A_WEEK_RE.search(t)
        if m:
            return 7, t[: m.start()] + " " + t[m.end():]
        return None, t

    @staticmethod
    def _quantity_and_product(t: str, material: Optional[str]) -> Tuple[Optional[int], Optional[str]]:
        quantity, product = None, None
        m_noun = _QTY_NOUN_RE.search(t)
        if m_noun:
            words = m_noun.group(3).strip()
            if words.split()[-1] in PRODUCT_NOUNS:
                product = words
        m = _QTY_KEYWORD_RE.search(t)
        if m:
            quantity = _to_int(m.group(1), m.group(2))
        elif m_noun:
            quantity = _to_int(m_noun.group(1), m_noun.group(2))
        else:
            m = _ANY_NUM_RE.search(t)
            if m:
                quantity = _to_int(m.group(1), m.group(2))
        if product:  # normalise spelling inside the product text (aluminum -> aluminium)
            for rx, canon in _MATERIAL_RE:  # only the longest matching synonym is replaced
                if rx.search(product):
                    product = rx.sub(canon.lower(), product)
                    break
        elif material:
            product = f"{material.lower()} parts"
        return quantity, product


LLM_PROMPT = (
    "Extract a manufacturing requirement from the text below. Reply with JSON only, using keys "
    "product, process, material, quantity (int), deadline_days (int), location (city). "
    "Use null for anything not stated.\n\nText: {text}"
)


class LLMParser(RequirementParser):
    """Optional LLM-backed parser.

    `llm_call` is any function `str -> str` that sends the prompt to an LLM and returns its text.
    Keeping it as a plain callable means no vendor SDK is required. If no callable is given, or the
    call/JSON parsing fails, we silently fall back to the rule-based parser. Fields the LLM left
    empty are filled in by the rule-based parser.
    """

    def __init__(self, llm_call: Optional[Callable[[str], str]] = None,
                 fallback: Optional[RequirementParser] = None):
        self.llm_call = llm_call
        self.fallback = fallback or RuleBasedParser()

    def parse(self, text: str) -> Requirement:
        baseline = self.fallback.parse(text)
        if self.llm_call is None:
            return baseline
        try:
            raw = self.llm_call(LLM_PROMPT.format(text=text))
            data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
            llm = Requirement(
                product=(data.get("product") or None),
                process=normalize_process(data.get("process")),
                material=normalize_material(data.get("material")),
                quantity=int(data["quantity"]) if data.get("quantity") else None,
                deadline_days=int(data["deadline_days"]) if data.get("deadline_days") else None,
                location=resolve_city(data.get("location")),
            )
        except Exception:
            return baseline
        merged = {f: getattr(llm, f) if getattr(llm, f) is not None else getattr(baseline, f) for f in FIELDS}
        return Requirement(**merged)


def parse_requirement(text: str, parser: Optional[RequirementParser] = None) -> Requirement:
    """Convenience wrapper: uses the rule-based parser unless another parser is supplied."""
    return (parser or RuleBasedParser()).parse(text)
