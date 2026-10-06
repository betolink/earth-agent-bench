# Correctness eval suite (`experiments/evals/`)

Single-clean-value earthaccess tasks. Each task asks the agent to make an access
micro-decision — search the right window with the right parameters, then choose
`open` / `download` / `virtualize` — and write one value to `./output/answer.txt`.

This is the **outcome** layer (did the agent get the right answer), complementary
to the 18 access-pattern tasks in `benchmark/tasks/` (did the agent pick the best
pattern). The same models × harnesses × conditions matrices drive both.

## Layout

```
experiments/evals/
  suite.yaml     # single source of truth: 10 gold answers + grader types
  tasks/*.md     # agent-facing instructions (answer sink standardized to ./output/answer.txt)
  README.md
```

## The judge is deterministic code, never an LLM

`earth_agent_bench.evals.grade()` compares the produced answer to the gold using
its `answer_type`:

| answer_type | comparison |
|---|---|
| `label` | case-insensitive, whitespace-collapsed exact string |
| `boolean` | normalized yes/no/true/false/1/0 |
| `integer` | numeric equality (± `tolerance`) |
| `string` | exact, whitespace-trimmed string |

An empty/missing answer is **uncovered** (infra failure) — reported, not scored
wrong. An unparseable or "Not Applicable" answer is **wrong**.

## Prompt hygiene (hint-free)

The agent-facing instruction must **not contain the answer**. The invariant is
enforced by a derived test
(`tests/test_evals.py::test_eval_prompts_do_not_leak_the_gold`): for every task
it derives the accepted answer tokens from the grader's own normalization
(`accepted_tokens`) and asserts none appear as words in the question body
(everything before the `Express your answer as` contract). No hand-maintained
phrase list, so it cannot rot out of sync with the judge.

Two consequences for authors:

- Write the question so it can't be answered by pattern-matching its own text:
  don't restate the options' semantics, don't give the procedure, don't name the
  value. Ask, and let the agent derive it (by reading the installed library — the
  capability under test).
- Keep authoring-only guidance in an HTML comment; it is stripped before the
  agent sees the instruction:

  ```
  <!-- authoring
  rationale, intended reasoning, re-sync notes — never rendered
  -->
  ```

  `render_eval_instruction()` removes `<!-- authoring ... -->` blocks and appends
  the absolute output-path note; `generate_package` uses it, so the agent sees
  exactly the question plus the sink.

These tasks are a **knowledge screen**, not a reasoning benchmark: with the
library installed and readable, a small model answers many of them. Treat
saturation as expected; add harder tasks separately (`docs/tasks-and-evals.md`
§0).

## Tool-efficiency bonus (FineEnvs)

`bonus = 0.1 * 15 / (15 + tool_calls)` when `tool_calls > 0` and instrumented,
else `reward = correctness`. Tool-call counts are optional until access
instrumentation lands (gap #6); pass `--tool-calls` when available.

## Usage

```bash
# grade one produced answer
uv run eab eval grade 01_hls_open_vs_download runs/.../output/answer.txt

# grade with instrumented tool calls
uv run eab eval grade 03_emit_virtualize runs/.../output/answer.txt --tool-calls 7

# aggregate per-attempt results into pass@1 / coverage / tool-call summary
uv run eab eval report runs/.../trial-1/evals
```

## Pinning live values

`09_atl06_search_count` depends on the live CMR count, so its gold is
`answer: null, pinned: false` — pin the integer at build time (same convention as
the benchmark's `concept_id: null`). The grader refuses to score an unpinned gold.

## Adding a task

A task is two files: the agent-facing instruction and its gold entry.

1. **Instruction** — add `tasks/NN_short_name.md`:
   - state the question and the step-by-step reasoning you expect;
   - end with the single-clean-value contract and the sink, e.g.
     `Write only that value to ./output/answer.txt (absolute: /app/output/answer.txt), then stop.`
   - allow metadata search; forbid science-data I/O when the task is a pure
     decision (the no-I/O constraint);
   - never reveal the gold.

2. **Gold** — add one entry to `suite.yaml`:

   ```yaml
   - task_id: 11_modis_resolution
     answer_type: label          # label | boolean | integer | string
     answer: "1km"
     note: "MOD11A1 is 1 km"
   ```

   For values that depend on live CMR (counts), set `answer: null, pinned: false`
   and pin the integer at build time; the grader refuses to score an unpinned
   gold. Use `tolerance` for integer answers that may vary slightly.

3. **Verify locally** (no model needed): write the gold into a temp
   `output/answer.txt` and grade it — it must score `1.0`; a wrong answer must
   score `0.0`; a missing answer must be *uncovered*.

   ```bash
   mkdir -p /tmp/ws/output
   printf '%s' '1km' > /tmp/ws/output/answer.txt
   uv run eab eval grade 11_modis_resolution /tmp/ws/output/answer.txt
   ```

4. **Package for Harbor** (when you want to run it):

   ```bash
   uv run eab harbor generate 11_modis_resolution --condition baseline
   uv run eab harbor run 11_modis_resolution --model <model> --harness <harness> --condition baseline
   ```

An agent adding a task follows the same three steps: write the `.md`, add the
gold to `suite.yaml`, and confirm `eab eval grade` returns 1.0 for the gold.

## Keeping the two copies in sync

The instruction `.md` files mirror `earthaccess/docs/evals/tasks/` (the authoring
copies). They diverge in one deliberate way: the answer sink here is
`./output/answer.txt` (repo convention) instead of `/workdir/answer.txt`. Re-sync
only the question/steps, never the sink.
