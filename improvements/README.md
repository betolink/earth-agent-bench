# improvements/ — per-model self-improvement skills

This directory holds **generated** countermeasure skills: one per model, distilled
from that model's failure postmortem. They are mounted only under the `improve`
condition (see `experiments/conditions.yaml`), never under the normal
`skills` / `mcp-skills` conditions.

## How it fits into the evaluation loop

For each model:

1. **Evaluate** the neutral conditions (`baseline`, `mcp`, `skills`, `mcp-skills`).
2. **Postmortem** — `eab postmortem <model>` inspects that run:
   - classifies every cell `solved | partial | timeout | fail` (timeouts from
     `exception_stats`, wrong answers from the verifier),
   - pulls failure signatures (failing tests, `KeyError`, wrong-vs-expected values),
   - tallies the agent trajectory (curl / `search_data` / S3 attempts / wall-clock),
   - writes `improvements/<model>/self-improvement/SKILL.md`.
3. **Re-run** with `--condition improve` (skills + mcp + the generated skill).
4. **Compare** `improve` vs `mcp-skills` vs `baseline` in the report.

This closes the loop: the benchmark both *measures* a model and *teaches* it its
own observed mistakes, then measures the delta.

## Layout

```
improvements/
  README.md                         # this file
  _template/self-improvement/SKILL.md   # skeleton the generator fills
  <model>/self-improvement/SKILL.md     # generated, one per model
```

## Naming

Harbor discovers skills as directories containing `SKILL.md`, so the artifact is
`<model>/self-improvement/SKILL.md` (the "self-improvement.md" skill). The directory
name — `self-improvement` — is the skill's name.

## Two fidelity levels

- **Deterministic digest** (always): templated rules filled from the run data —
  safe, reproducible, no model needed.
- **Prose refinement** (optional): pass the digest to a strong reference model
  (via the gateway) to write sharper model-specific guidance. Record which was
  used in the skill frontmatter (`generator:`).
