# Adding tasks to grade

EAB has two gradable suites. Put a task in the right one:

| suite | where | graded on |
|---|---|---|
| **grounded** (access-pattern selection) | `benchmark/tasks/<sphere>/<id>.yaml` | the access pattern/service/representation you actually used (dominant), with a thin output-validation gate |
| **correctness eval** (single value) | `experiments/evals/tasks/<id>.md` + `experiments/evals/suite.yaml` | typed-equality on the one value written to `output/answer.txt` |

Sections 1–4 below cover **grounded** tasks (the main study). Section 5 covers
**correctness eval** tasks (the cheap screen); the full eval detail is in
[`experiments/evals/README.md`](../experiments/evals/README.md) and the scoring
contract in [tasks-and-evals](tasks-and-evals.md).

## 1. Instruction (what the agent sees)

`render_instruction` produces this from the task YAML:

```
# <title>

<description>

**Goal — the deliverable is the code, not the science.** Write `access.py` that
gets the data the best way, and run it once on a small slice to prove the route.
We grade the access code, not the computed result.

**Dataset(s):**
- <short_name> (concept_id: <C…>)

**Steps:**
1. Write `access.py`.
2. Run it once on a small slice — write the demo output to `/app/output/`.
   Do NOT process the full window.
- Write `/app/output/access_summary.json`: {...}.

**Slice.** bbox [W, S, E, N]; <demo scope>; variables: <…>; output: <…>; units: <…>.

**Access policy.** Reach the data over HTTPS through `earthaccess` — virtualization,
Harmony, OPeNDAP, or a filtered download. Do not query CMR directly or fetch raw
URLs; downloading whole collections is the last resort.

**Skills.** If your environment provides skills, read the relevant ones first.
```

The access policy restates what the verifier enforces (raw CMR halves the score),
so the instruction and the grader agree. `kind: daily` swaps step 2 for "run it
and write the actual result for the single day/region".

## 2. Task YAML (verifier-side)

```yaml
task_id: atmosphere/a1-tempo-no2-florida-2024
science_sphere: atmosphere                 # atmosphere|cryosphere|biosphere|ocean|solid-earth|land-surface
title: Monthly tropospheric NO2 over Florida, 2024
kind: aggregate                            # subset | aggregate | daily
discipline_workflow:                        # human-readable steps (not graded verbatim)
  - Identify TEMPO L3 tropospheric NO2 (not total column, not L2)
  - Open the 2024 record over Florida lazily, QA/cloud filter, monthly means
access_requirement:
  description: Seasonal NO2 picture, monthly, QA-filtered.
  spatial_extent: {type: bbox, coordinates: [-87.5, 24.5, -80.0, 31.0]}
  temporal_extent: {start: 2024-01-01, end: 2024-12-31}
  demo_scope: {days: 1, granules: 1, note: "one day, one granule"}
  variables_of_interest: [tropospheric_no2_vertical_column]
  output_format: netcdf                      # netcdf|zarr|csv|geotiff|parquet
collections:
  - short_name: TEMPO_NO2_L3
    concept_id: C3685896708-LARC_CLOUD
    tier: preferred                          # preferred|acceptable|discouraged|unacceptable
    role: main
    services:
      - {pattern: S1, available: true, source: "catalog; verify via CMR"}
      - {pattern: C1, available: false, source: edvs-parquet,
         reason: "out-of-region: direct S3 unavailable"}
pattern_tiers:
  best: [S1]                                 # must be an HTTPS-reachable pattern
  acceptable: [S2, S3, S5]
  marginal: [F1, F2]
  inefficient: [M1, M2]
validation:
  units: mol m-2
  aggregation: monthly_mean
  checks: [variable_present, spatial_extent_correct, temporal_extent_correct, units_correct]
gold:
  primary_patterns: [S1]
  acceptable_patterns: [S2, S3, S5]
  reasoning: Harmony server-side subsetting is the best HTTPS path out-of-region.
labels:                                      # optional Harbor dataset metadata
  data_type: gridded                         # gridded|point|swath|vector
  processing_level: L3                       # L2|L3|L4
  length_class: short                        # short|long
  infeasible: false
  difficulty: medium
notes:
  - exact variable name pinned from UMM-Var at build time
```

Key fields (`src/earth_agent_bench/schemas.py`): `access_requirement`, `kind`,
`collections[].tier` + `services[]`, `pattern_tiers`, `validation`, `gold`,
`labels`.

### Labels (interoperability)

