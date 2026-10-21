# Literature Review

**Project:** YojanaBench — Open Benchmark for India Welfare-Scheme Document
Reasoning, Multi-Agent Audit Pipeline and DBT Money-Trace Grievance Module

This review surveys the published work related to this project, grouped into
four themes, identifies the **research gaps** each work leaves open, and maps
those gaps to what this project contributes. Every reference listed here was
checked against its original source (paper page, journal site, arXiv or
Government of India press release).

---

## 1. Scope and Method of the Survey

The literature was collected under four search themes:

| Theme | Question being asked | Papers |
|---|---|---|
| A. AI benchmarks | Do existing benchmarks test *this kind* of task? | GAIA, DocVQA, LawBench, LegalBench |
| B. Core methods | What techniques does the project build upon? | RAG survey, LLM multi-agent survey |
| C. AI for welfare schemes | What already exists for Indian scheme access? | Vaishnav & Nathan, myScheme study, hybrid-RAG chatbots, AgriGov, PM-KISAN chatbot |
| D. DBT, leakage & fraud | What exists for tracing money and catching fraud? | DBT impact studies, AI-for-DBT-integrity, RBI MuleHunter.AI, mule-detection research |

**Inclusion criteria:** papers/directly relevant systems that either
(1) define a benchmark or evaluation method, (2) provide a technique used by
this project, or (3) solve a part of the same real-world problem (scheme
discovery, eligibility, DBT leakage).

---

## 2. Theme A — General-Purpose and Domain AI Benchmarks

### 2.1 GAIA: A Benchmark for General AI Assistants
**Mialon et al., 2023** [1]

GAIA is a benchmark of 466 real-world questions testing reasoning,
multimodality and tool use in general-purpose assistants. It is an important
reference point because it shows how a *benchmark* should be built: real
questions, exact ground-truth answers, and reproducible scoring.

**Relevance to this project:** GAIA demonstrated that honest evaluation needs
an answer key that a human verified — the same principle YojanaBench applies,
but to a completely different task class.

**Limitation:** GAIA is general-purpose and English-only. It has no domain
documents, no eligibility or entitlement reasoning, no verdict ground truth
(`eligible / ineligible / needs_info`), and nothing India-specific. A welfare
scheme cannot be evaluated by a general assistant benchmark.

### 2.2 DocVQA: A Dataset for VQA on Document Images
**Mathew, Karatzas, Jawahar, 2021** [2]

DocVQA contains 50,000 extractive question-answering pairs over 12,000+
document images. It is the standard reference for "questions answered from
documents".

**Relevance:** YojanaBench's QA pairs over scheme guideline documents belong to
the same *document-QA* family, so DocVQA defines the evaluation vocabulary
(exact match, F1) that YojanaBench reuses.

**Limitation:** DocVQA answers are **span extractions** — copy the text from
the page. It has no eligibility verdicts, no numerical entitlement
computation, no counterfactual (boundary) scenarios, and no clause-level
evidence labels. Knowing *what the document says* is not the same as deciding
*whether a person qualifies*.

### 2.3 LawBench: Benchmarking Legal Knowledge of LLMs
**Fei et al., 2024** [3]

LawBench evaluates 20 Chinese legal tasks across three cognitive levels
(memorisation, understanding, application) — one of the first domain-specific
legal benchmarks for LLMs.

**Relevance:** it provides a template for organising a domain benchmark by
*cognitive difficulty*, which YojanaBench follows with its
base-case vs edge-case (counterfactual) split.

**Limitation:** it is confined to Chinese law. It contains no welfare-scheme
documents, no benefit-amount computation, no counterfactual eligibility
scenarios, and evaluates single-model prompting rather than a multi-agent
audit pipeline.

### 2.4 LegalBench: A Collaboratively Built Benchmark for Legal Reasoning
**Guha et al., 2024** [4]

LegalBench is a collaboratively built set of 162 tasks measuring US legal
reasoning (issue spotting, rule application, reasoning over contracts and
case law).

