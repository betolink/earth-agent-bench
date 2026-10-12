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

### Named runs, pause & resume

Every run has a **name** (`name:` in `run.yaml`, override `EAB_RUN_NAME`) and a
stamp. The driver writes `runs/manifests/<name>-<stamp>.json` binding the name to
the exact config (models/harnesses/conditions/trials/concurrency + git sha +
start time). `eab config`, `eab index` (`run_name`) and `eab trajectory` surface
it, so cells are attributable. Bump the name when the setup changes (timeout,
sampling) so runs stay comparable.

**Pause / resume** — stop and restart without losing completed cells:

```bash
touch runs/PAUSE          # driver pauses after the current cell (no work lost)
rm    runs/PAUSE          # resumes in place
# Full stop/resume across restarts: relaunch with the same stamp
EAB_RUN_START=20261011-005413 bash scripts/eab-full-run.sh
```

Resume skips any cell whose `result.json` has `n_completed_trials>0`
(`scripts/done_cells.py`, config-driven). A cell killed mid-flight isn't
completed, so it re-runs.

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
  the first `baseline` cells per harness within a couple of hours (`improve` is
  last, after the model's skill is generated).
- **Conditions.** `baseline` (no help) → `mcp` (CMR/earthaccess MCP) → `skills`
  (mounted SKILL.md files) → `mcp-skills` (both) → **`improve`** (skills + mcp + a
  model-specific self-improvement skill). `improve` runs **last**: the driver
  auto-generates the skill from the model's earlier (non-improve) runs right
  before it, so the improve cells actually mount it. Manually:

  ```bash
  eab postmortem <model> --harness all    # -> improvements/<model>/self-improvement/SKILL.md
  eab harbor run <task> --model <model> --harness pi --condition improve
  ```

  `--harness all` aggregates every harness's runs; the default (`pi`) uses only
  that harness. A model with no `improvements/<model>/` dir runs `improve` as
  `mcp-skills` (no model skill).

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
- **Archive a finished/abandoned run** so the dashboard/index only show the active
  one (the dashboard names the active run from its manifest):

  ```bash
  eab archive --name run-20261011-incomplete        # newest run
  eab archive --name pilot-1 --stamp 20261011-005413
  ```

  It moves the run's job dirs, log and manifest under `runs/archive/<name>/`.

## 5. Inspect a cell (trajectory + metadata)

Harbor records everything per trial. Resolve any `(model, harness, task,
condition)` cell without hunting through timestamped dirs:

```bash
# full bundle: metadata + the trajectory  -> traj.json
eab trajectory -t a3 -m tiel-coder-35b -H pi > traj.json
eab trajectory -t a3 -m tiel-coder-35b -H pi -c improve > improve.json

# what exists for this cell (all conditions/runs, newest last)
eab trajectory -t a3 -m tiel-coder-35b -H pi --list

# just the raw ATIF trajectory (no wrapper)
eab trajectory -t a3 -m tiel-coder-35b -H pi -f atif > t.json
# other single artifacts: -f result|reward|details|stdout|raw|session
```

`--task` accepts a unique prefix (`a3`). `--latest` (default) picks the newest
run; `--all` emits a JSON array of every match.

The **bundle** contains:

| key | what |
| --- | --- |
| `run` | task, model, harness, condition, trial, stamp, times, exception |
| `agent` | harness name/version, `model_name`, provider, **`params`** (agent kwargs / sampling), `env` (gateway base URL), mounted skills |
| `condition` | condition semantics (mcp / skills / improvement + description) |
| `environment` | mcp servers, skills/improvement mounted, agent timeout, task env vars |
| `task` | id, name, description, **`instruction`** (the exact prompt) |
| `metrics` | reward + component scores, input/output/cache tokens, cost |
| `verifier` | `details.json` (observed patterns, best-available, gap reason) |
| `trajectory` | the **ATIF v1.7** trajectory (`steps[]`, `final_metrics`) |

Raw artifacts are also on disk under
`runs/harbor/eab-<task>-<model>-<harness>-<cond>-<stamp>/<trial>/`:
`agent/trajectory.json`, `agent/<harness>.txt`, `agent/<harness>/sessions/*.jsonl`,
`verifier/*`, `result.json`.

## 6. Query across cells (index)

The filesystem is the source of truth; for cross-cell queries build the derived
**JSONL** index (one object per trial) — rebuild it any time, it's not authoritative:

```bash
eab index                    # -> runs/index.jsonl
eab index -f csv             # -> runs/index.csv (flattened, for spreadsheets)

jq 'select(.condition=="improve") | {task,reward}' runs/index.jsonl
jq -s 'group_by(.model) | map({model: .[0].model, mean: (map(.reward)|add/length)})' runs/index.jsonl
```

Each record: `task, model, harness, condition, stamp, trial, status
(solved|partial|fail|timeout|error), reward, components{...}, tokens, cost_usd,
steps, times, duration_sec` + paths (`run_dir`, `trajectory`, `reward_path`,
`details_path`, `result_path`). JSONL keeps the nested `components` intact; use
`-f csv` when you want a single flat table.


