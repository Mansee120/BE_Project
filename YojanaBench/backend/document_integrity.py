"""
document_integrity.py
---------------------
Deterministic fake / tampered-document detection.

The engine never sees the *content* of an uploaded document, so instead of
reading papers it validates that everything an application declares can
plausibly be true *at the same time*:

  1. impossible values      - age 150, disability 150 %, negative income …
  2. cross-field conflicts  - BPL household with a ₹9L income, APL card
                              marked BPL, income-tax payer below the tax
                              floor, widow below 18 …
  3. unsubstantiated claims - a claim whose backing certificate the scheme
                              requires is not among the submitted documents.

`apply_tamper` simulates a forged/omitted document so the Policy Sandbox can
show an official how many forgeries the checker would catch.
"""
from typing import List, Optional, Tuple

# -- plausibility bounds (documented in Mathematical_Calculations.md) ---------
MAX_PLAUSIBLE_AGE = 120
MAX_DISABILITY_PERCENT = 100
MIN_FAMILY_SIZE = 1
MAX_FAMILY_SIZE = 20
BPL_INCOME_LIMIT = 300_000        # a BPL household cannot earn more than this
TAX_PAYER_MIN_INCOME = 250_000    # income-tax floor (old regime)
IMPLAUSIBLE_INCOME = 10_000_000   # > ₹1 crore declared on a welfare form
MIN_COLLEGE_AGE = 17              # UG/PG/Professional applicant must be 17+

# -- claim -> evidence keywords (only checked when the scheme requires them) --
_CLAIM_EVIDENCE = [
    ("bpl", lambda a: a.get("bpl") is True,
     ["bpl card", "ration card"]),
    ("priority ration card (AAY/PHH)", lambda a: a.get("card_type") in ("AAY", "PHH"),
     ["ration card", "bpl card"]),
    ("disability", lambda a: _is_num(a.get("disability_percent")) and a["disability_percent"] > 0,
     ["disability certificate"]),
    ("widow status", lambda a: a.get("is_widow") is True,
     ["death certificate"]),
    ("farmer status", lambda a: a.get("is_farmer") is True,
     ["land records", "sowing certificate"]),
    ("SC/ST category", lambda a: a.get("category") in ("SC", "ST"),
     ["caste certificate", "category certificate"]),
]


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_integrity(applicant: Optional[dict], scheme: Optional[dict],
                    submitted_documents: Optional[List[str]] = None,
                    documents_assumed_complete: bool = True,
                    include_missing: bool = False) -> List[dict]:
    """Return a list of integrity flags: {code, severity, detail}.

    severity "high"  -> the declarations cannot all be true (suspected forgery)
    severity "medium"-> suspicious inconsistency an officer should review
    severity "low"   -> implausible data quality

    Evidence checks (3) only run when the application supplied an explicit
    document list; a QA item with no document list stays neutral.
    """
    a = applicant or {}
    flags = []

    def add(code, severity, detail):
        flags.append({"code": code, "severity": severity, "detail": detail})

    # -- 1. impossible / implausible values ---------------------------------
    if _is_num(a.get("age")) and not (0 <= a["age"] <= MAX_PLAUSIBLE_AGE):
        add("age_invalid", "high",
            f"Declared age {a['age']} is outside 0-{MAX_PLAUSIBLE_AGE}.")

    if _is_num(a.get("disability_percent")) and \
            not (0 <= a["disability_percent"] <= MAX_DISABILITY_PERCENT):
        add("disability_invalid", "high",
            f"Declared disability {a['disability_percent']}% is outside "
            f"0-{MAX_DISABILITY_PERCENT}%.")

    if _is_num(a.get("family_size")) and \
            not (MIN_FAMILY_SIZE <= a["family_size"] <= MAX_FAMILY_SIZE):
        add("family_size_invalid", "medium",
            f"Declared family size {a['family_size']} is outside "
            f"{MIN_FAMILY_SIZE}-{MAX_FAMILY_SIZE}.")

    if _is_num(a.get("annual_income")):
        if a["annual_income"] < 0:
            add("income_negative", "high",
                f"Declared annual income {a['annual_income']} is negative.")
        elif a["annual_income"] > IMPLAUSIBLE_INCOME:
            add("income_implausible", "medium",
                f"Declared annual income ₹{a['annual_income']:,} exceeds "
                f"₹{IMPLAUSIBLE_INCOME:,} — possible doctored figure.")

    # -- 2. cross-field contradictions --------------------------------------
    income = a.get("annual_income")
    if a.get("bpl") is True and _is_num(income) and income > BPL_INCOME_LIMIT:
        add("bpl_income_contradiction", "high",
            f"Declared BPL household but annual income ₹{income:,} exceeds "
            f"the BPL limit ₹{BPL_INCOME_LIMIT:,}.")

    if a.get("is_income_tax_payer") is True and _is_num(income) \
            and income < TAX_PAYER_MIN_INCOME:
        add("income_tax_contradiction", "high",
            f"Declared income-tax payer with annual income ₹{income:,}, "
            f"below the ₹{TAX_PAYER_MIN_INCOME:,} tax floor.")

    if a.get("card_type") in ("AAY", "PHH") and a.get("bpl") is False:
        add("card_bpl_contradiction", "high",
            f"Ration card {a['card_type']} (priority category) declared "
            "while the household is marked NOT BPL.")
    if a.get("card_type") == "APL" and a.get("bpl") is True:
        add("card_bpl_contradiction", "high",
            "Ration card APL declared while the household is marked BPL.")

    if a.get("is_widow") is True and _is_num(a.get("age")) and a["age"] < 18:
        add("widow_age_contradiction", "medium",
            f"Declared widow with age {a['age']}.")

    if a.get("education_level") in ("UG", "PG", "Professional") \
            and _is_num(a.get("age")) and a["age"] < MIN_COLLEGE_AGE:
        add("education_age_contradiction", "medium",
            f"Declared education level {a['education_level']} with age "
            f"{a['age']} (expected >= {MIN_COLLEGE_AGE}).")

    if a.get("secc_listed") is True and (a.get("owns_pucca_house") is True
                                         or a.get("house_type") == "pucca"):
        add("secc_pucca_contradiction", "medium",
            "Declared SECC-listed while also owning a pucca house.")

    # -- 3. claims not backed by the scheme's required evidence --------------
    explicit_docs = submitted_documents is not None and not documents_assumed_complete
    if explicit_docs and scheme:
        submitted_norm = [s.strip().lower() for s in submitted_documents]
        required_norm = [d["name"].strip().lower()
                         for d in scheme.get("required_documents", [])]

        if include_missing:
            missing = [name for name in required_norm
                       if name not in submitted_norm]
            if missing:
                add("missing_mandatory_document", "medium",
                    f"{len(missing)} mandatory document(s) not submitted: "
                    + ", ".join(missing))

        for label, predicate, keywords in _CLAIM_EVIDENCE:
            if not predicate(a):
                continue
            backing = [r for r in required_norm
                       if any(kw in r for kw in keywords)]
            if not backing:
                continue          # scheme does not demand proof of this claim
            if not any(b in submitted_norm for b in backing):
                add("unsupported_claim", "medium",
                    f"Claim '{label}' is not backed by any submitted document "
                    f"(expected: {', '.join(backing)}).")

    return flags


