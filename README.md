# earth-agent-bench

Access-pattern selection benchmark for AI agents working with NASA Earthdata.

> **Given a NASA Earthdata collection (with its CMR `concept_id`) and a bounded scientific access requirement, did the agent select and execute the best available access pattern — and could it justify why?**

The benchmark does not score "amazing science", and it does **not** test
collection *discovery* (handled by a separate project): each task names the exact
dataset(s) it must use. Each task wraps a thin, discipline-representative
computation (right variable, extent, units, trivial aggregation) around the real
evaluation surface: **access-pattern selection**, service discovery,
representation, and efficiency.

## Key concepts

- **Access-pattern preference** (`C1`…`M2`): **data virtualization first**
  (`C1` virtual zarr, `C2` native zarr, `C3` COG), then **Harmony** (`S1`), then
  **OPeNDAP** (`S3` DMR++ / `S2`), then **HTTP subsetting/aggregation** (`T*`,
  `F*`), and **full download last** (`M1`/`M2`). AppEEARS (`S4`) and Giovanni
  (`S5`) are not ranked as "good" patterns.
- **Out-of-region**: direct S3 / cloud-native *storage* is unavailable here, so
  access goes over **HTTPS** (virtualization, Harmony, OPeNDAP, or filtered
  download).
- **Oracles**: an EDVS parquet file decides virtualization (`C1`) availability;
  live CMR (`has_transforms`, RelatedUrls) decides Harmony (`S1`) and OPeNDAP
  (`S2`/`S3`); a curated YAML catalog covers the rest.
- **18 grounded tasks** across atmosphere, cryosphere, biosphere, ocean, solid
  earth, and land surface — real collections, regions, and event windows, each
  with a resolved `concept_id`.

## Documentation

- **[Quickstart](docs/quickstart.md)** — install, the environment contract
  (`EARTHDATA_TOKEN`, `LITE_LLM_ENDPOINT`, `LITE_LLM_API_KEY`), and `eab doctor`.
- **[Adding tasks](docs/adding-tasks.md)** — task YAML structure, the out-of-region
  rule, how grounded tasks are graded, and a checklist.
- **[Running & the dashboard](docs/running.md)** — single cells, the full sweep
  driver, `eab dashboard`, the loop/stall watchdog, and what to expect.
- **[Executor & profiler](docs/executor.md)** — `eab exec` (`ok|error|timeout|oom`
  + scalene/memray) for code deliverables.
- **[Tasks & evals](docs/tasks-and-evals.md)** — full task suite + evaluation spec.
- **[Reports](docs/reports/)** — grounded-sweep observations and collection
  verification (what to improve next).
- **[FineEnvs RL assessment](docs/rl-fineenvs-assessment.md)** — gap to the
  multi-harness RL recipe (future track).
- **[Consolidated plan](docs/consolidated-plan.md)** · **[Gaps](docs/gaps.md)**.

## Setup

```bash
uv sync
uv run python scripts/build_virtualizability_parquet.py   # fetch EDVS CSV -> parquet
```

## Usage

```bash
# the only env you need to run EAB (see docs/quickstart.md#environment-contract)
export EARTHDATA_TOKEN=... LITE_LLM_ENDPOINT=https://... LITE_LLM_API_KEY=...
uv run eab doctor                            # validate the contract + probe the gateway
uv run eab config                            # preview the run matrix: models × harnesses × conditions
uv run eab trajectory -t a3 -m tiel-coder-35b -H pi   # dump a cell's trajectory + metadata
uv run eab index                             # build runs/index.jsonl (per-trial metadata)
uv run eab dashboard                         # live TUI (runs · live agent · current task; Ctrl+L logs)
uv run eab archive                           # shelve the active run -> runs/archive/<name>

# full sweep, named (the name is the run identity for dashboard/manifest/archive)
EAB_MODELS=tiel-coder-35b EAB_HARNESSES=pi uv run eab run --name experiment-1

uv run eab validate                          # validate all 18 task YAMLs
uv run eab matrix TEMPO_NO2_L3               # service availability matrix
uv run eab matrix MUR-JPL-L4-GLOB-v4.1 --cmr # merge live CMR service discovery
uv run eab collections --grade B            # list EDVS grade-B collections
uv run eab instruction benchmark/tasks/atmosphere/a1-tempo-no2-florida-2024.yaml
uv run eab score observation.json            # score a run observation

# single-run trial (direct, no Harbor)
uv run eab run benchmark/tasks/cryosphere/c1-itslive-jakobshavn-2015-2024.yaml \
    --model tiel-coder-35b --harness opencode --condition mcp-skills --dry-run

# Harbor path: generate task.toml packages + JobConfig, then run (isolated, auto-scored)
uv run eab harbor generate cryo-1,atmo-2 --condition mcp-skills
uv run eab harbor run cryo-1 --model tiel-coder-35b --harness opencode --dry-run

# grade/profile a code deliverable (explicit ok|error|timeout|oom)
uv run eab exec /app/program.py --timeout 60 --mem-mb 512 --profile scalene

# per-model self-improvement: digest failures -> improvements/<model>/.../SKILL.md
uv run eab postmortem tiel-coder-35b

# correctness eval suite (single clean value per task)
uv run eab eval grade 01_hls_open_vs_download runs/.../output/answer.txt
uv run eab eval report runs/eval-results
```