**Relevance:** it shows how a large community can build many small, focused
tasks with clear labels — the model YojanaBench uses for its QA categories
(eligibility / entitlement / documents / appeal).

**Limitation:** it is US case law and contracts. It does not address
government benefit rules, document-compliance checklists, or numeric
entitlement calculation — the everyday "bureaucratic" law that citizens
actually face.

**Theme A conclusion:** benchmarks exist for *general questions*, *document
extraction*, and *legal reasoning* — but none of them measures
**scheme-eligibility decisions with computed benefits and tri-state verdicts**
on Indian welfare documents. That is the first gap.

---

## 3. Theme B — Core Techniques: RAG and Multi-Agent LLM Systems

### 3.1 Retrieval-Augmented Generation for Large Language Models: A Survey
**Gao et al., 2023** [5]

This survey organises RAG into *naive*, *advanced* and *modular* paradigms and
reviews how retrieved evidence improves factuality. It is the standard
citation for why an LLM should read the rulebook before answering.

**Relevance:** YojanaBench's RAG agent follows the survey's guidance — retrieve
first, then generate — and additionally combines **lexical (BM25) and semantic
(TF-IDF) retrieval** in the "hybrid" style the survey describes. Clause IDs
returned with every snippet give the provenance the survey calls for.

**Limitation:** the survey offers no *domain benchmark* for governance
documents, and its evaluation ideas (answer similarity) lack the
**verdict-level** and **computation-level** metrics needed for high-stakes
compliance decisions — you cannot score an eligibility decision with string
similarity alone.

### 3.2 Large Language Model based Multi-Agents: A Survey of Progress and
Challenges
**Guo et al., 2024** [6]

The survey systematically reviews LLM multi-agent designs: how agents are
profiled, how they communicate, and how capabilities are acquired.

**Relevance:** it justifies the architecture used here — specialised agents
with single responsibilities and an orchestrator that merges their outputs.
YojanaBench's 11-agent audit pipeline and 7-agent money-trace pipeline are a
concrete instance of the patterns this survey describes.

**Limitation:** the survey lists **no welfare-governance application** and no
verified benchmark on which an audit-style agent pipeline can be scored
against ground truth. Multi-agent systems are proposed faster than they are
*measured*.

**Theme B conclusion:** the *methods* (RAG, multi-agent orchestration) are
mature; the *evaluation of those methods on governance tasks* is missing. That
is the second gap.

---

## 4. Theme C — Existing Work on Indian Welfare-Scheme Access

### 4.1 Need of RAG for Conversational Assistants for Government Social Welfare
Scheme Popularization
**Vaishnav & Nathan, 2024** [7]

The authors built a RAG chatbot over 2,980 scraped government schemes and
measured response similarity, uncertainty and hallucination. They show that
retrieval-augmented generation **substantially reduces hallucination** compared
with a bare LLM, and that larger models perform better.

**Relevance:** this is the closest prior work to the retrieval side of
YojanaBench, and its findings directly motivate grounding every answer in
official scheme text.

**Limitation:** it has **no human-verified QA ground truth**, no eligibility
verdict labels, no entitlement computation checks, and no counterfactual or
edge-case evaluation. It measures whether answers *sound* similar to expected
responses — not whether the decision is *right*.

### 4.2 First Impressions from Comparing Form-Based and Conversational
Interfaces for Public Service Access in India
**Chaitra C R et al., 2025** [8]

A usability study comparing the official **myScheme** form application with a
RAG conversational prototype ("Prabodhini") on 15 users, reporting which
interface people prefer and how fast each is.

**Relevance:** it documents the real user-facing alternative to this project —
the myScheme portal — and confirms that citizens find conversational input
easier.

**Limitation:** it evaluates **usability**, not **correctness**. Nothing in the
study checks whether the scheme information returned matches the official
guideline documents. A fast but wrong answer still scores well in a usability
test. Interface studies leave open the question: *is the answer true?*

