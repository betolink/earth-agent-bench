# Documentation

Start with the [README](../README.md). Everything below is current unless it
lives under `docs/archive/`.

| Doc | What it covers |
|---|---|
| [Quickstart](quickstart.md) | Install, environment contract, first Harbor run, dataset |
| [Running & observing](running.md) | Master model config, matrices, live web viewer, index/report/trace analysis |
| [Adding tasks](adding-tasks.md) | Add a grounded task or a correctness eval, validate, ship |
| [Tasks & evals](tasks-and-evals.md) | The two suites, scoring contract, suite summary |
| [Harbor packaging](../harbor/README.md) | Task packages, verifier isolation, dataset publishing |
| [Executor](executor.md) | `eab exec` — ok/error/timeout/oom + profiling |
| [Gaps](gaps.md) | Backlog with acceptance criteria |

## Task-tree readmes

- [Task suites](../benchmark/tasks/README.md) — all task definitions
- [Access-pattern tasks](../benchmark/tasks/access-pattern/README.md) — the grounded suite
- [Correctness evals](../benchmark/tasks/correctness/README.md) — the single-value screen
- [MCP wiring](../mcp/README.md) — server manifest and per-harness registration
- [Skills](../skills/) — the five Earthdata skills

## Archive (historical)

Past plans, assessments, and run reports are kept for provenance and are **not**
maintained against the current code:

`docs/archive/` — consolidated/general/refined plans, RPI assessment, FineEnvs
RL assessment, unification proposal, and per-sweep reports.

## Conventions

- All commands run from the repo root via `uv run …` (`eab`, `harbor`).
- Credentials come from the host environment, never the repo:
  `EARTHDATA_TOKEN` (or `EARTHDATA_USERNAME` + `EARTHDATA_PASSWORD`),
  `LITE_LLM_ENDPOINT`, `LITE_LLM_API_KEY`. `eab doctor` validates them.
- `experiments/models.yaml` = who; `experiments/run.yaml` = which.
  `eab harbor run` with no arguments runs that selection.