`labels` is optional and feeds Harbor `[metadata]` so the suite can be filtered
like other geospatial benchmarks: `data_type` (gridded/point/swath/vector),
`processing_level`, `length_class`, `infeasible`, `difficulty`. The generator
always derives `sphere`, `kind`, gold patterns, collections and `concept_id`s.

### Out-of-region rule (important)

The benchmark runs **outside AWS**, so `C1` (cloud-native direct / S3) is
**unavailable**: mark `C1` services `available: false` and keep `C1` out of
`pattern_tiers`/`gold`. Rank the best **HTTPS** pattern first (Harmony `S1`, else
OPeNDAP `S2`, DMR++ `S3`, Giovanni `S5`). See the pattern codes in
`src/earth_agent_bench/patterns.py`.

## 3. How a grounded task is graded

`earth_agent_bench.scoring.score_run` (weights in `scoring/aggregate.py`) scores
the **observed, instrumented behavior**:

| component | weight |
|---|---|
| `access_pattern` (tier of the pattern you used; best=1.0, acceptable=0.7, marginal=0.3) | 0.45 |
| `service_discovery` | 0.15 |
| `representation` (lazy vs materialized) | 0.15 |
| `efficiency` (bytes/objects/runtime vs the envelope) | 0.15 |
| `validation` (real access + a valid artifact) | 0.10 |

The collection is **given** in the instruction, so collection selection is not
scored. Harbor also emits an all-or-nothing **`pass`** headline: the deliverable
must re-run successfully in the verifier container, use a sanctioned path (not
raw CMR), land on a best/acceptable pattern, and produce real access events.

## 4. Checklist to add a grounded task

1. Create `benchmark/tasks/<sphere>/<id>.yaml` using the shape above.
2. Choose the collection(s) and set `tier` + per-service `available` (no `C1`).
3. Set `pattern_tiers` and `gold` (best first; HTTPS only).
4. Fill `validation` (units, aggregation, checks) and optional `labels`.
5. Validate: `eab validate` (all tasks must pass the schema).
6. Smoke-test the package without a run:
   `eab harbor run <path> --model tiel-coder-35b --harness pi --condition baseline --dry-run`
   then inspect `harbor/generated/<task>/task.toml` and `instruction.md`.
7. Run one real cell: `eab harbor run <path> --model … --harness …` (needs the
   [environment contract](quickstart.md#environment-contract)).
8. Regenerate the published dataset: `eab harbor dataset all`.

Optionally add an oracle/catalog entry so `eab matrix` can reason about the
collection before CMR verification (see `benchmark/oracles/`).

## 5. Adding a correctness eval task

A correctness task is two files and is graded by deterministic typed equality
(never an LLM):

1. **Instruction** — add `experiments/evals/tasks/NN_short_name.md` ending with
   the single-value contract:

   ```
   Express your answer as a single short label (one of: open, download, virtualize).

   Write only that value to ./output/answer.txt (absolute: /app/output/answer.txt), then stop.
   ```

   Never reveal the answer; keep authoring notes in `<!-- authoring … -->`
   (stripped before the agent sees it). Allow metadata search; forbid science
   data I/O for pure decisions.

2. **Gold** — add one entry to `experiments/evals/suite.yaml`:

   ```yaml
   - task_id: 11_modis_resolution
     answer_type: label          # label | boolean | integer | string
     answer: "1km"
     note: "MOD11A1 is 1 km"
   ```

   For values that depend on live CMR (counts), set `answer: null, pinned: false`
   and pin the integer at build time; the grader refuses to score an unpinned
   gold. Use `tolerance` for integers that may vary slightly.

3. **Verify locally** (no model): write the gold into a temp `output/answer.txt`
   and grade it — it must be `1.0`, a wrong answer `0.0`, a missing answer
   *uncovered*:

   ```bash
   mkdir -p /tmp/ws/output && printf '%s' '1km' > /tmp/ws/output/answer.txt
   uv run eab eval grade 11_modis_resolution /tmp/ws/output/answer.txt
   ```

4. **Run it** like any task: `uv run eab harbor run 11_modis_resolution
   --model <id> --harness opencode`.

## 6. Validate and ship a new task

```bash
uv run eab validate                 # schema-check every grounded task
uv run pytest -q                    # incl. prompt-leak + scoring tests
uv run eab instruction <task.yaml>  # inspect exactly what the agent sees
uv run eab harbor run <task> --model <id> --harness opencode --dry-run
uv run eab harbor dataset all       # regenerate the published dataset
```

Checklist for either suite: the task validates, the rendered instruction does
not leak the gold, a dry-run package builds, and one real cell grades without an
infrastructure error.
