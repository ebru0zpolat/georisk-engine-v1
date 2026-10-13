# georisk-mcp

stdio MCP server that wraps the GeoRisk Engine HTTP API for DeerFlow and other MCP clients.

## Install

```bash
cd integrations/deerflow/mcp_server
pip install -e .
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `GEORISK_BASE_URL` | `http://127.0.0.1:8002` | GeoRisk API origin |
| `GEORISK_TIMEOUT_SECONDS` | `60` | HTTP timeout |
| `GEORISK_API_KEY` | *(unset)* | Optional `X-API-Key` header (for future server auth) |

## Run

```bash
georisk-mcp
```

## Tools

- `assess_asset` — authorized `POST /v1/risk/score`
- `compare_assets` — authorized `POST /v1/risk/batch`
- `get_source_evidence` — authorized source-validation retrieval
- `generate_evidence_pack` — authorized derived Markdown artifact generation

All four tools fail closed unless FastMCP authentication middleware supplies an
`AccessToken` already verified by a configured `TokenVerifier`. The host adapter maps
that verified identity into `TrustedExecutionContext`; it never trusts tool arguments or
headers directly. The current stdio entry point has no verifier and therefore remains
fail closed. See `docs/architecture/mcp-runtime-capability-authorization.md`.
