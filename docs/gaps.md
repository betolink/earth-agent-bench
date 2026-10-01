# Gaps & remaining work

Single authoritative list of what is missing before pilot and full runs.
Each item: why it matters, where it lives, acceptance criteria, status.
Scattered markers elsewhere (`confirm_at_pilot`, `verified: false`,
`status: pending`, TODO placeholders) all map to an item here.

Legend: **P0** blocks the pilot · **P1** blocks credible full-run results ·
**P2** external dependency · **P3** analysis layer.

---

## P0 — blocks the pilot

### 1. Harbor CLI adoption
- **What/why:** `eab harbor run` shells out to the `harbor` CLI, which is not yet
  installed or validated against the generated packages. The command line is a
  guess-encoded template.
- **Where:** `harbor/harbor.yaml` (template), `harbor/README.md`.
- **Acceptance:** a generated package runs end-to-end via the installed harbor
  CLI (`eab harbor run cryo-1 ... --condition baseline`) for at least one
  harness; harbor version recorded in `experiments/harnesses.yaml`; template
  flags corrected and frozen.

### 2. API model IDs (4 × `confirm_at_pilot`)
- **What/why:** exact LiteLLM provider strings and context lengths for Claude
  Sonnet 5.5, GPT Sol, DeepSeek Flash 4.1, GLM 5.3 Flash are unconfirmed.
- **Where:** `experiments/models.yaml` (grep `confirm_at_pilot`).
- **Acceptance:** gateway serves all 9 models with the pinned strings;
  `confirm_at_pilot` fields deleted from the roster.

### 3. Harness pins + headless verification
- **What/why:** all four harness versions are unpinned; pi's non-interactive
  invocation is unverified (`runner.py` prints a verify-at-pilot note);
  skills-mount conventions for opencode/codex/pi are unverified (claude-code's
  `.claude/skills/` is known).
- **Where:** `experiments/harnesses.yaml` (`version: null` × 4).
- **Acceptance:** versions pinned; `eab run` works headlessly for each harness;
  skills conditions mount on all four (conventions recorded in harnesses.yaml).

### 4. Service catalog verification (28 × `verified: false`)
- **What/why:** curated service availability in `benchmark/oracles/services.yaml`
  is unverified; live CMR already contradicted one entry (MOD11A1:
  `has_transforms: false`, AppEEARS available instead of assumed Harmony).
- **Where:** `benchmark/oracles/services.yaml`; cross-check with
  `eab matrix <short_name> --cmr`.
- **Acceptance:** every entry for the 18 tasks' collections is verified against
  CMR/DAAC docs and flipped to `verified: true` or corrected; task gold
  `pattern_tiers` re-checked where corrections land.

### 5. Reference solutions per task
- **What/why:** `solution/reference_workflow.py` is a TODO placeholder in every
  generated package; the validity rule (each task's expert workflow must achieve
  its own gold score before the experiment) is unenforceable without them.
- **Where:** `harbor_adapter.py` (`SOLVE_SH` / generated `solution/`);
  general-plan §40.
- **Acceptance:** one expert workflow per task passing primary pattern + science
  gate + efficiency envelopes; recorded reference metrics become the envelope
  calibration input (see #8).

---

## P1 — blocks credible full-run results

### 6. Access instrumentation
- **What/why:** `observed_patterns`, bytes, objects, runtime come from
  operator-filled `observation.json` or heuristics over `access_summary.json` —
  the benchmark's core claim ("best pattern *observed*, not claimed") is not
  yet instrumented.
- **Where:** `harbor_adapter.py` `VERIFY_PY` (heuristic classifier);
  `docs/tasks-and-evals.md` §9.2 (intended classification from access logs).
- **Acceptance:** HTTP/S3 request logging in the agent environment produces
  pattern classification + byte/object counts automatically into
  `observation.json`.

### 7. Minimal-science-gate depth
- **What/why:** verifier treats `validation_passed` as "an artifact exists".
  The gate is specified (variable/extent/units/aggregation) but not implemented
  per task.
- **Where:** `docs/tasks-and-evals.md` §9.1 (10% category); task
  `validation:` blocks carry the specs.
- **Acceptance:** per-task programmatic checks produce `validation_passed`
  from the artifact itself.

### 8. Efficiency envelope calibration
- **What/why:** default envelopes in `scoring/efficiency.py` are estimates; the
  reference solutions (#5) are the intended calibration source.
- **Acceptance:** envelopes per task derived from reference-run measurements,
  not defaults.

### 9. Task pinning details
- **What/why:** several `concept_id: null`, unconfirmed context windows
  (Tiel-Coder, Ornith-1.5-9B), and logical variable names pending UMM-Var
  pinning ("exact variable name pinned at task-build time").
- **Where:** task YAMLs (`collections[].concept_id`, notes);
  `experiments/models.yaml` (`context: null`).
- **Acceptance:** concept IDs and variable names pinned; contexts confirmed.

---

## P2 — external dependencies

### 10. earthaccess-mcp endpoint
- **What/why:** the intervention under test. `mcp/manifest.yaml`:
  `status: pending`, `url: null`. Until it ships, MCP conditions are
  discovery-level only (cmr-mcp).
- **Acceptance:** URL published; wired into `mcp/manifest.yaml`; MCP conditions
  re-interpreted as operational knowledge.

### 11. Final skills
- **What/why:** the 5 skills in `skills/` are scaffolds (the core
  data-access-patterns one is substantive; others are adapted/condensed).
- **Acceptance:** full skill set delivered alongside the earthaccess MCP work;
  scaffold tags removed.

---

## P3 — analysis layer

### 12. Batch orchestration
- **What/why:** `eab run` / `eab harbor run` execute single runs (or one task
  list); nothing walks the pilot/full matrices, writes a `RunManifest` per run,
  or enforces the closed-reference budget guard.
- **Where:** `experiments/pilot.yaml`, `experiments/full.yaml`.
- **Acceptance:** one command runs the pilot matrix restartably, skipping
  completed cells, marking infrastructure failures distinctly.

### 13. Statistics + result tables
- **What/why:** the specified outputs (condition comparison, price-tier,
  knowledge×tier interaction, cost-per-success, failure taxonomy) have no
  aggregation/analysis code.
- **Where:** `docs/tasks-and-evals.md` §9–§10; general-plan §42.
- **Acceptance:** `eab`-generated reports from collected runs.

### 14. Harbor packaging depth
- **What/why:** infrastructure-failure accounting (general-plan §51) and
  live-vs-reproducible modes (§52) are not yet wired into the generated
  packages.
- **Acceptance:** failure classification + a reproducible (cached/snapshot)
  mode exist.

---

## Map of scattered markers → this list

| Marker | Location | Gap |
|---|---|---|
| `confirm_at_pilot` (×4) | `experiments/models.yaml` | #2 |
| `version: null` (×4) | `experiments/harnesses.yaml` | #3 |
| `verified: false` (×28) | `benchmark/oracles/services.yaml` | #4 |
| `TODO` reference workflow | `harbor_adapter.py`, generated `solution/` | #5 |
| heuristic verifier note | `harbor/README.md` | #6 |
| `status: pending` | `mcp/manifest.yaml` | #10 |
| scaffold skills note | `skills/`, `docs/quickstart.md` §7 | #11 |
| "still to be built" batch note | `docs/quickstart.md` §6 | #12 |
| verifier fidelity note | `docs/consolidated-plan.md` §5.2 | #6/#7 |
