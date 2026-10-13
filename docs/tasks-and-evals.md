# Earth-Agent-Bench: Task Suite & Evaluation Specification

**Version:** 3.0 (grounded, access-pattern focused)
**Companion:** `docs/consolidated-plan.md`

---

## 0. Two suites, two questions

The repo ships two deliberately separate task suites. They answer different
questions, carry different golds, and are graded by different judges. Both run
through the same `eab harbor` pipeline (same models × harnesses × conditions,
same instrumentation), but the *measurement* differs — do not read one number as
the other.

| | Access-pattern benchmark (`benchmark/tasks/`) | Correctness eval (`experiments/evals/`) |
|---|---|---|
| Count / format | 18 `.yaml` (3 per sphere × 6) | 10 `.md` + `experiments/evals/suite.yaml` |
| Question | did the agent **pick and execute** the best access pattern? | did the agent produce the **single correct value**? |
| Gold | `pattern_tiers` (C1/S1/…) + per-collection services | one typed answer (`label`/`boolean`/`integer`/`string`) |
| Judge | weighted rubric over **observed behavior** (pattern 35% · discovery 15% · representation 15% · efficiency 15% · collection 10% · validation 10%) | deterministic typed equality, LLM-free |
| Output | component scores + overall `reward` 0..1 | `correct`/`covered` → pass@1 + coverage |
| Tests | **process**: access-pattern decision quality under Earthdata constraints | **outcome**: earthaccess API knowledge |
| Run | `eab harbor run <task>` (`eab run` for host-side smoke) | same, plus `eab eval grade` / `eab eval report` |

### 0.1 Why both — the value is orthogonal

- The **eval** suite isolates *knowledge*: given a tiny, unambiguous question
  ("which single function — `open`/`download`/`virtualize`?"), can the agent get
  the right answer? Cheap, fast, deterministic, with a clean pass@1.
- The **benchmark** suite isolates *judgment*: given a real, bounded access
  requirement, does the agent choose and execute the best pattern (C1/S1/…/M1)
  and justify it? Richer, slower, graded on a rubric.
- They fail for different reasons. An agent can know the API (eval passes) yet
  pick a wasteful pattern (benchmark scores low), or execute a reasonable pattern
  yet get a parameter/count wrong (eval fails). Reporting both separates
  "doesn't know the tooling" from "doesn't make the right access decision."
- Coverage matters for both: an infra failure is *uncovered*, never scored wrong.

### 0.2 Can they be graded the same way? No — and that is the point

A single clean value has exactly one right answer, so it takes a **deterministic
typed-equality judge** (normalized label, normalized boolean, numeric with
tolerance, exact string). There is nothing to weight and no partial credit; an
LLM judge would inject a second uncontrolled model.

An access-pattern task has **no single right answer** — there is a tiered ladder
(best / acceptable / marginal / inefficient) across several partially-orthogonal
dimensions (collection, service, lazy vs materialized, bytes). It needs a
**weighted rubric over observed behavior** (what the agent *actually called*, not
what it claimed).

Applying the rubric to a value question mis-scores it (its "validation gate" is
artifact-presence, not answer equality); applying equality to a pattern task is
impossible (there is no scalar to compare). Hence two judges, one per suite.

### 0.3 What each number means

- **Eval → pass@1 and coverage.** `pass@1` = fraction of *covered* attempts whose
  answer equals the gold; `coverage` = fraction that produced an answer (infra
  failures excluded). Read it as "API-knowledge accuracy." Not a rubric score.
- **Benchmark → weighted reward 0..1 and its breakdown.** The dominant term is
  the access-pattern tier (best 1.0 / acceptable 0.7 / marginal 0.3 / else 0.0,
  averaged over the patterns actually used); the rest reward discovering the
  available services, a lazy representation, staying inside efficiency
  envelopes, the right collection, and a passed science gate. **Not** a
  percent-correct score.

To add an eval task, see `experiments/evals/README.md`. Benchmark task anatomy
and the rubric are §1–§9 below.

---

## 1. Design principles

