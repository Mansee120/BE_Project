/* =====================================================================
   grievance.js — client for the YojanaBench grievance & money-trace module.
   Talks to /api/auth/*, /api/trace, /api/complaints, /api/beneficiaries/*.
   ===================================================================== */
const TOKEN_KEY = "yb_token";

const state = { token: localStorage.getItem(TOKEN_KEY) || "", user: null, schemes: [] };

/* ---------------------------- helpers ---------------------------- */
const $ = (sel) => document.querySelector(sel);

function esc(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function money(value) {
  if (value === null || value === undefined || value === "") return "—";
  return "₹" + Number(value).toLocaleString("en-IN");
}

async function api(path, { method = "GET", body = null, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && state.token) headers["Authorization"] = "Bearer " + state.token;
  const res = await fetch(path, {
    method, headers, body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch (e) { /* empty body */ }
  if (!res.ok) {
    const detail = (data && (data.detail || data.message)) || res.statusText;
    if (res.status === 401 && auth) logout();
    throw new Error(detail);
  }
  return data;
}

const VERDICT_LABEL = {
  received: "Money received", not_credited: "Not credited",
  partial: "Partial credit", diverted: "Diverted / stolen",
  failed: "Credit failed", multiple: "Multiple matches",
  not_found: "No record found", needs_info: "Needs more info",
};
const VERDICT_CLASS = {
  received: "v-received", partial: "v-partial", failed: "v-partial",
  multiple: "v-partial", not_credited: "v-missing", diverted: "v-diverted",
  not_found: "v-missing", needs_info: "v-partial",
};

function verdictBadge(v) {
  return `<span class="vbadge ${VERDICT_CLASS[v] || "v-partial"}">${esc(VERDICT_LABEL[v] || v)}</span>`;
}
function statusBadge(s) {
  return `<span class="sbadge s-${esc(s)}">${esc(s.replace(/_/g, " "))}</span>`;
}

/* ---------------------------- navigation ---------------------------- */
function setView(name) {
  document.querySelectorAll(".gview").forEach((el) => el.classList.remove("active"));
  const map = { login: "#view-login", home: "#view-home", file: "#view-file", detail: "#view-detail" };
  if (map[name]) $(map[name]).classList.add("active");
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === name);
  });
  if (name === "home") renderHome();
}

/* ---------------------------- auth ---------------------------- */
async function login() {
  $("#login-error").textContent = "";
  const username = $("#login-user").value.trim();
  const password = $("#login-pass").value;
  if (!username || !password) { $("#login-error").textContent = "Enter username and password."; return; }
  try {
    const data = await api("/api/auth/login", { method: "POST", auth: false, body: { username, password } });
    state.token = data.token; state.user = data.user;
    localStorage.setItem(TOKEN_KEY, state.token);
    await enterApp();
  } catch (err) {
    $("#login-error").textContent = err.message;
  }
}

function logout() {
  state.token = ""; state.user = null;
  localStorage.removeItem(TOKEN_KEY);
  $("#user-chip").textContent = "Not signed in";
  $("#role-pill").textContent = "Guest";
  $("#role-pill").className = "pill pill-muted";
  $("#btn-logout").style.display = "none";
  setView("login");
}

async function enterApp() {
  const u = state.user;
  $("#user-chip").textContent = `${u.name} · ${u.username}`;
  $("#role-pill").textContent = u.role === "official" ? "Officer" : "Beneficiary";
  $("#role-pill").className = "pill " + (u.role === "official" ? "pill-ok" : "pill-muted");
  $("#btn-logout").style.display = "block";
  document.querySelector('[data-view="file"]').style.display = u.role === "beneficiary" ? "" : "none";
  $("#officer-summary").style.display = u.role === "official" ? "" : "none";
  $("#list-title").textContent = u.role === "official" ? "All complaints" : "My complaints";
  setView("home");
}

async function boot() {
  loadSchemes();
  if (state.token) {
    try {
      state.user = await api("/api/auth/me");
      await enterApp();
      return;
    } catch (e) { logout(); }
  }
  setView("login");
}

