"""
appeal_agent.py  (Agent 8/8)
----------------------------
For any rejected (ineligible) or pending (needs_info) verdict, determines the
correct appeal channel from the scheme's appeal hierarchy and drafts an appeal
letter for human review.
"""
import datetime


class AppealAgent:
    def __init__(self, corpus):
        self.corpus = corpus

    def _draft_letter(self, case, verdict, first_channel):
        scheme = self.corpus.get_scheme(case["scheme_id"])
        today = datetime.date.today().isoformat()
        lines = [
            "To,",
            f"The {first_channel['authority']},",
            f"Subject: Appeal against decision under {scheme['name']} "
            f"(Scheme ID: {scheme['scheme_id']})",
            "",
            f"Date: {today}",
            "",
            f"Respected Sir/Madam,",
            "",
            f"I, the applicant (case reference {case.get('case_id', 'N/A')}), wish to "
            f"file an appeal against the decision of the auditing authority, which "
            f"returned a verdict of '{verdict['decision'].upper()}'.",
            "",
            f"Reason recorded: {verdict['explanation'].splitlines()[0]}",
            f"Applicant details: {case.get('applicant')}",
            "",
            f"I request a review of my application as per the grievance redressal "
            f"mechanism of the scheme. Kindly consider the appeal within "
            f"{first_channel['deadline_days']} days of receipt.",
            "",
            "Yours faithfully,",
            "(Applicant name / signature)",
        ]
        return "\n".join(lines)

    def run(self, case: dict, verdict: dict) -> dict:
        if verdict["decision"] == "eligible":
            return {"applicable": False, "reason": "Verdict is eligible; no appeal needed."}

        scheme = self.corpus.get_scheme(case["scheme_id"])
        hierarchy = scheme["appeal_hierarchy"]
        first = hierarchy[0]

        return {
            "applicable": True,
            "channel": first["authority"],
            "deadline_days": first["deadline_days"],
            "hierarchy": [
                {"level": a["level"], "authority": a["authority"],
                 "deadline_days": a["deadline_days"], "description": a["description"]}
                for a in hierarchy
            ],
            "next_step": (f"File the first appeal with {first['authority']} within "
                          f"{first['deadline_days']} days."),
            "draft_letter": self._draft_letter(case, verdict, first),
        }
