# Task collection verification (WIP)

> **Status: in progress.** Verifies each task's collection(s) against live CMR —
> correct dataset (DOI/summary), processing level (prefer L4 except natively-L2
> products), and **actually-available access services** (Harmony/OPeNDAP/HTTPS).
> Method + scripts are reproducible: `scripts/verify_collections.py`,
> `scripts/resolve_concept_ids.py`.

## Why

The grounded sweep showed the agent failing on **collection grounding** (it
guessed short names like `MCD04AOD` for MAIAC AOD). Collection *selection* is
handled by a separate project, so the tasks should hand the agent the exact
dataset and test only **access-pattern** choice. That requires the dataset ids to
be correct and the declared access patterns to be real.

## Changes applied

1. **Instruction** (`tasks.render_instruction`): added a `## Datasets to use`
   block listing the required dataset(s) with their **CMR `concept_id`**, and
   reframed the ask as *"choose the best access service and pattern for the
   dataset(s) above"* (no more "collection(s) you select").
2. **concept_id embedded** in all 18 task YAMLs (resolved via CMR, cloud-hosted
   preferred) — `scripts/resolve_concept_ids.py --write`.
3. **Two wrong short names fixed** (found by the DOI/level pass):
   - `c2`: `PREFIRE_SAT1_2B-Radiance` → **`PREFIRE_SAT1_1B-RAD`**
     (`C3523946238-LARC_CLOUD`) — PREFIRE radiance is the L1B product.
   - `o3`: `SEA_SURFACE_HEIGHT_ALT_GRIDS_L4_2SATS_5DAY_6THDEG_V_JPL` →
     **`…_V_JPL2205`** (`C2270392799-POCLOUD`) — the version suffix was missing.

## Processing levels (prefer L4, keep natively-L2)

| task | dataset | level | verdict |
|---|---|---|---|
| a1 | TEMPO_NO2_L3 | 3 | gridded L3 preferred over L2 ✓ |
| a2 | EMITL2BCH4PLM | 2B | natively L2B (plume) ✓ |
| a3 | MCD19A2 | 2G | analysis-ready MAIAC grid ✓ |
| b1 | HLSL30 / HLSS30 | 3 | natively L2 COG (HLS) ✓ |
| b2 | MOD17A2H / SPL4SMGP | 4 / 4 | ✓ |
| b3 | GEDI02_B / HLSL30 | 2B / 3 | GEDI natively L2B ✓ |
| c1 | NSIDC-0776 | 3 | ✓ |
| c2 | PREFIRE_SAT1_1B-RAD / MOD35_L2 | 1B / 2 | radiance natively L1B ✓ |
| c3 | AU_SI12 / AU_SI6 | 3 / 3 | ✓ |
| l1 | MOD11A1 / MOD11A2 | 3 / 3 | daily vs 8-day ✓ |
| l2 | VNP46A2 / VNP46A1 | 3 / 3 | ✓ |
| l3 | SPL4SMGP / MOD16A2 | 4 / 4 | ✓ |
| o1 | MODISA_L3m_CHL | 3 | ✓ |
| o2 | MUR-JPL-L4-GLOB-v4.1 | 4 | ✓ |
| o3 | SWOT_L2_LR_SSH_Expert_2.0 / …L4…JPL2205 | 2 / 4 | swath natively L2 + L4 grid ✓ |
| s1/s2 | SENTINEL-1_INTERFEROGRAMS | 2 | natively L2 ✓ |
| s3 | OPERA_L3_DISP-S1_V1 | 3 | ✓ |

All DOIs resolved (e.g. `MCD19A2` = `10.5067/MODIS/MCD19A2.061`), confirming the
datasets match the task intent.

## ⚠ Service availability — the open problem

Declared gold vs **actual** CMR services (Harmony via `has_transforms`; OPeNDAP/
AppEEARS via RelatedUrls):

