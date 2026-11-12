# Running the suite & observing progress

Harbor is the **only** execution path. `eab harbor generate|run` builds real
task packages and a JobConfig, then invokes the `harbor` CLI; there is no
host-side runner to keep in sync.

## 0. Prerequisites

Provide the environment contract as env vars or an env-file (never in the repo —
`.env` is gitignored):

```bash
export EARTHDATA_TOKEN=... LITE_LLM_ENDPOINT=https://your-gateway LITE_LLM_API_KEY=...
```

```bash
cp .env.example .env     # fill it in; gitignored
eab doctor               # checks the 3 vars, probes /v1/models, reports log-scope
```

You also need the `harbor` CLI and the agent harnesses (`pi` / `opencode` /
`codex` / `claude`). Nothing is hard-coded to a host or path.

## 0.1 Choose what to run — the master config

Two files split "who" from "which", so adding a model never means editing a task:

| file | question | edit it to… |
|---|---|---|
| `experiments/models.yaml` | **who exists** | add/remove models (id, tier, `litellm_model`, quantization, context) |
| `experiments/run.yaml` | **which to benchmark** | pick roster ids, harnesses, conditions, tasks, trials, concurrency |

Supporting config:

- `experiments/harnesses.yaml` — harness ids, versions, and **crossing
  restrictions** (e.g. `claude-code` only runs `claude-sonnet-5-5`).
- `experiments/conditions.yaml` — `baseline`, `mcp`, `skills`, `mcp-skills`.
- `harbor/harbor.yaml` — Harbor agent ids, gateway kwargs, budgets, resources,
  verifier mode, artifacts.

```bash
eab models list            # roster + tier + served name + whether run.yaml selects it
eab models discover        # what the gateway actually serves
eab models reconcile       # roster -> gateway name check
eab config                 # resolved matrix + cell count
```

Selection precedence: explicit flags > env (`EAB_MODELS`, `EAB_HARNESSES`,
`EAB_CONDITIONS`, `EAB_TASKS`, `EAB_TRIALS`) > `experiments/run.yaml` > defaults.
Use an alternate selection file with `--config <name>` or `EAB_RUN_CONFIG`.

## 1. Run

**One cell** (isolated Harbor job):

```bash
eab harbor run benchmark/tasks/atmosphere/a1-tempo-no2-florida-2024.yaml \
    --model tiel-coder-35b --harness pi --condition baseline
# add --dry-run to only generate + print the command
```

Aliases work too (`atmo-1`, `cryo-2`, `l1`, …) as do sphere directories and
globs.

**Packages only** (no execution):

```bash
eab harbor generate all --condition mcp-skills
```

**A matrix** (the normal path): omit the task argument to use `run.yaml`, and
pass comma lists (or `all`) for any axis:

```bash
eab harbor run                                   # run.yaml selection, all its tasks
eab harbor run --models tiel-coder-35b,ornith-1.5-9b --harnesses pi,opencode
eab harbor run --conditions baseline             # one condition across the matrix
eab harbor run all --models all --conditions baseline --dry-run   # preview
```

`eab harbor run` expands the cartesian product (task × model × harness ×
condition), applies the `harnesses.yaml` crossing restrictions, and prints what
it skipped. Each cell is a distinct job directory under `runs/harbor/`, so runs
never collide; with multiple conditions each condition gets its own generated
package directory (`harbor/generated/<condition>/<task>`), so a `--dry-run`
command stays valid. Pass `--job-name NAME` for a fixed path and `--force` to
replace it (multi-cell runs suffix it per cell).

### Naming: job · cell · trial

| term | what | example |
|---|---|---|
| **job** | one `harbor run` invocation for a task | `eab-a1-…-pi-baseline-20261112-194331` |
| **cell** | one task × model × harness × condition | `a1 … / tiel / pi / baseline` |
| **trial** | a repeat of a cell (`n_attempts`) | trial 2 |

The job name carries the identity (task, model, harness, condition, stamp) and is
what `eab index`, `eab trajectory`, `eab report` and `eab archive` parse.

## 2. Verify (what happens after the agent stops)

The verifier runs in a **separate container** (`verifier_environment_mode:
separate` in `harbor/harbor.yaml`), so the agent never shares a filesystem with
the answer key. Declared artifacts (`/app/output`, `/app/work`, `/app/access.py`,
`/logs/agent`) are re-materialized there at their original paths.

Then:

1. the deliverable (`access.py`) is re-run under the executor with a
   verifier-owned access log (`/logs/verifier/access_events.jsonl`);
