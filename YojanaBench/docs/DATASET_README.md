# YojanaBench Dataset

Human-verified benchmark for **India welfare-scheme document reasoning**.
This folder is self-contained and can be published/shipped independently of the code.

## Layout

```
data/
+-- schemes/          35 structured SchemeSchema JSON files (conditions + formulas)
+-- guidelines/       Rendered guideline "documents" (stand-ins for official PDFs)
+-- cases/            Sample case applications for the audit demo
+-- beneficiaries.json Synthetic beneficiary registry (B-0001..B-0012)
+-- dbt/
+|   +-- transactions.json  Mock DBT transaction ledger (money-trace ground truth)
+-- qa/
+|   +-- qa_benchmark.json   241 QA pairs (eligibility / entitlement / documents / appeal)
+-- meta/
    +-- leaderboard.json    Public leaderboard entries
```

Dataset build utilities live in `scripts/`:

```
scripts/build_guidelines.py   schemes -> guideline documents
scripts/gen_cases.py          regenerate the synthetic demo cases
scripts/gen_qa.py             regenerate the synthetic QA pairs
```

## Scheme corpus (35 schemes)

| Scheme ID | Name | Category | Level |
|---|---|---|---|
| PDS-NFSA-2023 | Public Distribution System (NFSA) | food | central |
| IGNOAPS-2023 | Old Age Pension | pension | central |
| IGNWPS-2023 | Widow Pension | pension | central |
| IGNDPS-2023 | Disability Pension | pension | central |
| PMKISAN-2023 | PM-KISAN income support | agriculture | central |
| PMS-SC-2023 | Post-Matric Scholarship (SC) | scholarship | central |
| MGNREGA-2023 | Rural employment guarantee | employment | central |
| PMJAY-2023 | Ayushman Bharat health cover | health | central |
| PMAYG-2023 | PMAY-Gramin housing | housing | central |
| NSP-PREMATRIC-2023 | Pre-Matric Scholarship (SC/ST) | scholarship | central |
| PMUY-2023 | PM Ujjwala Yojana (LPG connection) | energy | central |
| PMSBY-2023 | PM Suraksha Bima Yojana | insurance | central |
| PMJJBY-2023 | PM Jeevan Jyoti Bima Yojana | insurance | central |
| APY-2023 | Atal Pension Yojana | pension | central |
| SSY-2023 | Sukanya Samriddhi Yojana | savings | central |
| PMMVY-2023 | PM Matru Vandana Yojana | maternity | central |
| PMJDY-2023 | PM Jan Dhan Yojana | banking | central |
| PMFBY-2023 | PM Fasal Bima Yojana | agriculture | central |
| KCC-2023 | Kisan Credit Card | credit | central |
| PMKUSUM-2023 | PM-KUSUM solar pumps | energy | central |
| PMAYU-2023 | PMAY-Urban housing | housing | central |
| SBMG-2023 | Swachh Bharat Mission (Gramin) | sanitation | central |
| JJM-2023 | Jal Jeevan Mission | water | central |
| MDM-2023 | PM POSHAN (Mid-Day Meal) | nutrition | central |
| ICDS-2023 | Integrated Child Development Services | nutrition | central |
| SVA-2023 | PM SVANidhi (street vendors) | livelihood | central |
| PMEGP-2023 | PM Employment Generation Programme | employment | central |
| MUDRA-2023 | PM MUDRA Yojana | credit | central |
| SUI-2023 | Stand-Up India | entrepreneurship | central |
| PMVK-2023 | PM Vishwakarma | livelihood | central |
| ESRAM-2023 | eShram (unorganised workers) | labour | central |
| PMKMY-2023 | PM Kisan Maandhan Yojana | pension | central |
| DDUGKY-2023 | Deen Dayal Upadhyaya Grameen Kaushalya Yojana | skill | central |
| NRLM-2023 | DAY-NRLM (rural livelihoods) | livelihood | central |
| PMFME-2023 | PM Formalisation of Micro Food Processing Enterprises | food | central |

## QA benchmark schema

Each item:

```json
{
  "id": "YB-PDS-0002",
  "scheme_id": "PDS-NFSA-2023",
  "category": "eligibility | entitlement | documents | appeal",
  "question": "...",
  "reference_answer": "...",
  "verdict": "eligible | ineligible | needs_info | informational",
  "entitlement_value": 35.0,
  "entitlement_unit": "kg/month",
  "evidence_clause_ids": ["PDS-E1"],
  "counterfactual_of": null,
  "edge_case": "boundary_income | boundary_age | missing_document | overlapping_schemes | ...",
  "applicant": { "...machine-readable profile for end-to-end runs..." }
}
```

Edge/counterfactual coverage: boundary age (59/60/79/80), boundary income
(Rs. 2,50,000), boundary disability (60% vs 80%), missing mandatory documents,
category swaps, exclusion rules and overlapping schemes.

## Beneficiary registry & DBT ledger (money-trace module)

`data/beneficiaries.json` holds the 12 synthetic beneficiaries referenced by the
grievance module:

```json
{
  "beneficiary_id": "B-0004",
  "name": "Geeta Kumari",
  "aadhaar_last4": "1890",
  "mobile": "9xxxxxxxxx",
  "state": "Bihar",
  "bank_name": "Bank of India",
  "account_last4": "6611",
  "ifsc": "BKID000XXXX",
  "scheme_ids": ["PMAYG-2023"]
}
```

`data/dbt/transactions.json` is the mock **Direct Benefit Transfer ledger** — one
record per government disbursement, with the ground truth the trace agents must
recover:

```json
{
  "utr": "UTR2026PMAYG0001",
  "scheme_id": "PMAYG-2023",
  "beneficiary_id": "B-0004",
  "sanctioned_amount": 120000,
  "credited_amount": 120000,
  "expected_account_last4": "6611",
  "credited_to_account_last4": "9999",
  "credited_to_name": "Agent XYZ Enterprises",
  "status": "credited | not_credited | partial | diverted | failed",
  ...
}
```

The ledger deliberately covers every trace scenario: correct credit, silent
non-credit, partial/shortfall, failed/reverted credit, diversion to a third-party
account, and an **account (`****9999`) shared by three different beneficiaries** —
the mule-account fraud ring the `fraud` agent detects. These are synthetic
records for the offline demo, not real payment data.

## Important note on amounts

Amounts and ceilings are **simplified/illustrative values** chosen to make the
benchmark reproducible and self-contained. They reflect the structure and typical
magnitudes of the real schemes but should not be treated as the official current
rates. Replace with ministry-notified values for production use.

## Rebuilding the guideline documents

```
python scripts/build_guidelines.py
```
