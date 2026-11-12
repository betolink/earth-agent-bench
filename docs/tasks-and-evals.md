# Task suite & evaluation spec

EAB scores **process** — did the agent choose and execute the best access route —
not scientific novelty. This page is the scoring contract; how to author a task
lives in [adding-tasks](adding-tasks.md).

## 1. Two suites

Both run through the same Harbor pipeline and the same model × harness ×
condition matrix. Do not read one number as the other.

| | Access-pattern benchmark | Correctness eval |
|---|---|---|
| Where | `benchmark/tasks/*.yaml` (18) | `experiments/evals/tasks/*.md` + `suite.yaml` (10) |
| Question | did the agent pick **and execute** the best access route? | did the agent produce the **single correct value**? |
| Gold | `pattern_tiers` (C1/S1/…) + per-collection services | one typed answer (`label`/`boolean`/`integer`/`string`) |
| Judge | observed instrumented behavior → `pass` + weighted `score` | deterministic typed equality, LLM-free |
| Tests | **process** | **outcome** |
| Role | the study | a cheap screen |

- **Benchmark → `pass` (headline) and `score` (0..1).** `pass` is
  all-or-nothing: the verifier re-ran the deliverable successfully in its own
  container, the code used a sanctioned path (no raw CMR), the dominant observed
  pattern is best/acceptable, and real instrumented access occurred. `score` is
  the weighted rubric below. The published dataset metric reports mean `pass`.
- **Eval → pass@1 and coverage.** `pass@1` = fraction of *covered* attempts whose
  answer equals the gold; `coverage` = fraction that produced an answer. An
  infra failure is *uncovered*, never scored wrong.

## 2. Benchmark task contract

Each task names the dataset(s) and asks for **code**, run at **demo scope** —
"show the route, don't run the study" (`kind: daily` asks for the real value):

```
# <title>
<description>
**Goal — the deliverable is the code, not the science.** Write `access.py` …
**Dataset(s):** - <short_name> (concept_id: C…)
**Steps:** 1. Write `access.py`. 2. Run it once on a small slice → /app/output/.
**Slice.** bbox […]; <demo scope>; variables: …; output: …; units: …
**Access policy.** HTTPS via earthaccess; no raw CMR or direct URL fetches.
**Skills.** Read the relevant skills first.
```

The agent sees only the instruction. Everything else (`pattern_tiers`, `gold`,
`validation`, service availability) is verifier-side. The verifier never scores
the agent's `access_summary.json`; only instrumented events count.

## 3. Scoring

### 3.1 Weights (`src/earth_agent_bench/scoring/aggregate.py`)

| Component | Weight | Measure |
|---|---:|---|
| **Access pattern** | **0.45** | Observed pattern vs tiers: best 1.0 / acceptable 0.7 / marginal 0.3 / else 0.0 |
| Service discovery | 0.15 | Fraction of actually-available services surfaced |
| Representation | 0.15 | lazy/chunked vs materialized; format fit |
| Efficiency | 0.15 | Bytes/objects/runtime vs per-pattern envelopes |
| Validation gate | 0.10 | Real access occurred + a valid artifact |

Collection selection is **not** scored — the task names the dataset. An
**unsanctioned deliverable** (raw CMR / no earthaccess) is penalised 0.5× on
`score` **and fails `pass`**.

### 3.2 Pattern observation

The verifier classifies the *observed* pattern from instrumented access events,
never from agent claims. It first re-runs `access.py` in its own container with a
verifier-owned log (`/logs/verifier/access_events.jsonl`); if that yields no
events it uses the agent's instrumented events under `/logs/agent`:

| Pattern | Evidence |
|---|---|
| `C1` | `earthaccess.virtualize` / VirtualiZarr / kerchunk refs; HTTP range reads, no full download |
| `C2` / `C3` | direct Zarr-store / COG range access |
| `S1` | Harmony submission + staged output retrieval |
| `S2` / `S3` | pydap/netCDF4 DAP or DMR++-backed range reads |
| `S4` / `S5` | AppEEARS / Giovanni API calls |
| `F*` | granule-list filtering + selective downloads |
| `M1` | granule downloads without byte-level subsetting |

### 3.3 Efficiency envelopes

Defaults (per-task overrides allowed via `efficiency_envelopes`):

| Pattern | Max bytes | Max objects | Max runtime (s) |
|---|---:|---:|---:|
| C1 | 100 MB | 50 | 300 |
| C2 | 100 MB | 50 | 300 |
| C3 | 250 MB | 80 | 600 |
| S1 | 500 MB | 10 | 600 |
| S2 | 800 MB | 20 | 900 |
| S3 | 500 MB | 50 | 600 |
| S4 | 300 MB | 5 | 900 |
| S5 | 150 MB | 3 | 600 |
| F1–F4 | 5 GB | 500 | 1800 |
| M1 | 50 GB | 5000 | 7200 |

