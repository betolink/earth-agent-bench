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
  first-class pattern, ranked alongside OPeNDAP — and above it whenever the
  collection's [EarthDataVirtualizabilityScore](https://github.com/alex-s-gardner/EarthDataVirtualizabilityScore)
  (EDVS) grade is A or B.
- **Oracles**: an EDVS parquet file decides `C1` availability and DMR++ (`S3`);
  a curated YAML catalog covers other services (until verified against CMR);
  live CMR discovery is available on demand.
- **18 grounded tasks** across atmosphere, cryosphere, biosphere, ocean, solid
  earth, and land surface — real collections, regions, and event windows.

Docs: [consolidated plan](docs/consolidated-plan.md) · [tasks & evals](docs/tasks-and-evals.md) · [quickstart](docs/quickstart.md) · [gaps & remaining work](docs/gaps.md)

## Setup

```bash
uv sync
uv run python scripts/build_virtualizability_parquet.py   # fetch EDVS CSV -> parquet
```

## Usage

```bash
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

# correctness eval suite (single clean value per task)
uv run eab eval grade 01_hls_open_vs_download runs/.../output/answer.txt
uv run eab eval report runs/eval-results
```

Example run observation for `eab score`:

```json
{
  "task_id": "atmosphere/a1-tempo-no2-florida-2024",
  "observed_patterns": ["C1"],
  "collection_short_names": ["TEMPO_NO2_L3"],
  "discovered_services": ["C1", "S1", "S3"],
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
- `mcp/` — MCP server manifest and per-harness wiring; **cmr-mcp is live** at
  `https://cmr.earthdata.nasa.gov/mcp/v1`, earthaccess-mcp pending
- `docs/quickstart.md` — the runbook: EDL account, gateway setup, a manual quick
  trial, the four knowledge conditions, and the pilot scale-up path

## Experiment configuration (v3.1)

Run matrices and roster live in `experiments/`:

- **9 models in 3 tiers** — local (LFM2.5-2.6B, Ornith-1.5-9B, gpt-oss-20B, Qwen3.8-27B-GSQ,
  Tiel-Coder-35B-A3B), frontier-open API (DeepSeek Flash 4.1, GLM 5.3 Flash), and closed
  references to beat (Claude Sonnet 5.5, GPT Sol) under a shared budget cap
- **All models served by one LiteLLM gateway** (see `litellm.example.yaml`)
- **4 harnesses** — pi, opencode, codex cli (crossed with all models) and claude code
  (Sonnet-only lane)
- **4 knowledge conditions** — baseline / MCP / skills / MCP+skills

Open and economical models are the headline: the price-tier and knowledge×tier research
questions are specified in `docs/tasks-and-evals.md` §10. Every run records a
`RunManifest` (tokens, cost, tokens/s, quantization) to power the cost tables.

## Repository layout

```
benchmark/tasks/     18 task definitions (YAML, schema-validated)
benchmark/oracles/   curated service catalog
benchmark/data/      virtualizability.parquet (EDVS oracle)
src/earth_agent_bench/
  patterns.py        pattern registry + selection ladder
  schemas.py         pydantic task/result models
  tasks.py           task loading + instruction rendering
  evals.py           deterministic correctness grader (10 eval tasks)
  models.py          LiteLLM roster helpers (discover / reconcile)
  wiring.py          shared gateway / condition / MCP / skills wiring
  runner.py          direct single-run orchestrator (eab run)
  sweep.py           cartesian sweep (eab sweep)
  harbor/            real Harbor integration (packages, JobConfig, runtime/)
  oracles/           virtualizability (parquet), services, CMR, matrix
  scoring/           access-pattern, efficiency, discovery, aggregate
scripts/             parquet build script
tests/               unit tests
```

## Status

Working (v3.3): task suite, oracles, scoring, CLI, skills, MCP wiring, the
direct single-run runner (`eab run` / `eab sweep`), the correctness eval suite
(`eab eval`), and the **real Harbor** integration (`eab harbor`: `task.toml`
packages + JobConfig + instrumented auto-scoring verifier) are in place.
Remaining gaps: harbor/earthaccess version pinning, byte-level instrumentation,
reference solutions, earthaccess-mcp, and batch orchestration — see
`docs/gaps.md` and `docs/quickstart.md`.