### 4.3 AI-Driven Chatbot for Government Scheme Accessibility in India Using
Hybrid RAG with LLMs
**Vaishnavi P C & Paramarthalingam, 2024** [9]

Combines BM25 lexical retrieval with dense vector embeddings, adds
cross-encoder re-ranking and a rule-based personalisation layer (age, gender,
state) over ~3,500 schemes / ~70,000 text segments, using a locally deployed
model for controlled generation.

**Relevance:** independent confirmation that **hybrid retrieval (BM25 +
semantic)** is the right choice for scheme documents — the same combination
YojanaBench implements in pure Python. Its local-model requirement also
matches this project's offline, zero-cost design.

**Limitation:** the personalisation layer is a *filter*, not an *auditor*:
there is no tri-state verdict, no independent cross-check, no computed
entitlement value scored against ground truth, and no benchmark on which the
system's decisions can be reproduced and compared.

### 4.4 AI-Driven Welfare Scheme Recommendation Using Random Forest and RAG
**Karunamurthy & Barath, 2026** [10]

A multi-output Random Forest predicts eligibility probabilities across all
schemes; a calibrated threshold selects candidates; a RAG module then
generates explanations restricted to retrieved verified chunks — so the LLM
"cannot recommend a scheme the classifier did not flag eligible".

**Relevance:** the strongest prior art for **separating the decision from the
language**: a deterministic model decides, the LLM only explains. YojanaBench
applies the same principle — its deterministic rule engine decides, and the
optional LLM only polishes wording.

**Limitation:** evaluation is on **synthetic datasets** mimicking real records,
with no human-verified answer key, no tri-state "needs information" outcome,
no counterfactual advice, and no public leaderboard for third-party
comparison.

### 4.5 AgriGov: A Structured Multilingual Dataset Curation for Indian
Government Schemes for Farmers
**Bilal & Gopakumar, 2026** [11]

A trilingual (English–Hindi–Marathi) corpus of 50 government schemes scraped
from trusted portals, structured into semantic fields (title, eligibility,
application process, documents, exclusions), with ~2,100 human-corrected
translated segments growing to ~8,000 aligned pairs.

**Relevance:** demonstrates the value of **structured scheme schemas** — the
same idea as YojanaBench's `data/schemes/*.json`, where eligibility clauses,
entitlement formulas and document lists are explicit fields rather than free
text.

**Limitation:** AgriGov is a *dataset for translation, QA and retrieval*; it
carries no verdict ground truth, no entitlement formulas, no edge cases, and
no evaluation pipeline that scores decisions.

### 4.6 Government deployment: the PM-KISAN AI chatbot
**Government of India, Ministry of Agriculture & Farmers Welfare** [12]

The Government has launched an official AI chatbot integrated with the
PM-KISAN flagship scheme to answer beneficiary queries.

**Relevance:** shows the problem is recognised at the highest level — scheme
Q&A is now a real government service. It also raises the stakes: public-facing
scheme AI **must** be evaluated, because a wrong eligibility answer harms a
citizen.

**Limitation:** like the chatbots above, it answers questions; it publishes no
benchmark, no accuracy figures against an answer key, and no audit trail of
which rule produced which answer.

**Theme C conclusion:** existing systems focus on **finding** schemes and
**conversing** about them. None of them provides an open, reproducible
evaluation of whether the *decision* is correct, whether the *money* is right,
or what to do when the citizen fails. That is the third gap.

---

## 5. Theme D — DBT, Leakage and Mule-Account Fraud

### 5.1 Impact Assessment of the Direct Benefit Transfer Scheme in India: A
Case Study of Haryana
**IJCRT, 2023** [13]

Reports that DBT (the Jan-Dhan–Aadhaar–Mobile "JAM triangle") reduced
intermediaries: 85% of rural and 69% of urban households benefited; Haryana's
identity-linked transfers saved ₹1,200 crore by detecting fake beneficiaries;
pre-DBT, historically only about 15 paise of every rupee reached the intended
recipient.

