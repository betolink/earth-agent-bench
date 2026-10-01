# Earth-Agent-Bench: Consolidated Plan (v3)

**Supersedes for implementation purposes:** `general-plan.md` (v1, science-workflow focus) and `refined-plan.md` (v2.1, multi-pattern access focus).

**Companion documents:**

- `docs/tasks-and-evals.md` — the full task suite and evaluation specification (kept separate, as the canonical task reference).
- `docs/general-plan.md`, `docs/refined-plan.md` — historical design rationale.

---

## 1. What v3 changes and why

v2.1 established that the benchmark evaluates **best available access pattern selection**, not virtualization alone. v3 keeps that core and makes four consolidation decisions:

### 1.1 The benchmark question is operational, not scientific

> **Given a NASA Earthdata collection and a bounded scientific access requirement, did the agent select and execute the best available access pattern(s) — and could it justify why?**

The science in each task is a **thin, representative gate** (right variable, right extent, right units, trivial aggregation), not a full scientific workflow. We are not measuring "did we produce amazing science"; we are measuring "did we choose the best available access pattern(s) for a science-motivated requirement." Tasks remain detailed and representative of each discipline's real workflows so that the access problem is realistic, but the scored surface is access selection, service discovery, representation, and efficiency.

### 1.2 earthaccess virtualization is a first-class pattern

`earthaccess.virtualize()` → `write_virtual()` → `open_virtual()` — which build a virtual dataset (VirtualiZarr `ManifestArray`s) over NASA granules, persist it (Icechunk or kerchunk), and reopen it with automatic EDL chunk-container authorization — enter the pattern taxonomy as the canonical realization of pattern `C1`. Its standing:

- **Equal footing with OPeNDAP** (`S2`/`S3`/`T1`) as a first-class evaluation target.
- **Higher priority than OPeNDAP when the dataset fits the bill**, i.e. when the EarthDataVirtualizabilityScore (EDVS) grade says a lazy virtual datacube is achievable (grade `A` or `B`).
- Manual VirtualiZarr/kerchunk reference building counts as `C1`-equivalent, but tool-level credit is highest for the earthaccess path (it is the reproducible, one-call path an agent should prefer).

### 1.3 The virtualizability oracle is a local parquet file

