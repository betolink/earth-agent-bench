---
name: self-improvement
description: >
  Model-specific countermeasures distilled from this model's failure postmortem on
  the earth-agent-bench run. READ THIS FIRST and follow it before doing anything
  else; each rule maps to a failure this exact model actually made.
generator: {generator}
source_run: {run_start}
model: {model}
---

# Self-improvement — {model}

> Generated from the {run_start} evaluation. Do these; they are the mistakes you
> made last time.

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

{failure_table}

## What went wrong, and the fix

{observed}