/* ---------------------------- data loading ---------------------------- */
async function loadSchemes() {
  try {
    const data = await api("/api/schemes", { auth: false });
    state.schemes = data.schemes || [];
    const sel = $("#f-scheme");
    sel.innerHTML = state.schemes
      .map((s) => `<option value="${esc(s.scheme_id)}">${esc(s.name)} (${esc(s.scheme_id)})</option>`)
      .join("");
  } catch (e) { /* scheme list is best-effort */ }
}

async function renderHome() {
  if (!state.user) return;
  try {
    if (state.user.role === "official") {
      const s = await api("/api/complaints/summary");
      renderSummary(s);
    }
    const data = await api("/api/complaints");
    renderComplaints(data.complaints || []);
  } catch (err) {
    console.error(err);
  }
}

function renderSummary(s) {
  const cards = [
    { num: s.total, lbl: "Total complaints" },
    { num: s.diverted, lbl: "Suspected diversion" },
    { num: s.mule_ring, lbl: "Mule-account rings" },
    { num: (s.by_status && s.by_status.resolved) || 0, lbl: "Resolved" },
  ];
  $("#summary-cards").innerHTML = cards
    .map((c) => `<div class="stat"><div class="num">${esc(c.num)}</div><div class="lbl">${esc(c.lbl)}</div></div>`)
    .join("");
}

function renderComplaints(items) {
  const tbody = $("#complaints-table tbody");
  $("#complaints-empty").style.display = items.length ? "none" : "block";
  tbody.innerHTML = items.map((c) => {
    const f = (c.trace && c.trace.finding) || {};
    return `<tr class="clickable" data-id="${esc(c.complaint_id)}">
      <td><strong>${esc(c.complaint_id)}</strong></td>
      <td>${esc(c.beneficiary_name || "—")}</td>
      <td>${esc(c.scheme_id || "—")}</td>
      <td>${esc(c.utr || "—")}</td>
      <td>${verdictBadge(f.verdict)}</td>
      <td>${statusBadge(c.status || "filed")}</td>
      <td>${esc((c.filed_at || "").replace("T", " ").slice(0, 16))}</td>
    </tr>`;
  }).join("");
  tbody.querySelectorAll("tr.clickable").forEach((tr) => {
    tr.addEventListener("click", () => openComplaint(tr.dataset.id));
  });
}

/* ---------------------------- filing ---------------------------- */
async function fileComplaint() {
  $("#file-error").textContent = "";
  const payload = {
    scheme_id: $("#f-scheme").value,
    utr: $("#f-utr").value.trim() || null,
    beneficiary_id: $("#f-beneficiary").value.trim() || null,
    expected_amount: $("#f-amount").value ? Number($("#f-amount").value) : null,
    description: $("#f-desc").value.trim(),
  };
  if (!payload.scheme_id) { $("#file-error").textContent = "Choose a scheme."; return; }
  try {
    const record = await api("/api/complaints", { method: "POST", body: payload });
    renderTrace(record.trace, record);
  } catch (err) {
    $("#file-error").textContent = err.message;
  }
}

