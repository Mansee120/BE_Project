# YojanaBench

**An open, auditable benchmark for India welfare-scheme document reasoning + a multi-agent audit pipeline + a DBT money-trace grievance module.**

Final-year engineering project (Agentic AI / NLP / E-Governance). It ships three
deliverables:

1. **The YojanaBench dataset** — 10 high-volume welfare schemes, human-verified
   QA pairs across eligibility / entitlement / documents / appeal, plus
   counterfactual and edge cases with verdict ground truth.
2. **A reproducible multi-agent audit pipeline** — eight cooperating agents that
   take an application, retrieve the governing clauses, compute the entitlement,
   cross-check, produce a confidence-scored verdict, score themselves against the
   benchmark, and route rejected cases to the right appeal channel — **plus two
   advisory agents** that explain *how to qualify* (counterfactual) and *which
   missing document actually matters* (document-gap).
3. **A DBT grievance & money-trace module** — role-based logins (beneficiary /
   official), complaint registration for "money not received", and a **seven-agent
   pipeline that traces a Direct Benefit Transfer** from the government's sanction
   order to the beneficiary's bank account — detecting non-credit, partial credit,
   diversion to a third-party account, and **mule-account fraud rings**.

Designed to run **fully offline and at zero API cost**: every decision is made by
deterministic code; a local Ollama model is optional and only polishes wording.

> **How this differs from existing tools.** Portals like **myScheme.gov.in** (and
> its public rules API) already offer rule-based eligibility checking, and recent
> papers apply RAG/LLMs to scheme Q&A. YojanaBench's contribution is the *open,
> reproducible evaluation layer* those tools lack: tri-state `needs_info`
> verdicts, clause-cited audits, counterfactual advice, honest document-gap
> analysis, and a **public leaderboard** anyone can be scored on (see
> `NOVELTY.md`). We do **not** claim to be the first scheme finder.

---

## Score your own model (open leaderboard)

```powershell
# register the built-in pipeline
python benchmark.py --name "YojanaBench (built-in)"

# score a third-party model and add it to the leaderboard
python benchmark.py --name "MyModel" --predictions my_predictions.json
```

`my_predictions.json` = `{"items": [{"id": "YB-...", "verdict": "eligible",
"answer": "...", "entitlement_value": 200, "confidence": 0.9, "documents": []}]}`.
All models are scored with the same metrics in `backend/evaluation_agent.py`; the
ranked table is served at `GET /api/leaderboard` and shown on the dashboard.

---

## Quick start

```powershell
# from the YojanaBench folder
pip install -r requirements.txt
python run.py
```

Then open <http://127.0.0.1:8000> (the launcher opens it automatically).
Interactive API docs are at <http://127.0.0.1:8000/docs>.

Run the test suite:

```powershell
python -m pytest -q
```

---

## Project structure

