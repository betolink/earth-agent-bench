# RPI — Scoring baseline performance on the earthaccess eval tasks

Status: findings (Research → Plan → Implement). Companion to the 10 tasks in
`experiments/evals/tasks/` (the single-clean-value earthaccess suite).

Goal: score model **baseline** performance on the 10 tasks — no training, just a
reproducible pass@1 measurement. Two candidate substrates were considered:
**earth-agent-bench** (this repo) and the **FineEnvs multi-harness RL**
methodology (`05-multi-harness-rl`, github.com/adithya-s-k/FineEnvs).

> **Implementation status (updated after the work landed).** Implemented in this
> repo. The 10 tasks live in `experiments/evals/tasks/*.md`; golds + answer
> types are in `experiments/evals/suite.yaml`; the deterministic grader is
> `earth_agent_bench.evals` (`eab eval grade` / `eab eval report`); the answer
> sink is `./output/answer.txt` (tasks normalized); and the runnable path is
> **Harbor** (`eab harbor run`, real Harbor, instrumented auto-scoring), not the
> direct runner. The three "open decisions" at the end are resolved. See
> `docs/tasks-and-evals.md` §0 for the benchmark-vs-eval separation of concerns
> and `experiments/evals/README.md` for adding eval tasks.

---

## 1. Research

### 1.1 What the two approaches actually are

**FineEnvs `05-multi-harness-rl`** is an RL-training project, but its
*evaluation* half is self-contained and reusable without any training:

- **Task shape**: a natural-language question + data files + a *checkable
  answer* + a *deterministic grader*. The agent inspects data in a sandbox and
  writes an answer; the answer is compared against a held-out value.
- **Reward / score**: `bonus = 0.1 * 15 / (15 + tool_calls)` and
  `reward = correctness * (1 + bonus)`. Correct with 15 tool calls = `1.05`;
  wrong = `0`; no tool-count evidence = no bonus; a *failed/unrated*
  environment is **excluded, not scored wrong**.
- **Protocol**: fixed pass@1; report **coverage alongside pass@1**; per-pair
  results (`pairs/*.json`), identity/sampling version, and **tool-call + token
  metrics** per attempt.

That task shape is *exactly* the shape of the 10 tasks: "…Answer with a single
clean value… write only that value to `/workdir/answer.txt`." The FineEnvs
grader is the natural scoring core.

**earth-agent-bench** is an Earthdata-specific benchmark whose question is *not*
"did you compute the right number" but "did you select the best available access
pattern" (C1 virtualization vs S1 Harmony vs OPeNDAP vs filtered/full download).
Its scoring is process-oriented and multi-dimensional:

| Category | Weight |
|---|---:|
| Collection selection | 10% |
| Service discovery | 15% |
| **Access pattern** | **35%** |
| Representation | 15% |
| Efficiency | 15% |
| Validation gate | 10% |

Its value here is **not** its scorer (which scores *how* data was accessed, not
*whether the answer is right*) but its **execution + measurement layer**: four
harnesses (pi / opencode / codex-cli / claude-code), a 9-model roster, four
knowledge conditions (baseline / mcp / skills / mcp+skills), the `RunManifest`
(token/cost/tokens-per-second accounting), the `eab run` direct runner, and the
`eab harbor generate|run` isolated path.

### 1.2 Findings (the three things that matter)

1. **Outcome vs. process.** FineEnvs scores *correctness of the final value*
   plus an efficiency bonus; earth-agent-bench scores *access-pattern
   selection quality*. The 10 tasks are outcome tasks ("answer `open`",
   "answer `DMRPPParser`", "report the granule count"). Their correctness is a
   deterministic equality check — a FineEnvs-style grader, not an
   earth-agent-bench weighted rubric. The earth-agent-bench rubric would
   mis-score them (e.g. its "validation gate" is artifact-presence, not exact
   answer).

