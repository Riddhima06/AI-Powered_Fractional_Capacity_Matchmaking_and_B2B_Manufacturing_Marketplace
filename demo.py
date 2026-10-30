"""Run the full pipeline:  python demo.py   or   python demo.py "your own requirement text" """
import sys

from ai import load_manufacturers, match_manufacturers, parse_requirement

TEST_REQUIREMENTS = [
    "Need 500 aluminium parts using CNC machining within 10 days near Delhi.",
    "I need 200 ABS plastic components manufactured by injection molding in 15 days.",
    "Need 1000 stainless steel components using laser cutting within 7 days.",
    "Need 300 nylon parts using 3D printing within 20 days.",
    "Need 5000 titanium parts using CNC machining within 3 days near Chennai.",  # no eligible match
]


def show(text, manufacturers, top_n=3):
    req = parse_requirement(text)
    print("=" * 64)
    print("USER REQUIREMENT\n" + "-" * 16 + f"\n{text}\n")
    print("STRUCTURED REQUIREMENT\n" + "-" * 22)
    print(f"Product:  {req.product}\nProcess:  {req.process}\nMaterial: {req.material}\n"
          f"Quantity: {req.quantity}\nDeadline: {req.deadline_days} days\nLocation: {req.location}\n")

    results = match_manufacturers(req, manufacturers)
    eligible = [r for r in results if r["eligible"]]
    if eligible:
        print("TOP MATCHES\n" + "-" * 11)
        shown = eligible[:top_n]
    else:
        print("NO FULLY ELIGIBLE MANUFACTURER FOUND - closest alternatives (not eligible):\n" + "-" * 66)
        shown = results[:top_n]

    for i, r in enumerate(shown, 1):
        print(f"\n{i}. {r['manufacturer']} ({r['location']})")
        print(f"Match Score: {r['final_score']:.0f}%\n")
        print(f"Capability: {r['capability_score']}%\nMaterial:   {r['material_score']}%\n"
              f"Capacity:   {r['capacity_score']}%\nLocation:   {r['location_score']}%\n"
              f"Lead Time:  {r['lead_time_score']}%")
        if not r["eligible"]:
            print("Not eligible: " + "; ".join(r["ineligible_reasons"]))
        print(f"\nWhy:\n{r['explanation']}")
    print()


if __name__ == "__main__":
    data = load_manufacturers()
    print("NOTE: all manufacturers are FICTIONAL demo data.\n")
    for text in (sys.argv[1:] or TEST_REQUIREMENTS):
        show(text, data)
