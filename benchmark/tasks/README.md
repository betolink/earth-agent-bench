# Grounded access-pattern tasks

18 task YAMLs (three per sphere: atmosphere, cryosphere, biosphere, ocean,
solid-earth, land-surface). Each names the dataset(s) it must use and asks the
agent to **write `access.py`** and run it once on a small **demo slice**; the
route is graded, not the science.

## Anatomy

A `*.yaml` validated against `earth_agent_bench.schemas.Task`:

- `access_requirement` — `kind` (`subset`/`aggregate`/`daily`), bbox, science
  window, and the `demo_scope` executable slice.
- `collections` — datasets with resolved CMR `concept_id`s and service
  availability.
- `pattern_tiers` / `gold` — ranked access patterns (best → inefficient).
- `validation` — units, aggregation, the science gate.
- `labels` (optional) — data type, processing level, length class, infeasible,
  difficulty; carried into Harbor `[metadata]`.

The agent sees only the rendered instruction. Gold patterns, tiers, and service
data stay verifier-side.

## Grading

From **observed instrumented access behavior** plus a static code check, with an
all-or-nothing `pass` and a weighted `score` (access pattern 0.45 · service
discovery 0.15 · representation 0.15 · efficiency 0.15 · validation 0.10).
Collection *discovery* is not scored — the dataset is given. Full contract:
[docs/tasks-and-evals.md](../../docs/tasks-and-evals.md).

## Screening flow

1. **Screen** models on [`experiments/evals/tasks/`](../../experiments/evals/)
   (cheap single-value correctness).
2. **Select** the survivors in `experiments/run.yaml`.
3. **Run** this suite — the main study.

## Authoring / running

- Add a task: [docs/adding-tasks.md](../../docs/adding-tasks.md).
- Preview: `eab instruction benchmark/tasks/<sphere>/<id>.yaml`
- Validate: `eab validate`
- Run: `eab harbor run <id> --model <m> --harness <h> --condition <c>`
  (`eab harbor run` with no task runs the `run.yaml` selection).