1. **Access-pattern selection is the scored surface.** Each task is a bounded, science-motivated *access requirement*. The science computation is a thin, representative gate (right variable, right extent, right units, trivial aggregation such as a monthly or seasonal mean). We measure "did we choose the best available access pattern(s)," not "did we produce amazing science."
2. **Tasks are grounded and representative.** Every task mirrors a workflow a scientist in that discipline actually runs: real collection short names, real regions, real event windows, real variables, and the standard discipline aggregation. The workflow narrative is part of each task definition.
3. **Many source archives are not cloud optimized.** Whether a lazy virtual datacube (`C1`, earthaccess virtualization) is achievable — today or eventually — is decided by the [EarthDataVirtualizabilityScore](https://github.com/alex-s-gardner/EarthDataVirtualizabilityScore) (EDVS), consumed as `benchmark/data/virtualizability.parquet`. Grade `A`/`B` → `C1` available and top priority; `C`/`D`/unknown → blocked, with the recorded `deciding_criterion` as evidence.
4. **earthaccess virtualization (`earthaccess.virtualize`) is first-class**, on par with OPeNDAP and above it whenever the EDVS score fits the collection.
5. **Multi-collection tasks score per-collection patterns** and are averaged; they test pattern selection across mixed availability.

### 1.1 Task anatomy (machine-readable form)

Each task is a YAML file under `benchmark/tasks/<sphere>/` validated against `earth_agent_bench.schemas.Task`:

```yaml
task_id: atmosphere/a1-tempo-no2-florida-2024
science_sphere: atmosphere
title: Monthly tropospheric NO2 over Florida, 2024
discipline_workflow: [ ... representative steps ... ]
access_requirement:
  description: ...
  spatial_extent: {type: bbox, coordinates: [-87.5, 24.5, -80.0, 31.0]}
  temporal_extent: {start: 2024-01-01, end: 2024-12-31}
  variables_of_interest: [tropospheric_no2_vertical_column]
  output_format: netcdf
collections:
  - short_name: TEMPO_NO2_L3
    tier: preferred
    services: [{pattern: C1, available: true, grade: B, source: edvs-parquet}, ...]
pattern_tiers: {best: [C1], acceptable: [S1, S3, S2, S5], marginal: [F1, F2], inefficient: [M1, M2]}
efficiency_envelopes: {}          # optional per-pattern override; code defaults otherwise
validation: {checks: [variable_present, spatial_extent, temporal_extent, units], units: mol m-2}
gold:
  primary_patterns: [C1]
  acceptable_patterns: [S1, S3, S2, S5]
  reasoning: ...
```

The agent sees only `access_requirement` (rendered as an instruction). Everything else is verifier-side.

### 1.2 Task contract (v2): deliver the access code, at demo scope

The scored surface is the **access pattern**, so tasks ask for the **code that gets
the data**, run at the smallest scope that demonstrates the pattern — **not** the
full science result. This removes the artificial load of processing years of
granules (the cause of the timeouts) and keeps the observed-behavior signal.

**Deliverable (every task):**
1. `access.py` — the script that obtains the data with the best available pattern.
2. A **demo output** — run `access.py` on the smallest scope (one day / 2–4 granules
   / one small bbox) and write the artifact.
3. The **access summary** (pattern used, services found, bytes expected).

**Scope rule.** The *science* window (e.g. "2015–2024") stays in the goal prose, but
the **executable ask is a demo slice** — do not process the full range. **Exception:**
a **daily ask** (e.g. "SST over the Gulf of Mexico today") produces the real result
(one granule, quick).

**Task types** (each task declares one, `access_requirement.kind`) — the *ask shape*,
not the access approach (that is graded via `pattern_tiers`):
- `subset` — retrieve a spatial/temporal slice (a swath, a scene, a collocation table).
- `aggregate` — reduce over time (mean/composite/anomaly/series/change/fit).
- `daily` — a single-day ask; the actual result is the deliverable.

**Grading.** The verifier runs `access.py` at demo scope (`verify_exec`/executor →
`ok|error|timeout|oom`), then scores the **observed access events** (as today) plus a
code check (the script uses the sanctioned pattern — earthaccess, virtualize, open —
not raw CMR or direct URL fetches).

#### Task template

```
## Goal
<subset|aggregate|virtualize> <variable> for <region> over <science window>.

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

#### Draft type/scope per task

| task | type | demo scope |
|---|---|---|
| a1 TEMPO NO₂ | aggregate | one day, one granule |
| a2 EMIT CH₄ | aggregate | one plume scene |
| a3 MAIAC AOD | subset | one day over the bbox |
| b1 PNW wildfire | aggregate | one season slice |
| b2 Amazon GPP/SM | aggregate | one month |
| b3 GEDI/Landsat | aggregate | one footprint |
| c1 ITS_LIVE | aggregate | one scene pair |
| c2 PREFIRE | subset | one orbit over Greenland |
| c3 AMSR2 ice | aggregate | one day |
| l1 Phoenix LST | aggregate | one summer day |
| l2 Black Marble | subset | one night |
| l3 Iowa drought | aggregate | one month |
| o1 Chl-a | aggregate | one month |
| o2 MUR SST | **daily** | one day (the real result) |
| o3 SWOT | subset | one swath |
| s1 Türkiye | subset | one interferogram |
| s2 Reykjanes | subset | one scene pair |
| s3 Central Valley | aggregate | one scene pair |

---

## 2. Atmosphere

### A1 — Monthly tropospheric NO₂ over Florida, 2024 (`a1-tempo-no2-florida-2024`)

**Scenario.** Air-quality analyst builds a seasonal NO₂ picture over Florida for 2024 from TEMPO's hourly geostationary observations. The archive is large (17k granules, 12 TB); the regional/monthly slice needed is tiny.

**Representative workflow.** (1) Identify TEMPO L3 tropospheric NO₂ (not total column, not L2). (2) Discover access services for `TEMPO_NO2_L3`. (3) Open the 2024 record over the Florida bbox lazily. (4) Apply main QA flag and cirrus/cloud screening. (5) Monthly means of the tropospheric column. (6) Save small NetCDF.

- **Requirement:** bbox `[-87.5, 24.5, -80.0, 31.0]`; 2024-01-01→2024-12-31; variable `tropospheric_no2_vertical_column` (mol m⁻²); output NetCDF (month × lat × lon).
- **v2 deliverable:** `access.py` at demo scope — kind `virtualize`, one day (one granule). Code, not the full result.
- **Collections:** preferred `TEMPO_NO2_L3` (LARC/ASDC, netCDF-4, **EDVS grade B**, DMR++ published); acceptable `TEMPO_NO2_L2` (then S1/S2); discouraged OMI/OMPS L3 (coarser, different sampling).
- **Gold:** best `C1` (earthaccess virtualization; grade B, blocker only performance-related: "P-md: median 51 blocks in 46 runs"); acceptable `S1` (Harmony), `S3`/`S2` (DMR++ available), `S5` (Giovanni pre-aggregation, if output tolerance permits); inefficient `M1`.
- **Traps:** L2 vs L3; total vs tropospheric column; downloading all hourly granules; ignoring QA flags.
- **Gate:** variable present, Florida-only extent, 12 monthly steps, units mol m⁻², QA applied.

### A2 — EMIT methane plume screening, Permian Basin, 2024 (`a2-emit-methane-permian-2024`)

**Scenario.** Methane monitoring workflow: screen EMIT L2B methane plume-complexity observations over the Permian for 2024 and summarize detected plumes (count, max enhancement) per month.

**Representative workflow.** (1) Identify `EMITL2BCH4PLM` (plume product, not radiance). (2) Filter to bbox + 2024 via granule metadata. (3) Read plume masks/enhancements only. (4) Summarize per month. (5) Save CSV/NetCDF.

- **Requirement:** bbox `[-104.5, 30.5, -101.0, 33.5]`; 2024; variables `ch4_plume_enhancement`, plume mask; output CSV.
- **v2 deliverable:** `access.py` at demo scope — kind `subset`, one plume scene. Code, not the full result.
- **Collections:** preferred `EMITL2BCH4PLM` (LP DAAC/JPL, netCDF-4, EDVS grade TBD-not-sampled); discouraged `EMITL1BRAD` (radiance is not methane enhancement).
- **Gold:** best `S1` (Harmony subsetting, if association verified) or `S2`/`S3` (OPeNDAP/DMR++); acceptable `F1`+`F2` (granule filtering — plume product is per-scene and sparse); inefficient `M1`. *Verbatim tiers pinned when the service oracle entry is verified; curated default recorded in YAML.*
- **Traps:** confusing radiance with enhancement; full-scene downloads; ignoring QA bit flags.
- **Gate:** plume variable present, Permian extent, 2024 only, units ppb·m (or as-declared), monthly summary present.

### A3 — Canadian wildfire smoke AOD over the eastern US, June 2023 (`a3-maiac-aod-eastern-us-2023`)

**Scenario.** Air-quality event analysis: MODIS MAIAC AOD over the eastern US during the June 2023 Canadian smoke episode; daily maps + episode mean.

**Representative workflow.** (1) Identify `MCD19A2` (MAIAC AOD, HDF4, tiled). (2) Discover that virtualization is blocked (EDVS grade C: chunk misalignment across granules). (3) Choose server-side subsetting (Harmony) or DMR++ range reads. (4) QA-filter AOD. (5) Daily maps + episode mean. (6) Save NetCDF.

- **Requirement:** bbox `[-90.0, 35.0, -70.0, 45.0]`; 2023-06-01→2023-06-30; variable `AOD_550` (dimensionless); output NetCDF.
- **v2 deliverable:** `access.py` at demo scope — kind `subset`, one day over the bbox. Code, not the full result.
- **Collections:** preferred `MCD19A2` (LP DAAC, **EDVS grade C — chunk misalignment**); discouraged global MCD19A2 variants.
- **Gold:** best `S1` (Harmony — virtualization blocked per parquet); acceptable `S3`/`S2` (DMR++ available); marginal `F1` (tile filtering); inefficient `M1`.
- **Traps:** attempting `C1` despite grade C; global-tile downloads; wrong AOD band; no cloud/QA filtering.
- **Gate:** AOD variable, eastern-US extent, June 2023 only, dimensionless units, QA applied.

---

## 3. Cryosphere

### C1 — Jakobshavn Isbrae velocity, 2015–2024 (`c1-itslive-jakobshavn-2015-2024`)

**Scenario.** Glaciologist extracts a decade of ice velocity at Jakobshavn for a speed-up time series. ITS_LIVE also publishes **native Zarr datacubes** over the netCDF archive — the classic "don't download GeoTIFFs" case.

**Representative workflow.** (1) Identify ITS_LIVE velocity (`NSIDC-0776` mosaics + datacubes). (2) Prefer the Zarr datacube or virtualize the netCDF archive. (3) Regional lazy read of `vx`,`vy`. (4) Annual means. (5) Save NetCDF.

- **Requirement:** bbox `[-52.0, 68.5, -48.0, 70.0]`; 2015-01-01→2024-12-31; variables `vx`, `vy` (m yr⁻¹); output NetCDF.
- **v2 deliverable:** `access.py` at demo scope — kind `virtualize`, one scene pair. Code, not the full result.
- **Collections:** preferred `NSIDC-0776` (NSIDC, netCDF-4, **EDVS grade B**, blockers: some arrays absent across granules + time dim to add — a cube over `vx`/`vy` is available) and ITS_LIVE Zarr datacube endpoint (native `C2`); discouraged ITS_LIVE GeoTIFF mosaics (would force F1/M1).
- **Gold:** best `C2` (native Zarr datacube) or `C1` (earthaccess virtualization over the netCDF record; grade B); acceptable `S1` (Harmony ITS_LIVE service); inefficient `M1` (GeoTIFF downloads).
- **Traps:** downloading thousands of GeoTIFFs; missing the Zarr datacube; wrong variable pairing (vx/vy vs speed only).
- **Gate:** vx & vy present, Jakobshavn extent, 2015–2024, units m yr⁻¹, annual steps.

### C2 — PREFIRE ⊗ MODIS cloud-screened radiance collocation, Greenland winter 2024 (`c2-prefire-modis-greenland-2024`)

**Scenario.** Far-IR validation study: collocate PREFIRE L1b radiance with cloud-cleared MODIS observations over Greenland in winter 2024. Two collections, two access paths, one collocation product.

**Representative workflow.** (1) Identify `PREFIRE_SAT1_2B-Radiance` and `MOD35_L2` cloud mask. (2) Subset each to Greenland + Jan–Mar 2024. (3) Time/space match (±30 min, 25 km). (4) Apply MODIS cloud mask to PREFIRE footprints. (5) Save matched table (Parquet/CSV).

- **Requirement:** bbox `[-55, 59, -20, 84]`; 2024-01-01→2024-03-31; PREFIRE radiance + MOD35 cloud fraction/flags; output Parquet.
- **v2 deliverable:** `access.py` at demo scope — kind `subset`, one orbit over Greenland. Code, not the full result.
- **Collections:** preferred `PREFIRE_SAT1_2B-Radiance` (NSIDC, netCDF) + `MOD35_L2` (LAADS); both curated with `verified: false` service entries.
- **Gold:** best `S1`+`S1` (Harmony subsetting for both, if associations verified) with `S2`/`S3` acceptable for MOD35 (LAADS DMR++); marginal `F1`+`F2` metadata filtering; inefficient `M1` (winter = thousands of MODIS swaths).
- **Traps:** downloading whole MOD35 granules for a polar winter window; no time matching; ignoring swath-vs-granule geometry.
- **Gate:** both variables present, Greenland/winter extents, match tolerance met, cloud mask applied.

### C3 — Beaufort Sea ice concentration, melt season 2024 (`c3-amsr2-beaufort-2024`)

**Scenario.** Sea-ice analyst tracks 2024 melt onset and September minimum in the Beaufort Sea from AMSR2 L3 12.5 km grids. Grade-B archive whose only blocker is a missing time dimension — exactly what earthaccess virtualization repairs.

**Representative workflow.** (1) Identify `AU_SI12`. (2) Virtualize the record (grade B, "T: no time dimension" — the time axis is added when the store is built). (3) Regional daily series Apr–Sep. (4) Melt-onset + September-minimum diagnostics. (5) Save NetCDF.

- **Requirement:** bbox `[-160, 68, -120, 78]`; 2024-04-01→2024-09-30; variable sea-ice concentration (%); output NetCDF.
- **v2 deliverable:** `access.py` at demo scope — kind `subset`, one day. Code, not the full result.
- **Collections:** preferred `AU_SI12` (NSIDC, HDF-EOS5+ASCII, **EDVS grade B**, blocker "T: no time dimension"); acceptable `AU_SI6`.
- **Gold:** best `C1` (earthaccess virtualization; B fits the bill); acceptable `S1` (Harmony NSIDC); marginal `F1`; inefficient `M1`.
- **Traps:** downloading the global daily archive; missing land/ocean masks; pole-hole handling.
- **Gate:** concentration variable, Beaufort extent, Apr–Sep 2024, units %, daily steps.

---

## 4. Biosphere

### B1 — PNW wildfire vegetation recovery, 2020–2023 (`b1-pnw-wildfire-recovery-2020-2023`)

**Scenario.** Disturbance ecologist computes dNBR trajectories after the 2020 Oregon fires using HLS (Harmonized Landsat Sentinel-2) surface reflectance.

**Representative workflow.** (1) Identify `HLSL30`/`HLSS30`. (2) Discover COG layout (EDVS grade B, COG, blockers: no dimension names / per-tile grids). (3) Read only NIR/SWIR2 bands over burned area + reference period. (4) NBR/dNBR per 16-day step. (5) Recovery curve + map. (6) Save GeoTIFF + CSV.

- **Requirement:** bbox `[-124, 44, -118, 49]`; 2020-06-01→2023-10-31; variables NIR, SWIR2 reflectance; output GeoTIFF.
- **v2 deliverable:** `access.py` at demo scope — kind `aggregate`, one season slice. Code, not the full result.
- **Collections:** preferred `HLSL30`, `HLSS30` (LP DAAC, COG, **EDVS grade B**); acceptable Landsat C2 ARD tiles.
- **Gold:** best `C3` (COG band-specific range reads) or `S4` (AppEEARS serves HLS area/time-series sampling); acceptable `S1` (Harmony HLS); inefficient `M1` (full scenes; the archive is 16–22M granules).
- **Traps:** full-scene downloads; reading all bands; no BRDF/cloud masking; wrong tile grid.
- **Gate:** NBR derived from correct bands, fire-region extent, 2020–2023 window, dimensionless NBR units.

### B2 — Amazon GPP ⊗ SMAP soil moisture anomalies, 2023 (`b2-amazon-gpp-soilmoisture-2023`)

**Scenario.** Carbon–water coupling study: 2023 GPP (MOD17A2H) and SMAP L4 soil moisture (SPL4SMGP) anomalies against a 2018–2022 baseline over the Amazon.

**Representative workflow.** (1) Identify `MOD17A2H` + `SPL4SMGP`. (2) Access 2018–2023 records for both. (3) Regrid SMAP to MODIS grid (or coarse-aggregate). (4) 2023 anomalies vs baseline. (5) Correlation map. (6) Save NetCDF.

- **Requirement:** bbox `[-75, -10, -50, 5]`; baseline 2018-01-01→2022-12-31 + 2023; variables GPP (kg C m⁻² 8-day⁻¹), soil moisture (m³ m⁻³); output NetCDF.
- **v2 deliverable:** `access.py` at demo scope — kind `virtualize`, one month. Code, not the full result.
- **Collections:** preferred `MOD17A2H` (LP DAAC, HDF4) + `SPL4SMGP` (NSIDC, HDF5, **EDVS grade B**, blockers: time-var-without-time-dim + chunk metadata — cube-able).
- **Gold:** best `C1` for SPL4SMGP + `S1` for MOD17A2H; acceptable `S2`/`S3` where DMR++ exists; marginal `F1`/`F2`; inefficient `M1`.
- **Traps:** scale factors (GPP ×0.0001); grid/resolution mismatch; units; downloading global HDF4 tiles.
- **Gate:** both variables, Amazon extent, correct baseline window, units as declared, anomalies computed.

### B3 — GEDI ⊗ Landsat canopy change, Sierra Nevada 2019–2023 (`b3-gedi-landsat-canopy-2019-2023`)

**Scenario.** Forest structure change: GEDI L2B canopy cover footprints joined with HLS reflectance over Sierra Nevada managed forests.

**Representative workflow.** (1) Identify `GEDI02_B` + `HLSL30`. (2) Sample GEDI footprints (point data → AppEEARS point sampling or granule filtering). (3) Read HLS tiles for the same area/period. (4) Join footprint↔pixel; annual canopy-cover change. (5) Save Parquet.

- **Requirement:** bbox `[-121, 36, -118, 40]`; 2019-04-01→2023-12-31; variables GEDI canopy cover fraction (%), HLS reflectance; output Parquet.
- **v2 deliverable:** `access.py` at demo scope — kind `subset`, one footprint. Code, not the full result.
- **Collections:** preferred `GEDI02_B` (LP DAAC, HDF4) + `HLSL30` (COG, EDVS B); acceptable `GEDI_L4B_AGB_Density` (biomass framing).
- **Gold:** best `S4` for GEDI (AppEEARS point sampling) + `C3` for HLS; acceptable `S1`; marginal `F1`; inefficient `M1` (GEDI orbit granule sprawl).
- **Traps:** footprint/raster confusion; beam/shot QA; geolocation matching; full-orbit downloads.
- **Gate:** footprint variable present, region/period correct, join tolerance met, cover units %.

---

## 5. Ocean

### O1 — California Current chlorophyll during the 2023 heatwave (`o1-chlorophyll-ca-current-2023`)

**Scenario.** Ocean-color heatwave analysis: 2023 chlorophyll vs 2018–2022 monthly climatology in the California Current. The L3m archive is EDVS grade **D** (chunk shapes differ across granules for `chlor_a`) — virtualization is off the table, and the agent must find the next-best service.

**Representative workflow.** (1) Identify `MODISA_L3m_CHL`. (2) Check parquet: grade D, H2 blocker → `C1` unavailable. (3) Use OPeNDAP/DMR++ or Harmony if verified, else tightly-filtered daily downloads. (4) Monthly means; 2023 vs climatology anomalies. (5) Save NetCDF.

- **Requirement:** bbox `[-130, 33, -115, 45]`; baseline 2018-01-01→2022-12-31 + 2023; variable `chlor_a` (mg m⁻³); output NetCDF.
- **v2 deliverable:** `access.py` at demo scope — kind `virtualize`, one month. Code, not the full result.
- **Collections:** preferred `MODISA_L3m_CHL` (OB.DAAC, netCDF-4, **EDVS grade D — "H2: chunk shape differs across granules (chlor_a: [44,87] vs [16,1024])"**).
- **Gold:** best `S2`/`S3` (OB.DAAC OPeNDAP; verify association) or `S1` if verified; marginal `F2` (daily-file temporal filtering); inefficient `M1`.
- **Traps:** attempting virtualization on a D-grade archive; missing land/cloud flags; wrong climatology window.
- **Gate:** `chlor_a` present, California Current extent, correct windows, units mg m⁻³, anomalies + climatology produced.

### O2 — Great Barrier Reef thermal stress, 2024 (`o2-mur-sst-gbr-2024`)

**Scenario.** Coral thermal-stress monitoring: daily MUR SST over the GBR for austral summer 2023–24, degree-heating-week style accumulation. Grade-B archive that is cube-able over `analysed_sst` (the H2 blocker affects only `dt_1km_data`).

**Representative workflow.** (1) Identify `MUR-JPL-L4-GLOB-v4.1`. (2) Virtualize; read only `analysed_sst` (stable chunking per parquet evidence). (3) GBR daily series. (4) Thermal-stress accumulation vs bleaching threshold. (5) Save NetCDF.

- **Requirement:** bbox `[142, -25, 155, -8]`; 2023-12-01→2024-03-31; variable `analysed_sst` (K); output NetCDF.
- **v2 deliverable:** `access.py` at demo scope — kind `daily`, today, Gulf of Mexico (real result). Code, not the full result.
- **Collections:** preferred `MUR-JPL-L4-GLOB-v4.1` (PODAAC, netCDF-4, **EDVS grade B**, DMR++ yes); acceptable `MUR25-JPL-L4-GLOB-v4.1`.
- **Gold:** best `C1` (earthaccess virtualization over the stable variable); acceptable `S3`/`S2` (DMR++), `S1` (Harmony); inefficient `M1` (global 1-km grids).
- **Traps:** global-grid downloads; reading the misaligned `dt_1km_data`; K vs °C; wrong accumulation definition.
- **Gate:** `analysed_sst` present, GBR extent, summer window, units K, daily steps + accumulated stress.

### O3 — SWOT vs conventional altimetry, Gulf Stream 2023 (`o3-swot-altimetry-gulfstream-2023`)

**Scenario.** Altimetry validation: compare SWOT KaRIn swath SSH with the gridded two-satellite reference altimetry over the Gulf Stream for 2023.

**Representative workflow.** (1) Identify `SWOT_L2_LR_SSH_Expert_2.0` + `SEA_SURFACE_HEIGHT_ALT_GRIDS_L4_2SATS_5DAY_6THDEG_V_JPL`. (2) Subset swaths and grids to region/year. (3) Interpolate gridded SSH to swath points. (4) Difference statistics. (5) Save NetCDF.

- **Requirement:** bbox `[-80, 30, -60, 45]`; 2023-04-01→2023-12-31; variables swath SSH (m), gridded SLA (m); output NetCDF.
- **v2 deliverable:** `access.py` at demo scope — kind `subset`, one swath. Code, not the full result.
- **Collections:** preferred `SWOT_L2_LR_SSH_Expert_2.0` (PODAAC) + gridded reference (PODAAC, DMR++ yes).
- **Gold:** best `S1`+`S1` (Harmony for both, if verified) or `S3` for the gridded product; acceptable `F1` for swaths (pass-filtered); inefficient `M1`.
- **Traps:** pass/cycle sprawl; geoid vs SSH vs SLA confusion; interpolation across grid gaps.
- **Gate:** both SSH fields present, Gulf Stream extent, 2023 window, units m, collocation tolerance met.

---

## 6. Solid Earth

### S1 — Türkiye earthquake coseismic displacement, Feb 2023 (`s1-turkiye-earthquake-2023`)

**Scenario.** Geodesist extracts Sentinel-1 interferometric displacement for the Feb 6, 2023 Pazarcak earthquake. ASF GUNW products have **no Harmony/OPeNDAP path** — the correct behavior is aggressive granule filtering via the archive API (frame, date, path), then reading only the unwrapped-phase datasets.

**Representative workflow.** (1) Identify ASF GUNW collection (`SENTINEL-1_INTERFEROGRAMS`). (2) Discover no subsetting service exists (curated oracle). (3) Filter granules: bbox + Feb 2023 + relevant frames/paths. (4) Read unwrapped phase/coherence only. (5) Coseismic displacement map. (6) Save GeoTIFF.

- **Requirement:** bbox `[35.5, 36.5, 38.5, 39.5]`; 2023-02-01→2023-02-28; variables unwrapped phase, coherence; output GeoTIFF.
- **v2 deliverable:** `access.py` at demo scope — kind `subset`, one interferogram. Code, not the full result.
- **Collections:** preferred `SENTINEL-1_INTERFEROGRAMS` (ASF, netCDF-4 on cloud); acceptable OPERA CSLC-based pairs (region-dependent).
- **Gold:** best `F1`+`F4` (metadata/quality-filtered granule selection via archive API — no server-side subsetting exists); acceptable tightly-scoped `M1`; wrong `M1` (whole-region bulk download) scores 0 on access. `C1` is unavailable (not sampled in EDVS; curated oracle: no).
- **Traps:** bulk-downloading all GUNWs over Anatolia; ignoring perpendicular baseline; coherence threshold skipped.
- **Gate:** displacement variable present, epicentral region, Feb 2023, units rad or m, coherence applied.

### S2 — Reykjanes inflation time series, 2023–2024 (`s2-reykjanes-inflation-2023-2024`)

**Scenario.** Volcano deformation monitoring: InSAR time series over Reykjanes during the Nov 2023–Apr 2024 inflation/eruption sequence.

**Representative workflow.** (1) Same collection family as S1. (2) Filter to peninsula + window. (3) Stack unwrapped phase → displacement per date. (4) Reference-frame correction to a stable area. (5) Save NetCDF.

- **Requirement:** bbox `[-24.5, 63.8, -21.5, 64.5]`; 2023-11-01→2024-04-30; variables unwrapped phase, coherence; output NetCDF.
- **v2 deliverable:** `access.py` at demo scope — kind `subset`, one scene pair. Code, not the full result.
- **Gold:** as S1 — best `F1`+`F4`, acceptable scoped `M1`; reference-frame handling is a gate item.
- **Traps:** reference-frame omission; tropospheric ramp ignored; bulk downloads.

### S3 — Central Valley subsidence, 2015–2024 (`s3-central-valley-subsidence-2015-2024`)

**Scenario.** Hydrogeology: long-term InSAR subsidence velocity for the Central Valley. OPERA DISP-S1 (when in coverage) provides ready-made displacement time series; GUNW stacking is the fallback.

**Representative workflow.** (1) Identify `OPERA_L3_DISP-S1_V1` (preferred) or GUNW fallback. (2) Access the 2015/2016–2024 record. (3) Displacement→velocity fit. (4) Save GeoTIFF.

- **Requirement:** bbox `[-121.5, 36.0, -119.0, 37.8]`; 2015-01-01→2024-12-31; variable line-of-sight displacement/velocity; output GeoTIFF.
- **v2 deliverable:** `access.py` at demo scope — kind `virtualize`, one scene pair. Code, not the full result.
- **Collections:** preferred `OPERA_L3_DISP-S1_V1` (ASF/JPL, provisional); acceptable `SENTINEL-1_INTERFEROGRAMS`; note `OPERA_L2_CSLC-S1_V1` is EDVS grade B.
- **Gold:** best `F1` (archive-filtered reads of DISP granules; `C1` pending EDVS sampling of DISP-S1); acceptable scoped `M1`.
- **Traps:** velocity vs displacement confusion; unwrapped-phase 2π ambiguity; bulk GUNW download.

---

## 7. Land Surface & Human Environment

### L1 — Phoenix daytime LST, summers 2015–2024 (`l1-phoenix-lst-uhi-2015-2024`)

**Scenario.** Urban-heat analysis: MODIS LST (MOD11A1) summer daytime composite for Phoenix vs a rural control ring. HDF-EOS2 archive, whole-array chunks (EDVS B) — subsetting services are the efficient path.

**Representative workflow.** (1) Identify `MOD11A1` (not air temperature). (2) Access Jun–Sep records 2015–2024 over metro + ring. (3) QA (emissivity, cloud). (4) Urban−ring ΔLST per summer. (5) Save NetCDF.

- **Requirement:** bbox metro `[-112.8, 33.0, -111.5, 34.1]` (+ rural ring); Jun–Sep 2015–2024; variable `LST_Day_1km` (K); output NetCDF.
- **v2 deliverable:** `access.py` at demo scope — kind `aggregate`, one summer day. Code, not the full result.
- **Collections:** preferred `MOD11A1` (LP DAAC, HDF-EOS2, **EDVS grade B**, DMR++ yes); acceptable `MOD11A2`.
- **Gold:** best `S1` (Harmony ESI) or `C1` (grade B fits, with recorded caveat that whole-array chunks pin the cube shape); acceptable `S3`/`S2` (DMR++); inefficient `M1` (global tiles, 3M granules).
- **Traps:** LST-as-air-temperature; missing QA; K vs °C; global-tile downloads.
- **Gate:** `LST_Day_1km` present, metro+ring extents, summer windows ×10 years, units K, ΔLST computed.

### L2 — Black Marble nighttime-light recovery after Hurricane Ian (`l2-black-marble-ian-2022`)

**Scenario.** Disaster-impact mapping: VIIRS Black Marble (VNP46A2) gap-filled nighttime lights over Florida, Sep 2022–Mar 2023, county-level outage/recovery curve. LAADS cloud-hosted netCDF-4; virtualizability not yet sampled in EDVS — the parquet oracle returns *unknown*, and the agent must fall back to service discovery (curated: DMR++/OPeNDAP preferred).

**Representative workflow.** (1) Identify `VNP46A2` (moonlight-adaptive, gap-filled — not raw DNB). (2) Parquet lookup → grade unknown → `C1` not creditable. (3) Use DMR++/OPeNDAP or Harmony subset. (4) QA (cloud, lunar). (5) County aggregation + outage index. (6) Save CSV+NetCDF.

- **Requirement:** bbox `[-87.5, 24.5, -80.0, 31.0]`; 2022-09-20→2023-03-31; variable gap-filled BRDF-corrected NTL (nW cm⁻² sr⁻¹); output NetCDF.
- **v2 deliverable:** `access.py` at demo scope — kind `subset`, one night. Code, not the full result.
- **Collections:** preferred `VNP46A2` (LAADS); acceptable `VNP46A1` (with own gap filling).
- **Gold:** best `S3`/`S2` (DMR++/OPeNDAP; curated, `verified: false` until checked); acceptable `S1` if verified; `C1` only if a future parquet release grades the collection A/B; marginal `F2`; inefficient `M1`.
- **Traps:** raw DNB vs gap-filled product; moonlight/QA ignored; wrong county aggregation.
- **Gate:** NTL variable present, Florida extent, window correct, units as declared, recovery curve produced.

### L3 — Iowa 2022 drought: SMAP soil moisture ⊗ MODIS ET (`l3-iowa-drought-2022`)

**Scenario.** Agricultural drought characterization: 2022 growing-season SMAP L4 soil moisture + MODIS ET anomalies vs 2018–2022 climatology over the Iowa Corn Belt.

**Representative workflow.** (1) Identify `SPL4SMGP` + `MOD16A2`. (2) Access Apr–Oct 2018–2022. (3) Align grids/units. (4) 2022 anomalies (z-scores). (5) Drought-index map + series. (6) Save NetCDF.

- **Requirement:** bbox `[-96.6, 40.3, -90.0, 43.6]`; Apr–Oct 2018–2022; variables soil moisture (m³ m⁻³), ET (kg m⁻² 8-day⁻¹); output NetCDF.
- **v2 deliverable:** `access.py` at demo scope — kind `virtualize`, one month. Code, not the full result.
- **Collections:** preferred `SPL4SMGP` (NSIDC, HDF5, **EDVS grade B**) + `MOD16A2` (LP DAAC, HDF4).
- **Gold:** best `C1` for SPL4SMGP + `S1` for MOD16A2; acceptable `S3`/`S2` where DMR++ exists; marginal `F1`/`F2`; inefficient `M1`.
- **Traps:** grid mismatch (9 km vs 500 m); ET units/scale; climatology window; global-tile downloads.
- **Gate:** both variables, Iowa extent, growing seasons ×5 years, units declared, anomalies produced.

---

## 8. Task-suite summary

| ID | Task | Primary gold | EDVS grade (preferred coll.) | Key trap |
|---|---|---|---|---|
| A1 | TEMPO NO₂ Florida 2024 | `C1` | B | L2/L3, total/tropospheric, M1 sprawl |
| A2 | EMIT CH₄ Permian 2024 | `S1`/`S2` (verify) | unknown | radiance ≠ enhancement |
| A3 | MAIAC AOD eastern US 6/2023 | `S1` | C (misaligned) | forcing C1 despite grade C |
| C1 | ITS_LIVE Jakobshavn 2015–24 | `C2`/`C1` | B | GeoTIFF M1 sprawl |
| C2 | PREFIRE⊗MODIS Greenland w/2024 | `S1`+`S1` | unknown ×2 | two-collection access |
| C3 | AMSR2 Beaufort 2024 | `C1` | B (T blocker) | time-dim repair via earthaccess |
| B1 | HLS PNW recovery 2020–23 | `C3`/`S4` | B | full scenes, all bands |
| B2 | MOD17⊗SMAP Amazon 2023 | `S1`+`C1` | B (SMAP) | scale factors, grids |
| B3 | GEDI⊗HLS Sierra 2019–23 | `S4`+`C3` | B (HLS) | footprint vs raster |
| O1 | MODISA CHL CA Current | `S2`/`S3` | **D** | C1 blocked by H2 |
| O2 | MUR SST GBR 2023–24 | `C1` | B | wrong variable (dt_1km) |
| O3 | SWOT⊗altimetry Gulf Stream | `S1`/`S3` | unknown | swath+grid mixed access |
| S1 | GUNW Türkiye 2/2023 | `F1`+`F4` | unknown (no service) | bulk GUNW download |
| S2 | GUNW Reykjanes 2023–24 | `F1`+`F4` | unknown (no service) | reference frame |
| S3 | DISP-S1 Central Valley | `F1` | B (CSLC) | velocity vs displacement |
| L1 | MOD11A1 Phoenix 2015–24 | `S1`/`C1` | B | LST ≠ air temp; global tiles |
| L2 | VNP46A2 Ian 2022–23 | `S3`/`S2` | unknown | DNB vs gap-filled |
| L3 | SMAP⊗MOD16 Iowa 2022 | `C1`+`S1` | B (SMAP) | grids/units |

**Pilot suite:** A1 (virtualization-best), A3 (Harmony-best after C1 blocked), C1 (B-grade + native Zarr alternative).

Pattern coverage: `C1` ×7, `C2` ×1, `C3` ×2, `S1` ×9, `S2`/`S3` ×7, `S4` ×2, `F1`/`F4` ×3, `M1` as universal inefficient baseline. Unknown-grade entries are deliberate: they test fallback behavior when the parquet oracle cannot bless `C1`.

---

## 9. Evaluation framework

### 9.1 Scored categories and weights

| Category | Weight | Measure |
|---|---:|---|
| Service discovery | 15% | Fraction of actually-available services surfaced (trajectory evidence) |
| **Access pattern** | **45%** | Observed pattern vs tiers: best 1.0 / acceptable 0.7 / marginal 0.3 / else 0.0 |
| Representation | 15% | xarray-lazy/chunked vs materialized; format fit |
| Efficiency | 15% | Bytes/objects/runtime vs per-pattern envelopes |
| Minimal science gate | 10% | Binary gate: variables, extents, units, required aggregation |

Collection selection is **not** scored — the task names the dataset (see §1.2).
An **unsanctioned deliverable** (raw CMR / no earthaccess) is penalised 0.5× (§1.2).

### 9.2 Pattern observation

The verifier classifies the *observed* pattern from trajectory + access logs, never from agent claims:

- `C1`: `earthaccess.virtualize` / `write_virtual` / `open_virtual` (or VirtualiZarr/kerchunk refs) opened, HTTP range reads over source granules, no full-file downloads
- `C2`/`C3`: direct Zarr-store / COG range access
- `S1`: Harmony job submission + staged output retrieval
- `S2`/`S3`: pydap/netCDF4 DAP or DMR++-backed range reads
- `S4`/`S5`: AppEEARS/Giovanni API calls
- `F*`: granule-list filtering followed by selective downloads
- `M1`: granule downloads without byte-level subsetting beyond file selection

### 9.3 Efficiency envelopes (defaults; per-task overrides allowed)

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

Envelope score = mean of per-metric linear falloff from the envelope limit (1.0 at ≤ limit, 0.0 at ≥ 4× limit).

### 9.4 Verifier output schema

```json
{
  "reward": 0.86,
  "collection_selection": 1.0,
  "service_discovery": 0.75,
  "access_pattern": 0.85,
  "representation": 1.0,
  "efficiency": 0.82,
  "validation": 1.0,
  "access_pattern_details": {"observed": "S1", "best_available": "C1", "gap_reason": "..."},
  "efficiency_metrics": {"bytes_read": 118000000, "objects_read": 5, "runtime_seconds": 240},
  "trajectory_metrics": {"tool_calls": 22, "failed_attempts": 1}
}
```

### 9.5 Validity rule

Every task's expert reference solution must achieve its own gold score (primary pattern, gates passed, envelopes met) before the task enters any experiment. Tasks whose oracle entries are `verified: false` must be verified against CMR/live services at task-build time — the curated `services.yaml` records the verification state.

---

## 10. Model & harness roster (v3.1) — cost and accessibility as a research axis

Open and economical models are the headline of this benchmark, not a footnote. The roster
spans four price tiers so the primary lens is *"how much access-pattern selection
capability survives as cost decreases?"* — closed frontier models are the references to
beat, not the subject.

### 10.1 Roster (`experiments/models.yaml`)

| Tier | Model | Serving | Notes |
|---|---|---|---|
| local (5) | LFM2.5-2.6B Turbo-Brilliance | LiteLLM gateway | 2.6B edge floor; one reasoning mode pinned |
| | Ornith-1.5-9B (Q6_K) | LiteLLM gateway | dense baseline |
| | gpt-oss-20B (MXFP4) | LiteLLM gateway | reasoning effort pinned |
| | Qwen3.8-27B GSQ-RCO (IQ3_S+mtp) | LiteLLM gateway | research quant; avg bit-width recorded |
| | Tiel-Coder-35B-A3B (IQ4_XS) | LiteLLM gateway | local flagship, MoE A3B, MTP |
| frontier_open (2) | DeepSeek Flash 4.1 | LiteLLM | cheap-API tier |
| | GLM 5.3 Flash | LiteLLM | cheap-API tier |
| closed_reference (2) | Claude Sonnet 5.5 | LiteLLM (+ claude-code native lane) | reference to beat; shared $ cap |
| | GPT Sol | LiteLLM | reference to beat; shared $ cap |

Harnesses (`experiments/harnesses.yaml`): **pi, opencode, codex cli** (crossed with all
nine models through one LiteLLM gateway) and **claude code** (restricted lane:
Sonnet only, encoded in a machine-readable capability matrix). Every harness and model
version is pinned at pilot burn-in and recorded in `RunManifest`.

### 10.2 Research questions and hypotheses

**RQ-M1.** How much access-pattern selection capability survives at each price tier
(edge-local → dense-local → flagship-local → cheap open API → closed frontier)?

**RQ-M2.** Is the Earthdata-knowledge effect (MCP / skills) larger for smaller or
cheaper models — i.e., does operational knowledge compensate for model capability?

**RQ-M3.** What is the cost per successful access task at each tier, and where is the
knee of the cost-performance curve?

**H-M1.** Frontier-open API models close most of the gap to closed references at a
small fraction of the cost.

**H-M2.** Knowledge conditions (MCP/skills) yield larger score improvements for
smaller models than for flagship models.

**H-M3.** A well-informed small model (baseline → MCP+skills) matches or beats an
uninformed flagship model (baseline) on access-pattern selection.

### 10.3 Result tables (in addition to §9)

| Tier | Model | Access-pattern score | Overall | Cost/task (USD or kWh) | Tokens/s |
|---|---|---:|---:|---:|---:|

| Condition × tier | edge | dense | flagship-local | open-API | closed |
|---|---:|---:|---:|---:|---:|

The first table answers RQ-M1/M3; the second (condition × tier interaction) answers
RQ-M2 and directly tests H-M2/H-M3. Local-model cost is reported in wall-clock hours
and, where available, GPU energy — USD is zero by construction, which is the point.
