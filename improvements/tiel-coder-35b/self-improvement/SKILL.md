---
name: self-improvement
description: >
  Model-specific countermeasures distilled from Tiel-Coder-35B's failure postmortem
  on the earth-agent-bench run. READ THIS FIRST and follow it before doing anything
  else; each rule maps to a failure this exact model actually made.
generator: deterministic-digest (hand-reviewed)
source_run: 20261010-154909
model: tiel-coder-35b
---

# Self-improvement — Tiel-Coder-35B

> Generated from the 2026-10-10 evaluation. Do these; they are the mistakes you made
> last time.

## Hard rules (always)

1. **Out-of-region → HTTPS, never S3.** This runs outside AWS. `s3://…`,
   `*.s3.amazonaws.com`, `s3_credentials`, `s3fs` **will not work** (hang/403). Use
   the HTTPS object URL, or the HTTPS path `earthaccess.open()`/`download()` return.
2. **Inspect the inputs before writing code.** Print the real schema (columns, keys,
   units, dtypes) of every input file first. Never hardcode a column/field name.
3. **Match the exact acceptance criterion.** Re-read what is asked (and its units):
   token *count* vs bytes vs rows, one value vs a dataset, exact output name.
4. **Verify before you finish.** Run the task's own test/verifier or reproduce the
   expected output and diff it. "Looks right" is not done.
5. **Be decisive — minimize iterations.** Prefer the answer the skills/MCP give;
   avoid long live-probing loops. Every retry costs wall-clock and grows context.
6. **Respect the output contract.** Write exactly the required artifact path(s); no
   stray newlines/reformatting for binary or fixed-width files.

## Observed failures this run

| where | failure | classification |
|---|---|---|
| EAB baseline (pi) | **13 / 18 timed out**; 5 partial (0.40–0.78); 0 solved | timeout (budget) |
| TERM-01 ×4 harnesses | COBOL→Python byte-exact; 635–668 s | timeout (budget) |
| SWE-04 (codex, opencode) | pylint fix; 686 / 715 s | timeout (budget) |
| SCI-03 (claude-code **and** pi) | `KeyError: 'value'` at `pipeline.py:14` | wrong — assumed a column |
| TERM-03 (claude-code) | answered `213418`, expected `79586` | wrong — counted the wrong quantity |
| SWE-01 (opencode) | `test_no_content_length` still failing | wrong — patch unverified |
| SWE-04 (claude-code) | all 10 FAIL_TO_PASS failing | wrong — fix ineffective |

Trajectory evidence (EAB `a1-tempo`): ~325 `curl`, 157 `search_data`, 240 CMR,
269 S3, 187 `download` calls in one trial (~1 MB tool output) — heavy live probing.

## What went wrong, and the fix

- **You spent your whole budget probing CMR/S3 live.** You re-searched, re-opened and
  re-debugged the granule over and over until the clock ran out. → Answer from the
  skills/MCP when they give you a value; make **one** verification pass, then finish.
  Do not re-derive what you already know.
- **You assumed a column called `value`** (SCI-03, on two harnesses). → **Open the
  file and print its schema first**; build the code from the real columns.
- **You counted the wrong thing** (TERM-03: 213418 vs 79586). → Re-read the exact
  quantity and units before computing; sanity-check the magnitude.
- **You stopped before proving the fix** (SWE-01/04). → Run the task's failing test
  and confirm it passes before you stop.
- **You may have reached for S3** (269 S3 references). → Out of region it cannot work;
  always use HTTPS.

Bottom line: the work was usually *right*, but you **ran out of wall-clock by
over-exploring**. Decide early, verify once, output, stop.