| task | declared gold | actual services | flag |
|---|---|---|---|
| a1 | S1 | S1 | ok |
| a2 | S1 | — | **Harmony/OPeNDAP not found** |
| a3 | S1 | — | **Harmony/OPeNDAP not found** |
| b1 | C3,S4 | S4 | ok (COG not detected) |
| b2 | S1 | S4 (MOD17A2H), S1 (SPL4SMGP) | **MOD17A2H has no Harmony** |
| b3 | S4,C3 | S4 (HLS), — (GEDI) | GEDI services not detected |
| c1 | C2 | — | services not detected |
| c2 | S1 | — (PREFIRE), S1,S2 (MOD35) | **PREFIRE has no Harmony** |
| c3 | S1 | — | **Harmony/OPeNDAP not found** |
| l1 | S1 | S4 | **Harmony not found (AppEEARS only)** |
| l2 | S3,S2 | S2 | ok |
| l3 | S1 | S1 (SPL4SMGP), S4 (MOD16A2) | **MOD16A2 has no Harmony** |
| o1 | S2,S3 | S1,S2 | ok |
| o2 | S1 | S1,S2 | ok |
| o3 | S1,S1 | S1,S2 (SWOT L2), — (L4 grid) | L4 services not detected |
| s1/s2 | F1,F4 | — | download-based; not detected |
| s3 | F1 | — | download-based; not detected |

`has_transforms=False` for **MCD19A2, MOD11A1, MOD16A2, MOD17A2H, AU_SI12,
EMITL2BCH4PLM, PREFIRE** → their declared `S1` (Harmony) golds are **suspect**.
The correct best pattern is likely **AppEEARS (S4)** where available
(MOD11A1/MOD16A2/MOD17A2H/HLSL30/HLSS30/SPL4SMGP) or **HTTPS download (F1)**
(MCD19A2/AU_SI12/EMIT/PREFIRE).

**Caveat / next step:** a reliable Harmony check needs a proper probe — the CMR
`has_transforms` flag is legacy and the Harmony capabilities endpoint 404'd
(route changed). Until that's nailed, treat the `S1` golds as unverified.

## Re-derivation (applied)

Per the policy **data virtualization → Harmony → OPeNDAP → HTTP subsetting/
aggregation → full download** (AppEEARS/Giovanni excluded as "good"), each task's
`pattern_tiers` + `gold` were re-derived from verified availability
(`scripts/rederive_patterns.py --write`). Signals: virtualization oracle grade
A/B (C1), CMR `has_transforms` (S1), CMR RelatedUrls (S2/S3).

| task | best | task | best |
|---|---|---|---|
| a1 TEMPO NO2 | C1 | l1 Phoenix LST | C1 |
| a2 EMIT CH4 | F1,F2 | l2 Black Marble | S2 |
| a3 MAIAC AOD | F1,F2 | l3 Iowa drought | C1 |
| b1 HLS PNW | C1 | o1 Chl-a | S1 |
| b2 GPP/SM | C1 | o2 MUR SST | C1 |
| b3 GEDI/Landsat | C1 | o3 SWOT SSH | S2 |
| c1 ITS_LIVE | C1 | s1/s2 S1 InSAR | F1,F2 |
| c2 PREFIRE/MOD35 | S1 | s3 OPERA disp | F1,F2 |
| c3 AMSR2 ice | C1 | | |

**Scoring:** `collection_selection` dropped (dataset is given). Weights rebalanced
— `access_pattern` 0.45, `service_discovery` 0.15, `representation` 0.15,
`efficiency` 0.15, `validation` 0.10.

## Remaining follow-ups

1. **Reliable Harmony/OPeNDAP probe** — the CMR `has_transforms` flag is legacy
   and the Harmony `capabilities` route 404'd; nail a real probe and re-check the
   `S1` bests (a1, c2, o1 and the `S1=y` acceptable tiers).
2. **`services` availability** in the task YAMLs still needs the same correction
   (used by `service_discovery`), not just `pattern_tiers`.
3. Persist `access_events.jsonl` and record selected collections (see
   `docs/reports/eab-grounded-sweep-observations.md`).