**Relevance:** establishes the *economic importance* of the money-trace
problem this project attacks — leakage is large, measurable, and still
partially unsolved.

**Limitation:** impact studies work at the *aggregate* level (how much leakage
overall). They do not answer the individual citizen's question: *"the record
says paid — where did **my** money go?"*

### 5.2 Leveraging AI and ML to Enhance the Integrity of Social Protection and
DBT Systems
**IJCSP, 2025** [14]

Applies classification and anomaly-detection models to DBT/MGNREGS transaction
data, reporting up to ~27% reduction in false beneficiary inclusion and ~91%
accuracy in forecasting fraudulent transaction patterns.

**Relevance:** confirms that machine learning can find DBT fraud at scale, and
motivates including a fraud-detection stage in a grievance pipeline.

**Limitation:** statistical fraud models need large labelled training sets and
produce *probabilities*, not *explainable case verdicts*. A beneficiary (or an
officer) needs a concrete statement — "₹500 short, credited to account ending
4821" — with evidence, not an anomaly score.

### 5.3 RBI's MuleHunter.AI
**Reserve Bank of India / Press Information Bureau** [15]

The RBI has rolled out **MuleHunter.AI**, an AI/ML solution specifically for
**mule account detection** — accounts used to divert and layer funds in cyber
frauds — alongside revised instructions on unauthorised transactions and
expanded AI-driven fraud analytics.

**Relevance:** validates this project's design choice to treat *shared
receiving accounts* as a first-class fraud signal. YojanaBench's rule
"an account receiving benefits for ≥ 3 different beneficiaries is a mule ring"
is a transparent, explainable cousin of exactly what the RBI is automating.

**Limitation:** MuleHunter.AI is a bank-side monitoring system. It does not
connect a **welfare complaint** to the **sanction order** and the **credit
record**, nor does it explain to the citizen what happened to their money.

### 5.4 Money-Mule Detection as a Relational Learning Problem: A Study on the
RBIH NFPC Dataset
**Ahmad & Deodhar, 2026** [16]

Shows that a mule's individual transfers look ordinary — what reveals the
account is its *relationships* (shared counterparties, addresses) and its
*temporal shape* (burst in, burst out, silence). The paper argues that
production systems remain largely rule-based and that research usually
classifies transactions instead of accounts.

**Relevance:** provides the theoretical backing for account-level reasoning in
the fraud agent: YojanaBench looks at the *account's* history across
beneficiaries rather than judging one payment in isolation.

**Limitation:** it is a machine-learning study on internal banking data — not a
public, reproducible system, and not aimed at grievance redressal for welfare
beneficiaries.

**Theme D conclusion:** fraud research is bank-centred and aggregate; grievance
systems are form-centred and stop at "complaint registered". Nothing joins
them into an **auditable, citizen-facing money trace** with an explainable
verdict and a routed escalation notice. That is the fourth gap.

---

## 6. Comparative Summary of Related Work

| Work | Year | Task | Verdict ground truth | Entitlement maths | Counterfactual / edge cases | Human-verified QA | Public leaderboard | Post-disbursement trace |
|---|---|---|---|---|---|---|---|---|
| GAIA [1] | 2023 | General QA | — | — | — | ✓ | — | — |
| DocVQA [2] | 2021 | Document span QA | — | — | — | ✓ | — | — |
| LawBench [3] | 2024 | Chinese legal tasks | — | — | — | ✓ | — | — |
| LegalBench [4] | 2024 | US legal reasoning | — | — | — | ✓ | — | — |
| RAG Survey [5] | 2023 | Method survey | — | — | — | — | — | — |
| Multi-Agent Survey [6] | 2024 | Method survey | — | — | — | — | — | — |
| Vaishnav & Nathan [7] | 2024 | Scheme chatbot | — | — | — | — | — | — |
| myScheme interface study [8] | 2025 | Usability | — | — | — | — | — | — |
| Hybrid-RAG chatbot [9] | 2024 | Scheme retrieval | — | — | — | — | — | — |
| Random Forest + RAG [10] | 2026 | Recommendation | — | — | — | — | — | — |
| AgriGov [11] | 2026 | Dataset | — | — | — | — | — | — |
| DBT Haryana study [13] | 2023 | Impact | — | — | — | — | — | aggregate only |
| AI/ML for DBT integrity [14] | 2025 | Fraud ML | — | — | — | — | — | aggregate only |
| Money-mule relational ML [16] | 2026 | Fraud ML | — | — | — | — | — | account-level |
| **YojanaBench (this work)** | **2026** | **Scheme audit + money trace** | **✓ tri-state** | **✓ deterministic** | **✓** | **✓** | **✓** | **✓ 7-agent trace** |