Example run observation for `eab score`:

```json
{
  "task_id": "atmosphere/a1-tempo-no2-florida-2024",
  "observed_patterns": ["S1"],
  "collection_short_names": ["TEMPO_NO2_L3"],
  "discovered_services": ["S1", "S2", "S3"],
  "representation": "lazy",
  "validation_passed": true,
  "metrics": {"bytes_read": 45000000, "objects_read": 12, "runtime_seconds": 180}
}
```

Scoring weights (collection choice is **not** scored — the dataset is given):
**access pattern 45%** · service discovery 15% · representation 15% ·
efficiency 15% · validation gate 10%.

## Skills, MCP, and running a trial

- `skills/` — 5 Earthdata skills (core: `data-access-patterns`; plus
  `data-virtualization`, `earthdata-streaming-vs-download`, `xarray`,
  `dask-optimization`) mounted in the skills/mcp-skills conditions
- `improvements/` — per-model self-improvement skills, mounted only by the
  `improve` condition; generated with `eab postmortem`
- `mcp/` — MCP server manifest and per-harness wiring; **cmr-mcp is live** at
  `https://cmr.earthdata.nasa.gov/mcp/v1`, earthaccess-mcp pending
- **`eab dashboard`** — live TUI: run matrix, current agent stream, active task
  (see [running](docs/running.md))
- `docs/quickstart.md` — the runbook: EDL account, gateway setup, a manual quick
  trial, the knowledge conditions, and the pilot scale-up path

## Experiment configuration

Run matrices and roster live in `experiments/`:

- **7 local + 2 frontier-open + 2 closed-reference models** (see
  `experiments/models.yaml`), all served by one LiteLLM gateway
  (`litellm.example.yaml`)
- **4 harnesses** — pi, opencode, codex cli (crossed with all models) and claude code
- **5 knowledge conditions** — baseline / mcp / skills / mcp-skills / **improve**
  (skills + mcp + a model-specific skill generated from its failure postmortem)

Open and economical models are the headline: the price-tier and knowledge×tier research
questions are specified in `docs/tasks-and-evals.md` §10. Every run records a
`RunManifest` (tokens, cost, tokens/s, quantization) to power the cost tables.

## Repository layout

```
benchmark/tasks/     18 grounded task definitions (YAML, schema-validated)
benchmark/oracles/   curated service catalog
benchmark/data/      virtualizability.parquet (EDVS oracle)
experiments/         roster, conditions, harnesses, run matrices, eval suite
skills/ improvements/ knowledge skills + per-model self-improvement skills
src/earth_agent_bench/
  patterns.py        pattern registry + selection ladder
  schemas.py         pydantic task/result models
  tasks.py           task loading + instruction rendering (dataset + concept_id)
  runconfig.py       run config + manifests (models/harnesses/conditions/tasks)
  runs.py            run-dir parsing (parse_job_dir) + read_json
  trajectory.py      per-cell trajectory + metadata resolver (eab trajectory)
  index.py           rebuildable per-trial JSONL index (eab index)
  archive.py         shelve a run (eab archive)
  report.py          per-model reward + token aggregation (eab report)
  evals.py           deterministic correctness grader (10 eval tasks)
  models.py          LiteLLM roster helpers (discover / reconcile)
  mcp.py             MCP server manifest probe (eab mcp)
  wiring.py          shared gateway / condition / MCP / skills wiring
  runner.py          single-run orchestrator (eab run <task>)
  sweep.py           cartesian sweep (eab sweep)
  postmortem.py      per-model self-improvement skill generator (eab postmortem)
  dashboard.py       live TUI (Textual): eab dashboard
  harbor/            real Harbor integration (packages, JobConfig, runtime/)
    runtime/         verifiers + executor (ok|error|timeout|oom) + profiler
  oracles/           virtualizability (parquet), services, CMR, matrix
  scoring/           access-pattern, efficiency, discovery, aggregate
scripts/             EDVS build, sweep driver, loop watchdog, concept-id resolver
tests/               unit tests
```

## Status (0.1.0)

Working: the grounded task suite (dataset given + `concept_id`), oracles,
scoring, CLI, skills, MCP wiring, the full sweep driver (`eab run --name`) and
single run, the correctness eval suite (`eab eval`), real Harbor integration
(`eab harbor`), the code executor + profiler (`eab exec`), the per-model
self-improvement loop (`eab postmortem` + `improve`), run naming/manifests +
pause/resume + archive (`eab archive`), trajectory/index inspection
(`eab trajectory`, `eab index`), and the live dashboard (`eab dashboard`).

EAB is **self-contained** — no hard-coded hosts/paths; run it with
`EARTHDATA_TOKEN`, `LITE_LLM_ENDPOINT`, `LITE_LLM_API_KEY` (`eab doctor`
validates). Remaining gaps: harbor/earthaccess version pinning, a reliable
Harmony/OPeNDAP probe, byte-level instrumentation, reference solutions,
earthaccess-mcp, and batch orchestration — see `docs/gaps.md`,
`docs/reports/collection-verification.md` and `docs/quickstart.md`.
