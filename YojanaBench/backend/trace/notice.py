"""
Grievance notice agent (money-trace, Agent 7/7)
-----------------------------------------------
Drafts the escalation letter a beneficiary (or officer) can send to the bank /
scheme authority, quoting the trace evidence. Deterministic, offline, no LLM.
"""
from .. import config

# Authority + escalation channel per verdict category.
_ESCALATION = {
    "received": ("None - payment confirmed", 0),
    "not_credited": ("Scheme Nodal Officer / Bank Branch Manager", 30),
    "partial": ("Scheme Nodal Officer / Bank Branch Manager", 30),
    "diverted": ("District Grievance Cell + Bank Fraud Desk", 15),
    "failed": ("Bank Branch Manager (re-issue)", 15),
    "multiple": ("Scheme Nodal Officer", 30),
    "not_found": ("Scheme Nodal Officer", 30),
    "needs_info": ("Block Grievance Desk", 7),
}


class GrievanceNoticeAgent:
    def run(self, ctx: dict) -> dict:
        complaint = ctx["intake"]["complaint"]
        beneficiary = ctx["intake"].get("beneficiary") or {}
        finding = ctx["finding"]
        txn = ctx["lookup"].get("matched") or {}

        authority, deadline = _ESCALATION.get(finding["verdict"],
                                              ("Scheme Nodal Officer", 30))
        scheme_id = complaint.get("scheme_id", "(unspecified)")
        utr = txn.get("utr") or complaint.get("utr") or "(not available)"

        subject = f"Grievance: welfare benefit not received ({scheme_id}) - UTR {utr}"

        lines = [
            f"To: {authority}",
            f"Subject: {subject}",
            "",
            f"Name of beneficiary: {beneficiary.get('name', complaint.get('name', '(N/A)'))}",
            f"Aadhaar (last 4): {beneficiary.get('aadhaar_last4', complaint.get('aadhaar_last4', '(N/A)'))}",
            f"Bank: {beneficiary.get('bank_name', '(N/A)')}",
            f"Registered account (last 4): {finding.get('expected_account_last4') or beneficiary.get('account_last4', '(N/A)')}",
            f"Scheme: {scheme_id}",
            f"Transaction reference (UTR): {utr}",
            "",
            "FINDINGS OF THE MONEY-TRACE:",
            f"  - Verdict: {finding['verdict']} ({finding['headline']})",
            f"  - Sanctioned amount: {finding.get('sanctioned_amount')}",
            f"  - Amount credited: {finding.get('credited_amount')}",
        ]
        if finding.get("shortfall"):
            lines.append(f"  - Shortfall: {finding.get('shortfall')}")
        if finding.get("credited_to_account_last4"):
            lines.append(
                f"  - Credited to account (last 4): {finding['credited_to_account_last4']}"
                + (f" / name '{finding['credited_to_name']}'"
                   if finding.get("credited_to_name") else ""))
        if finding.get("mule_ring"):
            lines.append("  - ALERT: the receiving account is linked to multiple "
                         "beneficiaries (suspected mule account).")
        if finding.get("flags"):
            lines.append("  - Flags: " + ", ".join(sorted(set(finding["flags"]))))
        lines += [
            "",
            "REQUESTED ACTION:",
            f"  {finding['recommended_action']}",
            "",
            f"Please acknowledge within {deadline} days.",
            "",
            "Regards,",
            config.SMTP_FROM_NAME or "YojanaBench",
        ]

        return {
            "authority": authority,
            "deadline_days": deadline,
            "subject": subject,
            "body_text": "\n".join(lines),
        }
