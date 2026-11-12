# EAB small-model evaluation — LFM2.5-2.6B vs Ornith-1.5-9B

_Suite: correctness eval (10 deterministic single-value tasks). Harness: `pi`.
Condition: `baseline`. Runner: Harbor (isolated, auto-scored). Model endpoint:
BetoLink LiteLLM gateway. Earthdata: `EARTHDATA_TOKEN` (env, never baked)._

Comparison of the two small models in the roster: **LFM2.5-2.6B** (fastest) and
**Ornith-1.5-9B** (dense baseline).

## Results

Latest run per (model, task). `P` pass · `f` wrong · `X` uncovered
(infra: `AgentTimeoutError`, excluded from pass@1 per the eval suite's
`uncovered: excluded` rule).

| task | LFM2.5-2.6B | Ornith-1.5-9B |
|---|:--:|:--:|
| 01_hls_open_vs_download | f | f |
| 02_atl06_download_vs_open | P | P |
| 03_emit_virtualize | P | P |
| 04_mur_concat_dim | P | P |
| 05_emit_default_parser | P | P |
| 06_fallback_parser | P | P |
| 07_datalinks_access | P | X |
| 08_mur_cloud_hosted | P | X |
| 09_atl06_search_count | f | X |
| 10_hlss30_concept_id | P | X |
| **pass@1 (latest)** | **8/10** | **5/10** (4 uncovered) |
| **tokens (in / out)** | 1.07 M / 74 k | 4.85 M / 97 k |

## Findings

1. **The 2.6 B model beat the 9 B model** on this suite (8/10 vs 5/10) — and used
   ~4.5× fewer input tokens. Faster is not dumber here: LFM finished inside the
   600 s budget; Ornith over-explored.
2. **Both miss `01_hls_open_vs_download`** — the flagship "open vs download"
   decision (HLS is cloud COG; the answer is `open`). This is the highest-value
   micro-decision in the suite and the small models get it wrong.
3. **Ornith times out (uncovered) on the live-CMR tasks 07–10** — it issues many
   sequential `requests`/`earthaccess` searches and blows the 600 s agent budget
   (`AgentTimeoutError`), rather than answering wrongly. LFM answered those.
4. LFM's other miss is `09_atl06_search_count` (a live granule count).
5. Token shape: input ≫ output (system prompt + tool chatter) — Ornith's 4.85 M
   input reflects its longer looping trajectories.

## Tooling added for this run (the "easy wins")

- **`eab models doctor`** — preflight: served on the gateway + tool call + valid
  JSON (caught a real bug: urllib's default User-Agent was 403'd by the proxy).
- **`eab mcp doctor`** — probes the MCP servers (`cmr-mcp` reachable 200;
  `earthaccess-mcp` pending).
- **`eab report`** — aggregates Harbor runs into a per-model reward/token table.
- **Serving pins** in `experiments/models.yaml` (`serving:` block) recording
  ctx/KV/thinking per local model from clusterfunk/intelligence-index.

## Caveats / next

- `01` and `09` are worth a direct look (is the miss a knowledge gap or a
  parameter bug?).
- Ornith's timeouts should be counted as **uncovered**, not 0 — the raw
  `eab report` mean currently scores them 0.0; a follow-up should let the report
  exclude `AgentTimeoutError` runs.
- Run the **`mcp-skills`** condition next to test whether Earthdata knowledge
  compensates for model capability (EAB H-M2/H-M3).
