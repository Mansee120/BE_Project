/* =====================================================================
   YojanaBench dashboard logic
   Vanilla JS single-page app that talks to the FastAPI backend.
   ===================================================================== */
(function () {
  "use strict";

  // ------------------------------ state ------------------------------------
  const state = {
    schemes: [],            // compact summaries
    fullSchemes: {},        // scheme_id -> full schema
    stats: null,
    cases: [],
    lastBenchmark: null,
    lastAuditPayload: null,
  };

  const AGENTS = [
    "Corpus", "Intake", "RAG", "Entitlement",
    "Verification", "Orchestrator", "Evaluation", "Appeal",
  ];

  // Sample data shown on load so the dashboard looks complete while explaining
  // the project offline. Clicking any "Run / Generate / Load" button replaces
  // this preview with live results from the backend.
  const DUMMY = {
    stats: {
      schemes: 35,
      guideline_documents: 35,
      clauses: 325,
      estimated_pages: 29.2,
      qa_pairs: 241,
      qa_edge_cases: 29,
    },
    metrics: {
      verdict_accuracy: 1.0,
      answer_accuracy: 0.20,
      token_f1: 0.26,
      exact_match: 0.0,
      entitlement_error_abs: 0.0,
      document_f1: 1.0,
      calibration_ece: 0.05,
      edge_case_accuracy: 1.0,
      base_case_accuracy: 1.0,
      count: 241,
      category_breakdown: {
        eligibility: { count: 111, verdict_accuracy: 1.0, em: 0.02, f1: 0.29 },
        entitlement: { count: 53, verdict_accuracy: 1.0, em: 0.0, f1: 0.24 },
        documents: { count: 39, verdict_accuracy: null, em: 0.0, f1: 0.31 },
        appeal: { count: 38, verdict_accuracy: null, em: 0.0, f1: 0.21 },
      },
    },
    rows: [
      { id: "YB-IGNOAPS-0001", category: "eligibility",
        question: "Is a 68-year-old BPL widow eligible for IGNOAPS?",
        reference_answer: "Eligible: age >= 60 and BPL household.",
        predicted_answer: "Eligible: age >= 60 and BPL household.",
        edge_case: "", ground_verdict: "eligible", predicted_verdict: "eligible", em: 1, f1: 0.94 },
      { id: "YB-IGNDPS-0002", category: "eligibility",
        question: "Is a person with 45% disability eligible for IGNDPS?",
        reference_answer: "Eligible: severe disability (>= 40%) and age >= 18.",
        predicted_answer: "Eligible: severe disability (>= 40%) and age >= 18.",
        edge_case: "boundary disability", ground_verdict: "eligible", predicted_verdict: "eligible", em: 1, f1: 0.88 },
      { id: "YB-PMKISAN-0003", category: "eligibility",
        question: "Is an income-tax payer farmer eligible for PM-KISAN?",
        reference_answer: "Ineligible: income-tax payers and institutional landholders are excluded.",
        predicted_answer: "Ineligible: income-tax payers and institutional landholders are excluded.",
        edge_case: "exclusion", ground_verdict: "ineligible", predicted_verdict: "ineligible", em: 1, f1: 0.9 },
      { id: "YB-PDS-0004", category: "eligibility",
        question: "Can an APL household get priority rations under NFSA?",
        reference_answer: "Ineligible: priority households must hold PHH/AAY cards.",
        predicted_answer: "Ineligible: priority households must hold PHH/AAY cards.",
        edge_case: "", ground_verdict: "ineligible", predicted_verdict: "ineligible", em: 1, f1: 0.82 },
      { id: "YB-IGNOAPS-0005", category: "eligibility",
        question: "Is a 55-year-old without disability eligible for IGNOAPS?",
        reference_answer: "Ineligible: below the age-60 threshold.",
        predicted_answer: "Ineligible: below the age-60 threshold.",
        edge_case: "near-boundary age", ground_verdict: "ineligible", predicted_verdict: "ineligible", em: 1, f1: 0.86 },
      { id: "YB-PMAYG-0006", category: "eligibility",
        question: "Is a kutcha-house rural household eligible for PMAY-G?",
        reference_answer: "Eligible: houseless or kutcha house, rural, SECC-listed.",
        predicted_answer: "Eligible: houseless or kutcha house, rural, SECC-listed.",
        edge_case: "", ground_verdict: "eligible", predicted_verdict: "eligible", em: 1, f1: 0.91 },
      { id: "YB-IGNOAPS-0007", category: "entitlement",
        question: "What monthly pension does an eligible IGNOAPS beneficiary aged 75 receive?",
        reference_answer: "Rs. 300 per month (central share), enhanced for 80+.",
        predicted_answer: "Rs. 300 per month (central share), enhanced for 80+.",
        edge_case: "", ground_verdict: "eligible", predicted_verdict: "eligible", em: 1, f1: 0.72 },
      { id: "YB-IGNWPS-0008", category: "entitlement",
        question: "What monthly pension does an eligible IGNWPS widow receive?",
        reference_answer: "Rs. 300 per month (central share).",
        predicted_answer: "Rs. 300 per month (central share).",
        edge_case: "", ground_verdict: "eligible", predicted_verdict: "eligible", em: 1, f1: 0.75 },
      { id: "YB-MGNREGA-0009", category: "entitlement",
        question: "How many days of guaranteed wage employment does MGNREGA provide?",
        reference_answer: "100 days per household per financial year.",
        predicted_answer: "100 days per household per financial year.",
        edge_case: "", ground_verdict: "eligible", predicted_verdict: "eligible", em: 1, f1: 0.8 },
      { id: "YB-NSP-0010", category: "entitlement",
        question: "What is the pre-matric scholarship entitlement for a class 9 hosteller?",
        reference_answer: "Monthly maintenance allowance plus books/ad-hoc grant per guidelines.",
        predicted_answer: "Monthly maintenance allowance plus books/ad-hoc grant per guidelines.",
        edge_case: "", ground_verdict: "eligible", predicted_verdict: "eligible", em: 0, f1: 0.68 },
      { id: "YB-IGNDPS-0011", category: "documents",
        question: "Which document is mandatory to claim IGNDPS?",
        reference_answer: "Disability certificate of at least 40 percent.",
        predicted_answer: "Disability certificate of at least 40 percent.",
        edge_case: "", ground_verdict: "needs_info", predicted_verdict: "needs_info", em: 1, f1: 0.77 },
      { id: "YB-PMAYG-0012", category: "documents",
        question: "What proof is required to establish a PMAY-G applicant is houseless?",
        reference_answer: "SECC/housing deprivation proof and Aadhaar.",
        predicted_answer: "SECC/housing deprivation proof and Aadhaar.",
        edge_case: "missing doc", ground_verdict: "needs_info", predicted_verdict: "needs_info", em: 1, f1: 0.7 },
      { id: "YB-PDS-0013", category: "appeal",
        question: "How does a rejected NFSA applicant appeal?",
        reference_answer: "Approach the District Grievance Redressal Officer within 30 days.",
        predicted_answer: "Approach the District Grievance Redressal Officer within 30 days.",
        edge_case: "", ground_verdict: "ineligible", predicted_verdict: "ineligible", em: 0, f1: 0.61 },
      { id: "YB-PMJAY-0014", category: "appeal",
        question: "Where does a PM-JAY rejection get escalated?",
        reference_answer: "State Health Agency grievance cell, then Ayushman Bharat helpline.",
        predicted_answer: "State Health Agency grievance cell, then Ayushman Bharat helpline.",
        edge_case: "", ground_verdict: "ineligible", predicted_verdict: "ineligible", em: 0, f1: 0.64 },
    ],
    report: {
      overall_metrics: [
        { metric: "Items scored", value: 100 },
        { metric: "Verdict accuracy (primary)", value: 1.0 },
        { metric: "Answer accuracy (F1 >= 0.5)", value: 0.2 },
        { metric: "Token F1", value: 0.26 },
        { metric: "Exact Match", value: 0.0 },
        { metric: "Entitlement error (abs)", value: 0.0 },
        { metric: "Entitlement error (rel)", value: 0.0 },
        { metric: "Document F1", value: 1.0 },
        { metric: "Calibration ECE", value: 0.05 },
        { metric: "Edge-case accuracy", value: 1.0 },
        { metric: "Base-case accuracy", value: 1.0 },
      ],
      per_scheme_accuracy: [
        { scheme_id: "IGNOAPS-2023", items: 12, verdict_accuracy: 1.0, mean_token_f1: 0.29, mean_confidence: 0.92 },
        { scheme_id: "IGNDPS-2023", items: 11, verdict_accuracy: 1.0, mean_token_f1: 0.27, mean_confidence: 0.9 },
        { scheme_id: "IGNWPS-2023", items: 10, verdict_accuracy: 1.0, mean_token_f1: 0.28, mean_confidence: 0.91 },
        { scheme_id: "MGNREGA-2023", items: 9, verdict_accuracy: 1.0, mean_token_f1: 0.26, mean_confidence: 0.89 },
        { scheme_id: "NSP-PREMATRIC-2023", items: 11, verdict_accuracy: 1.0, mean_token_f1: 0.24, mean_confidence: 0.88 },
        { scheme_id: "PDS-NFSA-2023", items: 10, verdict_accuracy: 1.0, mean_token_f1: 0.25, mean_confidence: 0.9 },
        { scheme_id: "PMAYG-2023", items: 10, verdict_accuracy: 1.0, mean_token_f1: 0.27, mean_confidence: 0.89 },
        { scheme_id: "PMJAY-2023", items: 9, verdict_accuracy: 1.0, mean_token_f1: 0.23, mean_confidence: 0.87 },
        { scheme_id: "PMKISAN-2023", items: 10, verdict_accuracy: 1.0, mean_token_f1: 0.26, mean_confidence: 0.9 },
        { scheme_id: "PMS-SC-2023", items: 8, verdict_accuracy: 1.0, mean_token_f1: 0.28, mean_confidence: 0.91 },
      ],
      edge_vs_base: [
        { group: "edge_case", items: 54, verdict_accuracy: 1.0, mean_token_f1: 0.25 },
        { group: "base", items: 46, verdict_accuracy: 1.0, mean_token_f1: 0.27 },
      ],
      ablation_comparison: [
        { variant: "full", count: 100, verdict_accuracy: 1.0, verdict_accuracy_delta: 0.0, entitlement_error_abs: 0.0, token_f1: 0.26 },
        { variant: "no_verification", count: 100, verdict_accuracy: 0.939, verdict_accuracy_delta: -6.1, entitlement_error_abs: 0.0, token_f1: 0.25 },
        { variant: "llm_math", count: 100, verdict_accuracy: 1.0, verdict_accuracy_delta: 0.0, entitlement_error_abs: 1799.4, token_f1: 0.26 },
        { variant: "no_counterfactuals", count: 46, verdict_accuracy: 1.0, verdict_accuracy_delta: 0.0, entitlement_error_abs: 0.0, token_f1: 0.27 },
      ],
    },
    leaderboard: {
      entries: [
        { name: "YojanaBench (built-in)", note: "built-in deterministic pipeline", date: "2026-10-10",
          metrics: { verdict_accuracy: 1.0, answer_accuracy: 0.1964, token_f1: 0.2634, entitlement_error_abs: 0.0, document_f1: 1.0, calibration_ece: 0.0463 } },
        { name: "Baseline: always eligible", note: "trivial baseline", date: "2026-10-10",
          metrics: { verdict_accuracy: 0.6122, answer_accuracy: 0.0, token_f1: 0.0, entitlement_error_abs: null, document_f1: 0.0, calibration_ece: 0.0 } },
        { name: "Baseline: always ineligible", note: "trivial baseline", date: "2026-10-10",
          metrics: { verdict_accuracy: 0.3265, answer_accuracy: 0.0, token_f1: 0.0, entitlement_error_abs: null, document_f1: 0.0, calibration_ece: 0.0 } },
      ],
    },
    ablation: {
      comparison: [
        { variant: "full", label: "Full pipeline (all agents)", count: 100, verdict_accuracy: 1.0, verdict_accuracy_delta: 0.0, entitlement_error_abs: 0.0, token_f1: 0.26, calibration_ece: 0.046 },
        { variant: "no_verification", label: "Ablation: no Verification", count: 100, verdict_accuracy: 0.939, verdict_accuracy_delta: -6.1, entitlement_error_abs: 0.0, token_f1: 0.25, calibration_ece: 0.061 },
        { variant: "llm_math", label: "Ablation: LLM-only maths", count: 100, verdict_accuracy: 1.0, verdict_accuracy_delta: 0.0, entitlement_error_abs: 1799.4, token_f1: 0.26, calibration_ece: 0.052 },
        { variant: "no_counterfactuals", label: "Ablation: no counterfactuals", count: 46, verdict_accuracy: 1.0, verdict_accuracy_delta: 0.0, entitlement_error_abs: 0.0, token_f1: 0.27, calibration_ece: 0.043 },
      ],
    },
    audit: {
      case: { case_id: "CASE-0008", scheme_id: "PMAYG-2023",
              scheme_name: "Pradhan Mantri Awaas Yojana - Gramin" },
      verdict: {
        decision: "needs_info",
        human_approval_required: true,
        confidence: 0.62,
        agents_agree: true,
        explanation: "The applicant satisfies the rural and housing-deprivation clauses, but the audit cannot be completed: two mandatory documents are missing. The Verification agent disagreed with a full clearance, so the Orchestrator raised the human-approval gate and returned NEEDS_INFO.",
        computed_entitlement: 120000,
        entitlement_unit: "Rs.",
        entitlement_formula: "unit assistance = Rs. 120000 per eligible household",
        missing_documents: ["MGNREGA Job Card", "Bank account details"],
        evidence_clause_ids: ["PMAYG-EL-01", "PMAYG-EL-02", "PMAYG-DOC-01"],
      },
      evidence: [
        { doc_id: "PMAYG-EL-01", type: "eligibility", text: "PMAYG-EL-01 - Applicant must be a rural household listed under SECC deprived categories." },
        { doc_id: "PMAYG-EL-02", type: "eligibility", text: "PMAYG-EL-02 - Household must be houseless or living in a kutcha house." },
        { doc_id: "PMAYG-ENT-01", type: "entitlement", text: "PMAYG-ENT-01 - Unit assistance of Rs. 120000 payable in instalments." },
        { doc_id: "PMAYG-DOC-01", type: "documents", text: "PMAYG-DOC-01 - MGNREGA job card and bank account details are mandatory." },
      ],
      trace: [
        { agent: "IntakeAgent", detail: "Normalised 8 fields; 2 missing documents", ms: 1.4 },
        { agent: "RAGAgent", detail: "Retrieved 4 evidence clauses", ms: 2.1 },
        { agent: "EntitlementAgent", detail: "Eligibility=needs_info; entitlement=120000", ms: 0.9 },
        { agent: "VerificationAgent", detail: "cross_check=agree; missing_docs=2", ms: 1.1 },
        { agent: "Orchestrator", detail: "Decision=needs_info; confidence=0.62", ms: 0.8 },
        { agent: "AppealAgent", detail: "File the first appeal with the Block Development Officer within 30 days.", ms: 0.6 },
        { agent: "CounterfactualAgent", detail: "Provide these details to reach a decision: SECC listing.", ms: 1.3 },
        { agent: "DocumentGapAgent", detail: "gap=True; verdict_with_docs=eligible", ms: 0.7 },
        { agent: "NotificationAgent", detail: "needs_info; recipient=ramesh@example.in; actionable=True", ms: 0.5 },
      ],
      appeal: {
        applicable: true,
        next_step: "File the first appeal with the Block Development Officer within 30 days.",
        draft_letter: "To,\nThe Block Development Officer,\nPMAY-G Block Office\n\nSubject: Appeal against the NEEDS_INFO decision on application CASE-0008\n\nRespected Sir/Madam,\n\nMy application under Pradhan Mantri Awaas Yojana - Gramin was returned as NEEDS_INFO. I have since arranged the pending documents and request a re-audit. Kindly consider my case at the earliest.\n\nYours faithfully,\nApplicant",
      },
      counterfactual: {
        current_decision: "needs_info",
        feasible: true,
        suggestions: [
          { action: "provide a value for SECC listing", clause_id: "PMAYG-EL-02",
            text: "Household must be houseless or living in a kutcha house.",
            changeable: true, alone_sufficient: true, kind: "field" },
        ],
        missing_info_fields: ["secc_listed"],
        blockers: [],
        summary: "Provide these details to reach a decision: SECC listing.",
      },
      document_gap: {
        has_gap: true,
        verdict_if_docs_complete: "eligible",
        resolution: "Submit all 2 missing mandatory document(s) to become eligible.",
        documents: [
          { name: "MGNREGA Job Card", priority: 1, remaining_after: 1, alone_unblocks: false },
          { name: "Bank account details", priority: 2, remaining_after: 1, alone_unblocks: false },
        ],
      },
      notification: {
        notice_type: "needs_info",
        language: "en",
        recipient: "ramesh@example.in",
        authority_name: "Block Development Officer",
        authority_email: "bdo@example.gov.in",
        subject: "Action needed: complete your PMAY-G application (CASE-0008)",
        body_text: "Dear applicant,\n\nYour PMAY-G application CASE-0008 could not be completed. The following mandatory documents are missing:\n  - MGNREGA Job Card\n  - Bank account details\n\nPlease submit them within 30 days so the audit can be finalised. Once complete, the case is expected to become ELIGIBLE for unit assistance of Rs. 120000.\n\nRegards,\nYojanaBench (on behalf of the Block Development Officer)",
        actionable: true,
      },
    },
  };

  // Applicant form definition (kept generic so every scheme can be audited).
  const FIELDS = [
    { key: "age", label: "Age", type: "number" },
    { key: "gender", label: "Gender", type: "select", options: ["male", "female", "other"] },
    { key: "category", label: "Social category", type: "select", options: ["General", "SC", "ST", "OBC", "EWS"] },
    { key: "annual_income", label: "Annual income (Rs.)", type: "number" },
    { key: "region", label: "Region", type: "select", options: ["rural", "urban"] },
    { key: "state", label: "State", type: "text" },
    { key: "family_size", label: "Family size", type: "number" },
    { key: "card_type", label: "Ration card type", type: "select", options: ["AAY", "PHH", "APL", "None"] },
    { key: "bpl", label: "BPL household", type: "checkbox" },
    { key: "disability_percent", label: "Disability %", type: "number" },
    { key: "is_widow", label: "Widow", type: "checkbox" },
    { key: "is_farmer", label: "Farmer", type: "checkbox" },
    { key: "is_income_tax_payer", label: "Income-tax payer", type: "checkbox" },
    { key: "is_institutional_landholder", label: "Institutional landholder", type: "checkbox" },
    { key: "house_type", label: "House type", type: "select", options: ["houseless", "kutcha", "pucca"] },
    { key: "owns_pucca_house", label: "Owns pucca house", type: "checkbox" },
    { key: "secc_listed", label: "SECC listed", type: "checkbox" },
    { key: "education_level", label: "Education level", type: "select", options: ["11", "12", "UG", "PG", "Diploma", "Professional"] },
    { key: "class_level", label: "Class level", type: "number" },
    { key: "hosteller", label: "Hosteller", type: "checkbox" },
    { key: "email", label: "Email (for notices)", type: "email" },
  ];

  // ------------------------------ tiny helpers -----------------------------
  const $ = (sel) => document.querySelector(sel);

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  async function api(path, options) {
    const resp = await fetch(path, options);
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(text || ("HTTP " + resp.status));
    }
    return resp.json();
  }

  function pct(value) {
    if (value == null) return "n/a";
    return (value * 100).toFixed(1) + "%";
  }

  // ============================== NAVIGATION ===============================
  function showPage(name) {
    document.querySelectorAll(".nav-item").forEach((b) =>
      b.classList.toggle("active", b.dataset.page === name));
    document.querySelectorAll(".page").forEach((p) =>
      p.classList.toggle("active", p.id === "page-" + name));
    const titles = {
      dashboard: ["Dashboard", "India welfare-scheme reasoning benchmark & multi-agent audit pipeline"],
      audit: ["Audit a Case", "Run the full multi-agent pipeline on one application"],
      benchmark: ["Benchmark", "Score the pipeline against human-verified ground truth"],
      ablations: ["Ablation Study", "Measure what each pipeline component contributes"],
      schemes: ["Scheme Corpus", "35 high-volume welfare schemes with structured rules"],
      appeal: ["Appeal Routing", "Grievance hierarchy and draft appeal generation"],
      notices: ["Notices", "Grounded citizen notices, inbox sync and the appeal register"],
      email: ["Email", "Compose and send emails, and configure the mailbox"],
    };
    $("#page-title").textContent = titles[name][0];
    $("#page-subtitle").textContent = titles[name][1];
  }

  // ============================== DASHBOARD ================================
  function renderStats() {
    const s = state.stats;
    if (!s) return;
    const cards = [
      [s.schemes, "Schemes in corpus"],
      [s.guideline_documents, "Guideline documents"],
      [s.clauses, "Indexed clauses / chunks"],
      [s.estimated_pages + "+", "Estimated PDF pages"],
      [s.qa_pairs, "Human-verified QA pairs"],
      [s.qa_edge_cases, "Counterfactual / edge cases"],
    ];
    $("#stat-grid").innerHTML = cards.map(([num, lbl]) =>
      `<div class="stat"><div class="num">${esc(num)}</div><div class="lbl">${esc(lbl)}</div></div>`
    ).join("");
  }

  function renderPipeline() {
    $("#pipeline-flow").innerHTML = AGENTS.map((a, i) =>
      `<span class="chip"><span class="dot"></span>${esc(a)} <span class="idx">${i + 1}/8</span></span>`
    ).join("");
  }

  function metricCard(label, value, cls) {
    return `<div class="metric"><div class="m-val ${cls || ""}">${esc(value)}</div>
      <div class="m-lbl">${esc(label)}</div></div>`;
  }

  function renderMetrics(container, m) {
    container.innerHTML = [
      metricCard("Verdict accuracy", pct(m.verdict_accuracy), "good"),
      metricCard("Answer accuracy", pct(m.answer_accuracy)),
      metricCard("Token F1", m.token_f1.toFixed(3)),
      metricCard("Exact match", m.exact_match.toFixed(3)),
      metricCard("Entitlement error", m.entitlement_error_abs == null ? "n/a" : m.entitlement_error_abs),
      metricCard("Document F1", pct(m.document_f1)),
      metricCard("Calibration (ECE)", m.calibration_ece.toFixed(3)),
      metricCard("Edge-case accuracy", pct(m.edge_case_accuracy)),
      metricCard("Base-case accuracy", pct(m.base_case_accuracy)),
      metricCard("Items scored", m.count),
    ].join("");
  }

  function renderCategoryChart(container, breakdown) {
    const entries = Object.entries(breakdown);
    container.innerHTML = entries.map(([cat, v]) => {
      const value = v.verdict_accuracy != null ? v.verdict_accuracy : v.f1;
      const w = Math.max(2, Math.round(value * 100));
      return `<div class="bar-row">
        <div class="bar-label">${esc(cat)} (${v.count})</div>
        <div class="bar-track"><div class="bar-fill" style="width:${w}%"></div></div>
        <div class="bar-val">${pct(value)}</div>
      </div>`;
    }).join("");
  }

  // Fill every dashboard page with sample data so the whole app looks complete
  // while it is being demonstrated. Any "Run / Generate / Load" button replaces
  // the preview with live backend results.
  function renderDummyStats() {
    const s = DUMMY.stats;
    const cards = [
      [s.schemes, "Schemes in corpus"],
      [s.guideline_documents, "Guideline documents"],
      [s.clauses, "Indexed clauses / chunks"],
      [s.estimated_pages + "+", "Estimated PDF pages"],
      [s.qa_pairs, "Human-verified QA pairs"],
      [s.qa_edge_cases, "Counterfactual / edge cases"],
    ];
    $("#stat-grid").innerHTML = cards.map(([num, lbl]) =>
      `<div class="stat"><div class="num">${esc(num)}</div><div class="lbl">${esc(lbl)}</div></div>`
    ).join("");
  }

  function renderDummyDashboard() {
    renderDummyStats();

    renderMetrics($("#quick-metrics"), DUMMY.metrics);
    renderCategoryChart($("#category-chart"), DUMMY.metrics.category_breakdown);
    $("#metrics-run-note").textContent = `Sample preview · ${DUMMY.metrics.count} items`;

    $("#report-body").innerHTML = renderReport(DUMMY.report);
    $("#leaderboard-body").innerHTML = renderLeaderboard(DUMMY.leaderboard.entries);

    renderMetrics($("#bench-metrics"), DUMMY.metrics);
    renderCategoryChart($("#bench-category-chart"), DUMMY.metrics.category_breakdown);
    renderBenchRows(DUMMY.rows);
    $("#bench-count").textContent = DUMMY.rows.length + " items shown";

    renderAblation(DUMMY.ablation);

    renderVerdict(DUMMY.audit);
  }

  async function runQuickBenchmark() {
    const btn = $("#btn-quick-benchmark");
    btn.disabled = true; btn.textContent = "Running…";
    try {
      const data = await api("/api/benchmark/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      renderMetrics($("#quick-metrics"), data.metrics);
      renderCategoryChart($("#category-chart"), data.metrics.category_breakdown);
      $("#metrics-run-note").textContent =
        `Scored ${data.metrics.count} items` + (data.llm_used ? " · LLM assisted" : " · deterministic agents");
      state.lastBenchmark = data;
    } catch (err) {
      $("#metrics-run-note").textContent = "Error: " + err.message;
    } finally {
      btn.disabled = false; btn.textContent = "Run full benchmark";
    }
  }

  // ============================== ACCURACY REPORT ==========================
  async function generateReport() {
    const btn = $("#btn-accuracy-report");
    const box = $("#report-body");
    btn.disabled = true; btn.textContent = "Generating…";
    box.innerHTML = `<div class="muted center">Scoring benchmark and building tables…</div>`;
    try {
      const data = await api("/api/report");
      box.innerHTML = renderReport(data);
    } catch (err) {
      box.innerHTML = `<div class="muted center">Error: ${esc(err.message)}</div>`;
    } finally {
      btn.disabled = false; btn.textContent = "Generate report";
    }
  }

  function reportTable(title, cols, rows) {
    const head = cols.map((c) => `<th>${esc(c.label)}</th>`).join("");
    const body = rows.map((r) =>
      `<tr>${cols.map((c) => `<td>${c.render ? c.render(r[c.key], r) : esc(r[c.key])}</td>`).join("")}</tr>`
    ).join("");
    return `<div class="report-block">
      <div class="report-title">${esc(title)}</div>
      <div class="table-wrap"><table class="results-table">
        <thead><tr>${head}</tr></thead><tbody>${body}</tbody>
      </table></div>
    </div>`;
  }

  const num = (v, d) => (v == null ? "n/a" : Number(v).toFixed(d == null ? 4 : d));

  function renderReport(data) {
    const overall = reportTable("Overall metrics", [
      { key: "metric", label: "Metric" },
      { key: "value", label: "Value", render: (v) => (typeof v === "number" ? num(v) : esc(v)) },
    ], data.overall_metrics);

    const perScheme = reportTable("Per-scheme accuracy", [
      { key: "scheme_id", label: "Scheme" },
      { key: "items", label: "Items" },
      { key: "verdict_accuracy", label: "Verdict acc.", render: (v) => pct(v) },
      { key: "mean_token_f1", label: "Mean token F1", render: (v) => num(v, 3) },
      { key: "mean_confidence", label: "Mean conf.", render: (v) => num(v, 3) },
    ], data.per_scheme_accuracy);

    const edge = reportTable("Edge-case vs base-case", [
      { key: "group", label: "Group" },
      { key: "items", label: "Items" },
      { key: "verdict_accuracy", label: "Verdict acc.", render: (v) => pct(v) },
      { key: "mean_token_f1", label: "Mean token F1", render: (v) => num(v, 3) },
    ], data.edge_vs_base);

    const ablation = reportTable("Ablation study", [
      { key: "variant", label: "Variant" },
      { key: "count", label: "Items" },
      { key: "verdict_accuracy", label: "Verdict acc.", render: (v) => pct(v) },
      { key: "verdict_accuracy_delta", label: "Δ vs full", render: (v) => deltaLabel(v) },
      { key: "entitlement_error_abs", label: "Ent. error", render: (v) => num(v, 2) },
      { key: "token_f1", label: "Token F1", render: (v) => num(v, 3) },
    ], data.ablation_comparison);

    return overall + perScheme + edge + ablation;
  }

  // ============================== LEADERBOARD ==============================
  async function loadLeaderboard() {
    const btn = $("#btn-leaderboard");
    const box = $("#leaderboard-body");
    btn.disabled = true; btn.textContent = "Loading…";
    box.innerHTML = `<div class="muted center">Fetching rankings…</div>`;
    try {
      const data = await api("/api/leaderboard");
      box.innerHTML = renderLeaderboard(data.entries || []);
    } catch (err) {
      box.innerHTML = `<div class="muted center">Error: ${esc(err.message)}</div>`;
    } finally {
      btn.disabled = false; btn.textContent = "Load leaderboard";
    }
  }

  function renderLeaderboard(entries) {
    if (!entries.length) return `<div class="muted center">No entries yet.</div>`;
    const rows = entries.map((e, i) => Object.assign({ rank: i + 1 }, e, e.metrics));
    return reportTable("YojanaBench leaderboard", [
      { key: "rank", label: "#", render: (v) => `<strong>${v}</strong>` },
      { key: "name", label: "Model" },
      { key: "verdict_accuracy", label: "Verdict acc.", render: (v) => pct(v) },
      { key: "answer_accuracy", label: "Answer acc.", render: (v) => pct(v) },
      { key: "token_f1", label: "Token F1", render: (v) => num(v, 3) },
      { key: "entitlement_error_abs", label: "Ent. error", render: (v) => num(v, 2) },
      { key: "document_f1", label: "Doc F1", render: (v) => num(v, 3) },
      { key: "calibration_ece", label: "ECE", render: (v) => num(v, 3) },
      { key: "note", label: "Note" },
    ], rows);
  }

  // ============================== AUDIT ====================================
  function renderApplicantFields() {
    // De-duplicate field definitions by key
    const seen = new Set();
    const html = FIELDS.filter((f) => {
      if (seen.has(f.key)) return false;
      seen.add(f.key); return true;
    }).map((f) => {
      const id = "f-" + f.key;
      if (f.type === "select") {
        return `<label class="field"><span>${esc(f.label)}</span>
          <select id="${id}"><option value=""></option>
          ${f.options.map((o) => `<option value="${esc(o)}">${esc(o)}</option>`).join("")}
          </select></label>`;
      }
      if (f.type === "checkbox") {
        return `<label class="field"><span>${esc(f.label)}</span>
          <input type="checkbox" id="${id}" /></label>`;
      }
      return `<label class="field"><span>${esc(f.label)}</span>
        <input type="${f.type}" id="${id}" /></label>`;
    }).join("");
    $("#applicant-fields").innerHTML = html;
  }

  function setField(key, value) {
    const el = $("#f-" + key);
    if (!el) return;
    if (el.type === "checkbox") el.checked = value === true || value === "true";
    else if (value != null) el.value = value;
  }

  function clearFields() {
    const seen = new Set();
    FIELDS.forEach((f) => {
      if (seen.has(f.key)) return; seen.add(f.key);
      const el = $("#f-" + f.key);
      if (!el) return;
      if (el.type === "checkbox") el.checked = false; else el.value = "";
    });
  }

  function collectApplicant() {
    const applicant = {};
    const seen = new Set();
    FIELDS.forEach((f) => {
      if (seen.has(f.key)) return; seen.add(f.key);
      const el = $("#f-" + f.key);
      if (!el) return;
      if (el.type === "checkbox") applicant[f.key] = el.checked;
      else if (el.value !== "") applicant[f.key] = el.value;
    });
    return applicant;
  }

  function renderDocChecklist(scheme) {
    const box = $("#doc-checklist");
    if (!scheme) { box.innerHTML = `<span class="muted">Select a scheme first</span>`; return; }
    box.innerHTML = scheme.required_documents.map((d) =>
      `<label><input type="checkbox" class="doc-check" value="${esc(d.name)}" checked />
        ${esc(d.name)} ${d.mandatory ? "" : "<span class='muted'>(optional)</span>"}</label>`
    ).join("");
  }

  function collectSubmittedDocs() {
    return Array.from(document.querySelectorAll(".doc-check"))
      .filter((c) => c.checked).map((c) => c.value);
  }

  function setSubmittedDocs(list) {
    const norm = (list || []).map((s) => s.toLowerCase());
    document.querySelectorAll(".doc-check").forEach((c) => {
      c.checked = norm.includes(c.value.toLowerCase());
    });
  }

  async function loadSampleCases() {
    const data = await api("/api/cases");
    state.cases = data.cases;
    $("#sample-case").innerHTML = `<option value="">— choose a demo case —</option>` +
      state.cases.map((c, i) => `<option value="${i}">${esc(c.case_id)} · ${esc(c.label)}</option>`).join("");
  }

  function applySampleCase(index) {
    const c = state.cases[index];
    if (!c) return;
    $("#audit-scheme").value = c.scheme_id;
    onSchemeChange();
    clearFields();
    Object.entries(c.applicant).forEach(([k, v]) => setField(k, v));
    setSubmittedDocs(c.submitted_documents);
  }

  function onSchemeChange() {
    const sid = $("#audit-scheme").value;
    renderDocChecklist(state.fullSchemes[sid]);
  }

  async function runAudit() {
    const schemeId = $("#audit-scheme").value;
    if (!schemeId) { alert("Please choose a scheme."); return; }
    const btn = $("#btn-audit");
    btn.disabled = true; btn.textContent = "Auditing…";
    try {
      const payload = {
        scheme_id: schemeId,
        applicant: collectApplicant(),
        submitted_documents: collectSubmittedDocs(),
        use_llm: $("#audit-use-llm").checked,
      };
      const result = await api("/api/audit", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      state.lastAuditPayload = payload;
      renderVerdict(result);
    } catch (err) {
      $("#audit-result").innerHTML = `<div class="empty-state"><div class="empty-icon">!</div>
        <p>Audit failed: ${esc(err.message)}</p></div>`;
    } finally {
      btn.disabled = false; btn.textContent = "Run audit";
    }
  }

  function confClass(c) { return c >= 0.75 ? "" : (c >= 0.55 ? "low" : "vlow"); }

  function renderVerdict(result) {
    const v = result.verdict;
    const scheme = state.fullSchemes[result.case.scheme_id] || {};
    const decision = v.decision;

    let html = `<div class="verdict-head">
      <div><div class="verdict-title">${esc(scheme.name || result.case.scheme_name)}</div>
      <span class="muted">${esc(result.case.scheme_id)} · case ${esc(result.case.case_id)}</span></div>
      <span class="badge badge-${esc(decision)}">${esc(decision.replace("_", " "))}</span>
    </div>`;

    if (v.human_approval_required) {
      html += `<div class="flag red" style="margin-top:10px">⚠ Human-approval gate: this verdict requires officer review before action.</div>`;
    }

    // Confidence
    html += `<div class="conf-wrap">
      <div class="conf-row"><span>Confidence</span><span>${(v.confidence * 100).toFixed(0)}%
        · agents ${v.agents_agree ? "agree" : "disagree"}</span></div>
      <div class="conf-track"><div class="conf-fill ${confClass(v.confidence)}" style="width:${v.confidence * 100}%"></div></div>
    </div>`;

    // Explanation
    html += `<div class="section-label">Explanation</div>
      <p style="font-size:13px;line-height:1.65;white-space:pre-wrap">${esc(v.explanation)}</p>`;

    // Entitlement
    if (v.computed_entitlement != null) {
      html += `<div class="section-label">Computed entitlement</div>
        <div class="ent-box"><div class="ent-val">${esc(v.computed_entitlement)} ${esc(v.entitlement_unit || "")}</div>
        <div class="ent-formula">${esc(v.entitlement_formula || "")}</div></div>`;
    }

    // Missing documents
    if (v.missing_documents && v.missing_documents.length) {
      html += `<div class="section-label">Missing documents (${v.missing_documents.length})</div>
        <div class="flags">${v.missing_documents.map((d) => `<div class="flag red">${esc(d)}</div>`).join("")}</div>`;
    }

    // Evidence
    html += `<div class="section-label">Evidence citations (${result.evidence.length})</div>
      <ul class="evidence-list">${result.evidence.map((e) =>
        `<li><span class="cid">${esc(e.doc_id)}</span>${esc(e.text)}
          <span class="ctype">${esc(e.type)}</span></li>`).join("")}</ul>`;

    // Agent trace
    html += `<div class="section-label">Agent trace</div><ul class="trace">
      ${result.trace.map((t) => `<li><span class="t-dot"></span>
        <div><div class="t-agent">${esc(t.agent)}</div><div class="muted">${esc(t.detail)}</div></div>
        <span class="t-ms">${t.ms} ms</span></li>`).join("")}</ul>`;

    // Appeal
    if (result.appeal && result.appeal.applicable) {
      html += `<div class="section-label">Appeal routing</div>
        <div class="appeal-box"><h5>Appeal required</h5>
        <div class="next">${esc(result.appeal.next_step)}</div>
        <pre class="letter">${esc(result.appeal.draft_letter)}</pre></div>`;
    }

    // Counterfactual advisor — "how to qualify"
    const cf = result.counterfactual;
    if (cf && cf.current_decision !== "eligible") {
      html += `<div class="section-label">Counterfactual advisor — how to qualify</div>`;
      const blocked = !cf.feasible && cf.blockers && cf.blockers.length;
      html += `<div class="flag ${blocked ? "red" : "green"}">${esc(cf.summary)}</div>`;
      const sugg = (cf.suggestions || []).filter((s) => s.kind !== "missing_info");
      if (sugg.length) {
        html += `<ul class="cf-list">` + sugg.map((s) =>
          `<li class="${s.changeable ? "" : "cf-blocked"}">
            <span class="cf-act">${esc(s.action)}</span>
            ${s.alone_sufficient ? '<span class="cf-badge ok">sufficient alone</span>' : ""}
            ${s.changeable ? "" : '<span class="cf-badge no">cannot change</span>'}
            <div class="muted">[${esc(s.clause_id)}] ${esc(s.text)}</div>
          </li>`).join("") + `</ul>`;
      }
      if ((cf.missing_info_fields || []).length) {
        html += `<div class="muted" style="margin-top:8px">Missing information:
          ${cf.missing_info_fields.map(esc).join(", ")}</div>`;
      }
    }

    // Document-gap analysis
    const dg = result.document_gap;
    if (dg && dg.has_gap) {
      const cls = dg.verdict_if_docs_complete === "eligible" ? "green" : "amber";
      html += `<div class="section-label">Document-gap analysis</div>
        <div class="flag ${cls}">${esc(dg.resolution)}</div>`;
      if (dg.documents && dg.documents.length) {
        html += `<ul class="cf-list">` + dg.documents.map((d) =>
          `<li><span class="cf-act">${esc(d.name)}</span>
            ${d.alone_unblocks
              ? '<span class="cf-badge ok">final gap</span>'
              : `<span class="cf-badge">${d.remaining_after} still missing</span>`}
          </li>`).join("") + `</ul>`;
      }
    }

    // Citizen notice (email automation layer)
    const n = result.notification;
    if (n) {
      const badgeCls = { eligible: "badge-eligible", ineligible: "badge-ineligible",
                         needs_info: "badge-needs_info" }[n.notice_type] || "badge-needs_info";
      const hasTo = !!(n.recipient && n.recipient.indexOf("@") !== -1);
      html += `<div class="section-label">Citizen notice — email automation</div>
        <div class="notice-box">
          <div class="notice-head">
            <span class="badge ${badgeCls}">${esc(String(n.notice_type).replace("_", " "))}</span>
            <span class="muted">${esc(n.language || "en")} · to: ${esc(n.recipient || "no email on file")}
              ${n.actionable ? " · actionable" : ""}</span>
          </div>
          <div class="notice-subject">${esc(n.subject)}</div>
          <pre class="letter">${esc(n.body_text)}</pre>
          <div class="notice-actions">
            <label class="switch"><input type="checkbox" id="notify-auth" ${n.authority_email ? "" : "disabled"} />
              cc authority${n.authority_name ? " (" + esc(n.authority_name) + ")" : ""}</label>
            <button class="btn btn-primary" id="btn-send-notice" ${hasTo ? "" : "disabled"}>Send notice</button>
          </div>
          <div id="notice-status" class="muted"></div>
        </div>`;
    }

    $("#audit-result").innerHTML = html;
    const sendBtn = $("#btn-send-notice");
    if (sendBtn) sendBtn.addEventListener("click", sendNotice);
  }

  async function sendNotice() {
    if (!state.lastAuditPayload) return;
    const btn = $("#btn-send-notice");
    const status = $("#notice-status");
    if (!btn || !status) return;
    btn.disabled = true; btn.textContent = "Sending…";
    try {
      const payload = Object.assign({}, state.lastAuditPayload, {
        send: true,
        notify_authority: $("#notify-auth") ? $("#notify-auth").checked : false,
      });
      const data = await api("/api/notify", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const d = data.delivery || {};
      if (d.sent) status.textContent = "Sent to " + d.to + ".";
      else if (d.outbox_path && d.error) status.textContent =
        "Live send failed (" + d.error + "). Saved to " + d.outbox_path + ".";
      else if (d.outbox_path) status.textContent =
        "Outbox (dry-run): written to " + d.outbox_path + " — set YOJANA_SMTP_* to deliver live.";
      else status.textContent = "Not sent: " + (d.error || "unknown error");
    } catch (err) {
      status.textContent = "Send failed: " + err.message;
    } finally {
      btn.disabled = false; btn.textContent = "Send notice";
    }
  }

  // ============================== NOTICES / EMAIL ==========================
  async function updateNotifyStatus() {
    try {
      const d = await api("/api/notifications/status");
      const pill = $("#notify-layer-status");
      if (!pill) return;
      const live = d.smtp === "configured";
      pill.textContent = live ? "SMTP live" : "Outbox (dry-run)";
      pill.className = "pill " + (live ? "pill-ok" : "pill-muted");
    } catch (_) { /* ignore */ }
  }

  async function updateMessageStatus() {
    try {
      const d = await api("/api/messages/status");
      const pill = $("#message-layer-status");
      if (!pill) return;
      const live = d.mode === "live";
      pill.textContent = live ? "SMS live" : "SMS outbox (dry-run)";
      pill.className = "pill " + (live ? "pill-ok" : "pill-muted");
    } catch (_) { /* ignore */ }
  }

  function onNoticeChannelChange() {
    const channel = ($("#notice-channel") || {}).value || "email";
    const emailField = $("#notice-email-field");
    const phoneField = $("#notice-phone-field");
    if (emailField) emailField.style.display = channel === "sms" ? "none" : "";
    if (phoneField) phoneField.style.display = channel === "sms" ? "" : "none";
  }

  async function sendCaseNotice() {
    const btn = $("#btn-notice-send");
    const status = $("#notice-send-status");
    if (!btn || !status) return;
    const schemeId = ($("#notice-scheme") || {}).value;
    const channel = ($("#notice-channel") || {}).value || "email";
    const name = ($("#notice-name") || {}).value.trim();
    const email = ($("#notice-email") || {}).value.trim();
    const phone = ($("#notice-phone") || {}).value.trim();
    if (!schemeId) { status.textContent = "Pick a scheme first."; return; }
    if (channel === "sms" && !phone) { status.textContent = "Enter a mobile number."; return; }
    if (channel === "email" && !email) { status.textContent = "Enter an email address."; return; }
    btn.disabled = true; btn.textContent = "Sending…";
    status.textContent = "";
    try {
      const applicant = { email: email, phone: phone };
      if (name) applicant.full_name = name;
      const data = await api("/api/notify", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scheme_id: schemeId, applicant: applicant, submitted_documents: [],
          send: true, channel: channel, to: email, phone: phone, case_id: null,
          notify_authority: $("#notice-notify-auth") ? $("#notice-notify-auth").checked : false,
        }),
      });
      const d = data.delivery || {};
      const to = channel === "sms" ? phone : email;
      if (d.sent) status.textContent = "Sent to " + to + " via " + channel + ".";
      else if (d.outbox_path && d.error) status.textContent =
        "Live send failed (" + d.error + "). Saved to " + d.outbox_path + ".";
      else if (d.outbox_path) status.textContent =
        channel + " outbox (dry-run): " + d.outbox_path;
      else status.textContent = "Not sent: " + (d.error || "unknown error");
    } catch (err) {
      status.textContent = "Send failed: " + err.message;
    } finally {
      btn.disabled = false; btn.textContent = "Send notice";
    }
  }

  async function loadAppealRegister() {
    const body = $("#appeal-rows");
    if (!body) return;
    try {
      const d = await api("/api/appeals");
      const rows = d.appeals || [];
      body.innerHTML = rows.length ? rows.map((a) => `<tr>
        <td><strong>${esc(a.case_id)}</strong></td>
        <td>${esc(a.attempt)}</td>
        <td>L${esc(a.level)}</td>
        <td class="pred-tag pred-${esc(a.decision)}">${esc(a.decision)}</td>
        <td>${esc(String(a.date || "").replace("T", " "))}</td>
      </tr>`).join("") : `<tr><td colspan="5" class="muted center">No appeals recorded yet.</td></tr>`;
    } catch (err) {
      body.innerHTML = `<tr><td colspan="5" class="muted center">Error: ${esc(err.message)}</td></tr>`;
    }
  }

  async function loadEmailSettings() {
    try {
      const d = await api("/api/email/settings");
      const s = d.settings || {};
      $("#set-smtp-host").value = s.SMTP_HOST || "";
      $("#set-smtp-port").value = s.SMTP_PORT == null ? "" : s.SMTP_PORT;
      $("#set-smtp-user").value = s.SMTP_USER || "";
      $("#set-smtp-pass").value = s.SMTP_PASSWORD || "";
      $("#set-smtp-name").value = s.SMTP_FROM_NAME || "";
      $("#set-authority").value = s.AUTHORITY_EMAIL_DEFAULT || "";
      $("#set-smtp-ssl").checked = !!s.SMTP_USE_SSL;
      $("#set-imap-host").value = s.IMAP_HOST || "";
      $("#set-imap-port").value = s.IMAP_PORT == null ? "" : s.IMAP_PORT;
      $("#set-imap-user").value = s.IMAP_USER || "";
      $("#set-imap-pass").value = s.IMAP_PASSWORD || "";
    } catch (_) { /* ignore */ }
  }

  function collectEmailSettings() {
    const num = (sel) => { const v = $(sel).value.trim(); return v === "" ? null : Number(v); };
    return {
      SMTP_HOST: $("#set-smtp-host").value.trim(),
      SMTP_PORT: num("#set-smtp-port"),
      SMTP_USER: $("#set-smtp-user").value.trim(),
      SMTP_PASSWORD: $("#set-smtp-pass").value,
      SMTP_FROM_NAME: $("#set-smtp-name").value.trim(),
      SMTP_USE_SSL: $("#set-smtp-ssl").checked,
      AUTHORITY_EMAIL_DEFAULT: $("#set-authority").value.trim(),
      IMAP_HOST: $("#set-imap-host").value.trim(),
      IMAP_PORT: num("#set-imap-port"),
      IMAP_USER: $("#set-imap-user").value.trim(),
      IMAP_PASSWORD: $("#set-imap-pass").value,
    };
  }

  async function saveEmailSettings() {
    const btn = $("#btn-email-save");
    const note = $("#email-test-note");
    btn.disabled = true; btn.textContent = "Saving…";
    try {
      const d = await api("/api/email/settings", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectEmailSettings()),
      });
      const s = d.settings || {};
      $("#set-smtp-pass").value = s.SMTP_PASSWORD || "";
      $("#set-imap-pass").value = s.IMAP_PASSWORD || "";
      updateNotifyStatus();
      note.textContent = "Settings saved. Click “Test connection” to verify.";
    } catch (err) {
      note.textContent = "Save failed: " + err.message;
    } finally {
      btn.disabled = false; btn.textContent = "Save settings";
    }
  }

  async function testEmailConnection() {
    const btn = $("#btn-email-test");
    const pill = $("#email-test-status");
    const note = $("#email-test-note");
    btn.disabled = true; btn.textContent = "Testing…";
    try {
      const r = await api("/api/email/test", { method: "POST" });
      if (r.ok) {
        pill.textContent = "SMTP OK"; pill.className = "pill pill-ok";
        note.textContent = r.message || "Authenticated.";
      } else if (r.mode === "outbox") {
        pill.textContent = "outbox (dry-run)"; pill.className = "pill pill-muted";
        note.textContent = r.error || "";
      } else {
        pill.textContent = "failed"; pill.className = "pill pill-off";
        note.textContent = "Login failed: " + (r.error || "unknown error");
      }
    } catch (err) {
      pill.textContent = "failed"; pill.className = "pill pill-off";
      note.textContent = "Test failed: " + err.message;
    } finally {
      btn.disabled = false; btn.textContent = "Test connection";
    }
  }

  async function draftManualEmail() {
    const btn = $("#btn-mail-draft");
    const status = $("#mail-status");
    btn.disabled = true; btn.textContent = "Drafting…";
    try {
      const data = await api("/api/email/draft", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          instruction: $("#mail-instruction").value,
          recipient_name: $("#mail-name").value,
          scheme_id: $("#mail-scheme").value || null,
          tone: $("#mail-tone").value,
          language: $("#mail-lang").value,
        }),
      });
      if (!data.subject && !data.body_text) {
        status.textContent = "Write an instruction first, then generate.";
      } else {
        $("#mail-subject").value = data.subject || "";
        $("#mail-body").value = data.body_text || "";
        status.textContent = data.generated
          ? "Drafted by AI (" + (data.model || "local model") + "). Review, then send."
          : "AI offline — used a clean template. Review, then send.";
      }
    } catch (err) {
      status.textContent = "Draft failed: " + err.message;
    } finally {
      btn.disabled = false; btn.textContent = "Generate with AI";
    }
  }

  async function sendManualEmail() {
    const btn = $("#btn-mail-send");
    const status = $("#mail-status");
    const to = $("#mail-to").value.trim();
    if (!to) { status.textContent = "Enter a recipient email first."; return; }
    btn.disabled = true; btn.textContent = "Sending…";
    try {
      const data = await api("/api/email/send", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          to: to,
          subject: $("#mail-subject").value,
          body_text: $("#mail-body").value,
          scheme_id: $("#mail-scheme").value || null,
          notify_authority: $("#mail-notify-auth").checked,
        }),
      });
      const d = data.delivery || {};
      if (d.sent) status.textContent = "Sent to " + d.to + ".";
      else if (d.outbox_path && d.error) status.textContent =
        "Live send failed (" + d.error + "). Saved to " + d.outbox_path + ".";
      else if (d.outbox_path) status.textContent =
        "Outbox (dry-run): written to " + d.outbox_path + " — set YOJANA_SMTP_* to deliver live.";
      else status.textContent = "Not sent: " + (d.error || "unknown error");
    } catch (err) {
      status.textContent = "Send failed: " + err.message;
    } finally {
      btn.disabled = false; btn.textContent = "Send email";
    }
  }

  async function syncReplies() {
    const btn = $("#btn-sync-replies");
    const box = $("#replies-body");
    if (!btn || !box) return;
    btn.disabled = true; btn.textContent = "Syncing…";
    try {
      const d = await api("/api/replies/sync", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ since_hours: 72, auto_send: false }),
      });
      if (!d.replies_found) {
        box.innerHTML = `<div class="flag">No inbox replies found in the last 72h.
          (IMAP disabled — configure YOJANA_IMAP_* to read a real mailbox.)</div>`;
      } else {
        box.innerHTML = d.processed.map((p) => {
          const matched = (p.matched_documents || []).length;
          return `<div class="flag ${matched ? "green" : ""}">
            <b>${esc(p.case_id || p.from)}</b> — ${matched} document(s) matched
            ${p.new_verdict ? " · new verdict: <b>" + esc(p.new_verdict) + "</b>" : ""}
            ${p.error ? " · " + esc(p.error) : ""}</div>`;
        }).join("");
      }
    } catch (err) {
      box.innerHTML = `<div class="flag red">Sync failed: ${esc(err.message)}</div>`;
    } finally {
      btn.disabled = false; btn.textContent = "Sync inbox replies";
    }
  }

  // ============================== BENCHMARK ================================
  async function runBenchmarkPage() {
    const btn = $("#btn-run-benchmark");
    btn.disabled = true; btn.textContent = "Running…";
    try {
      const payload = {
        scheme_id: $("#bench-scheme").value || null,
        category: $("#bench-category").value || null,
        use_llm: false,
      };
      const data = await api("/api/benchmark/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      renderMetrics($("#bench-metrics"), data.metrics);
      renderCategoryChart($("#bench-category-chart"), data.metrics.category_breakdown);
      renderBenchRows(data.rows);
      $("#bench-count").textContent = data.rows.length + " items scored";
    } catch (err) {
      $("#bench-count").textContent = "Error: " + err.message;
    } finally {
      btn.disabled = false; btn.textContent = "Run benchmark";
    }
  }

  function renderBenchRows(rows) {
    $("#bench-rows").innerHTML = rows.map((r) => {
      const pv = r.predicted_verdict || "—";
      return `<tr>
        <td><strong>${esc(r.id)}</strong></td>
        <td>${esc(r.category)}</td>
        <td class="qa">
          <div>${esc(r.question)}</div>
          <div class="muted" style="margin-top:5px"><b>ref:</b> ${esc(r.reference_answer)}</div>
          <div class="muted" style="margin-top:3px"><b>pred:</b> ${esc(r.predicted_answer)}</div>
          ${r.edge_case ? `<div class="muted" style="margin-top:3px">edge: ${esc(r.edge_case)}</div>` : ""}
        </td>
        <td class="pred-tag pred-${esc(r.ground_verdict)}">${esc(r.ground_verdict || "—")}</td>
        <td class="pred-tag pred-${esc(pv)}">${esc(pv)}</td>
        <td>${r.em}</td>
        <td>${r.f1.toFixed(2)}</td>
      </tr>`;
    }).join("") || `<tr><td colspan="7" class="muted center">No items match the filters.</td></tr>`;
  }

  // ============================== ABLATIONS ================================
  async function runAblation() {
    const btn = $("#btn-run-ablation");
    btn.disabled = true; btn.textContent = "Running…";
    try {
      const data = await api("/api/ablation/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_llm: false }),
      });
      renderAblation(data);
    } catch (err) {
      $("#ablation-rows").innerHTML =
        `<tr><td colspan="7" class="muted center">Error: ${esc(err.message)}</td></tr>`;
    } finally {
      btn.disabled = false; btn.textContent = "Run ablation study";
    }
  }

  function deltaLabel(pp) {
    if (pp == null) return "—";
    const sign = pp > 0 ? "+" : "";
    const cls = pp < 0 ? "pred-ineligible" : (pp > 0 ? "pred-eligible" : "muted");
    return `<span class="${cls}">${sign}${pp.toFixed(1)} pp</span>`;
  }

  function renderAblation(data) {
    $("#ablation-rows").innerHTML = data.comparison.map((r) =>
      `<tr>
        <td><strong>${esc(r.label)}</strong></td>
        <td>${r.count}</td>
        <td>${pct(r.verdict_accuracy)}</td>
        <td>${deltaLabel(r.verdict_accuracy_delta)}</td>
        <td>${r.entitlement_error_abs == null ? "n/a" : r.entitlement_error_abs}</td>
        <td>${r.token_f1.toFixed(3)}</td>
        <td>${r.calibration_ece.toFixed(3)}</td>
      </tr>`).join("");

    // Bar chart of verdict accuracy per variant
    $("#ablation-chart").innerHTML = data.comparison.map((r) => {
      const val = r.verdict_accuracy || 0;
      const w = Math.max(2, Math.round(val * 100));
      const accent = r.variant === "full" ? "" : "accent";
      return `<div class="bar-row">
        <div class="bar-label">${esc(r.variant)}</div>
        <div class="bar-track"><div class="bar-fill ${accent}" style="width:${w}%"></div></div>
        <div class="bar-val">${pct(val)}</div>
      </div>`;
    }).join("");
  }

  // ============================== SCHEMES ==================================
  function renderSchemeGrid() {
    const grid = $("#scheme-grid");
    grid.innerHTML = state.schemes.map((s) => {
      const full = state.fullSchemes[s.scheme_id] || {};
      const elig = (full.eligibility_clauses || []).map((c) => `<li><b>${esc(c.clause_id)}</b> — ${esc(c.text)}</li>`).join("");
      const ent = (full.entitlement_rules || []).map((c) => `<li><b>${esc(c.rule_id)}</b> — ${esc(c.text)}</li>`).join("");
      const docs = (full.required_documents || []).map((d) => `<li>${esc(d.name)}${d.mandatory ? "" : " (optional)"}</li>`).join("");
      const apl = (full.appeal_hierarchy || []).map((a) => `<li>L${a.level}: ${esc(a.authority)} — ${esc(a.deadline_days)} days</li>`).join("");
      return `<div class="scheme-card">
        <div class="scheme-top">
          <span class="badge-cat">${esc(s.category)}</span>
          <h5>${esc(s.name)}</h5>
          <div class="sid">${esc(s.scheme_id)} · ${esc(s.level)} · ${esc(s.state)}</div>
        </div>
        <div class="scheme-body">
          <p>${esc(s.summary)}</p>
          <div class="scheme-facts">
            <span class="fact">${s.n_eligibility} eligibility</span>
            <span class="fact">${s.n_entitlement} entitlement</span>
            <span class="fact">${s.n_documents} documents</span>
            <span class="fact">${s.n_appeal_levels} appeal levels</span>
          </div>
          <details class="scheme-det"><summary>Eligibility criteria</summary><ul>${elig}</ul></details>
          <details class="scheme-det"><summary>Entitlement rules</summary><ul>${ent}</ul></details>
          <details class="scheme-det"><summary>Required documents</summary><ul>${docs}</ul></details>
          <details class="scheme-det"><summary>Appeal hierarchy</summary><ul>${apl}</ul></details>
        </div>
      </div>`;
    }).join("");
  }

  // ============================== APPEAL ===================================
  function renderAppealHierarchy() {
    const sid = $("#appeal-scheme").value;
    const full = state.fullSchemes[sid];
    const box = $("#appeal-hierarchy");
    if (!full) { box.innerHTML = `<span class="muted">Choose a scheme.</span>`; return; }
    box.innerHTML = full.appeal_hierarchy.map((a) =>
      `<div class="hier-step">
        <div class="hier-level">${a.level}</div>
        <div class="hier-body"><div class="auth">${esc(a.authority)}</div>
        <div class="desc">${esc(a.description)}</div></div>
        <div class="hier-days">${esc(a.deadline_days)} days</div>
      </div>`).join("");
  }

  // ============================== BOOTSTRAP ================================
  async function loadFullSchemes() {
    await Promise.all(state.schemes.map(async (s) => {
      state.fullSchemes[s.scheme_id] = await api("/api/schemes/" + s.scheme_id);
    }));
  }

  function fillSchemeSelects() {
    const options = state.schemes.map((s) =>
      `<option value="${esc(s.scheme_id)}">${esc(s.name)}</option>`).join("");
    $("#audit-scheme").innerHTML = options;
    $("#bench-scheme").innerHTML = `<option value="">All schemes</option>` + options;
    $("#appeal-scheme").innerHTML = options;
    $("#mail-scheme").innerHTML = `<option value="">No scheme</option>` + options;
    $("#notice-scheme").innerHTML = options;
  }

  async function updateLlmPill() {
    try {
      const data = await api("/api/health");
      const ok = data.llm && data.llm.available;
      const pill = $("#llm-pill");
      pill.textContent = ok ? "LLM: Ollama ready" : "LLM: offline (deterministic mode)";
      pill.className = "pill " + (ok ? "pill-ok" : "pill-off");
    } catch (_) { /* ignore */ }
  }

  async function init() {
    renderApplicantFields();
    renderPipeline();
    renderDummyDashboard();
    // navigation
    document.querySelectorAll(".nav-item").forEach((b) =>
      b.addEventListener("click", () => { if (b.dataset.page) showPage(b.dataset.page); }));
    $("#btn-refresh").addEventListener("click", () => refreshAll());
    $("#btn-quick-benchmark").addEventListener("click", runQuickBenchmark);
    $("#btn-accuracy-report").addEventListener("click", generateReport);
    $("#btn-leaderboard").addEventListener("click", loadLeaderboard);
    $("#btn-audit").addEventListener("click", runAudit);
    $("#audit-scheme").addEventListener("change", onSchemeChange);
    $("#sample-case").addEventListener("change", (e) => {
      if (e.target.value !== "") applySampleCase(Number(e.target.value));
    });
    $("#btn-run-benchmark").addEventListener("click", runBenchmarkPage);
    $("#btn-run-ablation").addEventListener("click", runAblation);
    $("#appeal-scheme").addEventListener("change", renderAppealHierarchy);
    $("#btn-sync-replies").addEventListener("click", syncReplies);
    $("#btn-load-appeals").addEventListener("click", loadAppealRegister);
    $("#notice-channel").addEventListener("change", onNoticeChannelChange);
    $("#btn-notice-send").addEventListener("click", sendCaseNotice);
    $("#btn-mail-draft").addEventListener("click", draftManualEmail);
    $("#btn-mail-send").addEventListener("click", sendManualEmail);
    $("#btn-email-save").addEventListener("click", saveEmailSettings);
    $("#btn-email-test").addEventListener("click", testEmailConnection);

    try {
      state.stats = await api("/api/stats");
      const schemeData = await api("/api/schemes");
      state.schemes = schemeData.schemes;
      renderStats();
      fillSchemeSelects();
      await loadFullSchemes();
      renderSchemeGrid();
      await loadSampleCases();
      onSchemeChange();
      renderAppealHierarchy();
      updateLlmPill();
      updateNotifyStatus();
      updateMessageStatus();
      onNoticeChannelChange();
      loadAppealRegister();
      loadEmailSettings();
    } catch (err) {
      renderDummyStats();
      $("#metrics-run-note").textContent = "Sample preview (backend offline)";
    }
  }

  async function refreshAll() {
    updateLlmPill();
    state.stats = await api("/api/stats");
    renderStats();
  }

  /* ---------------------- login gate ---------------------- */
  const TOKEN_KEY = "yb_token";
  let booted = false;

  function showGate() {
    $("#auth-gate").classList.remove("hidden");
    $("#dash-user").textContent = "Not signed in";
    $("#btn-dash-logout").style.display = "none";
  }

  function hideGate(user) {
    $("#auth-gate").classList.add("hidden");
    $("#dash-user").textContent = (user.name || user.username) + " · " + user.role;
    $("#btn-dash-logout").style.display = "block";
  }

  function initOnce() {
    if (booted) return;
    booted = true;
    init();
  }

  async function gateLogin() {
    const username = $("#gate-user").value.trim();
    const password = $("#gate-pass").value;
    $("#gate-error").textContent = "";
    if (!username || !password) {
      $("#gate-error").textContent = "Enter username and password.";
      return;
    }
    try {
      const resp = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!resp.ok) throw new Error("Invalid username or password");
      const data = await resp.json();
      localStorage.setItem(TOKEN_KEY, data.token);
      sessionStorage.setItem("yb_dash_auth", "1");
      hideGate(data.user);
      initOnce();
    } catch (err) {
      $("#gate-error").textContent = err.message;
    }
  }

  async function boot() {
    $("#gate-login").addEventListener("click", gateLogin);
    $("#gate-pass").addEventListener("keydown", (e) => { if (e.key === "Enter") gateLogin(); });
    $("#btn-dash-logout").addEventListener("click", () => {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem("yb_dash_auth");
      location.reload();
    });
    const token = localStorage.getItem(TOKEN_KEY);
    const sameTab = sessionStorage.getItem("yb_dash_auth") === "1";
    if (!token || !sameTab) { showGate(); return; }
    try {
      const resp = await fetch("/api/auth/me", { headers: { Authorization: "Bearer " + token } });
      if (!resp.ok) throw new Error("session expired");
      const user = await resp.json();
      hideGate(user);
      initOnce();
    } catch (_) {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem("yb_dash_auth");
      showGate();
    }
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
