"""
gen_cases.py
------------
Development helper that (re)generates the synthetic demo cases under
``data/cases/``. Each case is a machine-readable applicant profile plus the
documents submitted, matching the schema of the hand-authored cases
(CASE-0001 .. CASE-0005), which are preserved.

Run:  python scripts/gen_cases.py
"""
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.pipeline import Pipeline  # noqa: E402
from backend import config  # noqa: E402

# Hand-authored cases that must never be overwritten.
KEEP = {f"CASE-{i:04d}" for i in range(1, 6)}

FIRST_GENERATED = 6


def mandatory_docs(pipeline, scheme_id):
    s = pipeline.corpus.get_scheme(scheme_id)
    return [d["name"] for d in s["required_documents"] if d.get("mandatory", True)]


# (scheme_id, description, applicant profile, document mode)
PROFILES = [
    ("PDS-NFSA-2023", "AAY household",
     {"age": 35, "category": "SC", "region": "rural", "family_size": 4,
      "card_type": "AAY", "bpl": True, "is_income_tax_payer": False}, "all"),
    ("PDS-NFSA-2023", "APL household",
     {"age": 40, "category": "General", "region": "urban", "family_size": 3,
      "card_type": "APL", "bpl": False, "is_income_tax_payer": False}, "all"),
    ("MGNREGA-2023", "Rural adult demanding work",
     {"age": 30, "region": "rural", "category": "OBC"}, "all"),
    ("MGNREGA-2023", "Urban adult",
     {"age": 28, "region": "urban", "category": "General"}, "all"),
    ("PMAYG-2023", "Houseless SECC-listed family",
     {"age": 38, "family_size": 5, "house_type": "houseless",
      "owns_pucca_house": False, "secc_listed": True}, "all"),
    ("PMAYG-2023", "Family already owning a pucca house",
     {"age": 45, "family_size": 4, "house_type": "pucca",
      "owns_pucca_house": True, "secc_listed": True}, "all"),
    ("PMKISAN-2023", "Small farmer",
     {"age": 40, "is_farmer": True, "is_institutional_landholder": False,
      "is_income_tax_payer": False, "region": "rural"}, "all"),
    ("PMKISAN-2023", "Farmer who pays income tax",
     {"age": 52, "is_farmer": True, "is_institutional_landholder": False,
      "is_income_tax_payer": True, "region": "rural"}, "all"),
    ("PMJAY-2023", "BPL family seeking health cover",
     {"age": 55, "bpl": True, "region": "rural", "family_size": 4}, "all"),
    ("PMJAY-2023", "APL family",
     {"age": 33, "bpl": False, "region": "urban", "family_size": 3}, "all"),
    ("NSP-PREMATRIC-2023", "SC girl in class 9 within income limit",
     {"age": 14, "category": "SC", "class_level": 9, "annual_income": 150000}, "all"),
    ("NSP-PREMATRIC-2023", "General category student",
     {"age": 15, "category": "General", "class_level": 9, "annual_income": 150000}, "all"),
    ("PMS-SC-2023", "SC degree student within income limit",
     {"age": 19, "category": "SC", "education_level": "UG",
      "annual_income": 120000, "hosteller": True}, "all"),
    ("PMS-SC-2023", "SC student above income ceiling",
     {"age": 21, "category": "SC", "education_level": "PG",
      "annual_income": 400000, "hosteller": False}, "all"),
    ("IGNOAPS-2023", "BPL senior aged 82 (higher slab)",
     {"age": 82, "bpl": True, "category": "General"}, "all"),
    ("IGNOAPS-2023", "BPL senior aged 65",
     {"age": 65, "bpl": True, "category": "OBC"}, "all"),
    ("IGNOAPS-2023", "Non-BPL senior",
     {"age": 66, "bpl": False, "category": "General"}, "all"),
    ("IGNWPS-2023", "BPL widow aged 45",
     {"age": 45, "gender": "female", "is_widow": True, "bpl": True,
      "category": "OBC"}, "all"),
    ("IGNWPS-2023", "BPL widow aged 82 (higher slab)",
     {"age": 82, "gender": "female", "is_widow": True, "bpl": True,
      "category": "General"}, "all"),
    ("IGNDPS-2023", "BPL person with 85% disability",
     {"age": 30, "disability_percent": 85, "bpl": True, "category": "SC"}, "all"),
    ("IGNDPS-2023", "Person with disability below 80%",
     {"age": 30, "disability_percent": 60, "bpl": True, "category": "SC"}, "all"),
    ("IGNDPS-2023", "Eligible applicant (missing disability certificate)",
     {"age": 30, "disability_percent": 85, "bpl": True, "category": "SC"}, "missing"),
    ("IGNOAPS-2023", "Eligible senior (missing bank passbook)",
     {"age": 65, "bpl": True, "category": "General"}, "missing"),
    ("PMUY-2023", "Eligible BPL woman",
     {"age": 32, "gender": "female", "bpl": True}, "all"),
    ("PMUY-2023", "Male applicant from a BPL home",
     {"age": 40, "gender": "male", "bpl": True}, "all"),
    ("PMSBY-2023", "Adult aged 40",
     {"age": 40}, "all"),
    ("PMSBY-2023", "Senior aged 75",
     {"age": 75}, "all"),
    ("PMJJBY-2023", "Adult aged 30",
     {"age": 30}, "all"),
    ("PMJJBY-2023", "Person aged 55",
     {"age": 55}, "all"),
    ("APY-2023", "Non-taxpaying worker aged 25",
     {"age": 25, "is_income_tax_payer": False}, "all"),
    ("APY-2023", "Income tax payer aged 30",
     {"age": 30, "is_income_tax_payer": True}, "all"),
    ("SSY-2023", "Girl child aged 5",
     {"age": 5, "gender": "female"}, "all"),
    ("PMMVY-2023", "Mother aged 24",
     {"age": 24, "gender": "female"}, "all"),
    ("PMJDY-2023", "Adult aged 35",
     {"age": 35}, "all"),
    ("PMFBY-2023", "Farmer seeking crop cover",
     {"age": 45, "is_farmer": True}, "all"),
    ("PMFBY-2023", "Non-farmer applicant",
     {"age": 45, "is_farmer": False}, "all"),
    ("KCC-2023", "Farmer aged 40",
     {"age": 40, "is_farmer": True}, "all"),
    ("KCC-2023", "Non-farmer aged 40",
     {"age": 40, "is_farmer": False}, "all"),
    ("PMKUSUM-2023", "Farmer seeking solar pump",
     {"age": 50, "is_farmer": True}, "all"),
    ("PMAYU-2023", "Low income household without a pucca house",
     {"age": 38, "annual_income": 250000, "owns_pucca_house": False}, "all"),
    ("SBMG-2023", "BPL rural household",
     {"age": 35, "region": "rural", "bpl": True}, "all"),
    ("JJM-2023", "Rural household",
     {"age": 30, "region": "rural"}, "all"),
    ("MDM-2023", "Child aged 9",
     {"age": 9}, "all"),
    ("ICDS-2023", "Toddler aged 3",
     {"age": 3}, "all"),
    ("SVA-2023", "Urban adult vendor",
     {"age": 35, "region": "urban"}, "all"),
    ("PMEGP-2023", "Adult applicant",
     {"age": 30}, "all"),
    ("MUDRA-2023", "Small enterprise with low income",
     {"age": 35, "annual_income": 80000}, "all"),
    ("MUDRA-2023", "Larger enterprise",
     {"age": 35, "annual_income": 800000}, "all"),
    ("SUI-2023", "Woman entrepreneur",
     {"age": 30, "gender": "female", "category": "General"}, "all"),
    ("SUI-2023", "General category male applicant",
     {"age": 30, "gender": "male", "category": "General"}, "all"),
    ("PMVK-2023", "Adult artisan",
     {"age": 40}, "all"),
    ("ESRAM-2023", "Worker aged 30",
     {"age": 30}, "all"),
    ("ESRAM-2023", "Senior aged 62",
     {"age": 62}, "all"),
    ("PMKMY-2023", "Young farmer aged 28",
     {"age": 28, "is_farmer": True}, "all"),
    ("DDUGKY-2023", "Rural youth aged 22",
     {"age": 22, "region": "rural"}, "all"),
    ("NRLM-2023", "BPL rural household",
     {"age": 35, "region": "rural", "bpl": True}, "all"),
    ("PMFME-2023", "Adult entrepreneur",
     {"age": 30}, "all"),
]


