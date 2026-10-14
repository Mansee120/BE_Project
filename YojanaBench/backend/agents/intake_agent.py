"""
intake_agent.py  (Agent 2/8)
----------------------------
Online agent that turns a raw application into a validated CaseRecord.

Responsibilities:
  * normalise applicant fields (aliases, income in "lakhs" -> rupees, int casts)
  * detect / confirm the target scheme
  * work out the required document checklist and the missing documents
  * mark unknown fields instead of guessing (drives needs_info later)
"""
from .. import config  # noqa: F401  (kept for symmetry / future tuning)

# Common aliases users may submit in the UI form.
_FIELD_ALIASES = {
    "income": "annual_income",
    "annualIncome": "annual_income",
    "familySize": "family_size",
    "family": "family_size",
    "disability": "disability_percent",
    "disabilityPercent": "disability_percent",
    "widow": "is_widow",
    "farmer": "is_farmer",
    "bpl_card": "bpl",
    "ration_card": "card_type",
    "class": "class_level",
    "hostel": "hosteller",
    "residence": "region",
}

# Fields that should be coerced to integers when possible.
_INT_FIELDS = {"age", "family_size", "disability_percent", "class_level", "annual_income"}
_BOOL_FIELDS = {
    "bpl", "is_widow", "is_farmer", "is_income_tax_payer",
    "is_institutional_landholder", "hosteller", "owns_pucca_house", "secc_listed",
}


class IntakeAgent:
    def __init__(self, corpus):
        self.corpus = corpus

    # -- helpers --------------------------------------------------------------
    def _normalise_applicant(self, raw: dict) -> dict:
        clean = {}
        for key, value in raw.items():
            # Accept alias keys and drop empty strings
            key = _FIELD_ALIASES.get(key, key)
            if value is None or value == "":
                continue
            # Boolean strings -> real booleans
            if key in _BOOL_FIELDS and isinstance(value, str):
                value = value.strip().lower() in ("true", "yes", "1", "y")
            # Allow income expressed in lakhs (e.g. 2.5) to be read as lakhs.
            # Do this BEFORE the integer cast so the decimal part is preserved.
            if key == "annual_income" and isinstance(value, (int, float)) \
                    and not isinstance(value, bool) and 0 < value < 100:
                value = value * 100000
            # Coerce numeric-looking text into integers
            if key in _INT_FIELDS and not isinstance(value, bool):
                try:
                    value = int(float(value))
                except (TypeError, ValueError):
                    pass
            clean[key] = value
        return clean

    def _document_check(self, scheme, submitted):
        required = [d for d in scheme["required_documents"] if d.get("mandatory", True)]
        required_names = [d["name"] for d in required]
        # `None` means the caller did not supply a document list (e.g. a pure QA
        # item) -> we assume the checklist is complete and stay neutral.
        # An explicit list (even empty) means we judge it as submitted.
        if submitted is None:
            return {"required": required_names, "submitted": [], "missing": [],
                    "assumed_complete": True}
        norm_sub = {s.strip().lower() for s in submitted}
        missing = [name for name in required_names if name.strip().lower() not in norm_sub]
        return {"required": required_names, "submitted": list(submitted),
                "missing": missing, "assumed_complete": False}

    # -- public ---------------------------------------------------------------
    def run(self, scheme_id: str, applicant: dict, submitted_documents: list = None,
            case_id: str = None) -> dict:
        scheme = self.corpus.get_scheme(scheme_id)
        if scheme is None:
            raise ValueError(f"Unknown scheme_id: {scheme_id}")

        normalised = self._normalise_applicant(applicant or {})
        docs = self._document_check(scheme, submitted_documents)

        return {
            "case_id": case_id or "CASE-ADHOC",
            "scheme_id": scheme_id,
            "scheme_name": scheme["name"],
            "applicant": normalised,
            "required_documents": docs["required"],
            "submitted_documents": docs["submitted"],
            "missing_documents": docs["missing"],
            "documents_assumed_complete": docs["assumed_complete"],
        }
