"""Scientific-validation tooling (distinct from API/data-source validation).

This package hosts the study harnesses that produce the *evidence* required to
pass the six-month validation gates defined in
``docs/business/SIX_MONTH_VALIDATION_GATES.md``. It is deliberately separate
from ``app.services.validation_service`` (which validates API inputs and data
sources) — the code here answers a scientific question, not a request-shape one.
"""
