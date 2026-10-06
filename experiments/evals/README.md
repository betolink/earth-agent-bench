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

## Keeping the two copies in sync

The instruction `.md` files mirror `earthaccess/docs/evals/tasks/` (the authoring
copies). They diverge in one deliberate way: the answer sink here is
`./output/answer.txt` (repo convention) instead of `/workdir/answer.txt`. Re-sync
only the question/steps, never the sink.
