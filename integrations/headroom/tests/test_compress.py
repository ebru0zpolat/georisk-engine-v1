"""Tests for optional Headroom compression in georisk-mcp."""

from __future__ import annotations

import json
import os

import pytest

from georisk_mcp.compress import (
    CompressionResult,
    compression_enabled,
    format_tool_response,
    maybe_compress_tool_output,
)


@pytest.fixture(autouse=True)
def _clear_compress_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEORISK_MCP_COMPRESS", raising=False)
    monkeypatch.delenv("GEORISK_MCP_COMPRESS_MIN_TOKENS", raising=False)


def test_compression_disabled_passthrough() -> None:
    content = '{"audit_id": "abc", "overall_score": 70}'
    result = maybe_compress_tool_output(content, tool_name="georisk_score")
    assert result == CompressionResult(content=content, metrics=None)
    assert format_tool_response(content, tool_name="georisk_score") == content


def test_compression_enabled_without_headroom_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEORISK_MCP_COMPRESS", "1")
    assert compression_enabled() is True

    content = '{"audit_id": "abc", "overall_score": 70}'
    wrapped = format_tool_response(content, tool_name="georisk_score")
    assert wrapped == content


def test_compression_enabled_with_headroom(monkeypatch: pytest.MonkeyPatch) -> None:
    headroom = pytest.importorskip("headroom")
    _ = headroom  # silence unused in environments without headroom

    monkeypatch.setenv("GEORISK_MCP_COMPRESS", "1")
    monkeypatch.setenv("GEORISK_MCP_COMPRESS_MIN_TOKENS", "10")

    blob = json.dumps(
        {"components": {f"c{i}": {"score": i, "detail": "x" * 250} for i in range(35)}},
        indent=2,
    )
    out = format_tool_response(blob, tool_name="georisk_score")
    parsed = json.loads(out)
    assert parsed["_georisk_mcp"]["compressed"] is True
    assert parsed["_georisk_mcp"]["tool"] == "georisk_score"
    assert parsed["_georisk_mcp"]["tokens_saved"] > 0
    assert isinstance(parsed["payload"], str)
