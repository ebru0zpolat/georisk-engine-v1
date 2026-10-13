# Headroom × GeoRisk Engine

Optional [Headroom](https://github.com/chopratejas/headroom) integration for compressing large GeoRisk MCP tool outputs before they reach an LLM.

**Spec:** [docs/integrations/headroom_georisk_engine.md](../../docs/integrations/headroom_georisk_engine.md)

| Layer | Role |
|-------|------|
| **GeoRisk core** | Deterministic scores, reports, scenario API (`app/`) |
| **georisk-mcp** | MCP bridge — HTTP only, no duplicate scoring |
| **Headroom** | Local context compression (library, proxy, or MCP tools) |

Headroom does **not** change GeoRisk scores or reports on the server. It only shrinks what agents read after MCP tool calls.

## Why this matters

GeoRisk MCP tools can return large payloads:

| Tool | Typical size driver |
|------|---------------------|
| `georisk_score` | Full component vector, GEE features, industrial verification |
| `georisk_scenario_run` | Hazard results, propagation graph, audit context |
| `georisk_report_markdown` | Multi-section DD appendix |
| `georisk_report_pdf` | Base64-encoded PDF |

Headroom's SmartCrusher and text compressors often cut JSON and report text by **60–90%** while preserving fields agents need for memos and explainability.

## Integration modes

### Mode A — Headroom MCP + GeoRisk MCP (recommended)

Register both servers. The agent calls `georisk_*` tools, then `headroom_compress` on demand (or relies on proxy-level compression for all LLM traffic).

```bash
pip install "headroom-ai[mcp]"
pip install -e integrations/deerflow/mcp_server
headroom mcp install
```

Merge `examples/mcp_config.snippet.json` into your MCP host config (Cursor, DeerFlow, Claude Code).

### Mode B — Automatic compression in georisk-mcp

Enable server-side compression when Headroom is installed in the same Python environment:

```bash
pip install "headroom-ai[mcp]"
pip install -e integrations/deerflow/mcp_server
export GEORISK_MCP_COMPRESS=1
georisk-mcp
```

When compression saves tokens, responses are wrapped:

```json
{
  "_georisk_mcp": {
    "compressed": true,
    "tool": "georisk_score",
    "tokens_before": 4200,
    "tokens_after": 680,
    "tokens_saved": 3520,
    "compression_ratio": 0.8381,
    "transforms_applied": ["router:smart_crusher:0.00"],
    "note": "Payload compressed with Headroom. Use headroom_retrieve if you need the full original (CCR)."
  },
  "payload": "… compressed JSON or Markdown …"
}
```

Environment:

| Variable | Default | Purpose |
|----------|---------|---------|
| `GEORISK_MCP_COMPRESS` | off | Set `1` / `true` to enable |
| `GEORISK_MCP_COMPRESS_MIN_TOKENS` | `800` | Skip compression below this size |
| `GEORISK_MCP_COMPRESS_TARGET_RATIO` | `0.5` | Headroom target ratio |
| `GEORISK_MCP_COMPRESS_MODEL` | `claude-sonnet-4-5-20250929` | Token counting model |

### Mode C — Headroom proxy (zero MCP changes)

Run the proxy in front of your LLM provider; all conversation traffic is compressed automatically:

```bash
headroom proxy --port 8787
# Point your agent at http://127.0.0.1:8787
```

Use alongside GeoRisk MCP for tool calls. See [Headroom proxy docs](https://headroom-docs.vercel.app/docs/proxy).

## Layout

| Path | Purpose |
|------|---------|
| `examples/mcp_config.snippet.json` | Combined Headroom + GeoRisk MCP config |
| `examples/cursor_mcp.snippet.json` | Cursor-specific MCP settings snippet |
| `../deerflow/mcp_server/georisk_mcp/compress.py` | Optional compression helper (Mode B) |

## Quick smoke test (Mode B)

```bash
export GEORISK_MCP_COMPRESS=1
PYTHONPATH=integrations/deerflow/mcp_server python - <<'PY'
import json
import os
os.environ.setdefault("GEORISK_MCP_COMPRESS_MIN_TOKENS", "10")
from georisk_mcp.compress import format_tool_response

blob = json.dumps({"components": {f"c{i}": {"score": i, "detail": "x" * 300} for i in range(40)}}, indent=2)
out = format_tool_response(blob, tool_name="georisk_score")
parsed = json.loads(out)
assert parsed["_georisk_mcp"]["compressed"] is True
print("saved", parsed["_georisk_mcp"]["tokens_saved"], "tokens")
PY
```

## Tests

```bash
PYTHONPATH=. pytest integrations/headroom/tests integrations/deerflow/tests -q
```

## Related

- DeerFlow VC builder: [integrations/deerflow/README.md](../deerflow/README.md)
- Architecture separation: [docs/architecture/deerflow-georisk-separation.md](../../docs/architecture/deerflow-georisk-separation.md)