The [EarthDataVirtualizabilityScore](https://github.com/alex-s-gardner/EarthDataVirtualizabilityScore) (EDVS) grades 86 NASA collections by opening granules, not by reading catalog metadata. For now we consume it as a parquet file:

- Location: `benchmark/data/virtualizability.parquet`
- Built by: `scripts/build_virtualizability_parquet.py` (fetches `results/virtualizability.csv` from the EDVS repo, normalizes columns, writes parquet)
- Consumed by: `earth_agent_bench.oracles.virtualizability.VirtualizabilityOracle`
- Semantics: grade `A` → `C1` available and top priority; grade `B` → `C1` available (with recorded caveats, e.g. time-dim to add at store build — earthaccess handles this); grade `C`/`D`/unknown → `C1` unavailable, decide by the recorded blocker. The `deciding_criterion` is surfaced to the verifier and (in MCP conditions) to the agent, because for non-cloud-optimized datasets the score also answers **"could such a pattern eventually be built?"** — a task may ask the agent to report this.

### 1.4 Task/eval specification lives in its own document

`docs/tasks-and-evals.md` holds the 18 grounded tasks (with representative discipline workflows, real collection short names, real bboxes/time windows) and the full evaluation framework. Task YAML files under `benchmark/tasks/` are the machine-readable counterparts.

---

## 2. Consolidated access pattern taxonomy

Pattern IDs follow v2.1 with `C1` sharpened:

| ID | Pattern | Family | Notes |
|---|---|---|---|
| `C1` | Virtual Zarr via **earthaccess virtualization** (`earthaccess.virtualize`) | Cloud-native | Requires EDVS grade A/B. Manual VirtualiZarr/kerchunk = C1-equivalent |
| `C2` | Native Zarr store | Cloud-native | e.g. ITS_LIVE datacubes served as Zarr |
| `C3` | Cloud-Optimized GeoTIFF | Cloud-native | e.g. HLS, ECOSTRESS |
| `C4` | Parquet / Arrow | Cloud-native | Tabular/point collections |
| `C5` | Server-mediated cloud streaming | Cloud-native | e.g. TileDB/zarr streaming services |
| `S1` | Harmony subsetting | Subsetting | Async; NetCDF4/Zarr/GeoTIFF outputs |
| `S2` | OPeNDAP (Hyrax/Cloud) | Subsetting | DAP2/DAP4 server-side slicing |
| `S3` | OPeNDAP-in-the-Cloud (DMR++) | Subsetting | Range requests over sidecar metadata |
| `S4` | AppEEARS | Subsetting | LP DAAC area/point/time-series sampling |
| `S5` | Giovanni | Subsetting | Pre-aggregated atmospheric products |
| `S6` | EDSC client-side subsetting | Subsetting | Granule filtering before download |
| `T1` | OPeNDAP streaming (DAP4) | Streaming | Sequential reads from Hyrax |
| `T2` | Zarr streaming | Streaming | xpublish/zarrita |
| `T3` | HTTP range streaming | Streaming | COG / virtual Zarr streaming clients |
| `F1`–`F4` | Spatial / temporal / variable / quality-filtered download | Filtered download | No server-side subsetting |
| `M1`/`M2` | Full granule / full archive download | Materialization | Last resort |

### 2.1 Selection ladder (decision tree, v3)

```
requirement (bbox/time/variables)
  |
  1. EDVS grade A/B? -------------------> C1  (earthaccess virtualization)
  2. Native Zarr endpoint exists? -------> C2
  3. DMR++ sidecars published? ----------> S3
  4. OPeNDAP (Hyrax/Cloud) service? -----> S2 (or T1 for sequential scans)
  5. Harmony-enabled? -------------------> S1
  6. AppEEARS (land point/area)? -------> S4
  7. Giovanni (atmos composition)? -----> S5
  8. else --------------------------------> F1-F4 (metadata-filtered download)
  9. last resort -------------------------> M1 (never M2)
```

Steps 1–5 are "first-class" (C1 outranks OPeNDAP exactly when the score fits). Ties within a step are decided by expected bytes/objects for the requirement. The ladder is a *default*; per-task gold standards may override with justification (e.g. Giovanni's pre-aggregation makes it *best* for a regional monthly mean).

---

## 3. Oracle architecture

| Oracle | Source | Status in v3 | Storage |
|---|---|---|---|
| Virtualizability | EDVS project | **Parquet, primary** | `benchmark/data/virtualizability.parquet` |
| Service availability | CMR service associations (`/search/services.umm_json`) | Live query at build time, cached snapshots | `eab matrix --cmr <short_name>` |
| DAAC capabilities | Manual curation | Curated YAML, `verified: false` until checked | `benchmark/oracles/services.yaml` |
| Live probes | Service reachability | Deferred (runtime probe before evaluation) | — |

`ServiceAvailabilityMatrix` combines them per collection; `VirtualizabilityOracle` is authoritative for `C1` availability (that is exactly "does the archive fit the bill").

---

## 4. Scoring (unchanged weights from v2.1)

| Category | Weight |
|---|---:|
| Collection selection | 10% |
| Service discovery | 15% |
| **Access pattern** | **35%** |
| Representation | 15% |
| Efficiency | 15% |
| Minimal science gate | 10% |

Per-pattern efficiency envelopes have code-level defaults, overridable per task. Full spec: `docs/tasks-and-evals.md`.

---

## 5. Repository structure (v3)

```
earth-agent-bench/
├── pyproject.toml
├── README.md
├── docs/
│   ├── general-plan.md            # v1 (historical)
│   ├── refined-plan.md            # v2.1 (historical)
│   ├── consolidated-plan.md       # v3 (this file)
│   └── tasks-and-evals.md         # task suite + evaluation spec
├── src/earth_agent_bench/
│   ├── patterns.py                # pattern registry
│   ├── schemas.py                 # pydantic task/gold/result models
│   ├── tasks.py                   # task loading + validation
│   ├── cli.py                     # eab validate | matrix | score
│   ├── oracles/
│   │   ├── virtualizability.py    # EDVS parquet oracle
│   │   ├── services.py            # curated YAML service catalog
│   │   ├── cmr.py                 # live CMR service associations
│   │   └── service_matrix.py      # combined matrix + selection ladder
│   └── scoring/
│       ├── access_pattern.py      # tier scoring (1.0/0.7/0.3/0.0)
│       ├── service_discovery.py
│       ├── efficiency.py          # envelope defaults + scoring
│       └── aggregate.py
├── benchmark/
│   ├── tasks/<sphere>/*.yaml      # 18 grounded tasks
│   ├── oracles/services.yaml      # curated service availability
│   └── data/virtualizability.parquet
├── skills/                        # Earthdata skills (data-access-patterns is the core)
│   ├── data-access-patterns/
│   ├── data-virtualization/
│   ├── earthdata-streaming-vs-download/
│   ├── xarray/
│   └── dask-optimization/
├── mcp/
│   ├── manifest.yaml              # cmr-mcp (ready) · earthaccess-mcp (pending)
│   └── harnesses/                 # per-harness registration examples
├── scripts/
│   └── build_virtualizability_parquet.py
├── experiments/
│   ├── models.yaml                # 9-model roster: 5 local, 2 frontier-open, 2 closed refs
│   ├── harnesses.yaml             # pi / opencode / codex-cli / claude-code + crossing rules
│   ├── conditions.yaml            # baseline / mcp / skills / mcp-skills
│   ├── pilot.yaml                 # 3 tasks × 3 tier-anchored models × 3 harnesses + reference lane
│   ├── full.yaml                  # 9 × 3 × 4 × 18 × N + claude-code lane
│   └── litellm.example.yaml       # single-gateway config stub for all 9 models
├── harbor/
│   ├── harbor.yaml                # harbor CLI command template + agent map + env passthrough
│   ├── README.md                  # package layout + verifier behavior
│   └── generated/                 # eab harbor generate output (gitignored)
├── tests/
└── evaluation/                     # later phases (batch orchestration + statistics)
```

Deferred to later phases: harbor CLI version pinning (the command template in
`harbor/harbor.yaml` is finalized at pilot burn-in), batch matrix orchestration,
and statistics. In place now: the model/harness roster and run matrices
(`experiments/`, v3.1), skills, MCP wiring, the direct single-run runner
(`eab run`), and the Harbor thin wrapper (`eab harbor generate|run`) with an
auto-scoring verifier. The authoritative remaining-work list with acceptance
criteria is `docs/gaps.md`.

### 5.1 Experimental roster (v3.1)

Cost and accessibility are a first-class research axis: open and economical models are the
headline, closed frontier models are the references to beat.

- **Models (9)** in three tiers: `local` (LFM2.5-2.6B, Ornith-1.5-9B, gpt-oss-20B,
  Qwen3.8-27B-GSQ, Tiel-Coder-35B-A3B — all verified HF artifacts, sized for a single
  16–24GB GPU), `frontier_open` (DeepSeek Flash 4.1, GLM 5.3 Flash), and
  `closed_reference` (Claude Sonnet 5.5, GPT Sol) under a shared hard budget cap.
- **All models are served by one LiteLLM gateway** — harnesses never see a provider
  difference; exact provider strings are confirmed at pilot burn-in.
- **Harnesses (4)**: pi, opencode, codex cli (crossed with all nine models) and
  claude code (restricted lane: Sonnet only, per its Anthropic-native binding).
  Capability matrix lives in `experiments/harnesses.yaml`.
- **Run matrices**: pilot (`pilot.yaml`) = 108 + 12 runs; full (`full.yaml`) = 5,832 + 216 runs at 3 trials (tunable).
- **RunManifest** (in `schemas.py`) records model_id, tier, quantization, harness,
  condition, tokens, cost_usd and tokens_per_second for every execution, enabling the
  price-tier and knowledge×tier interaction analyses specified in
  `docs/tasks-and-evals.md` §10.

### 5.2 Execution paths (v3.2)

Two runners, one benchmark core:

- **`eab run`** (direct): builds `runs/<task>/<model>/<harness>/<condition>/trial-N/`
  — rendered instruction with an output contract (agent writes `./output/` +
  `access_summary.json`), harness model/MCP config, skills mount, `manifest.json`,
  `observation.template.json` — then launches the harness headlessly. Best for
  water-testing.
- **`eab harbor generate|run`** (thin Harbor wrapper): renders the same task into a
  Harbor package (`harbor/generated/`, gitignored) — agent environment Dockerfile
  (agent Python stack baked, secrets runtime-injected), condition wiring, and a
  verifier that classifies the run and scores it (`tests/evaluation.json`). The
  harbor command line is a template in `harbor/harbor.yaml`, pinned at pilot.
- Task aliases (`cryo-1`, `atmo-2`, `pilot`, `all`) work across both paths.
- Verifier fidelity is scaffolding-level for now: heuristics over
  `access_summary.json` / operator-filled `observation.json`; real
  instrumentation replaces it (see `docs/quickstart.md` §7).

---

## 6. Core principle

> When an AI agent is asked to access a NASA Earthdata collection for a science-motivated requirement, does giving it operational knowledge about available access services — including whether the archive can be virtualized (EDVS) — cause it to select a more efficient, justified access pattern?

The MCP remains the intervention; the skills the complementary intervention; models/harnesses experimental factors; the **service availability matrix** the ground-truth oracle; the **18 grounded access scenarios** the workload; Harbor the controlled execution environment.
