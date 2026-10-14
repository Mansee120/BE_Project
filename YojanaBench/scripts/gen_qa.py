"""
gen_qa.py
---------
Development helper that (re)generates the synthetic QA pairs appended to
``data/qa/qa_benchmark.json``. The hand-authored items (the first 56, with
``YB-*`` ids) are preserved; everything after them is rewritten from the scheme
schemas so the file always satisfies the YojanaBench item schema.

Run:  python scripts/gen_qa.py
"""
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.pipeline import Pipeline  # noqa: E402
from backend import config  # noqa: E402

# Number of hand-authored items at the top of the file that we must not touch.
N_HAND = 56
TARGET = 100


def clause_ids(scheme, kind):
    if kind == "eligibility":
        return [c["clause_id"] for c in scheme["eligibility_clauses"]]
    if kind == "entitlement":
        return [e["rule_id"] for e in scheme["entitlement_rules"]]
    if kind == "documents":
        return [d["doc_id"] for d in scheme["required_documents"]]
    return []


# Per-scheme applicants used to synthesise eligibility + entitlement items.
PROFILES = {
    "PDS-NFSA-2023": [
        ("AAY rural household", {"age": 34, "category": "SC", "region": "rural",
         "family_size": 4, "card_type": "AAY", "bpl": True, "is_income_tax_payer": False}),
        ("Priority household (PHH) in a city", {"age": 29, "category": "OBC",
         "region": "urban", "family_size": 6, "card_type": "PHH", "bpl": True,
         "is_income_tax_payer": False}),
        ("APL family of an income-tax payer", {"age": 41, "category": "General",
         "region": "urban", "family_size": 3, "card_type": "APL", "bpl": False,
         "is_income_tax_payer": True}),
    ],
    "IGNOAPS-2023": [
        ("BPL senior aged 71", {"age": 71, "bpl": True, "category": "General"}),
        ("BPL senior aged 88", {"age": 88, "bpl": True, "category": "OBC"}),
        ("Senior above the poverty line", {"age": 67, "bpl": False, "category": "General"}),
    ],
    "IGNWPS-2023": [
        ("BPL widow aged 52", {"age": 52, "gender": "female", "is_widow": True,
         "bpl": True, "category": "SC"}),
        ("BPL widow aged 85", {"age": 85, "gender": "female", "is_widow": True,
         "bpl": True, "category": "General"}),
        ("Married woman in a BPL home", {"age": 44, "gender": "female",
         "is_widow": False, "bpl": True, "category": "OBC"}),
    ],
    "IGNDPS-2023": [
        ("BPL applicant with 90% disability", {"age": 34, "disability_percent": 90,
         "bpl": True, "category": "SC"}),
        ("BPL applicant with 80% disability", {"age": 40, "disability_percent": 80,
         "bpl": True, "category": "OBC"}),
        ("Applicant with 55% disability", {"age": 34, "disability_percent": 55,
         "bpl": True, "category": "SC"}),
    ],
    "MGNREGA-2023": [
        ("Rural adult seeking work", {"age": 31, "region": "rural", "category": "OBC"}),
        ("Rural adult aged 18", {"age": 18, "region": "rural", "category": "SC"}),
        ("Urban adult resident", {"age": 27, "region": "urban", "category": "General"}),
    ],
    "PMAYG-2023": [
        ("Houseless SECC-listed family", {"age": 39, "family_size": 5,
         "house_type": "houseless", "owns_pucca_house": False, "secc_listed": True,
         "region": "rural"}),
        ("Kutcha-house SECC-listed family", {"age": 47, "family_size": 4,
         "house_type": "kutcha", "owns_pucca_house": False, "secc_listed": True,
         "region": "rural"}),
        ("Family already owning a pucca house", {"age": 44, "family_size": 4,
         "house_type": "pucca", "owns_pucca_house": True, "secc_listed": True,
         "region": "rural"}),
    ],
    "PMKISAN-2023": [
        ("Small farmer, not an income-tax payer", {"age": 43, "is_farmer": True,
         "is_institutional_landholder": False, "is_income_tax_payer": False,
         "region": "rural"}),
        ("Institutional landholder", {"age": 50, "is_farmer": True,
         "is_institutional_landholder": True, "is_income_tax_payer": False,
         "region": "rural"}),
        ("Farmer who pays income tax", {"age": 55, "is_farmer": True,
         "is_institutional_landholder": False, "is_income_tax_payer": True,
         "region": "rural"}),
    ],
    "PMJAY-2023": [
        ("BPL rural family", {"age": 58, "bpl": True, "region": "rural",
         "family_size": 4}),
        ("BPL urban family of six", {"age": 36, "bpl": True, "region": "urban",
         "family_size": 6}),
        ("APL urban family", {"age": 44, "bpl": False, "region": "urban",
         "family_size": 3}),
    ],
    "NSP-PREMATRIC-2023": [
        ("SC day-scholar in class 9", {"age": 14, "category": "SC",
         "class_level": 9, "annual_income": 120000, "hosteller": False}),
        ("ST hosteller in class 10", {"age": 15, "category": "ST",
         "class_level": 10, "annual_income": 180000, "hosteller": True}),
        ("General-category student", {"age": 15, "category": "General",
         "class_level": 9, "annual_income": 150000}),
    ],
    "PMS-SC-2023": [
        ("SC hosteller in a UG course", {"age": 19, "category": "SC",
         "education_level": "UG", "annual_income": 150000, "hosteller": True}),
        ("SC day-scholar in class 12", {"age": 17, "category": "SC",
         "education_level": "12", "annual_income": 200000, "hosteller": False}),
        ("SC applicant above the income ceiling", {"age": 21, "category": "SC",
         "education_level": "PG", "annual_income": 400000, "hosteller": False}),
    ],
}


