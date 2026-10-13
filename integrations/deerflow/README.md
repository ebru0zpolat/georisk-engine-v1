# DeerFlow × GeoRisk Engine

Venture-capital and due-diligence workflows for DeerFlow agents calling GeoRisk Engine over MCP.

**Spec:** [docs/integrations/deerflow_vc_builder_georisk_engine.md](../../docs/integrations/deerflow_vc_builder_georisk_engine.md)  
**Separation:** [DeerFlow analyst layer vs GeoRisk core](../../docs/architecture/deerflow-georisk-separation.md)

| Layer | What it does |
|-------|----------------|
| **GeoRisk core** (this repo `app/`) | Deterministic, versioned, auditable scores & scenario API |
| **DeerFlow** (external) | SuperAgent harness — research, memos, QA, client output, scenario *explanation* |
| **`georisk-mcp`** (this repo) | MCP bridge only — no duplicate scoring |

DeerFlow runs multi-minute to multi-hour jobs via sandbox, memory, tools, skills, and sub-agents; extend with custom skills + MCP. GeoRisk numbers always come from HTTP tools, never from agent invention.

## Layout

| Path | Purpose |
|------|---------|
| `mcp_server/` | Installable `georisk-mcp` stdio MCP server |
| `skill/georisk-vc-builder/` | DeerFlow custom skill (copy into DeerFlow checkout) |
| `examples/` | `extensions_config` snippet and sample prompts |
| `tests/` | HTTP client tests (mocked; no DeerFlow runtime in CI) |

## Quick start

### 1. GeoRisk API

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8002
```

### 2. MCP server

```bash
pip install -e integrations/deerflow/mcp_server
# Verify: python -c "from georisk_mcp.client import GeoRiskClient; ..."
```

Environment (optional): `GEORISK_BASE_URL`, `GEORISK_TIMEOUT_SECONDS`, `GEORISK_API_KEY` (sent as `X-API-Key` when set).

Optional Headroom compression for large tool payloads: set `GEORISK_MCP_COMPRESS=1` and install `headroom-ai[mcp]` in the same venv. See [integrations/headroom/README.md](../headroom/README.md).

### 3. DeerFlow

1. Clone [deer-flow](https://github.com/bytedance/deer-flow) and follow its quickstart.
2. Copy skill:

   ```bash
   cp -r integrations/deerflow/skill/georisk-vc-builder \
     /path/to/deer-flow/skills/custom/georisk-vc-builder
   ```

3. Merge `examples/extensions_config.snippet.json` into DeerFlow `extensions_config.json`.
4. Ensure `georisk-mcp` is on `PATH` (from step 2).
5. Open DeerFlow UI and use prompts in `examples/sample_prompt.md`.

## MCP tools

| Tool | Description |
|------|-------------|
| `assess_asset` | Registry-authorized single-asset assessment |
| `compare_assets` | Registry-authorized batch comparison |
| `get_source_evidence` | Registry-authorized source evidence retrieval |
| `generate_evidence_pack` | Registry-authorized derived evidence artifact |

## Security (v1)

GeoRisk API has **no built-in auth**. Run MCP and API on localhost or a trusted network until API key middleware is added on the server side. The MCP client already sends `X-API-Key` when `GEORISK_API_KEY` is set.

## Manual smoke test

```bash
# Terminal A
uvicorn app.main:app --port 8002

# Terminal B (client only — no mcp package required)
PYTHONPATH=.:integrations/deerflow/mcp_server python -c "
from georisk_mcp.client import GeoRiskClient, build_score_body
with GeoRiskClient() as c:
    print('health', c.health()['status'])
    print('demos', len(c.list_demos()))
    s = c.score(build_score_body(asset_name='Smoke', latitude=39.97, longitude=32.74))
    print('score', s['overall_score'], s['audit_id'])
"

# MCP stdio server (install mcp in a dedicated venv if it conflicts with FastAPI pins)
pip install -e integrations/deerflow/mcp_server
georisk-mcp   # runs stdio; pair with DeerFlow extensions_config.json
```

In-process smoke (no live server): `PYTHONPATH=. pytest integrations/deerflow/tests -q`

## Tests

```bash
PYTHONPATH=. pytest integrations/deerflow/tests
```
