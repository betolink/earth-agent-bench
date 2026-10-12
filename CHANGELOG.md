# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **0.1.0 is the initial release.** Everything before it was exploratory work;
> this entry is finalized when 0.1.0 is committed/tagged. No per-change entries
> are kept until then.

## [0.1.0] - 2026-10-12

First tagged release. Access-pattern selection benchmark for AI agents on NASA
Earthdata: each task names the exact dataset(s) and asks the agent to pick and
execute the best available access pattern.

### Added
- **Grounded task suite** — 18 schema-validated tasks across atmosphere,
  cryosphere, biosphere, ocean, solid-earth and land-surface, each with a
  resolved CMR `concept_id`, gold access pattern and a thin scientific gate.
- **Instruction now names the dataset(s)** — a `## Datasets to use` block
  (short_name + `concept_id`); collection *discovery* is out of scope.
- **Access-pattern preference** — virtualization (`C1/C2/C3`) → Harmony (`S1`) →
  OPeNDAP (`S3/S2`) → HTTP subsetting/aggregation (`T*`/`F*`) → download
  (`M1/M2`); AppEEARS/Giovanni excluded (`patterns.SELECTION_LADDER`).
- **Full sweep driver** — `eab run --name <experiment>` (named runs), resumable
  (`EAB_RUN_START`), graceful pause (`runs/PAUSE`), gateway preflight, loop/stall
  watchdog, per-combo perms reclaim.
- **Run identity** — `experiments/run.yaml` `name` + `EAB_RUN_NAME`, run
  manifests (`runs/manifests/<name>-<stamp>.json`), `eab config`, `eab archive`.
- **Inspection** — `eab trajectory` (per-cell trajectory + metadata: model
  params, task, environment, ATIF trajectory), `eab index` (rebuildable per-trial
  JSONL), `eab report`.
- **Condition wiring** — baseline / mcp / skills / mcp-skills / improve; the
  per-model `improve` skill is auto-generated (`eab postmortem`) before the
  `improve` combo.
- **Real Harbor integration** — generated `task.toml` packages + JobConfig,
  in-container verifiers, `eab harbor`.
- **Executor + profiler** — `eab exec` (`ok|error|timeout|oom`, scalene/memray),
  staged as a future efficiency pass (`docs/executor.md`).
- **Oracles** — EDVS virtualizability parquet, curated service catalog, live CMR
  discovery.
- **Live dashboard** — `eab dashboard` (Textual): run matrix, live agent stream,
  current task, Ctrl+L logs.
- **Self-contained** — env contract `EARTHDATA_TOKEN`, `LITE_LLM_ENDPOINT`,
  `LITE_LLM_API_KEY`; `eab doctor`; secrets via env/env-file (no loose files).

### Changed
- **Scoring** — dropped `collection_selection` (the dataset is given); reweighted
  to access_pattern 0.45 · service_discovery 0.15 · representation 0.15 ·
  efficiency 0.15 · validation 0.10.
- **Task pattern tiers re-derived** from verified availability (EDVS grade →
  virtualization; CMR `has_transforms` → Harmony; RelatedUrls → OPeNDAP).
- **Two wrong short names fixed** — `PREFIRE_SAT1_1B-RAD`, `…_V_JPL2205`.
- Config-driven everywhere: models/harnesses/conditions/tasks/paths load from
  `experiments/*.yaml` (no hard-coded lists); shared `runs.parse_job_dir`.
- Docstrings on all top-level defs; `ruff` config + clean.

### Fixed
- Driver deadlock: `disown` the loop watchdog so it isn't counted by the
  run-cell pool / bare `wait`.
- `DONE: unbound variable` on empty resume (`set -u` + `${#DONE[@]}`).
- Dashboard live view now renders every harness schema (pi/opencode/codex/claude
  + generic); run-dir stamp parsing no longer mishandles the trailing stamp.

[0.1.0]: https://github.com/betolink/earth-agent-bench/releases/tag/v0.1.0
