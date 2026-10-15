# YojanaBench — Novelty Map

A quick, defensible map of **what is new in this project** and **exactly where it
lives in the code**. Useful for the report / viva.

> **Positioning vs. existing tools.** Central/State portals such as
> **myScheme.gov.in** and its public rules API (`rules.myscheme.gov.in`) already
> do scheme *discovery* and a rule-based *eligibility engine*, and recent papers
> (e.g. SchemesSense, AgriGov) apply RAG/LLMs to scheme Q&A. YojanaBench does
> **not** claim to be the first scheme finder. Its contributions are the things
> those tools do **not** provide: an **open, reproducible benchmark** with
> **tri-state (needs_info) verdicts**, **clause-cited audits**, **counterfactual
> "how to qualify" advice**, **document-gap analysis that is honest about whether
> papers will even help**, and a **public leaderboard** anyone can be scored on.
> We therefore say "to our knowledge one of the first *open, auditable*
> benchmarks", not "the first".

## 1. Dataset contribution — an open India welfare-scheme reasoning benchmark

| Novel element | Where it lives |
|---|---|
| 10 structured scheme schemas (conditions + formulas) | `data/schemes/*.json` |
| Guideline documents with clause IDs | `data/guidelines/*.txt`, built by `scripts/build_guidelines.py` |
| 241 QA pairs (eligibility/entitlement/documents/appeal) | `data/qa/qa_benchmark.json` |
| Verdict ground truth `eligible / ineligible / needs_info` | `qa_benchmark.json` → `verdict` field |
| Counterfactuals & edge cases (boundary age/income/disability, missing docs, category swaps, overlapping schemes) | `qa_benchmark.json` → `edge_case`, `counterfactual_of` |

## 2. Methodology contributions

| Novel element | Where it lives |
|---|---|
| **Tri-state rule engine** (`True`/`False`/`Unknown`) with "unknown" as a first-class `needs_info` verdict | `backend/condition_eval.py` (`evaluate`, `evaluate_all`) |
| **Decision/maths separated from language** — benefits computed in Python, never by an LLM | `backend/agents/entitlement_agent.py` (`_compute_rule`) |
| **Independent cross-check** — second agent re-derives eligibility; disagreement ⇒ `needs_info` | `backend/agents/verification_agent.py` (`_independent_decision`) |
| **Evaluation protocol**: EM, token-F1, verdict accuracy, entitlement error, document F1, calibration (ECE) | `backend/agents/evaluation_agent.py` |
| **Counterfactual / edge vs base breakdown** | `evaluation_agent.py` → `edge_case_accuracy`, `base_case_accuracy` |
| **Open leaderboard** — third parties scored on the same items/metrics | `backend/leaderboard.py`, `benchmark.py`, `GET /api/leaderboard` |

## 3. Systems contributions

| Novel element | Where it lives |
|---|---|
| **Clause-level hybrid retrieval** (BM25 + TF-IDF) preserving rule integrity | `backend/retrieval.py` |
| **Grounded verdicts** — every verdict cites `evidence_clause_ids` | `backend/agents/orchestrator.py`, `rag_agent.py` |
| **Confidence-gated human-approval loop** | `orchestrator.py` (`human_approval_required`) |
| **Counterfactual Eligibility Advisor** — minimal profile changes that flip ineligible→eligible, with verified "sufficient alone" flags and honest immutable blockers | `backend/agents/counterfactual_agent.py` |
| **Document-Gap Analyzer** — ranks missing docs *and* states whether submitting them will actually change the verdict | `backend/agents/document_gap_agent.py` |
| **Appeal generation** from the scheme's grievance hierarchy | `backend/agents/appeal_agent.py` |
| **Fully offline, zero-cost reproducibility** (Ollama optional) | `backend/llm.py`, fallback in `orchestrator.py` |
| **Baselines & ablation study** with measured component contribution | `backend/ablation.py` |
| **Open evaluation harness + public leaderboard** | `benchmark.py`, `backend/leaderboard.py` |
| **DBT money-trace grievance pipeline** — trace a welfare payment from the government sanction order to the citizen's bank account (credited / not-credited / partial / diverted), with **mule-account fraud-ring detection** | `backend/trace/` |
| **Role-based portal** — separate beneficiary / official logins with stdlib-only PBKDF2 + signed-token auth and per-role complaint scoping | `backend/auth.py`, `backend/complaints.py` |

### 3a. DBT money-trace — the "where did my money go?" contribution

Existing scheme tools stop at *"are you eligible?"*. YojanaBench additionally
answers the **post-disbursement** question a citizen actually asks: *"the
government says it paid me — where is the money?"*

| Novel element | Where it lives |
|---|---|
| **Seven-agent DBT trace** (intake → lookup → credit-check → reconcile → fraud → verdict → notice) | `backend/trace/` |
| **Credit-reaches-beneficiary check** against the registered account/name | `backend/trace/credit_check.py` |
| **Mule-account ring detection** — one receiving account shared by ≥3 beneficiaries is flagged as organised siphoning | `backend/trace/fraud.py` |
| **Grounded verdicts** (`received` / `not_credited` / `partial` / `diverted` / `failed` / `multiple` / `not_found` / `needs_info`) with confidence & recommended action | `backend/trace/orchestrator.py` |
| **Auto-drafted escalation notice** routed to the right authority with a deadline | `backend/trace/notice.py` |
| **Mock-but-realistic DBT ledger** with diversion scenarios as ground truth | `data/dbt/transactions.json`, `data/beneficiaries.json` |

## 4. Measured component contribution (ablation study)

Run on the 56-item benchmark via `POST /api/ablation/run`:

| Variant | Verdict accuracy | Δ vs full | Entitlement error |
|---|---|---|---|
| Full pipeline | 100.0% | 0.0 pp | 0.0 |
| No Verification | 93.9% | **−6.1 pp** | 0.0 |
| LLM-only maths | 100.0% | 0.0 pp | **1799.4** |
| No counterfactuals (base items) | 100.0% | 0.0 pp | 0.0 |

**Interpretation**
- Removing **Verification** costs ~6 accuracy points — it is what catches
  missing-document and disagreement cases.
- Replacing deterministic maths with a naive "LLM-style" estimator leaves the
  verdicts intact but blows up the **entitlement error** — proving the value of
  computing benefits in code.

## 5. What is *reused* (not claimed as novel)

FastAPI, Uvicorn, Pydantic, Ollama, pytest, BM25/TF-IDF algorithms, HTML/CSS/JS.
The novelty is in the **dataset**, the **audit methodology/design**, and the
**integrated reproducible system** — not in the supporting libraries.