```
YojanaBench/
├── backend/
│   ├── app.py                 FastAPI app + REST endpoints
│   ├── pipeline.py            Wires the 8 core + 2 advisory agents (run_case / run_benchmark)
│   ├── config.py              Paths and tunables
│   ├── condition_eval.py      Deterministic rule engine (tri-state)
│   ├── retrieval.py           Hybrid BM25 + TF-IDF retriever (pure Python)
│   ├── llm.py                 Optional local Ollama client
│   ├── ablation.py            Baselines & ablation study runner
│   ├── report.py              Accuracy-report tables (pandas) for API/CLI
│   ├── leaderboard.py         File-backed public leaderboard
│   ├── auth.py                PBKDF2 passwords + HMAC session tokens (roles)
│   ├── dbt.py                 DBT ledger + beneficiary registry loader
│   ├── complaints.py          File-backed complaint store + role scoping
│   ├── trace/                 Grievance money-trace pipeline (7 agents)
│   │   ├── intake.py              validate complaint, resolve beneficiary
│   │   ├── dbt_lookup.py          find the disbursement record (UTR / scheme)
│   │   ├── credit_check.py        did the money land in the beneficiary account?
│   │   ├── reconcile.py           sanctioned vs credited / shortfall
│   │   ├── fraud.py               diversion, mule rings, duplicate UTRs
│   │   ├── orchestrator.py        verdict + confidence + recommended action
│   │   ├── notice.py              draft escalation notice to the authority
│   │   └── pipeline.py            wires the seven agents (`trace_complaint`)
│   └── agents/
│       ├── corpus_agent.py         1) ingest PDFs/guidelines -> clause store
│       ├── intake_agent.py         2) normalise application -> CaseRecord
│       ├── rag_agent.py            3) hybrid retrieval of evidence clauses
│       ├── entitlement_agent.py    4) eligibility + deterministic benefit maths
│       ├── verification_agent.py   5) independent cross-check + doc check
│       ├── orchestrator.py         6) final verdict + confidence + gate
│       ├── evaluation_agent.py     7) EM / F1 / accuracy / error / calibration
│       ├── appeal_agent.py         8) grievance routing + draft appeal letter
│       ├── counterfactual_agent.py 9) how-to-qualify advisor (minimal changes)
│       └── document_gap_agent.py  10) which missing doc actually matters
├── frontend/                  Beautiful vanilla-JS dashboard (no build step)
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   ├── grievance.html         Beneficiary/officer grievance portal
│   └── grievance.js
├── data/                      Standalone, publishable benchmark dataset
│   ├── schemes/               10 structured SchemeSchema JSON files
│   ├── guidelines/            Rendered guideline documents (clause-tagged)
│   ├── cases/                 Sample applications for the demo (CASE-*.json)
│   ├── beneficiaries.json     Synthetic beneficiary registry (B-0001..B-0012)
│   ├── dbt/
│   │   └── transactions.json  Mock DBT transaction ledger (money-trace ground truth)
│   ├── qa/
│   │   └── qa_benchmark.json  100 QA pairs (eligibility/entitlement/documents/appeal)
│   └── meta/
│       └── leaderboard.json   Public leaderboard entries
├── scripts/                   Maintenance / dataset-build utilities
│   ├── build_guidelines.py    Renders schemes -> guideline documents
│   ├── gen_cases.py           Regenerates the synthetic demo cases
│   └── gen_qa.py              Regenerates the synthetic QA pairs
├── tests/                     pytest: rule engine, agents, pipeline, advisors, API, grievance
├── run.py                     One-command launcher
├── benchmark.py               Open evaluation harness (score + publish)
├── report.py                  Accuracy-report CLI (prints DataFrames + CSVs)
└── requirements.txt
```

---

## The agents

| # | Agent | Responsibility |
|---|-------|----------------|
| 1 | Corpus | Ingest schemes + guideline docs, clause-level chunking, build retriever & stats |
| 2 | Intake | Field extraction/validation, scheme detection, missing-document diff |
| 3 | RAG | Hybrid BM25 + TF-IDF retrieval, returns evidence clauses with citations |
| 4 | Entitlement | Evaluates eligibility clauses and computes the benefit with **code, not LLM** |
| 5 | Verification | Independent re-derivation + document completeness; flags disagreement |
| 6 | Orchestrator | Merges outputs into a Verdict; confidence; **human-approval gate** |
| 7 | Evaluation | EM, token-F1, verdict accuracy, entitlement error, document F1, calibration |
| 8 | Appeal | Maps rejected/pending verdicts to the grievance channel + drafts letter |
| 9 | Counterfactual Advisor | Minimal, *verified* profile changes that flip ineligible→eligible; flags immutable blockers |
| 10 | Document-Gap Analyzer | Ranks missing docs and states whether submitting them will change the verdict |

The **deterministic rule engine** is the key design choice: eligibility and maths
are computed in Python, so amounts cannot be hallucinated. The LLM is optional.
Agents 9–10 turn the abstract verdict into a concrete **"what do I do next?"**
answer without ever inventing eligibility.

---

## Dashboard pages

