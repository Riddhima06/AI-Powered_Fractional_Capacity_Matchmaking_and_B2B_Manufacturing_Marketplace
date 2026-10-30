# Manufacturing AI – Requirement Understanding + Supplier Matchmaking

> All manufacturers in `data/manufacturers.json` are **fictional demo data**.

## 1. What it does
1. **Understands** a buyer's plain-English requirement and turns it into structured fields.
2. **Matches and ranks** manufacturers with a transparent, explainable score.

No frontend, database, auth or API server – just a Python module that FastAPI can call later.

> The first version uses AI-assisted requirement understanding combined with a deterministic weighted
> matchmaking algorithm. This provides transparent and explainable recommendations while keeping the
> system practical and easy to validate.

No machine-learning model is trained: ranking is plain arithmetic you can verify by hand.

## 2. Architecture
```
text ──► RequirementParser ──► Requirement ──► match_manufacturers() ──► ranked results + explanations
          ├─ RuleBasedParser   (default, local)        │
          └─ LLMParser         (optional)         scoring.py  location.py
```
| File | Role |
|---|---|
| `ai/requirement_parser.py` | `RequirementParser` interface, `RuleBasedParser`, optional `LLMParser` |
| `ai/scoring.py` | Capability / material / capacity / lead-time rules, weights, final score |
| `ai/location.py` | Demo city coordinates, Haversine distance, distance bands |
| `ai/matcher.py` | `match_manufacturers()`, eligibility, explanations, JSON loader |
| `data/manufacturers.json` | 11 fictional manufacturers |

## 3. How requirement extraction works
The text is lower-cased, then: a synonym table maps variants to one standard value
(`aluminum`→`Aluminium`, `CNC machine`→`CNC Machining`, `moulding`→`Injection Molding`);
regexes find the deadline (`within 10 days`, `in 2 weeks`, `10-day`), then the quantity
(`500 pieces`, `quantity 500`, `1,000 parts`, `2k`); city names (and aliases like `Bangalore`) give the location.
The deadline is removed before looking for the quantity so "10 days" is never mistaken for a quantity.
Anything not found is `None`.

`LLMParser(llm_call)` takes **any function `str -> str`** that calls an LLM. If it is missing or fails, the
rule-based parser is used, so **no API key is ever required**.

## 4. How matchmaking works
Every manufacturer gets five 0–100 scores, combined with fixed weights. A field the buyer didn't mention
isn't a constraint (scores 100).

## 5. Scoring formula
```
Final = capability*0.40 + material*0.20 + capacity*0.20 + location*0.10 + lead_time*0.10
```
| Score | Rule |
|---|---|
| Capability / Material | 100 if supported, else 0 |
| Capacity | `ratio = daily_capacity / quantity`: ≥1.5 → 100, ≥1 → 90, else `ratio × 70` |
| Location | Haversine km → 0–25: 100, –50: 90, –100: 75, –200: 50, –500: 30, more: 10 (`DISTANCE_BANDS`, editable) |
| Lead time | ≤80% of deadline → 100, ≤ deadline → 85, late → `60 − %overshoot` (min 0) |

**Eligible** = has the process, has the material, and `daily_capacity × deadline_days ≥ quantity`.
Results list eligible manufacturers first (by score, descending), then ineligible ones marked as alternatives
with `ineligible_reasons`. Use `include_ineligible=False` to drop them.

## 6. Dataset structure
`id, company_name, location, latitude, longitude, capabilities[], materials[], daily_capacity, lead_time_days, demo_data`

## 7–9. Install, demo, tests
```bash
pip install -r requirements.txt     # only pytest is needed
python demo.py                      # 5 built-in test requirements (the last has no eligible match)
python demo.py "Need 800 brass parts using CNC within 12 days near Jaipur"
pytest
```

## 10. Example
```python
from ai import load_manufacturers, match_manufacturers, parse_requirement

req = parse_requirement("Need 500 aluminium parts using CNC machining within 10 days near Delhi.")
# Requirement(product='aluminium parts', process='CNC Machining', material='Aluminium',
#             quantity=500, deadline_days=10, location='Delhi')
top = match_manufacturers(req, load_manufacturers())[0]
# {'manufacturer': 'Alpha Precision Works', 'final_score': 100.0, 'capability_score': 100,
#  'material_score': 100, 'capacity_score': 100, 'location_score': 100, 'lead_time_score': 100,
#  'eligible': True, 'explanation': 'Strong capability and material compatibility. ...', ...}
```

## 11. Connecting to FastAPI later
```python
@app.post("/match")
def match(body: MatchRequest):
    req = parse_requirement(body.text)
    return {"requirement": req.to_dict(), "matches": match_manufacturers(req, manufacturers_from_db)}
```
`match_manufacturers` takes plain dicts, so the JSON loader can be swapped for database rows with the same fields.
