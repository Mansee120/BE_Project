"""
build_guidelines.py
-------------------
Dataset build utility for YojanaBench.

Reads the structured scheme schemas in data/schemes/*.json and renders
human-readable "guideline documents" (plain-text stand-ins for the official
government PDFs) into data/guidelines/<scheme_id>.txt.

The Corpus Agent ingests BOTH:
  * the machine-readable schema (schemes/*.json)  -> conditions & formulas
  * the guideline text         (guidelines/*.txt)  -> chunks, citations, stats

Run:  python scripts/build_guidelines.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
SCHEMES_DIR = os.path.join(DATA_DIR, "schemes")
GUIDELINES_DIR = os.path.join(DATA_DIR, "guidelines")


def render_scheme(scheme: dict) -> str:
    """Render one scheme schema into a pseudo-guideline document string."""
    lines = []
    lines.append("=" * 78)
    lines.append(f"GOVERNMENT GUIDELINE DOCUMENT")
    lines.append(f"SCHEME: {scheme['name']}")
    lines.append(f"SCHEME ID: {scheme['scheme_id']}")
    lines.append(f"LEVEL: {scheme['level'].upper()}   |   STATE: {scheme.get('state', 'All India')}")
    lines.append(f"CATEGORY: {scheme['category'].upper()}")
    lines.append("=" * 78)
    lines.append("")
    lines.append("1. OBJECTIVE")
    lines.append(f"   {scheme['summary']}")
    lines.append("")

    lines.append("2. ELIGIBILITY CRITERIA")
    for c in scheme["eligibility_clauses"]:
        tag = "MANDATORY" if c.get("mandatory", True) else "OPTIONAL"
        lines.append(f"   [{c['clause_id']}] ({tag}) {c['text']}")
    lines.append("")

    lines.append("3. ENTITLEMENT / BENEFIT RULES")
    for e in scheme["entitlement_rules"]:
        lines.append(f"   [{e['rule_id']}] {e['text']}")
    lines.append("")

    lines.append("4. DOCUMENTS REQUIRED")
    for d in scheme["required_documents"]:
        tag = "MANDATORY" if d.get("mandatory", True) else "OPTIONAL"
        lines.append(f"   [{d['doc_id']}] ({tag}) {d['name']}")
    lines.append("")

    lines.append("5. APPLICATION & GRIEVANCE / APPEAL HIERARCHY")
    for a in scheme["appeal_hierarchy"]:
        lines.append(
            f"   [{scheme['scheme_id'].split('-')[0]}-APL{a['level']}] "
            f"Level {a['level']}: {a['authority']} - within {a['deadline_days']} days. {a['description']}"
        )
    lines.append("")
    lines.append("=" * 78)
    lines.append("END OF GUIDELINE DOCUMENT")
    lines.append("")
    return "\n".join(lines)


def main():
    os.makedirs(GUIDELINES_DIR, exist_ok=True)
    count = 0
    for fname in sorted(os.listdir(SCHEMES_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(SCHEMES_DIR, fname), "r", encoding="utf-8") as f:
            scheme = json.load(f)
        text = render_scheme(scheme)
        out = os.path.join(GUIDELINES_DIR, f"{scheme['scheme_id']}.txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        count += 1
        print(f"  rendered {scheme['scheme_id']:<20} -> {os.path.basename(out)}")
    print(f"\nDone. {count} guideline documents written to {GUIDELINES_DIR}")


if __name__ == "__main__":
    main()