- **Dashboard** — dataset statistics, one-click full benchmark, metric cards,
  per-category accuracy chart, agent pipeline diagram, the **accuracy report**
  (overall / per-scheme / edge-vs-base / ablation tables, exportable via
  `python report.py` → `reports/*.csv`), and the **open leaderboard**.
- **Audit a Case** — dynamic application form, document checklist, verdict card
  with confidence bar, evidence citations, agent trace timeline, appeal letter,
  plus the **counterfactual advisor** ("how to qualify") and **document-gap**
  panels.
- **Benchmark** — filter and run the benchmark, metrics + per-category breakdown,
  full results table (question, reference, prediction, EM/F1).
- **Ablations** — baselines & ablation study: full pipeline vs. no-Verification
  vs. LLM-only maths vs. no-counterfactuals, with Δ-vs-full comparison and chart.
- **Schemes** — one card per scheme with eligibility, entitlement, documents and
  appeal hierarchy.
- **Appeal Routing** — grievance hierarchy per scheme.
- **Grievance & Money-Trace** (`/grievance`) — role-based login; beneficiaries file
  a "money not received" complaint and see a traced verdict, officials see all
  complaints, diversion/mule alerts, and move cases through the workflow.

---

## Grievance & DBT money-trace module

Welfare schemes disburse money by **Direct Benefit Transfer (DBT)**, but a citizen
who did not receive a payment has no way to tell *where it went*. This module
closes that loop.

**Roles & logins.** `backend/auth.py` implements stdlib-only auth: PBKDF2-HMAC-SHA256
password hashing and compact HMAC-SHA256 signed bearer tokens carrying the role and
linked beneficiary id. Two roles — `beneficiary` (files complaints, sees only their
own) and `official` (sees and acts on everything). Demo accounts are seeded into
`runtime/users.json` on first use (see `SEED_USERS`); e.g. `geeta / geeta123`
(a PMAY-G diversion victim), `ravi / ravi123`, `officer / officer123`.

**The seven money-trace agents** (`backend/trace/`, deterministic, offline):

| # | Agent | Responsibility |
|---|-------|----------------|
| 1 | Intake | Validate/normalise the complaint, resolve the beneficiary from the registry |
| 2 | DBT lookup | Find the government disbursement record by UTR or beneficiary+scheme |
| 3 | Credit check | Did the money land in the **beneficiary's own** account/name? |
| 4 | Reconcile | Sanctioned vs credited amount; shortfall / partial credit |
| 5 | Fraud | Diversion to a third party, **mule-account rings** (account shared by ≥3 beneficiaries), duplicate UTRs, entity payees |
| 6 | Orchestrator | Fuse into a verdict + confidence + recommended action |
| 7 | Grievance notice | Draft the escalation letter to the correct authority |

**Verdicts:** `received`, `not_credited`, `partial`, `diverted`, `failed`,
`multiple`, `not_found`, `needs_info`. A diverted payment to an account shared by
many beneficiaries is surfaced as a **suspected mule account**.

**Endpoints** are all behind the bearer token; see the REST API table below. Data
lives in `data/beneficiaries.json` (registry) and `data/dbt/transactions.json`
(mock ledger with credited / not-credited / partial / diverted scenarios).

```powershell
# file a complaint and auto-trace the money (as beneficiary geeta)
$tok = (Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/auth/login `
        -ContentType application/json `
        -Body '{"username":"geeta","password":"geeta123"}').token
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/complaints `
  -Headers @{ Authorization = "Bearer $tok" } -ContentType application/json `
  -Body '{"scheme_id":"PMAYG-2023","utr":"UTR2026PMAYG0001","description":"housing money missing"}'
```

---

## Dataset at a glance

| Metric | Value |
|---|---|
| Schemes | 10 (food, pensions, agriculture, scholarship, employment, health, housing) |
| Guideline documents | 10 |
| Indexed clauses / chunks | 104 |
| QA pairs | 100 |
| — eligibility | 61 |
| — entitlement | 28 |
| — documents | 6 |
| — appeal | 5 |
| Sample demo cases | 28 |
| Edge / counterfactual cases | 29 / 25 |