*(✓ = provided by the work; — = not addressed)*

---

## 7. Research Gaps Identified

| Gap | Statement of the gap | Where it was observed |
|---|---|---|
| **G1 — No domain benchmark** | No benchmark scores Indian welfare-scheme reasoning with verdicts, entitlement values and cited clauses | [1][2][3][4] cover general, document, legal — not schemes |
| **G2 — Extraction ≠ decision** | Document QA extracts text; it never decides *eligibility* or handles *missing information* | [2] spans only; [7][9] answers only |
| **G3 — Evaluation without truth** | Scheme chatbots are evaluated by similarity/usability, not against a human-verified answer key | [7][8][9][10] |
| **G4 — No honesty about uncertainty** | Systems are forced-choice (Yes/No) or free-text; none emits a first-class **"needs information"** verdict with the missing fields named | [7][9][10][12] |
| **G5 — Decision/maths not separated or verified** | Where arithmetic appears (benefit amounts), it is produced by the language model or not computed at all; no independent cross-check agent | [7][9][10] |
| **G6 — No post-disbursement accountability** | Fraud/DBT work is aggregate or bank-internal; no public system traces one complaint from sanction → credit with an explainable verdict and escalation notice | [13][14][15][16] |
| **G7 — No reproducible comparison** | No one can score a third-party model on the same scheme items — there is no shared answer key or leaderboard | all of Theme C |

---

## 8. How This Project Addresses Each Gap

| Gap | YojanaBench's answer | Where in this project |
|---|---|---|
| G1 | 35 schemes, human-verified QA pairs, verdict ground truth, entitlement targets | `data/schemes/*.json`, `data/qa/qa_benchmark.json` |
| G2 | Every QA item carries a decision + computed value + cited clause IDs, not a text span | `entitlement_agent.py`, `orchestrator.py` |
| G3 | Scoring with EM, token-F1, verdict accuracy, entitlement error, document F1, ECE — all against the answer key | `evaluation_agent.py` |
| G4 | **Tri-state rule engine** (`True / False / Unknown`) → `eligible / ineligible / needs_info`, with the missing fields explicitly listed | `condition_eval.py` |
| G5 | Benefits computed in deterministic Python (never by an LLM) + an **independent Verification agent**; disagreement forces human review; ablation quantifies both | `entitlement_agent.py`, `verification_agent.py`, `ablation.py` |
| G6 | **Seven-agent DBT money trace**: sanction → ledger → credit check → reconciliation → mule-ring fraud → verdict → routed notice | `backend/trace/*` |
| G7 | Open leaderboard: anyone can score their model on the same items with the same metrics | `benchmark.py`, `leaderboard.py` |

