# earth-agent-bench

Access-pattern selection benchmark for AI agents working with NASA Earthdata.

> **Given a NASA Earthdata collection and a bounded scientific access requirement, did the agent select and execute the best available access pattern — and could it justify why?**

The benchmark does not score "amazing science." Each task wraps a thin,
discipline-representative computation (a gate: right variable, right extent,
right units, trivial aggregation) around the real evaluation surface: service
discovery, access-pattern selection, representation, and efficiency.

## Key concepts

- **Access pattern taxonomy** (`C1`…`M2`): cloud-native direct access,
  server-mediated subsetting, streaming, filtered download, materialization.
- **earthaccess virtualization** (`C1`, `earthaccess.virtualize`) is a
  first-class pattern ranked above OPeNDAP when the collection's
  [EarthDataVirtualizabilityScore](https://github.com/alex-s-gardner/EarthDataVirtualizabilityScore)
  (EDVS) grade is A or B — **but `C1`/direct-S3 is unavailable here**: the suite
  runs **out-of-region**, so tasks rank the best **HTTPS** pattern (Harmony `S1`,
  OPeNDAP `S2`, DMR++ `S3`, Giovanni `S5`).
- **Oracles**: an EDVS parquet file decides `C1` availability and DMR++ (`S3`);
  a curated YAML catalog covers other services (until verified against CMR);
  live CMR discovery is available on demand.
- **18 grounded tasks** across atmosphere, cryosphere, biosphere, ocean, solid
  earth, and land surface — real collections, regions, and event windows.

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

Scoring weights: collection 10% · service discovery 15% · **access pattern 35%** ·
representation 15% · efficiency 15% · validation gate 10%.

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

## Experiment configuration (v3.1)

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
  tasks.py           task loading + instruction rendering
  evals.py           deterministic correctness grader (10 eval tasks)
  models.py          LiteLLM roster helpers (discover / reconcile)
  wiring.py          shared gateway / condition / MCP / skills wiring
  runner.py          direct single-run orchestrator (eab run)
  sweep.py           cartesian sweep (eab sweep)
  postmortem.py      per-model self-improvement skill generator (eab postmortem)
  dashboard.py       live TUI (Textual): eab dashboard
  harbor/            real Harbor integration (packages, JobConfig, runtime/)
    runtime/         verifiers + executor (ok|error|timeout|oom) + profiler
  oracles/           virtualizability (parquet), services, CMR, matrix
  scoring/           access-pattern, efficiency, discovery, aggregate
scripts/             EDVS build, sweep driver, loop watchdog, fix-perms
tests/               unit tests
```

## Status

Working (v3.4): task suite, oracles, scoring, CLI, skills, MCP wiring, the
direct single-run runner (`eab run` / `eab sweep`), the correctness eval suite
(`eab eval`), the real Harbor integration (`eab harbor`), the code executor +
profiler (`eab exec`), the per-model self-improvement loop (`eab postmortem` +
the `improve` condition), and the live dashboard (`eab dashboard`).

EAB is **self-contained** — no hard-coded hosts/paths; run it with
`EARTHDATA_TOKEN`, `LITE_LLM_ENDPOINT`, `LITE_LLM_API_KEY` (`eab doctor`
validates). Remaining gaps: harbor/earthaccess version pinning, byte-level
instrumentation, reference solutions, earthaccess-mcp, and batch orchestration —
see `docs/gaps.md` and `docs/quickstart.md`.