# -- forgery simulation (Policy Sandbox) -------------------------------------
def apply_tamper(applicant: dict, submitted_documents: List[str],
                 document: str, action: str
                 ) -> Tuple[dict, List[str], List[dict]]:
    """Simulate tampering with one document.

    action = "omit"   -> the document claimed on the form was never submitted
    action = "forge"  -> the document's declared facts are doctored so they
                         contradict the rest of the application

    Returns (tampered_applicant, tampered_documents, change_descriptions).
    """
    if action not in ("omit", "forge"):
        raise ValueError(f"Unknown tamper action: {action}")

    docs = list(submitted_documents or [])
    app = dict(applicant or {})
    changes = []

    if action == "omit":
        if document not in docs:
            # tolerate case differences so the UI can pass a display name
            match = next((d for d in docs if d.lower() == document.lower()), None)
            if match is None:
                raise ValueError(f"Document '{document}' is not in the submission.")
            document = match
        docs.remove(document)
        changes.append({"location": "submitted_documents",
                        "field": document, "old_value": document,
                        "new_value": "(removed from submission)"})
        return app, docs, changes

    # -- forge: doctor the declarations this document certifies ---------------
    d = document.lower()
    if "income" in d:
        mutation = [("is_income_tax_payer", True), ("annual_income", 0)]
        strategy = "income proof forged: zero income while still declared an income-tax payer"
    elif "ration" in d or "bpl" in d:
        mutation = [("bpl", True), ("card_type", "APL")]
        strategy = "ration/BPL card forged: BPL claim on an APL card"
    elif "age" in d or "birth" in d:
        mutation = [("age", 150)]
        strategy = "age proof forged: implausible age on the application"
    elif "disability" in d:
        mutation = [("disability_percent", 150)]
        strategy = "disability certificate forged: percentage outside 0-100"
    else:
        mutation = [("annual_income", IMPLAUSIBLE_INCOME + 1)]
        strategy = f"document '{document}' forged: doctored income figure above ₹{IMPLAUSIBLE_INCOME:,}"

    for field, value in mutation:
        changes.append({"location": "applicant", "field": field,
                        "old_value": app.get(field), "new_value": value})
        app[field] = value
    changes.append({"location": "strategy", "field": document,
                    "old_value": "forged", "new_value": strategy})
    return app, docs, changes