**Beyond the gaps:** two advisory features that no surveyed work provides —
the **Counterfactual Advisor** ("the smallest change that would make you
eligible", verified by re-running the rules) and the **Document-Gap Analyzer**
("will submitting these papers even change the verdict?").

---

## 9. Conclusion

The literature shows a clear progression: from general QA benchmarks (GAIA,
DocVQA) to domain legal benchmarks (LawBench, LegalBench), from naive LLM
answers to grounded RAG, and from single models to multi-agent systems. On the
Indian welfare side, tools such as myScheme and several recent RAG chatbots
solve **discovery and conversation**, while DBT research solves **aggregate
leakage and bank-side fraud detection**.

The intersection — **an open, auditable evaluation of scheme decisions, and a
citizen-facing trace of where a specific payment went** — is empty. That
intersection is precisely where YojanaBench sits. Its claims are deliberately
narrow and defensible: not "the first scheme finder", but, to our knowledge,
one of the first **open, reproducible benchmarks** for welfare-scheme document
reasoning — with tri-state verdicts, clause-cited audits, deterministic benefit
maths, verified counterfactual advice, and a seven-agent DBT money trace.

---

## 10. References

[1] G. Mialon, C. Fourrier, C. Swift, T. Wolf, Y. LeCun and T. Scialom,
"GAIA: A Benchmark for General AI Assistants," 2023.

[2] M. Mathew, D. Karatzas and C. V. Jawahar, "DocVQA: A Dataset for VQA on
Document Images," in *Proceedings of the IEEE/CVF Winter Conference on
Applications of Computer Vision (WACV)*, 2021.

[3] Z. Fei, X. Shen, D. Zhu, et al., "LawBench: Benchmarking Legal Knowledge
of Large Language Models," 2024.

[4] N. Guha, J. Nyarko, D. E. Ho, et al., "LegalBench: A Collaboratively Built
Benchmark for Measuring Legal Reasoning in Large Language Models," 2024.

[5] Y. Gao, Y. Xiong, X. Gao, et al., "Retrieval-Augmented Generation for Large
Language Models: A Survey," 2023.

[6] T. Guo, X. Chen, Y. Wang, et al., "Large Language Model based Multi-Agents:
A Survey of Progress and Challenges," 2024.

[7] V. Vaishnav and G. O. Nathan, "Need of Retrieval Augmented Generation for
Conversational Assistants for Government Social Welfare Scheme
Popularization," *International Journal of Science and Research Archive*,
13(01), pp. 1299–1312, 2024. DOI: 10.30574/ijsra.2024.13.1.1747.

[8] C. C. R., P. Voora, B. R. Bikkina, et al., "First Impressions from
Comparing Form-Based and Conversational Interfaces for Public Service Access
in India," 2025.

[9] P. C. Vaishnavi and A. Paramarthalingam, "AI-Driven Chatbot for Government
Scheme Accessibility in India Using Hybrid Retrieval-Augmented Generation with
Large Language Models," *International Journal of Innovative Research in
Technology*, 2024.

[10] A. Karunamurthy and S. Barath, "AI-Driven Welfare Scheme Recommendation
Using Random Forest and RAG," *IJLTEMAS*, 2026.

[11] M. Bilal and G. Gopakumar, "AgriGov: A Structured Multilingual Dataset
Curation for Indian Government Schemes for Farmers," arXiv:2606.08272, 2026.

[12] Ministry of Agriculture & Farmers Welfare, Government of India, "AI
Chatbot launched for the Pradhan Mantri Kisan Samman Nidhi (PM-KISAN) Scheme,"
Press Information Bureau release, New Delhi.

[13] "Impact Assessment of the Direct Benefit Transfer Scheme in India: A Case
Study of Haryana," *IJCRT*, 2023.

[14] "Leveraging Artificial Intelligence and Machine Learning to Enhance the
Integrity and Efficiency of India's Social Protection and Direct Benefit
Transfer Systems," *IJCSP*, 2025.

[15] Reserve Bank of India, "MuleHunter.AI — AI/ML solution for mule account
detection," Press Information Bureau releases, Government of India.

[16] O. Ahmad and A. Deodhar, "Money-Mule Detection as a Relational Learning
Problem: A Study on the RBIH NFPC Dataset," arXiv:2610.21314, 2026.

---

*Note: references [1]–[8] are carried over from the project's original
literature survey table (`YojanaBench_Literature_Survey.pdf`); [9]–[16] were
added for this review and verified against the publisher's or arXiv's record.*
