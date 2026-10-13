# `benchmark/tasks/` — the grounded access-pattern benchmark

The **main run**: 18 grounded tasks (one YAML per task, grouped by science
sphere). Each names the dataset(s) it must use and asks the agent to **write
`access.py`** and run it once on a small **demo slice** — then we grade the
**route it chose**, not the science it computed.

## What a task is
A `*.yaml` validated against `earth_agent_bench.schemas.Task`:

- `access_requirement` — `kind` (`subset`/`aggregate`/`daily`), bbox, the science
  window, and `demo_scope` (the small executable slice).
- `collections` — the dataset(s) to use, each with a resolved CMR `concept_id`.
- `pattern_tiers` / `gold` — the ranked access patterns (best → inefficient).
- `validation` — units, aggregation, the science gate.

The agent sees only the rendered instruction (goal = the code, the dataset, the
steps, the slice, "read the skills"); everything else is verifier-side.

## How it's graded
From the **observed access behavior** — the instrumented calls the agent actually
made (`earthaccess.open`/`virtualize` → `C1`, `harmony.submit` → `S1`, …) — plus a
static code check on `access.py`. Components: access-pattern **0.45** · service
discovery 0.15 · representation 0.15 · efficiency 0.15 · validation 0.10.
Collection *discovery* is **not** scored (the dataset is given; that belongs to
the project's semantic-discovery part).

## Why this is NOT `experiments/evals/tasks/`
| | `experiments/evals/tasks/` | **`benchmark/tasks/` (this)** |
|---|---|---|
| Asks | one clean value → `output/answer.txt` | write `access.py` + run it on a demo slice |
| Grades | deterministic typed-equality (the **answer**) | observed behavior (the **route**) |
| Layer | **outcome** | **process** |
| Role | cheap **screen** | the **main run** |

## Screening flow (how to use both)
1. **Screen** — run small local models on `experiments/evals/tasks/` (10
   single-value tasks; cheap, fast, deterministic). Outcome = pass@1/coverage.
2. **Select** — keep the models that clear the screen; they become `models:` in
   `experiments/run.yaml`.
3. **Run** — run this suite (`benchmark/tasks/`) with the selected models; this is
   the study.

After a model is vetted, only `benchmark/tasks/` is used.

## Authoring / running
- Add a task: see `docs/adding-tasks.md` and `docs/task-template.md`.
- Preview an instruction: `eab instruction benchmark/tasks/<sphere>/<id>.yaml`.
- Validate: `eab validate`.
- Run: `eab run --name <experiment>` (the full sweep driver) or
  `eab harbor run <id> --model <m> --harness <h> --condition <c>`.
