# Harbor packaging

`eab harbor` turns benchmark tasks into Harbor task packages and wraps the
`harbor` CLI (thin — the command template lives in `harbor.yaml` so the exact
flags can be pinned at pilot burn-in).

## Commands

```bash
# generate packages (aliases: cryo-1, atmo-2, solid-3; also 'all' and 'pilot')
uv run eab harbor generate cryo-1,atmo-2 --condition mcp-skills

# render the harbor command without running (prints argv)
uv run eab harbor run cryo-1 --model tiel-coder-35b --harness opencode --dry-run

# run for real (requires the harbor CLI installed and authenticated)
uv run eab harbor run cryo-1 --model tiel-coder-35b --harness opencode --condition baseline
```

## Generated package layout (`harbor/generated/<task>/`, gitignored)

```
instruction.md          agent-facing requirement + output contract (no gold)
AGENTS.md               workspace rules (+ skills pointer when mounted)
agent-requirements.txt  agent-side Python stack (from pyproject [agent] group)
environment/Dockerfile  workspace image; condition extras copied (skills/, MCP configs)
solution/               expert reference placeholder — validates the benchmark, not given to the agent
tests/
  task.yaml             the task definition (verifier side only)
  verify.py             classifies the run, scores it, writes evaluation.json
  earth_agent_bench/    vendored schemas + scoring (no pandas needed)
  run.sh, Dockerfile    verifier entrypoint
skills/, opencode.jsonc, config.toml, .mcp.json, pi.json   condition wiring (when applicable)
```

## Verifier behavior

- If the agent wrote `output/observation.json`, it is used verbatim.
- Otherwise `output/access_summary.json` is classified heuristically
  (service names → pattern IDs; `artifact*` presence = gate passed).
  This is scaffolding fidelity — real byte/object instrumentation replaces it
  later (see `docs/quickstart.md` §6).
- Exit code: 0 when any output artifact exists, 1 otherwise; the full
  `VerifierResult` is written to `tests/evaluation.json`.

## Secrets

Never baked into images or the repo. `harbor.yaml` lists the environment
variables (`EARTHDATA_USERNAME/PASSWORD`, gateway keys) to pass through to the
agent environment at runtime.
