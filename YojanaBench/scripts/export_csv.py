"""
export_csv.py
-------------
Export every YojanaBench dataset to CSV under ``data/csv/``.

One CSV file per logical table so the dataset can be opened in Excel / loaded
into pandas without any JSON parsing:

    schemes.csv               one row per scheme
    eligibility_clauses.csv   scheme eligibility clauses (long form)
    entitlement_rules.csv     scheme entitlement rules (long form)
    required_documents.csv    required documents (long form)
    appeal_hierarchy.csv      appeal levels (long form)
    qa_benchmark.csv          the 100 human-verified QA pairs (+ applicant cols)
    cases.csv                 the sample demo applications (+ applicant cols)
    beneficiaries.csv         the DBT beneficiary registry
    dbt_transactions.csv      the mock DBT transaction ledger
    guidelines.csv            the rendered guideline documents

Run:  python scripts/export_csv.py
"""
import csv
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "csv")


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_csv(name, rows, fieldnames=None):
    """Write rows (list of dicts) to OUT/name, preserving key order."""
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    if fieldnames is None:
        fieldnames = []
        for r in rows:
            for k in r:
                if k not in fieldnames:
                    fieldnames.append(k)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f"  {name:<26} {len(rows):>4} rows  ->  {path}")
    return fieldnames


def join_list(value):
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value)
    return value


def export_schemes():
    files = sorted(glob.glob(os.path.join(DATA, "schemes", "*.json")))
    schemes, elig, ent, docs, appeal = [], [], [], [], []

    for fp in files:
        s = read_json(fp)
        schemes.append({
            "scheme_id": s["scheme_id"],
            "name": s["name"],
            "level": s.get("level", ""),
            "state": s.get("state", ""),
            "category": s.get("category", ""),
            "summary": s.get("summary", ""),
            "n_eligibility": len(s.get("eligibility_clauses", [])),
            "n_entitlement": len(s.get("entitlement_rules", [])),
            "n_documents": len(s.get("required_documents", [])),
            "n_appeal_levels": len(s.get("appeal_hierarchy", [])),
        })
        sid = s["scheme_id"]
        for c in s.get("eligibility_clauses", []):
            elig.append({
                "scheme_id": sid,
                "clause_id": c.get("clause_id", ""),
                "field": c.get("field", ""),
                "operator": c.get("operator", ""),
                "value": join_list(c.get("value")),
                "mandatory": c.get("mandatory", ""),
                "text": c.get("text", ""),
            })
        for r in s.get("entitlement_rules", []):
            ent.append({
                "scheme_id": sid,
                "rule_id": r.get("rule_id", ""),
                "text": r.get("text", ""),
                "when": json.dumps(r.get("when", {}), ensure_ascii=False),
                "compute": json.dumps(r.get("compute", {}), ensure_ascii=False),
                "clause_ids": join_list(r.get("clause_ids", [])),
            })
        for d in s.get("required_documents", []):
            docs.append({
                "scheme_id": sid,
                "doc_id": d.get("doc_id", ""),
                "name": d.get("name", ""),
                "mandatory": d.get("mandatory", ""),
            })
        for a in s.get("appeal_hierarchy", []):
            appeal.append({
                "scheme_id": sid,
                "level": a.get("level", ""),
                "authority": a.get("authority", ""),
                "deadline_days": a.get("deadline_days", ""),
                "description": a.get("description", ""),
            })

    print("Schemes:")
    write_csv("schemes.csv", schemes)
    write_csv("eligibility_clauses.csv", elig)
    write_csv("entitlement_rules.csv", ent)
    write_csv("required_documents.csv", docs)
    write_csv("appeal_hierarchy.csv", appeal)


def _applicant_columns(records):
    cols = []
    for r in records:
        for k in (r.get("applicant") or {}):
            if "applicant_" + k not in cols:
                cols.append("applicant_" + k)
    return cols


def export_qa():
    data = read_json(os.path.join(DATA, "qa", "qa_benchmark.json"))
    items = data["items"]
    app_cols = _applicant_columns(items)
    rows = []
    for it in items:
        row = {
            "id": it["id"],
            "scheme_id": it["scheme_id"],
            "category": it["category"],
            "question": it["question"],
            "reference_answer": it["reference_answer"],
            "verdict": it.get("verdict", ""),
            "entitlement_value": it.get("entitlement_value", ""),
            "entitlement_unit": it.get("entitlement_unit", ""),
            "evidence_clause_ids": join_list(it.get("evidence_clause_ids", [])),
            "counterfactual_of": it.get("counterfactual_of", ""),
            "edge_case": it.get("edge_case", ""),
            "secondary_scheme_id": it.get("secondary_scheme_id", ""),
            "submitted_documents": join_list(it.get("submitted_documents", [])),
        }
        for c in app_cols:
            row[c] = (it.get("applicant") or {}).get(c[len("applicant_"):], "")
        rows.append(row)
    print("QA benchmark:")
    write_csv("qa_benchmark.csv", rows)


def export_cases():
    files = sorted(glob.glob(os.path.join(DATA, "cases", "*.json")))
    cases = [read_json(fp) for fp in files]
    app_cols = _applicant_columns(cases)
    rows = []
    for c in cases:
        row = {
            "case_id": c["case_id"],
            "scheme_id": c["scheme_id"],
            "label": c.get("label", ""),
            "submitted_documents": join_list(c.get("submitted_documents", [])),
        }
        for col in app_cols:
            row[col] = (c.get("applicant") or {}).get(col[len("applicant_"):], "")
        rows.append(row)
    print("Demo cases:")
    write_csv("cases.csv", rows)


def export_beneficiaries():
    data = read_json(os.path.join(DATA, "beneficiaries.json"))
    rows = []
    for b in data["beneficiaries"]:
        row = dict(b)
        row["scheme_ids"] = join_list(b.get("scheme_ids", []))
        rows.append(row)
    print("Beneficiaries:")
    write_csv("beneficiaries.csv", rows)


def export_dbt():
    data = read_json(os.path.join(DATA, "dbt", "transactions.json"))
    rows = [dict(t) for t in data["transactions"]]
    print("DBT ledger:")
    write_csv("dbt_transactions.csv", rows)


def export_guidelines():
    files = sorted(glob.glob(os.path.join(DATA, "guidelines", "*.txt")))
    rows = []
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            text = f.read()
        rows.append({
            "scheme_id": os.path.splitext(os.path.basename(fp))[0],
            "filename": os.path.basename(fp),
            "chars": len(text),
            "text": text,
        })
    print("Guidelines:")
    write_csv("guidelines.csv", rows)


def main():
    print(f"Exporting YojanaBench dataset to CSV -> {OUT}\n")
    export_schemes()
    export_qa()
    export_cases()
    export_beneficiaries()
    export_dbt()
    export_guidelines()
    print("\nDone.")


if __name__ == "__main__":
    main()