def main():
    pipeline = Pipeline()
    cases_dir = config.CASES_DIR
    os.makedirs(cases_dir, exist_ok=True)

    # Remove previously generated cases (keep the hand-authored ones).
    for fname in os.listdir(cases_dir):
        if not fname.endswith(".json"):
            continue
        cid = fname[:-5]
        if cid in KEEP:
            continue
        try:
            n = int(cid.split("-")[1])
        except (IndexError, ValueError):
            continue
        if n >= FIRST_GENERATED:
            os.remove(os.path.join(cases_dir, fname))

    case_id = FIRST_GENERATED
    for scheme_id, desc, applicant, mode in PROFILES:
        docs = mandatory_docs(pipeline, scheme_id)
        submitted = list(docs)
        if mode == "missing" and docs:
            submitted = docs[1:]  # drop one mandatory doc -> NEEDS_INFO
        result = pipeline.run_case(scheme_id, applicant,
                                   submitted_documents=submitted)
        decision = result["verdict"]["decision"]
        ent = result["verdict"]["computed_entitlement"]
        unit = result["verdict"]["entitlement_unit"]
        ent_txt = f" at {ent} {unit}" if ent else ""
        label = f"{desc} - should be {decision.upper()}{ent_txt}"

        cid = f"CASE-{case_id:04d}"
        case = {
            "case_id": cid,
            "scheme_id": scheme_id,
            "label": label,
            "applicant": applicant,
            "submitted_documents": submitted,
        }
        with open(os.path.join(cases_dir, f"{cid}.json"), "w",
                  encoding="utf-8") as f:
            json.dump(case, f, indent=2)
        case_id += 1

    total = len([f for f in os.listdir(cases_dir) if f.endswith(".json")])
    print(f"Generated {case_id - FIRST_GENERATED} cases; {total} total in {cases_dir}")


if __name__ == "__main__":
    main()
