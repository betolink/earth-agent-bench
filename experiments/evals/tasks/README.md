# `experiments/evals/tasks/` — the correctness screen

The **screen**: 10 single-value tasks (one `.md` per task). Each asks an
access **micro-decision** (search the right window, then choose
`open` / `download` / `virtualize`) and the agent writes **one value** to
`./output/answer.txt`. We grade whether the **answer is right**.

## What a task is
A `*.md` instruction (question + the single-value contract) paired with a gold
entry in `../suite.yaml`:

```yaml
- task_id: 01_hls_open_vs_download
  answer_type: label          # label | boolean | integer | string
  answer: open
```

## How it's graded
`earth_agent_bench.evals.grade()` — deterministic **typed equality**, never an
LLM. An empty/missing answer is **uncovered** (infra failure, excluded); an
unparseable answer is **wrong**. A prompt-hygiene test
(`tests/test_evals.py`) asserts the instruction never leaks the gold.

## Role: the model screen
Use this suite **first** to decide which small local models are competent enough
for the big run:

1. run the candidate small models here (cheap, fast, deterministic);
2. keep the ones that clear the bar;
3. take them to `benchmark/tasks/` (the main run).

## Why this is NOT `benchmark/tasks/`
| | **`experiments/evals/tasks/` (this)** | `benchmark/tasks/` |
|---|---|---|
| Asks | one clean value → `output/answer.txt` | write `access.py` + run it on a demo slice |
| Grades | the **answer** (typed equality) | the **route** (observed behavior) |
| Layer | **outcome** | **process** |
| Role | cheap **screen** | the **main run** |

Both suites share the same `models × harnesses × conditions` matrices. See
`../README.md` (suite overview) and `../../../benchmark/tasks/README.md` (the
main run).

## Authoring / running
See `../README.md` ("Adding a task").
