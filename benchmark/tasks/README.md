# Tasks

All task definitions live here, split by **what the suite assesses**:

| Folder | Count | Question | Grading |
|---|---:|---|---|
| [`access-pattern/`](access-pattern/) | 18 | did the agent pick **and execute** the best access route? | `pass` + weighted `score` from instrumented behavior |
| [`correctness/`](correctness/) | 10 | did the agent produce the **single correct value**? | deterministic typed equality (0/1) |

```
benchmark/tasks/
  access-pattern/        # the main study
    atmosphere/ biosphere/ cryosphere/ land-surface/ ocean/ solid-earth/
    <id>.yaml
  correctness/           # the cheap screen
    suite.yaml           # golds + grader types
    <id>.md
```

- **Add a task:** [docs/adding-tasks.md](../../docs/adding-tasks.md) (both suites).
- **Validate:** `eab validate`
- **Run the main study:** `eab harbor run` (uses `experiments/run.yaml`) or
  `eab harbor run access-pattern`
- **Run the screen:** `eab harbor run correctness`
- **Run everything:** `eab harbor run all`
- **Publish:** `eab harbor dataset all`

The dataset manifest (`harbor/dataset.toml`) pins every package by content
digest; regenerate it after adding or editing a task.