/* ---------------------------- trace rendering ---------------------------- */
function renderTrace(trace, record) {
  const f = (trace && trace.finding) || {};
  const matched = trace && trace.matched_transaction;
  const notice = (trace && trace.notice) || {};
  const esc_data = trace && trace.escalation;

  const facts = [
    ["Sanctioned", money(f.sanctioned_amount)],
    ["Credited", money(f.credited_amount)],
    ["Shortfall", f.shortfall ? money(f.shortfall) : "—"],
    ["Expected account", f.expected_account_last4 ? "****" + f.expected_account_last4 : "—"],
    ["Credited to account", f.credited_to_account_last4 ? "****" + f.credited_to_account_last4 : "—"],
    ["Credit holder", f.credited_to_name || "—"],
  ];

  const flags = (f.flags || []);
  const agentRows = (trace.trace || []).map((t) => `
    <tr><td><code>${esc(t.agent)}</code></td><td>${esc(t.summary)}</td>
        <td style="text-align:right">${esc(t.ms)} ms</td></tr>`).join("");

  $("#trace-result").innerHTML = `
    <div class="verdict-head ${VERDICT_CLASS[f.verdict] || ""}">
      ${verdictBadge(f.verdict)}
      <div class="verdict-text">
        <h5>${esc(f.headline || "")}</h5>
        <span class="muted-line">Confidence ${(f.confidence * 100).toFixed(0)}%${
          f.severity && f.severity !== "none" ? " · severity " + esc(f.severity) : ""}</span>
      </div>
    </div>
    ${f.mule_ring ? '<p class="alert-line">⚠ The receiving account is shared by multiple beneficiaries — suspected mule account.</p>' : ""}
    <div class="kv-grid">
      ${facts.map(([k, v]) => `<div class="kv"><span>${esc(k)}</span><strong>${esc(v)}</strong></div>`).join("")}
    </div>
    ${flags.length ? `<div class="flag-row">${flags.map((x) => `<span class="flag">${esc(x.replace(/_/g, " "))}</span>`).join("")}</div>` : ""}
    <p class="action-line"><strong>Recommended action:</strong> ${esc(f.recommended_action || "")}</p>
    ${esc_data ? `<p class="muted-line">Escalate to <strong>${esc(esc_data.authority || "")}</strong> within ${esc(esc_data.deadline_days || "—")} days.</p>` : ""}
    ${notice.body_text ? `<details class="notice-box"><summary>Draft grievance notice</summary><pre>${esc(notice.body_text)}</pre></details>` : ""}
    ${record ? `<button class="btn btn-ghost btn-block" data-open="${esc(record.complaint_id)}">Open complaint ${esc(record.complaint_id)}</button>` : ""}
    <details class="agent-box"><summary>Agent trace (${(trace.trace || []).length} agents)</summary>
      <div class="table-wrap"><table class="results-table"><tbody>${agentRows}</tbody></table></div>
    </details>`;
  const openBtn = $("#trace-result [data-open]");
  if (openBtn) openBtn.addEventListener("click", () => openComplaint(openBtn.dataset.open));
}

/* ---------------------------- complaint detail ---------------------------- */
async function openComplaint(id) {
  try {
    const c = await api("/api/complaints/" + encodeURIComponent(id));
    setView("detail");
    renderDetail(c);
  } catch (err) { alert(err.message); }
}

function renderDetail(c) {
  const f = (c.trace && c.trace.finding) || {};
  const canUpdate = state.user && state.user.role === "official";
  const history = (c.history || []).map((h) =>
    `<li><strong>${esc(h.status)}</strong> · ${esc(h.by)} · ${esc((h.at || "").replace("T", " ").slice(0, 16))}${h.note ? " — " + esc(h.note) : ""}</li>`).join("");

  $("#detail-body").innerHTML = `
    <div class="card">
      <div class="card-head">
        <h4>${esc(c.complaint_id)} ${verdictBadge(f.verdict)}</h4>
        ${statusBadge(c.status)}
      </div>
      <div class="kv-grid">
        <div class="kv"><span>Beneficiary</span><strong>${esc(c.beneficiary_name || "—")}</strong></div>
        <div class="kv"><span>Scheme</span><strong>${esc(c.scheme_id || "—")}</strong></div>
        <div class="kv"><span>UTR</span><strong>${esc(c.utr || "—")}</strong></div>
        <div class="kv"><span>Filed by</span><strong>${esc(c.filed_by || "—")}</strong></div>
      </div>
      ${c.description ? `<p class="action-line"><em>"${esc(c.description)}"</em></p>` : ""}
    </div>
    <div class="card" style="margin-top:16px">
      <div class="card-head"><h4>Money-trace</h4></div>
      <div id="detail-trace"></div>
    </div>
    <div class="card" style="margin-top:16px">
      <div class="card-head"><h4>Workflow history</h4></div>
      <ul class="history">${history}</ul>
      ${canUpdate ? `
        <div class="status-controls">
          <select id="d-status">
            ${["filed", "traced", "under_review", "resolved", "rejected"]
              .map((s) => `<option value="${s}" ${s === c.status ? "selected" : ""}>${s.replace(/_/g, " ")}</option>`).join("")}
          </select>
          <input id="d-note" type="text" placeholder="Officer note (optional)" />
          <button class="btn btn-primary" id="btn-status">Update status</button>
        </div>
        <p id="status-msg" class="form-error"></p>` : ""}
    </div>`;
  renderTraceInto("#detail-trace", c.trace);

  if (canUpdate) {
    $("#btn-status").addEventListener("click", async () => {
      $("#status-msg").textContent = "";
      try {
        const updated = await api(`/api/complaints/${encodeURIComponent(c.complaint_id)}/status`, {
          method: "PATCH",
          body: { status: $("#d-status").value, note: $("#d-note").value.trim() },
        });
        renderDetail(updated);
      } catch (err) { $("#status-msg").textContent = err.message; }
    });
  }
}

