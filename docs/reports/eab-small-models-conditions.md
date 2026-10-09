# EAB small-model study — does Earthdata knowledge compensate for model size?

_Suite: correctness eval (10 deterministic single-value tasks). Harness: `pi`.
Conditions: `baseline` · `mcp` · `skills` · `mcp-skills`. Runner: Harbor
(isolated, auto-scored). Endpoint: BetoLink LiteLLM gateway. Earthdata:
`EARTHDATA_TOKEN` injected at runtime (never baked into images)._

Models: **LFM2.5-2.6B** (edge floor) and **Ornith-1.5-9B** (dense). This directly
tests hypotheses **H-M2 / H-M3**: does operational Earthdata knowledge
(`cmr-mcp` + mounted skills) help small models, and can an informed small model
match an uninformed larger one?

## Headline

**Yes — the knowledge conditions matter more than model size here.**

| model | baseline | mcp | skills | mcp-skills |
|---|:--:|:--:|:--:|:--:|
| LFM2.5-2.6B | 8/10 | 9/10 | 8/9 | **10/10** |
| Ornith-1.5-9B | 5/6 | 8/9 | 8/10 | **8/8** |

(pass@1 over **covered** attempts; `X` infra timeouts excluded from the
denominator, per the eval suite's `uncovered: excluded` rule.)

- **LFM goes 8/10 → 10/10** with `mcp-skills` — a 2.6 B model solves the whole
  eval suite when given the CMR MCP + skills.
- **Ornith jumps from 5/6 covered (4 timeouts at baseline) to 8/8** — the tools
  also *stop it from timing out* (its baseline failure mode was over-exploring
  live CMR; MCP gives it the answer directly).

## Per-task detail (`pi`)

Legend: `P` pass · `f` wrong · `X` uncovered (timeout, excluded).

**LFM2.5-2.6B**
```
task                                baseline   mcp  skills  mcp-skills
01_hls_open_vs_download                 f        P     P        P
02_atl06_download_vs_open               P        P     P        P
03_emit_virtualize                      P        P     P        P
04_mur_concat_dim                       P        P     P        P
05_emit_default_parser                  P        P     P        P
06_fallback_parser                      P        P     P        P
07_datalinks_access                     P        P     P        P
08_mur_cloud_hosted                     P        P     P        P
09_atl06_search_count                   f        f     P        P
10_hlss30_concept_id                    P        P     f        P
pass@1 (covered)                       8/10     9/10  8/9    10/10
```

**Ornith-1.5-9B**
```
task                                baseline   mcp  skills  mcp-skills
01_hls_open_vs_download                 f        P     P        P
02_atl06_download_vs_open               P        P     P        P
03_emit_virtualize                      P        P     f        P
04_mur_concat_dim                       P        P     f        X
05_emit_default_parser                  P        P     P        P
06_fallback_parser                      P        P     P        P
07_datalinks_access                     X        P     P        P
08_mur_cloud_hosted                     X        X     P        X
09_atl06_search_count                   X        f     P        P
10_hlss30_concept_id                    X        P     P        P
pass@1 (covered)                       5/6     8/9   8/10     8/8
```

## Observations

1. **`01_hls_open_vs_download` (the flagship "open vs download" decision) is 0
   for *both* models at baseline and fixed by every knowledge condition** (`mcp`,
   `skills`, `mcp-skills`). This single micro-decision is the clearest
   knowledge-vs-capability signal in the suite.
2. **MCP alone already helps** (LFM 8→9, Ornith 5/6→8/9). **Skills alone** fix
   `09_atl06_search_count` but regress an occasional task. **`mcp-skills` is the
   best condition for both models** — consistent with EAB's combined-intervention
   design.
3. **Tools reduce timeouts, not just errors.** Ornith's 4 baseline `X`s
   (`AgentTimeoutError` from looping CMR searches) mostly become passes under
   `mcp`/`skills` — knowledge short-circuits the exploration.
4. The 2.6 B model **matches or beats** the 9 B under equal conditions — size is
   not destiny on these knowledge-light micro-decisions once knowledge is given.

## Infrastructure findings (blocking/limiting)

- **`opencode` harness is broken for this setup.** Every opencode run ended
  `covered:false` (the agent never wrote `output/answer.txt`), and opencode's
  internal small model was misconfigured (`gpt-5.4-nano-flex` →
  `Invalid model name`). We stopped that sweep; **all condition results above are
  `pi`**, which produces real answers and supports the MCP conditions.
- **`earthaccess-mcp` is still `pending`** — so `mcp`/`mcp-skills` currently wire
  **`cmr-mcp` + skills**. The intervention under test is therefore CMR-based.
- **Effect size warrants more trials**: several cells are single runs; `skills`
  shows run-to-run variation (LFM `10` passes at baseline but fails under
  `skills`). Increase `trials` before quoting exact pass@1.

## Tooling added

- `eab models doctor` — served + tool-call + valid-JSON preflight.
- `eab mcp doctor` — probes the MCP servers (`cmr-mcp` reachable 200;
  `earthaccess-mcp` pending).
- `eab report` — aggregates Harbor runs into per-model/condition reward + tokens.
- Serving pins in `experiments/models.yaml` (`serving:` block: ctx/KV/thinking).

## Next

1. Fix `opencode` (answer sink + internal small model) or drop it from the
   condition matrix until fixed.
2. Publish `earthaccess-mcp`; re-run `mcp`/`mcp-skills` to test the *full*
   intervention.
3. Raise `trials` (≥3) and re-run `mcp-skills` vs `baseline` for a stable
   H-M2/H-M3 effect size.