2. **Harness/measurement is the expensive, reusable part.** earth-agent-bench
   already owns multi-harness, multi-model, multi-condition orchestration and
   token/cost instrumentation — exactly what a *baseline sweep* needs. FineEnvs
   owns a clean answer-grading + pass@1 + coverage + tool-efficiency protocol.
   The two compose: **earth-agent-bench as the runner, FineEnvs as the scorer.**

3. **The answer-sink convention diverges.** The 10 tasks instruct writing to
   `/workdir/answer.txt` (FineEnvs convention). earth-agent-bench's output
   contract is `./output/` + `access_summary.json`. A baseline harness must
   reconcile these: either (a) normalize the task template to a single
   `answer.txt` artifact the verifier reads, or (b) have the verifier accept
   `/workdir/answer.txt`. This is the one concrete integration seam.

### 1.3 What already exists in this repo

- `experiments/evals/tasks/*.md` — the 10 tasks (already copied in).
- `src/earth_agent_bench/` — schemas, tasks loader, runner, oracles, scoring.
- `experiments/models.yaml`, `harnesses.yaml`, `conditions.yaml` — the factor
  rosters for a baseline matrix.
- `RunManifest` (schemas.py) — token/cost/tokens-per-second accounting.

What does **not** exist yet for these 10 tasks: a gold-answer/grader mapping, a
pass@1 + coverage reporter, and tool-call counting per attempt.

---

## 2. Plan

### 2.1 Scoring model (adopt FineEnvs, adapted)

For each (task, model, harness, condition) cell, run N=1 trial by default
(baseline = pass@1 over a single attempt; raise N for variance):

```
correct  = grader(produced_answer, gold_answer)
bonus    = 0.1 * 15 / (15 + tool_calls) if tool_calls > 0 else 0
reward   = correct * (1 + bonus)          # 0.0, 1.0..1.1 range
coverage = 1 if environment produced a grade else 0   # infra failures excluded
```

Report, per cell and aggregated:
- **pass@1** (mean correctness over *covered* attempts) — the headline.
- **coverage** (fraction of attempts that yielded a grade) — always reported
  next to pass@1.
- **mean tool calls** and **mean tokens / cost** (from `RunManifest`).

### 2.2 Grader design

Deterministic, per-task type (no LLM judging):

| Answer type | Comparison |
|---|---|
| label (`open`/`download`/`virtualize`/`direct`/`time`/`DMRPPParser`/`HDFParser`) | case-insensitive exact string |
| yes/no | normalized boolean |
| integer count (`09_atl06_search_count`) | numeric equality (allow ±0) |
| concept-id string (`10_hlss30_concept_id`) | exact string |

Each task gets a `gold` block: `answer` + `type` + (for tolerance) optional
`tolerance`. A `grader` function in `scoring/` implements it and returns
`{correct: bool, tool_calls: int|null}`.

### 2.3 Baseline sweep shape

- **Models**: tier-anchored subset for a cheap first pass — e.g. one local
  (`lfm2.5-2.6b` or `tiel-coder-35b`), one frontier-open (`glm-5.3-flash`),
  one closed reference (`claude-sonnet-5-5`) — rather than all 9.
- **Harnesses**: all available (`pi`, `opencode`, `codex-cli`; claude-code for
  the reference lane).
- **Conditions**: `baseline` first (no MCP, no skills); add `mcp` / `skills` /
  `mcp-skills` only after baseline is reproducible.
- **Tasks**: all 10.

### 2.4 The integration seam (answer sink)

Normalize the task contract to a single artifact `answer.txt`:

- Rewrite the closing line of the 10 task templates from
  `echo -n "<value>" > /workdir/answer.txt` to the repo convention
  `write ./output/answer.txt`, **or** extend the Harbor verifier / runner to
  read `/workdir/answer.txt`. Prefer the former (keeps tasks self-contained and
  harness-agnostic).

---

## 3. Implement

As implemented (differs from the sketch below):

