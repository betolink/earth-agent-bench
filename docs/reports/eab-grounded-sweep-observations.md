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

---

## Update (2026-10-12): dataset-given schema + skills (tiel / pi)

Two changes were tested on a fresh `tiel-coder-35b / pi` run (`schema-test-tiel-pi`):

1. **Schema** — each task now states the dataset + `concept_id`; collection
   scoring dropped; `pattern_tiers` re-derived from verified availability
   (virtualization → Harmony → OPeNDAP → HTTP → download).
2. **Skills** — the earthaccess mandate was moved into the skill **description**
   (the only part `pi` injects) plus a login/budget rule.

### Results
| | baseline | skills |
|---|---|---|
| mean reward | 0.117 | 0.038 |
| nonzero | 7/18 | 3/18 |
| timeouts | 13/18 | 15/18 |
| earthaccess calls | ~0 | **256–687/cell** |
| raw CMR | 100–270 | 0–42 |
| `virtualize(` | 0 | 0–39 |

### Findings
- **The description mandate works.** In `skills`, earthaccess went from ~unused to
  256–687 calls/cell, raw CMR collapsed, and the agent **actually virtualizes**
  (0 → 24–39). The agent **never read the `SKILL.md` body** (`read=0`) — `pi`
  injects only the name/description, so the body is effectively decorative.
- **But results got worse.** The agent now does the *right* things and
  **thrashes** — hundreds of earthaccess calls, hitting the ~627 s wall — so
  completion *decreased*. The binding constraint is **budget discipline**, not
  knowledge. Moving the thrashing from raw CMR to earthaccess + expensive
  virtualization attempts did not help completion.
- **Takeaway:** the injected **description** is the whole game for `pi`; it must
  carry a *decisive recipe + budget rule* (one search → act → write), not more
  prose. Applied: `data-access-patterns` description now says
  "one search, then access and write; do not loop," plus a `Budget discipline`
  section in the body.
- **Open:** the 600 s cap is likely too low for virtualization on this model;
  consider a larger cap or a "virtualize only if quick, else Harmony/OPeNDAP" rule.

---

## Headline result: skills work — `tiel-pi` baseline vs skills (2026-10-14)

After the **instrumentation fix** (see `docs/reports/instrumentation-fix.md` — it
was recording **no access events**, so `access_pattern` was always 0) and the
settled setup (goal = the code · `Slice` · neutral wording · earthaccess +
scope-the-request skill), the skills condition finally shows a real effect.

Run `tiel-pi` (stamp `20261013-164623`), model **tiel-coder-35b**, harness **pi**:

| metric | baseline | **skills** |
|---|---|---|
| mean reward | 0.322 | **0.590** |
| nonzero | 13/18 | 16/18 |
| timeouts | 13/18 | 11/18 |
| **access_pattern** | 0.33 | **0.56** |
| **skill body read** | 6/18 | **17/18** |
| earthaccess calls | 6,794 | 11,868 |
| **`virtualize(`** | **0** | **653** |
| harmony | 0 | 850 |
| **raw CMR** | 1,486 | **260** |
| exec `ok` | 5 | 8 |
| code sanctioned | 4 T / 3 F / 9 – | 11 T / 6 – |

**Findings**
- **The skill works.** With it the agent **reads the skill (17/18)** and
  **virtualizes** (`653` calls vs **0** at baseline) → `access_pattern` **0.33 →
  0.56** and the reward nearly **doubles (0.32 → 0.59)**.
- **Raw CMR collapsed** (1,486 → 260) — the earthaccess mandate landed.
- **Baseline never virtualizes (0)** — without the skill the agent's prior is
  discovery + CMR; the *scope-the-request / virtualize-first* skill is what drives
  the better route.
- Completion is still imperfect (11–13/18 timeouts), but the **route quality** —
  the scored surface — improved materially.

**Caveat:** this effect only appeared once **both** (a) the instrumentation was
fixed (so `access_pattern` could score) **and** (b) the skill reached the model
(injected description + the task's "read the skills"). Earlier "skills vs
baseline" deltas were flat because neither held.