Envelope score = mean per-metric linear falloff (1.0 at ≤ limit, 0.0 at ≥ 4×).

### 3.4 Verifier output

`/logs/verifier/reward.json` (numeric, for Harbor) and `details.json` (full
diagnostics):

```json
{
  "pass": 1.0,
  "reward": 1.0,
  "score": 0.86,
  "service_discovery": 0.75,
  "access_pattern": 1.0,
  "representation": 1.0,
  "efficiency": 0.82,
  "validation": 1.0,
  "access_pattern_details": {"observed_patterns": ["S1"], "best_available": ["S1"]},
  "efficiency_metrics": {"objects_read": 5, "runtime_seconds": 240}
}
```

`reward.txt` carries `pass`. Correctness evals write `reward`/`pass` = 0/1.

## 4. Suite summary

| Task | Sphere | Kind | Collections | Gold | Acceptable |
|---|---|---|---|---|---|
| `atmosphere/a1-tempo-no2-florida-2024` | atmosphere | aggregate | TEMPO_NO2_L3 | `C1` | `S1+S3+S2` |
| `atmosphere/a2-emit-methane-permian-2024` | atmosphere | aggregate | EMITL2BCH4PLM | `F1+F2` | `F3+F4` |
| `atmosphere/a3-maiac-aod-eastern-us-2023` | atmosphere | subset | MCD19A2 | `F1+F2` | `F3+F4` |
| `biosphere/b1-pnw-wildfire-recovery-2020-2023` | biosphere | aggregate | HLSL30+HLSS30 | `C1` | `S1+S3+S2` |
| `biosphere/b2-amazon-gpp-soilmoisture-2023` | biosphere | aggregate | MOD17A2H+SPL4SMGP | `C1` | `S1+S3+S2` |
| `biosphere/b3-gedi-landsat-canopy-2019-2023` | biosphere | aggregate | GEDI02_B+HLSL30 | `C1` | `S1+S3+S2` |
| `cryosphere/c1-itslive-jakobshavn-2015-2024` | cryosphere | aggregate | NSIDC-0776 | `C1` | `S1+S3+S2` |
| `cryosphere/c2-prefire-modis-greenland-2024` | cryosphere | subset | PREFIRE_SAT1_1B-RAD+MOD35_L2 | `S1` | `S3+S2` |
| `cryosphere/c3-amsr2-beaufort-2024` | cryosphere | aggregate | AU_SI12 | `C1` | `S1+S3+S2` |
| `land-surface/l1-phoenix-lst-uhi-2015-2024` | land-surface | aggregate | MOD11A1 | `C1` | `S1+S3+S2` |
| `land-surface/l2-black-marble-ian-2022` | land-surface | subset | VNP46A2 | `S2` | `F1+F2` |
| `land-surface/l3-iowa-drought-2022` | land-surface | aggregate | SPL4SMGP+MOD16A2 | `C1` | `S1+S3+S2` |
| `ocean/o1-chlorophyll-ca-current-2023` | ocean | aggregate | MODISA_L3m_CHL | `S1` | `S3+S2` |
| `ocean/o2-mur-sst-gbr-2024` | ocean | daily | MUR-JPL-L4-GLOB-v4.1 | `C1` | `S1+S3+S2` |
| `ocean/o3-swot-altimetry-gulfstream-2023` | ocean | subset | SWOT_L2_…+SEA_SURFACE_HEIGHT_… | `S2` | `F1+F2` |
| `solid-earth/s1-turkiye-earthquake-2023` | solid-earth | subset | SENTINEL-1_INTERFEROGRAMS | `F1+F2` | `F3+F4` |
| `solid-earth/s2-reykjanes-inflation-2023-2024` | solid-earth | subset | SENTINEL-1_INTERFEROGRAMS | `F1+F2` | `F3+F4` |
| `solid-earth/s3-central-valley-subsidence-2015-2024` | solid-earth | aggregate | OPERA_L3_DISP-S1_V1 | `F1+F2` | `F3+F4` |

Pattern coverage: `C1` ×7 · `C2`/`C3`/`S1`/`S2`/`S3`/`S4` · `F1`/`F4` ×5 · `M1`
as the universal inefficient baseline. The authoritative gold is each task's
YAML; this table is a summary.

## 5. Validity rule

Every task's expert reference solution must achieve its own gold score (primary
pattern, gates passed, envelopes met) before the task enters an experiment.
Curated service entries marked `verified: false` must be checked against live
CMR before their tiers are trusted. Reference solutions and oracle verification
are tracked in [gaps](gaps.md) §4–5.

## 6. Model roster

The roster and price tiers live in `experiments/models.yaml` (run
`eab models list`); research questions and result tables are maintained there and
in the archived plans (`docs/archive/`). The full historical task-by-task spec
(prose, traps, EDVS grades) is in
`docs/archive/consolidated-plan.md`.
