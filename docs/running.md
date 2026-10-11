# Running the suite & observing progress

## 0. Prerequisites

Provide the environment contract as **env vars or a secrets file** (never in the
repo — `.env` is gitignored). Either export them:

```bash
export EARTHDATA_TOKEN=... LITE_LLM_ENDPOINT=https://your-gateway LITE_LLM_API_KEY=...
```

or keep them in an env-file and point the driver at it:

```bash
cp .env.example .env    # fill it in; gitignored
EAB_ENV_FILE=.env bash scripts/eab-full-run.sh
```

Validate before a run:

```bash
eab doctor          # checks the 3 vars, probes /v1/models, reports log-scope
```

You also need the `harbor` CLI and the agent harnesses (`pi` / `opencode` /
`codex` / `claude`). Nothing is hard-coded to a host or path.

## 0.1 Configure which models to benchmark

Two files:

- **`experiments/models.yaml`** — the **roster**: every available model, keyed by
  id, with the name your gateway serves and its tier:
  ```yaml
  models:
    my-model-id:
      tier: local
      litellm_model: local/My-Model   # must be served by LITE_LLM_ENDPOINT
  ```
- **`experiments/run.yaml`** — the **run selection**: which roster ids,
  harnesses, conditions and tasks to run:
  ```yaml
  models: [my-model-id, another-id]
  harnesses: [pi, opencode, codex-cli]
  conditions: [baseline, improve, mcp, skills, mcp-skills]
  tasks: all
  ```

- **Parallelism (`concurrency`)** — how many cells run at once: **`1` = sequential**
  (correct for a single local GPU / single-slot model server), **`>1` = parallel**
  (for models served remotely through the gateway, where the endpoint handles
  concurrent requests). Override with `EAB_CONCURRENCY`. (Within a cell, Harbor
  still runs one trial at a time, and the loop watchdog auto-disables when
  `concurrency > 1` since it's a single-trial helper.)

Everything is **env-overridable**: `EAB_MODELS`, `EAB_HARNESSES`,
`EAB_CONDITIONS`, `EAB_TASKS`, `EAB_TRIALS` (comma-separated), and
`EAB_ENV_FILE`. Preview + validate (rejects ids not in the roster):

```bash
eab config                 # show the resolved matrix + cell count
eab config --shell         # the driver reads this
eab models discover        # list what your gateway actually serves
```

Then run:

```bash
bash scripts/eab-full-run.sh                 # honors run.yaml
# or ad hoc:
EAB_MODELS=my-model-id EAB_CONDITIONS=baseline,improve bash scripts/eab-full-run.sh
```

## 1. Run

**One cell** (isolated Harbor job — the normal path):

```bash
eab harbor run benchmark/tasks/atmosphere/a1-tempo-no2-florida-2024.yaml \
    --model tiel-coder-35b --harness pi --condition baseline
# add --dry-run to only generate + print the command
```

**Packages only** (no execution): `eab harbor generate <tasks> --condition mcp-skills`.

**Whole grounded sweep** (the driver used for the 540-cell matrix):

```bash
bash scripts/eab-full-run.sh
```

It iterates `18 tasks × {models} × {pi, opencode, codex-cli} × {baseline, improve,
mcp, skills, mcp-skills}`, one Harbor job per cell, logging to
`runs/eab-full-<stamp>.log`. It also starts the loop watchdog and reclaims
root-owned run files after each combo.

**Direct runner (no Harbor)**: `eab run <path> --model … --harness …` and
`eab sweep all --models … --harnesses … --conditions all`.

### The loop/stall watchdog (`scripts/loop_watchdog.py`)

Harbor can't interrupt an agent mid-run, so a host-side monitor tails the current
trial and kills its container only when truly stuck:

- **STALL** — no agent output for > `WATCH_STALL` s (default **180**), or
- **LOOP** — the same command (URLs/tokens normalized) ≥ `WATCH_EXACT` times (default **5**).

Otherwise the trial runs to the **600 s** agent cap. Tune via `WATCH_STALL`,
`WATCH_EXACT`. Killed trials surface as an errored cell, so prefer raising the
agent cap or fixing the root cause over aggressive killing.

## 2. Observe — the dashboard

```bash
eab dashboard                 # refresh every 300s
eab dashboard --interval 60
```

```
┌ status: processes · current job · EAB progress n/540 ───────────────┐
│ TOP (50%)   coding matrix + EAB combos ×18   │  coding per-task grid │
├─────────────────────────────────────────────────────────────────────┤
│ BOTTOM (50%)  LIVE agent stream (70%)        │  CURRENT TASK (30%)   │
└─────────────────────────────────────────────────────────────────────┘
```

- **LIVE** (70%) — the running trial's agent stream, condensed to `🧠 thinking /
  ▶ tool / ✓ done` lines; refreshed every 4 s.
- **CURRENT TASK** (30%) — the active task's `instruction.md` (what it's solving).
- **EAB combos** — one row per `model × harness × condition`; cells show
  `✓` pass · partial = yellow · `✗` fail · `⏱` timeout · `·` pending.
- **Ctrl+L** — full run log in a popup. Keys: `r` refresh · `+/-` interval · `s`
  auto · `q` quit. Runs as part of EAB (`earth_agent_bench.dashboard`); the shim
  `tools/bench_dashboard.py` still works.

Also: `eab report` aggregates Harbor runs into a per-model reward + token table;
raw artifacts are under `runs/harbor/<job>/` (`result.json`, `*/verifier/details.json`).

## 3. Expectations

- **Coverage, not just pass/fail.** Outcomes are `solved | partial | timeout |
  stuck`. Watch `AgentTimeoutError`/watchdog kills — a cell that times out is
  *uninformative about capability*, not a wrong answer.
- **Time.** One cell is up to 600 s agent + verifier; the full grounded sweep
  (5 conditions) is ~540 jobs → many hours to a few days on a single GPU. Expect
  the first `baseline`+`improve` pair per harness within a couple of hours.
- **Conditions.** `baseline` (no help) → `skills` (mounted SKILL.md files) →
  `mcp` (CMR/earthaccess MCP) → `mcp-skills` (both) → **`improve`** (skills + mcp +
  a model-specific skill). The `improve` skill is generated per model:

  ```bash
  eab postmortem tiel-coder-35b          # writes improvements/<model>/self-improvement/SKILL.md
  eab harbor run <task> --model tiel-coder-35b --harness pi --condition improve
  ```

- **Out-of-region.** Tasks must be winnable over **HTTPS** only (no S3 / `C1`); a
  task whose best pattern is unreachable is a task bug, not a model failure.
- **Code deliverables** can be graded/sized with the executor:
  `eab exec program.py --timeout 60 --mem-mb 512 --profile scalene` (see
  [executor](executor.md)).

## 4. Housekeeping

- Containers run as **root**, so run artifacts land `root:root`. Reclaim with
  `scripts/fix-perms.sh` (no sudo needed) — the driver already calls it per combo.
- Observability that reads **LiteLLM spend/logs** needs a log/admin-scoped key
  (`eab doctor` flags inference-only keys).