function renderTraceInto(sel, trace) {
  const f = (trace && trace.finding) || {};
  const notice = (trace && trace.notice) || {};
  const agentRows = (trace.trace || []).map((t) =>
    `<tr><td><code>${esc(t.agent)}</code></td><td>${esc(t.summary)}</td><td style="text-align:right">${esc(t.ms)} ms</td></tr>`).join("");
  const flags = f.flags || [];
  $(sel).innerHTML = `
    <div class="verdict-head ${VERDICT_CLASS[f.verdict] || ""}">
      ${verdictBadge(f.verdict)}
      <div class="verdict-text"><h5>${esc(f.headline || "")}</h5>
        <span class="muted-line">Confidence ${((f.confidence || 0) * 100).toFixed(0)}%</span></div>
    </div>
    <div class="kv-grid">
      <div class="kv"><span>Sanctioned</span><strong>${money(f.sanctioned_amount)}</strong></div>
      <div class="kv"><span>Credited</span><strong>${money(f.credited_amount)}</strong></div>
      <div class="kv"><span>Expected account</span><strong>${f.expected_account_last4 ? "****" + esc(f.expected_account_last4) : "—"}</strong></div>
      <div class="kv"><span>Credited to</span><strong>${f.credited_to_account_last4 ? "****" + esc(f.credited_to_account_last4) + (f.credited_to_name ? " (" + esc(f.credited_to_name) + ")" : "") : "—"}</strong></div>
    </div>
    ${f.mule_ring ? '<p class="alert-line">⚠ Suspected mule account — shared by multiple beneficiaries.</p>' : ""}
    ${flags.length ? `<div class="flag-row">${flags.map((x) => `<span class="flag">${esc(x.replace(/_/g, " "))}</span>`).join("")}</div>` : ""}
    <p class="action-line"><strong>Recommended action:</strong> ${esc(f.recommended_action || "")}</p>
    ${notice.body_text ? `<details class="notice-box" open><summary>Draft grievance notice</summary><pre>${esc(notice.body_text)}</pre></details>` : ""}
    <details class="agent-box"><summary>Agent trace (${(trace.trace || []).length} agents)</summary>
      <div class="table-wrap"><table class="results-table"><tbody>${agentRows}</tbody></table></div></details>`;
}

/* ---------------------------- wiring ---------------------------- */
window.addEventListener("DOMContentLoaded", () => {
  $("#btn-login").addEventListener("click", login);
  $("#login-pass").addEventListener("keydown", (e) => { if (e.key === "Enter") login(); });
  $("#btn-logout").addEventListener("click", logout);
  $("#btn-reload").addEventListener("click", renderHome);
  $("#btn-file").addEventListener("click", fileComplaint);
  $("#btn-back").addEventListener("click", () => setView("home"));
  document.querySelectorAll(".nav-item[data-view]").forEach((btn) =>
    btn.addEventListener("click", () => { if (!state.user && btn.dataset.view !== "home") { setView("login"); return; } setView(btn.dataset.view); }));
  boot();
});
