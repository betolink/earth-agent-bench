# Task template (v2 contract)

Authoring template for a grounded EAB task. The scored surface is the **access
pattern**, so the deliverable is the **access code** run at a **demo scope**, not
the full science result. See `docs/tasks-and-evals.md` §1.2 for the contract.

## 1. Instruction (what the agent sees)

`render_instruction` produces this from the task YAML:

```
# <title>

<description>

**Dataset(s):**
- <short_name> (concept_id: <C…>)

**Deliverable — write and run `access.py`:**
1. `access.py` obtains the data by the best route.
2. Run it once on the smallest slice that shows the route (<demo scope>) — write the demo artifact to `/app/output/`.
3. Do NOT process the full window — show the route, don't run the study.
- Write `/app/output/access_summary.json`: {"collections": ["SHORT_NAME"], "access_services_used": ["<service>"], "bytes_read_estimate": 0, "route_notes": "why you picked this route"}.

**Access.** Use earthaccess for everything (`earthaccess.login()` takes no arguments) — do NOT probe the raw CMR API or fetch granule URLs directly.

**Target.** bbox [W, S, E, N]; <start> to <end>; product: <…>; variables: <…>; output: <…>; units: <…>.

**Skills.** If your environment provides skills, read the relevant ones first.
```
(`kind: daily` swaps step 2 for "Run it and write the actual result for the single day / region".)

## 2. Task YAML (verifier-side)

```yaml
task_id: <sphere>/<slug>
science_sphere: <atmosphere|cryosphere|biosphere|ocean|solid-earth|land-surface>
title: <...>
kind: <subset|aggregate|daily>                 # NEW: the ask shape (drives the deliverable)
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
