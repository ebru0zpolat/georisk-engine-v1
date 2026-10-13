"""Generate the packaged MCP view from the authoritative application registry."""

from __future__ import annotations

import json
from pathlib import Path

from app.capabilities.registry import registry_projection

TARGET = Path("integrations/deerflow/mcp_server/georisk_mcp/capability_registry.generated.json")


def main() -> None:
    TARGET.write_text(
        json.dumps(registry_projection(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
