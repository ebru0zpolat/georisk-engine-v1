from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GeoRiskMcpSettings:
    base_url: str
    timeout_seconds: float
    api_key: str | None
    compress_tool_outputs: bool

    @classmethod
    def from_env(cls) -> GeoRiskMcpSettings:
        base = os.environ.get("GEORISK_BASE_URL", "http://127.0.0.1:8002").rstrip("/")
        timeout = float(os.environ.get("GEORISK_TIMEOUT_SECONDS", "60"))
        api_key = os.environ.get("GEORISK_API_KEY") or None
        compress = os.environ.get("GEORISK_MCP_COMPRESS", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        return cls(
            base_url=base,
            timeout_seconds=timeout,
            api_key=api_key,
            compress_tool_outputs=compress,
        )
