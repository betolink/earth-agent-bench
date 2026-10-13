# Task template (v2 contract)

Authoring template for a grounded EAB task. The scored surface is the **access
pattern**, so the deliverable is the **access code** run at a **demo scope**, not
the full science result. See `docs/tasks-and-evals.md` §1.2 for the contract.

## 1. Instruction (what the agent sees)

`render_instruction` produces this from the task YAML:

```
# <title>

<description>

## Requirement
- Spatial extent (bbox): [W, S, E, N]
- Temporal extent (science window): <start> to <end>
- Variables of interest: <...>
- Output format: <...>

## Datasets to use
Use the following dataset(s) — this is the required collection; do not search for
alternatives. Resolve access via the CMR concept_id:
- <short_name> (concept_id: <C…>)

## Deliverable
1. Write `access.py` that obtains the data with the best access pattern.
2. Run it on the SMALLEST scope that shows the pattern (one day / a couple of
   granules / one small bbox) and write the demo artifact.
3. Write the access summary (pattern used, services found, bytes expected).
Do NOT process the full time range — demonstrate the pattern, don't run the study.

## Access policy (outside AWS; HTTPS only)
- Use earthaccess for everything (login() no args; never raw CMR or direct URL
  fetches — open() returns an authenticated file object).
- Order: virtualize (DMR++ then native parser) → stream via open() (xarray/h5py) →
  Harmony/OPeNDAP (async, last) → download.
- Be decisive: one search, then act and write; do not loop.

## Skills
If your environment provides skills, READ them before starting and use the ones
relevant to this task.
```

## 2. Task YAML (verifier-side)

```yaml
task_id: <sphere>/<slug>
science_sphere: <atmosphere|cryosphere|biosphere|ocean|solid-earth|land-surface>
title: <...>
kind: <subset|virtualize|aggregate|daily>      # NEW: drives the demo scope
discipline_workflow: [ <representative steps> ]
access_requirement:
  description: <goal prose; the science window may be long>
  spatial_extent: {type: bbox, coordinates: [W, S, E, N]}
  temporal_extent: {start: <YYYY-MM-DD>, end: <YYYY-MM-DD>}   # science window
  demo_scope: {days: 1, granules: 2}            # NEW: the executable slice
  variables_of_interest: [<...>]
  output_format: <netcdf|geotiff|parquet|csv>
collections:
  - short_name: <...>
    concept_id: <C…>
    tier: preferred
    services: [ {pattern: C1, available: true, grade: B, source: edvars-parquet}, ... ]
pattern_tiers: {best: [C1], acceptable: [S1, S3, S2], marginal: [F1, F2], inefficient: [M1, M2]}
validation: {checks: [...], units: <...>}
gold:
  primary_patterns: [C1]
  acceptable_patterns: [S1, S3, S2]
  reasoning: <...>
notes: [ ... ]
```

## 3. Checklist

- [ ] `kind` set; demo scope is small (1 day / 2–4 granules / one bbox).
- [ ] dataset(s) named with a resolved `concept_id` (see `docs/reports/collection-verification.md`).
- [ ] `pattern_tiers` / `gold` re-derived from verified availability.
- [ ] instruction renders the Deliverable + Access policy + Skills blocks.
- [ ] the science window is stated but the executable ask is the demo slice
      (except `kind: daily`, where the real result is the deliverable).
