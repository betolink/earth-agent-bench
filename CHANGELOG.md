# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **0.1.0 is the initial release.** Everything before it was exploratory work;
> this entry is finalized when 0.1.0 is committed/tagged. No per-change entries
> are kept until then.

## [Unreleased]

### Changed
- **Harbor is the only execution path.** Removed the host-side runner/sweep
  (`runner.py`, `sweep.py`, `scripts/eab-full-run.sh`, `done_cells.py`,
  `loop_watchdog.py`, `patch-harbor.sh`), the live dashboard, and the
  postmortem/`improve` condition (`postmortem.py`, `improvements/`). Kept
  `eab index`, `eab trajectory`, `eab report`, `eab archive`, `eab analyze`.
- **Reward semantics.** Benchmark verifiers now emit an all-or-nothing `pass`
  (headline) alongside the weighted `score`; `reward.txt` carries `pass`. The
  agent's self-reported `access_summary.json` is never scored.
- **Trusted verification.** Generated packages set
  `[verifier].environment_mode = "separate"`; the deliverable is re-run in the
  verifier container with a verifier-owned access log, and artifacts are
  re-materialized there.

### Added
- **Matrix runs from the master config** — `eab harbor run` with no task argument
  runs the `experiments/run.yaml` selection and expands the full
  model × harness × condition × task matrix; `--models` / `--harnesses` /
  `--conditions` (comma lists or `all`) override any axis, and
  `harnesses.yaml` crossing restrictions are enforced. Multiple conditions get
  per-condition package dirs so `--dry-run` commands stay valid.
- **`eab models list`** — the roster (`experiments/models.yaml`) with tier,
  served name, and whether `run.yaml` selects it.
- **`eab view`** — wrapper around Harbor's bundled web viewer
  (`harbor view <folder> --jobs`) for live inspection of runs under
  `runs/harbor` (trajectories, rewards, verifier logs).
- **Harbor conformance** in generated `task.toml`: `[metadata]` labels,
  `[task]` authors/keywords, root `source`, `[[artifacts]]`, resource caps.
- **Pinned agent stack** (`uv pip compile`) plus the earthaccess fork commit.
- **Harbor dataset** — `eab harbor dataset` writes a digest-pinned
  `harbor/dataset.toml` with `harbor/metric.py` (mean `pass`), so any Harbor
  install can download and run the suite.
- **Access policy** rendered in benchmark instructions, matching what the
  verifier enforces; `eab instruction --no-policy` keeps the old variant.
- **Conformance tests** (`tests/test_harbor_conformance.py`): every generated
  package validates against Harbor's `TaskConfig`, artifacts/verifier mode are
  asserted, and `pass`/metric behavior is covered.
- Optional task `labels:` block (data type, level, length class, infeasible,
  difficulty) feeding Harbor metadata.

### Docs
- **Full documentation pass.** README rewritten around the Harbor-only workflow
  (master model config, matrix runs, live web viewer, `pass`/`score`); new
  `docs/README.md` index; `tasks-and-evals.md` condensed to the scoring contract
  plus a suite table; task-tree and eval readmes refreshed.
- **Historical material moved** to `docs/archive/` (plans, RPI/FineEnvs
  assessments, per-sweep reports, unification proposal); references updated.

### Deferred
- Sealed/offline mode, infeasible-task variants, and a long-horizon suite
  (`docs/gaps.md` §17–19).

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