2. if that produces no events, the agent's instrumented events under
   `/logs/agent` are used instead;
3. the agent's `access_summary.json` is **never** scored;
4. `reward.json` gets `pass` (all-or-nothing headline) and `score` (weighted),
   and `reward.txt` gets `pass`.

Harbor's trial status and the verifier's `pass` are separate signals: a harness
can exit non-zero (`n_errored_trials`, `NonZeroAgentExitCodeError`) after writing
a valid deliverable, in which case the verifier still re-runs it and scores it.
Read `verifier/details.json` for `exec_status`, `events_source`, `pass_reasons`
and `uncovered`; do not treat an agent exit code as the benchmark result.

## 3. Publish as a Harbor dataset

```bash
eab harbor dataset all
# -> harbor/dataset.toml (digest-pinned tasks) + harbor/metric.py
```

`metric.py` reports the mean `pass`, so the dataset is pass@1-comparable. Any
Harbor install can then pull it:

```bash
harbor datasets download eab/earth-agent-bench
```

## 4. Observe live — the Harbor web viewer

Harbor ships a local web viewer (bundled static frontend, no build needed). It
browses job directories and streams trial trajectories while agents run:

```bash
eab view                       # runs/harbor, jobs mode -> http://127.0.0.1:8080/
eab view runs/archive          # an archived tree
eab view harbor/generated --mode tasks --port 8090   # task definitions
```

`eab view` is a thin wrapper around `harbor view <folder> --jobs`; use `--host
0.0.0.0` to reach it from another machine and `--no-build` to skip a frontend
rebuild. It shows per-trial status, reward, agent trajectory/tool calls, and
verifier logs.

For cross-cell numbers, build the index:

```bash
eab index                    # -> runs/index.jsonl (one record per trial)
eab index -f csv             # -> runs/index.csv
eab report --model tiel-coder-35b
```

Cross-cell queries (the filesystem under `runs/harbor/` is the source of truth):

```bash
jq 'select(.condition=="skills") | {task,reward}' runs/index.jsonl
jq -s 'group_by(.model) | map({model: .[0].model, mean: (map(.reward)|add/length)})' runs/index.jsonl
```

Each record: `task, model, harness, condition, stamp, trial, status
(solved|partial|fail|timeout|error), reward, components{...}, tokens, cost_usd,
steps, times, duration_sec` + artifact paths.

## 5. Inspect a cell (trajectory + metadata)

```bash
eab trajectory -t a3 -m tiel-coder-35b -H pi > traj.json
eab trajectory -t a3 -m tiel-coder-35b -H pi --list
eab trajectory -t a3 -m tiel-coder-35b -H pi -f atif > t.json
# other single artifacts: -f result|reward|details|stdout|raw|session
```

The bundle carries the run identity, agent/model params, condition wiring, the
exact instruction, metrics, verifier details, and the ATIF trajectory. Raw
artifacts live under
`runs/harbor/<job>/<task>__<id>/`: `agent/trajectory.json`, `verifier/*`,
`artifacts/`, `result.json`.

## 6. Analyse a whole run

```bash
eab analyze --model tiel-coder-35b --harness pi
```

Sends the run's trajectories to a judge model in batches and writes a rolling
postmortem plus a fact-checked final report. This is the closest analogue to a
reviewer reading traces for shortcuts.

## 7. Expectations

- **Coverage, not just pass/fail.** Outcomes are `solved | partial | timeout |
  error`. A timed-out cell is *uninformative about capability*, not a wrong answer.
- **Time.** One cell is up to 720 s agent + 600 s verifier. A full
  `18 tasks × models × harnesses × conditions` matrix is many hours on a single
  GPU; screen candidate models on `experiments/evals/tasks` first.
- **Conditions.** `baseline` → `mcp` → `skills` → `mcp-skills`.
- **Out-of-region.** Tasks must be winnable over **HTTPS** only (no S3 / `C1`); a
  task whose best pattern is unreachable is a task bug, not a model failure.
- **Code deliverables** can be graded/sized with the executor:
  `eab exec program.py --timeout 60 --mem-mb 512 --profile scalene` (see
  [executor](executor.md)).

## 8. Housekeeping

- Containers run as **root**, so run artifacts can land `root:root`. Reclaim
  with `scripts/fix-perms.sh`.
- Observability that reads **LiteLLM spend/logs** needs a log/admin-scoped key
  (`eab doctor` flags inference-only keys).
- **Archive a finished/abandoned run:**

  ```bash
  eab archive --dry-run
  eab archive
  eab archive --name pilot-1
  ```
