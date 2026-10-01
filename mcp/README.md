# MCP wiring

Machine-readable server manifest: `mcp/manifest.yaml`.

| Server | Endpoint | Status |
|---|---|---|
| `cmr-mcp` | `https://cmr.earthdata.nasa.gov/mcp/v1` | ready (public, no auth) |
| `earthaccess-mcp` | TBD | pending — not deployed yet |

Until `earthaccess-mcp` ships, the `mcp` and `mcp-skills` conditions run with
**cmr-mcp only** and results are interpreted accordingly (discovery-level knowledge,
not operational knowledge).

## Per-harness registration

Copy the matching example from `mcp/harnesses/` into the harness's project/config
location:

| Harness | Example file | Where it goes |
|---|---|---|
| claude code | `claude-code.mcp.json` | `.mcp.json` in the run workspace |
| codex cli | `codex-config.toml` | merge into `~/.codex/config.toml` or `config.toml` |
| opencode | `opencode.jsonc` | `opencode.jsonc` in the run workspace |
| pi | `pi.json` | pi project config (verify exact path at pilot burn-in) |

Skills mounting: claude code reads `.claude/skills/<name>/SKILL.md` from the run
workspace; for the other harnesses, verify their skills/AGENTS.md conventions at pilot
burn-in and record them in `experiments/harnesses.yaml`.
