# Correctness eval suite

Ten single-value Earthdata tasks. Each asks for one access micro-decision —
search the right window, then choose `open` / `download` / `virtualize` — written
to `output/answer.txt`. This is the **outcome** screen; the main study is the 18
access-pattern tasks in [`benchmark/tasks/`](../../benchmark/tasks/).

```
experiments/evals/
  suite.yaml     # single source of truth: 10 golds + grader types
  tasks/*.md     # agent-facing instructions
```

## Deterministic judge (never an LLM)

`earth_agent_bench.evals.grade()` compares the answer to the gold by type:

| `answer_type` | comparison |
|---|---|
| `label` | case-insensitive, whitespace-collapsed |
| `boolean` | normalized yes/no/true/false/1/0 |
| `integer` | numeric equality (± `tolerance`) |
| `string` | exact, whitespace-trimmed |

Missing answer → **uncovered** (infra failure, reported not scored wrong).
Unparseable or "Not Applicable" → **wrong**. The verifier writes `reward`/`pass`
0/1 to `/logs/verifier/`.

## Prompt hygiene

The instruction must not contain the answer. A derived test
(`tests/test_evals.py`) normalizes the gold through the grader and asserts no
accepted token appears in the question body. Keep authoring notes in an HTML
comment (`<!-- authoring … -->`); `render_eval_instruction` strips it.

These are a **knowledge screen**, not a reasoning benchmark — saturation is
expected.

## Usage

```bash
uv run eab eval grade 01_hls_open_vs_download runs/.../output/answer.txt
uv run eab eval grade 03_emit_virtualize runs/.../output/answer.txt --tool-calls 7
uv run eab eval report runs/.../trial-1/evals
```

`reward = correctness`; with instrumented tool calls the optional FineEnvs bonus
is `0.1 * 15 / (15 + tool_calls)`.

## Adding a task

1. Add `tasks/NN_short_name.md` ending with the single-value contract and the
   sink: `Write only that value to ./output/answer.txt (absolute:
   /app/output/answer.txt), then stop.` Allow metadata search; forbid science
   data I/O for pure decisions.
2. Add the gold to `suite.yaml`:

   ```yaml
   - task_id: 11_modis_resolution
     answer_type: label          # label | boolean | integer | string
     answer: "1km"
   ```

   Live-CMR values use `answer: null, pinned: false` and are pinned at build
   time; the grader refuses to score an unpinned gold.
3. Verify locally: write the gold to a temp `output/answer.txt` — it must grade
   `1.0`; a wrong answer `0.0`; a missing answer *uncovered*.
4. Package/run: `uv run eab harbor run 11_modis_resolution --model … --harness …`.

The `.md` files mirror `earthaccess/docs/evals/tasks/`; the only intended
divergence is the repo answer sink.