def mandatory_names(scheme):
    return [d["name"] for d in scheme["required_documents"] if d.get("mandatory", True)]


def build_eligibility_item(seq, scheme, desc, applicant):
    return {
        "id": f"YB-{scheme['scheme_id'].split('-')[0]}-S{seq:03d}",
        "scheme_id": scheme["scheme_id"],
        "category": "eligibility",
        "question": f"Is the applicant eligible for {scheme['name']}? ({desc})",
        "reference_answer": None,          # filled after the pipeline run
        "verdict": None,                   # filled after the pipeline run
        "entitlement_value": None,
        "entitlement_unit": None,
        "evidence_clause_ids": clause_ids(scheme, "eligibility"),
        "counterfactual_of": None,
        "edge_case": None,
        "applicant": applicant,
    }


def build_entitlement_item(seq, scheme, desc, applicant):
    return {
        "id": f"YB-{scheme['scheme_id'].split('-')[0]}-E{seq:03d}",
        "scheme_id": scheme["scheme_id"],
        "category": "entitlement",
        "question": f"What benefit does the applicant receive under {scheme['name']}? ({desc})",
        "reference_answer": None,
        "verdict": None,
        "entitlement_value": None,
        "entitlement_unit": None,
        "evidence_clause_ids": clause_ids(scheme, "entitlement"),
        "counterfactual_of": None,
        "edge_case": None,
        "applicant": applicant,
    }


def build_documents_item(scheme):
    docs = mandatory_names(scheme)
    return {
        "id": f"YB-{scheme['scheme_id'].split('-')[0]}-D001",
        "scheme_id": scheme["scheme_id"],
        "category": "documents",
        "question": f"Which documents must accompany a {scheme['name']} application?",
        "reference_answer": "Required documents: " + ", ".join(docs),
        "verdict": "informational",
        "entitlement_value": None,
        "entitlement_unit": None,
        "evidence_clause_ids": clause_ids(scheme, "documents"),
        "counterfactual_of": None,
        "edge_case": None,
        "applicant": {},
    }


def build_appeal_item(scheme):
    levels = scheme["appeal_hierarchy"]
    parts = [f"Level {a['level']}: {a['authority']} within {a['deadline_days']} days"
             for a in levels]
    return {
        "id": f"YB-{scheme['scheme_id'].split('-')[0]}-A001",
        "scheme_id": scheme["scheme_id"],
        "category": "appeal",
        "question": f"What is the appeal procedure for a rejected {scheme['name']} application?",
        "reference_answer": "Appeal procedure: " + "; ".join(parts),
        "verdict": "informational",
        "entitlement_value": None,
        "entitlement_unit": None,
        "evidence_clause_ids": [f"{scheme['scheme_id'].split('-')[0]}-APL{a['level']}"
                                for a in levels],
        "counterfactual_of": None,
        "edge_case": None,
        "applicant": {},
    }


def main():
    path = config.QA_BENCHMARK_PATH
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data["items"]
    hand = items[:N_HAND]          # keep the human-authored block
    pipeline = Pipeline()

    scheme_ids = sorted(pipeline.corpus.schemes)
    generated = []
    seq = 0

    # 1) eligibility + entitlement items per scheme
    for sid in scheme_ids:
        scheme = pipeline.corpus.get_scheme(sid)
        profiles = PROFILES.get(sid, [])
        for desc, applicant in profiles:
            seq += 1
            elig = build_eligibility_item(seq, scheme, desc, applicant)
            r = pipeline.run_case(sid, applicant)
            elig["verdict"] = r["verdict"]["decision"]
            elig["reference_answer"] = r["verdict"]["answer"]
            generated.append(elig)

        # one entitlement item from the first (eligible) profile
        if profiles:
            desc, applicant = profiles[0]
            seq += 1
            ent_item = build_entitlement_item(seq, scheme, desc, applicant)
            r = pipeline.run_case(sid, applicant)
            ent = r["verdict"].get("computed_entitlement")
            unit = r["verdict"].get("entitlement_unit")
            ent_item["entitlement_value"] = ent if ent else None
            ent_item["entitlement_unit"] = unit if ent else None
            ent_item["verdict"] = r["verdict"]["decision"]
            ent_item["reference_answer"] = (
                f"Entitlement: {ent} {unit}." if ent
                else "No monetary entitlement applies to this scheme."
            )
            generated.append(ent_item)

    # 2) documents + appeal reference items (one each per scheme)
    for sid in scheme_ids:
        scheme = pipeline.corpus.get_scheme(sid)
        generated.append(build_documents_item(scheme))
        generated.append(build_appeal_item(scheme))

    # 3) trim to the TARGET total, preserving the hand-authored block
    room = TARGET - len(hand)
    new_items = generated[:room] if room > 0 else []

    data["items"] = hand + new_items
    data["num_items"] = len(data["items"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Kept {len(hand)} hand-authored + wrote {len(new_items)} generated "
          f"= {len(data['items'])} items")


if __name__ == "__main__":
    main()