| Planned | Actual |
|---|---|
| sidecar `*.yaml` per task | consolidated `experiments/evals/suite.yaml` |
| `scoring/eval_grader.py` | `earth_agent_bench/evals.py` (`EvalGold`, `grade`, `summarize`) |
| `scoring/eval_report.py` | `eab eval report` (CLI) |
| answer sink `/workdir/answer.txt` | `./output/answer.txt` (tasks normalized) |
| direct runner | Harbor (`eab harbor run`) with the eval verifier |

Concrete steps, in dependency order.

### 3.1 Add a gold/grader schema

Extend `src/earth_agent_bench/schemas.py` with an `EvalGold` model and add a
sidecar per task (e.g. `experiments/evals/tasks/01_hls_open_vs_download.yaml`
alongside the `.md`, mirroring `benchmark/tasks/<sphere>/*.yaml`):

```yaml
task_id: evals/01_hls_open_vs_download
answer_type: label          # label | boolean | integer | string
answer: "open"              # or true / 42 / "C2021957295-LPCLOUD"
tool_calls_field: null      # source of tool-count (harness trace, if available)
```

### 3.2 Add a deterministic grader

New module `src/earth_agent_bench/scoring/eval_grader.py`:

```python
def grade(task, produced: str, tool_calls: int | None) -> EvalResult:
    correct = compare(task.answer_type, task.answer, produced)
    bonus = 0.1 * 15 / (15 + tool_calls) if tool_calls and tool_calls > 0 else 0.0
    return EvalResult(correct=correct, reward=(correct * (1 + bonus)),
                      tool_calls=tool_calls, covered=True)
```

Wire a `compare()` for the four types above (label/boolean/integer/string).

### 3.3 A pass@1 + coverage reporter

New `src/earth_agent_bench/scoring/eval_report.py` that, given a directory of
`pairs/*.json` (one per attempt), emits a `summary.json` with:

```json
{ "pass@1": 0.6, "coverage": 0.9, "mean_reward": 0.61,
  "mean_tool_calls": 8.4, "by_task": { ... }, "by_harness": { ... } }
```

Reuse the FineEnvs rule: *graded-wrong = 0, ungraded/infra-failed = excluded*,
and fail nonzero on incomplete coverage (surface it, don't hide it).

### 3.4 Adapt the answer-sink contract

Edit the 10 task templates' final line to the repo convention, e.g.:

```
Write only that value to ./output/answer.txt, then stop.
```

Keep the gold hidden from the rendered `instruction.md` (the runner already
hides gold standards).

### 3.5 Run the baseline

```bash
uv sync                     # bench tooling + Harbor (dev group)
uv run python scripts/build_virtualizability_parquet.py   # oracles (if needed)

# one cell, Harbor path (isolated + auto-scored)
uv run eab harbor run experiments/evals/tasks/01_hls_open_vs_download.md \
    --model lfm2.5-2.6b --harness pi --condition baseline --dry-run
# drop --dry-run; the eval verifier grades output/answer.txt automatically

# grade a produced answer directly
uv run eab eval grade 01_hls_open_vs_download <run>/output/answer.txt
```

Or, host-side, `uv run eab run experiments/evals/tasks/01_hls_open_vs_download.md
--model lfm2.5-2.6b --harness opencode --condition baseline`, then grade the
`output/answer.txt` it produces.

### 3.6 First deliverable

A baseline table with rows = 10 tasks, columns = `{model}×{harness}`
(baseline condition), cells = `correct/covered (tool calls)`, plus a headline
`pass@1` and `coverage` per model. This is the number the 10 tasks are built to
produce.

---

## Open decisions (resolved)

1. **Answer sink** — normalized to `./output/answer.txt`; the verifier searches
   `/app`, `/home/user`, `/`, and the workspace (plus `--search-root`).
2. **Tool-call source** — the FineEnvs tool bonus applies only when a tool-call
   count is instrumented; otherwise `reward ≡ correctness`. Harbor's ATIF
   trajectory carries the counts when needed.
3. **Trial count** — N=1 by default (`n_attempts: 1`); raise per `experiments/run.yaml`.
