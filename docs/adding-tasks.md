# Adding tasks

EAB has two suites. Put a task in the right one:

| suite | where | graded on |
|---|---|---|
| **grounded** (access-pattern selection) | `benchmark/tasks/<sphere>/<id>.yaml` | the access pattern/service/representation you actually used (dominant), with a thin output-validation gate |
| **correctness eval** (single value) | `experiments/evals/tasks/<id>.md` + `experiments/evals/suite.yaml` | typed-equality on the one value written to `output/answer.txt` |

This guide is for **grounded** tasks; see [tasks-and-evals](tasks-and-evals.md) §9 for the
eval suite and the full evaluation spec (§1.1 has the deep task anatomy).

## Grounded task anatomy

A grounded task is a small YAML file validated against `earth_agent_bench.schemas.Task`:

```yaml
task_id: atmosphere/a1-tempo-no2-florida-2024
science_sphere: atmosphere                 # atmosphere|cryosphere|biosphere|ocean|solid-earth|land-surface
title: Monthly tropospheric NO2 over Florida, 2024
discipline_workflow:                        # human-readable steps (not graded verbatim)
  - Identify TEMPO L3 tropospheric NO2 (not total column, not L2)
  - Open the 2024 record over Florida lazily, QA/cloud filter, monthly means
access_requirement:
  description: Seasonal NO2 picture, monthly, QA-filtered.
  spatial_extent: {type: bbox, coordinates: [-87.5, 24.5, -80.0, 31.0]}
  temporal_extent: {start: 2024-01-01, end: 2024-12-31}
  variables_of_interest: [tropospheric_no2_vertical_column]
  output_format: netcdf                      # netcdf|zarr|csv|geotiff|parquet
collections:
  - short_name: TEMPO_NO2_L3
    tier: preferred                          # preferred|acceptable|discouraged|unacceptable
    role: main
    services:
      - {pattern: S1, available: true, source: "catalog; verify via CMR"}
      - {pattern: C1, available: false, source: edvs-parquet,
         reason: "out-of-region: direct S3 unavailable"}
  - short_name: TEMPO_NO2_L2
    tier: acceptable
    reason: hourly swath; higher QA burden
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
notes:
  - exact variable name pinned from UMM-Var at build time
```

Key fields (`src/earth_agent_bench/schemas.py`): `access_requirement`,
`collections[].tier` + `services[]`, `pattern_tiers`, `validation`, `gold`.

### Out-of-region rule (important)

The benchmark runs **outside AWS**, so `C1` (cloud-native direct / S3) is
**unavailable**: mark `C1` services `available: false` and keep `C1` out of
`pattern_tiers`/`gold`. Rank the best **HTTPS** pattern first (Harmony `S1`, else
OPeNDAP `S2`, DMR++ `S3`, Giovanni `S5`). See the pattern codes in
`src/earth_agent_bench/patterns.py`.

## How a grounded task is graded

`earth_agent_bench.scoring.score_run` (weights in `scoring/aggregate.py`) scores the
**observed, instrumented behavior** (preferred over the agent's self-report):

| component | weight |
|---|---|
| `access_pattern` (tier of the pattern you used; best=1.0, acceptable=0.7, marginal=0.3) | 0.35 |
| `service_discovery` | 0.15 |
| `representation` (lazy vs materialized) | 0.15 |
| `efficiency` (bytes/objects/runtime vs the envelope) | 0.15 |
| `collection_selection` (preferred/acceptable/...) | 0.10 |
| `validation` (output artifact passes the checklist) | 0.10 |

So a task must let the agent (a) pick a top-tier pattern for the right
collection, (b) *execute* it, and (c) emit a valid artifact. The exact scientific
value is not the score — `validation` is only a 0.10 gate.

## Checklist to add a grounded task

1. Create `benchmark/tasks/<sphere>/<id>.yaml` using the shape above.
2. Choose the collection(s) and set `tier` + per-service `available` (no `C1`).
3. Set `pattern_tiers` and `gold` (best first; HTTPS only).
4. Fill `validation` (units, aggregation, checks).
5. Validate: `eab validate` (all tasks must pass the schema).
6. Smoke-test the package without a run:
   `eab harbor run <path> --model tiel-coder-35b --harness pi --condition baseline --dry-run`
   then inspect `harbor/generated/<task>/task.toml` and `instruction.md`.
7. Run one real cell: `eab harbor run <path> --model … --harness …` (needs the
   [environment contract](quickstart.md#environment-contract)).

Optionally add an oracle/catalog entry so `eab matrix` can reason about the
collection before CMR verification (see `benchmark/oracles/`).
