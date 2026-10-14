"""
trace
=====
Multi-agent "did my welfare money actually reach me?" pipeline for the
YojanaBench grievance module.

Seven cooperating agents trace a Direct Benefit Transfer (DBT) payment from the
government's sanction order to the beneficiary's bank account:

1. ``trace_intake``    - validate/normalise the complaint, resolve beneficiary
2. ``dbt_lookup``      - find the government disbursement record (UTR / scheme)
3. ``credit_check``    - did the money land in the beneficiary's own account?
4. ``reconcile``       - sanctioned vs credited amount / shortfall
5. ``fraud_detect``    - diversion, mule accounts, duplicate references
6. ``orchestrate``     - fuse into a verdict + confidence + recommended action
7. ``grievance_notice``- draft the escalation letter to the authority

Use :func:`trace_complaint` for a one-shot run or instantiate ``TracePipeline``
to reuse the agents.
"""
from .pipeline import TracePipeline, trace_complaint

__all__ = ["TracePipeline", "trace_complaint"]
