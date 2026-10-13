"""Optional Headroom compression for large GeoRisk MCP tool outputs."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompressionMetrics:
    tokens_before: int
    tokens_after: int
    tokens_saved: int
    compression_ratio: float
    transforms_applied: tuple[str, ...]


@dataclass(frozen=True)
class CompressionResult:
    content: str
    metrics: CompressionMetrics | None = None


def compression_enabled() -> bool:
    return os.environ.get("GEORISK_MCP_COMPRESS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def compression_min_tokens() -> int:
    raw = os.environ.get("GEORISK_MCP_COMPRESS_MIN_TOKENS", "800")
    try:
        return max(0, int(raw))
    except ValueError:
        return 800


def _headroom_model() -> str:
    return os.environ.get("GEORISK_MCP_COMPRESS_MODEL", "claude-sonnet-4-5-20250929")


def _headroom_target_ratio() -> float:
    raw = os.environ.get("GEORISK_MCP_COMPRESS_TARGET_RATIO", "0.5")
    try:
        value = float(raw)
    except ValueError:
        value = 0.5
    return min(max(value, 0.05), 1.0)


def maybe_compress_tool_output(content: str, *, tool_name: str) -> CompressionResult:
    """Compress tool output when Headroom is installed and compression is enabled."""
    if not compression_enabled():
        return CompressionResult(content=content)

    try:
        from headroom import compress as headroom_compress
    except ImportError:
        return CompressionResult(content=content)

    messages: list[dict[str, Any]] = [{"role": "user", "content": content}]
    result = headroom_compress(
        messages,
        model=_headroom_model(),
        compress_user_messages=True,
        target_ratio=_headroom_target_ratio(),
        protect_recent=0,
    )

    if result.tokens_before < compression_min_tokens():
        return CompressionResult(content=content)

    if result.tokens_saved <= 0:
        return CompressionResult(content=content)

    compressed = result.messages[0]["content"]
    if not isinstance(compressed, str):
        compressed = str(compressed)

    metrics = CompressionMetrics(
        tokens_before=result.tokens_before,
        tokens_after=result.tokens_after,
        tokens_saved=result.tokens_saved,
        compression_ratio=result.compression_ratio,
        transforms_applied=tuple(result.transforms_applied),
    )
    return CompressionResult(content=compressed, metrics=metrics)


def format_tool_response(content: str, *, tool_name: str) -> str:
    """Return MCP tool payload, optionally wrapped with compression metadata."""
    result = maybe_compress_tool_output(content, tool_name=tool_name)
    if result.metrics is None:
        return result.content

    envelope = {
        "_georisk_mcp": {
            "compressed": True,
            "tool": tool_name,
            "tokens_before": result.metrics.tokens_before,
            "tokens_after": result.metrics.tokens_after,
            "tokens_saved": result.metrics.tokens_saved,
            "compression_ratio": round(result.metrics.compression_ratio, 4),
            "transforms_applied": list(result.metrics.transforms_applied),
            "note": (
                "Payload compressed with Headroom. Use headroom_retrieve if you "
                "need the full original (CCR)."
            ),
        },
        "payload": result.content,
    }
    return json.dumps(envelope, indent=2)
