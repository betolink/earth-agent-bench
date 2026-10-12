# EAB grounded sweep — observations & improvement backlog (WIP)

> **Status: preliminary.** Numbers are from the in-progress run
> `20261011-005413` (model `tiel-coder-35b`; harnesses `pi` / `opencode` /
> `codex-cli`; conditions `baseline` / `mcp` / `skills` / `mcp-skills` /
> `improve`). At the time of writing: **204 cells indexed** (mostly `pi` +
> early `opencode`). Figures will move; the *patterns* are what matter.

## Headline

The tasks are **not** failing because the agent picks the wrong access pattern.
They fail for three other reasons, in order of impact:

1. **Non-completion** — the agent runs out of the 600 s budget before it performs
   any access (dominant).
2. **Measurement gaps** — the grader can't see behavior the agent *did* produce
   (raw-HTTP access invisible; `representation` always 0).
3. **Collection grounding** — the agent cannot reliably resolve a dataset
   *description* (e.g. "MAIAC AOD") to the canonical CMR **short_name**.

## Observed patterns (evidence)

### 1. Timeouts dominate
- **169 / 204 cells timed out (83%)**; only 35 completed; **44 / 204 scored > 0**.
- Top `gap_reason` is `observed None; best available [S1]` (~164 cells) — the
  verifier saw **no access at all**.
- Median deadline cell: ~55 steps at ~10 s/step on the local 35B, still running
  varied commands at the wall (see the earlier timeout analysis).

### 2. When the agent *does* execute, it usually picks the right pattern
- Of the 35 completed cells, **23 have `access_pattern > 0`** and the observed
  pattern is almost always **S1 = best** (Harmony).
- Best partials: `a3` baseline reward **0.60** (`access_pattern=1.0`,
  `service_discovery=1.0`, `validation=1.0`), `c2` baseline reward **0.80**.
- ⇒ The knowledge/pattern choice works; it's the *finish line* and the
  *measurement* that don't.

### 3. Collection grounding is the weakest link
- Of the 35 completed cells, only **10 have `collection_selection > 0`**.
- **129 / 204 trajectories searched CMR collections via raw HTTP**
  (`cmr.earthdata.nasa.gov/search/collections.json`) with free-text queries;
  **17 explicitly guessed short names** (`cands=[...]`, `short_name_contains`).

**Case study — `a3-maiac-aod-eastern-us-2023`** (gold `MCD19A2`):
```
query: "MAIAC AOD" / short_name_contains=MAIAC   (raw requests → CMR)
guessed: MOD19A2 MCD19A1 MCD19A2 MCD04 MCD04AOD MCD05 MCD06 MCD09
         MCD09GA MCD13A2 MCD13Q1 MCD14A1 MOD04AOD MYD04AOD ...
selected: MCD04AOD   (wrong; then built the whole Harmony pipeline on it)
```
The agent sprays plausible-looking short names, locks onto the first candidate,
and never resolves the real product (`MCD19A2`). The free-text CMR `query=`
parameter does not surface it.

**Other examples** (`SELECTED` vs `GOLD`):
| task | gold | agent selected |
|---|---|---|
| a3 MAIAC AOD | `MCD19A2` | `MCD04AOD` |
| c1 ITS_LIVE | `NSIDC-0776` | *(none)* |
| c3 AMSR2 sea-ice | `AU_SI12`, `AU_SI6` | *(none)* |
| l2 Black Marble | `VNP46A2`, `VNP46A1` | *(none)* |
| o3 SWOT SSH | `SWOT_L2_LR_SSH_Expert_2.0`, … | SWOT *variants* (SALTO, KARIN…) |
| b3 GEDI/Landsat | `GEDI02_B`, `HLSL30` | `GEDI02_B_L2B_AAA_001` (scored 1.0 via substring) |

Two sub-patterns: (a) the canonical short name is non-obvious and the model
doesn't know it; (b) often the agent **records no collection at all** (empty
`access_summary`), so `collection_selection = 0` by absence.

### 4. The instrumentation only credits *library* calls
- `eab_instrument` patches `earthaccess` / `harmony` / `pydap` / `s3fs` /
  `virtualizarr` — **not raw HTTP**. Agents that hit the right service via
  `requests`/`curl` (common) get `observed = None` → zero `access_pattern`.
- The raw `access_events.jsonl` is **not persisted** to the host (0 files under
  `runs/`), so this is hard to audit after the fact.

### 5. `representation` is always 0 (0 / 204)
- A fixed **15% of the weight is never earned**, whichever observation path the
  verifier takes (`unknown` ends up in the scored observation). Looks like a
  wiring gap: the events-derived `lazy`/`materialized` isn't reaching
  `score_run`, and the agent self-report leaves it at the default.

### 6. `validation` is the easiest component
- 44 / 204 cells earn `validation` — agents do write *some* output artifact even
  when the rest fails. It's the only component that scores broadly.

## What we need to improve (backlog)

**A. Measurement fidelity** (highest leverage — makes the scores mean something)
- Instrument **raw HTTP** to Earthdata hosts (or require/encourage the
  library path) so correct service use is observed.
- **Persist `access_events.jsonl`** into the run dir (`artifacts/logs/`) for
  post-hoc debugging.
- Record the **selected collections** in `details.json` (today only the score is
  kept — we had to reconstruct it from trajectories).

**B. Scoring fixes**
- Fix the **`representation`** wiring (0.15 always lost).
- Add a **pattern-only metric** (credit the chosen pattern independently of
  finishing the pipeline) to isolate the skill effect from the time wall.
- Collection normalization: expand **aliases** / concept-id matching (the
  substring rule already rescued `b3`; make it principled).

**C. Collection grounding** (the actual knowledge gap)
- A dedicated **collection-resolution skill**: description → canonical
  `short_name`/`concept_id`, with the reliable lookup path
  (`earthaccess.search_datasets` / CMR `short_name` / the **cmr MCP**) and the
  rule *"resolve, then verify against CMR before building the pipeline."*
- Emphasize the **cmr-mcp** in the `mcp` conditions (baseline had none).
- Consider task metadata: expose the dataset *keywords* so a correct
  description→short_name mapping is discoverable, not guessed.

**D. Budget / completion**
- The 600 s cap is the binding constraint. Either raise it for local models or
  cut per-step cost; run a small **higher-timeout sample** to confirm.
- The **pattern-only** score (B) separates "knew the answer but ran out of time"
  from "didn't know".

**E. Security**
- A trajectory **hardcoded the EDL token literal** into a bash command
  (`tok='eyJ0eXAiOiJKV1Q…'`) → the token is now in run artifacts on disk. Enforce
  env-var use and add a redaction/scrub step over trajectories.

## How to reproduce / inspect

```bash
eab index                                   # -> runs/index.jsonl (per-cell metadata)
eab trajectory -t a3 -m tiel-coder-35b -H pi -c baseline > a3.json
eab trajectory -t a3 -m tiel-coder-35b -H pi --list
```

Sources: `runs/index.jsonl`, `runs/harbor/**/{agent/trajectory.json,verifier/details.json}`,
`src/earth_agent_bench/{scoring,harbor/runtime}`.

## Open questions

- Is the collection gap a *knowledge* problem (model doesn't know `MCD19A2`) or a
  *tooling* problem (no reliable resolution path)? The `mcp` condition should
  answer this — so far `mcp` cells still time out before resolving.
- How much of the timeout is *search/probing* vs *implementation*? Needs the
  pattern-only metric + a step-timeline breakdown.
- Should the grader reward *any* acceptable collection (tier `acceptable`) more
  leniently, or keep the gold strict?
