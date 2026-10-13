"""Tests for scripts/run_integrated_audit.py preflight."""

from __future__ import annotations

import pytest


def test_require_gee_identity_exits_without_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDIT_USE_MOCK", raising=False)
    monkeypatch.delenv("GEE_PROJECT", raising=False)
    monkeypatch.delenv("GEE_PROJECT_ID", raising=False)

    import scripts.run_integrated_audit as ria

    monkeypatch.setattr(ria, "load_dotenv", lambda *args, **kwargs: None)

    with pytest.raises(SystemExit) as exc:
        ria.require_gee_identity_or_mock()
    assert exc.value.code == 1


def test_require_gee_identity_ok_with_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_USE_MOCK", "true")
    monkeypatch.delenv("GEE_PROJECT", raising=False)
    monkeypatch.delenv("GEE_PROJECT_ID", raising=False)

    import scripts.run_integrated_audit as ria

    ria.require_gee_identity_or_mock()  # no exit


def test_require_gee_identity_ok_with_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDIT_USE_MOCK", raising=False)
    monkeypatch.setenv("GEE_PROJECT", "test-project-id")

    import scripts.run_integrated_audit as ria

    ria.require_gee_identity_or_mock()