> Amounts and ceilings are **simplified, illustrative values** for a reproducible
> demo — see `docs/DATASET_README.md`.

---

## Benchmark results (deterministic pipeline)

| Metric | Score |
|---|---|
| Verdict accuracy (primary) | **1.00** |
| Answer accuracy (F1 ≥ 0.5) | 0.20 |
| Token-F1 | 0.26 |
| Exact Match | 0.00 |
| Entitlement error (abs) | **0.00** |
| Document F1 | **1.00** |
| Calibration (ECE) | 0.05 |
| Edge-case accuracy | 1.00 |

Strict free-text EM is low by design (explanations are verbose); the structured,
decision-relevant metrics — verdict accuracy, entitlement error, document F1 —
are what the pipeline is optimised for and where it is near-perfect.

### Ablation study (component contribution)

| Variant | Verdict accuracy | Δ vs full | Entitlement error |
|---|---|---|---|
| Full pipeline | 100.0% | 0.0 pp | 0.0 |
| No Verification | 93.9% | **−6.1 pp** | 0.0 |
| LLM-only maths | 100.0% | 0.0 pp | **1799.4** |
| No counterfactuals (base items) | 100.0% | 0.0 pp | 0.0 |

Removing Verification costs ~6 accuracy points (it catches missing-document /
disagreement cases); replacing deterministic maths with a naive estimator leaves
verdicts intact but inflates the entitlement error. See `NOVELTY.md`.

---

## REST API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Service + LLM status |
| GET | `/api/stats` | Dataset statistics |
| GET | `/api/schemes` | Scheme summaries |
| GET | `/api/schemes/{id}` | Full scheme schema |
| GET | `/api/cases` | Sample applications |
| POST | `/api/audit` | Run the pipeline for one case |
| GET | `/api/benchmark` | Raw QA benchmark (filterable) |
| POST | `/api/benchmark/run` | Score the pipeline over the benchmark |
| POST | `/api/ablation/run` | Run baselines & ablation study (component deltas) |
| GET | `/api/report` | Full accuracy report tables (overall, per-scheme, ablation) |
| GET | `/api/leaderboard` | Ranked public leaderboard entries |

### Grievance & money-trace (bearer-token protected)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/login` | Authenticate → signed bearer token + user |
| GET | `/api/auth/me` | Current user |
| POST | `/api/auth/register` | Create an account (officials need an official caller) |
| GET | `/api/beneficiaries/{id}` | Beneficiary profile + their DBT ledger (own record, or any as official) |
| GET | `/api/dbt/transactions` | Query the DBT ledger (beneficiaries scoped to self) |
| POST | `/api/trace` | Run the money-trace pipeline without filing (preview) |
| POST | `/api/complaints` | File a grievance and auto-trace it |
| GET | `/api/complaints` | List complaints (officials: all; beneficiaries: own) |
| GET | `/api/complaints/summary` | Aggregate counts (officials only) |
| GET | `/api/complaints/{id}` | Complaint detail + trace (role-scoped) |
| PATCH | `/api/complaints/{id}/status` | Move a complaint through the workflow (officials only) |

---

## Optional: local LLM (Ollama)

The pipeline never needs an LLM. To let the Orchestrator polish explanations:

```powershell
ollama serve
ollama pull llama3
```

Set `YOJANA_OLLAMA_MODEL` / `YOJANA_OLLAMA_HOST` if you use different values.
When Ollama is absent the UI shows “deterministic mode” and everything still works.

---

## Testing

```powershell
python -m pytest -q     # 103 tests: rule engine, agents, advisors, pipeline, API, grievance
```

---

## Notes & limitations

- Scheme values are illustrative; replace with ministry-notified rates for
  production use.
- The corpus uses rendered guideline documents; the Corpus agent is written to
  swap in real PDF extraction (PyMuPDF/pdfplumber) without changing the pipeline.
