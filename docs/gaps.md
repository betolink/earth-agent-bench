# Gaps & remaining work

Single authoritative list of what is missing before pilot and full runs.
Each item: why it matters, where it lives, acceptance criteria, status.
Scattered markers elsewhere (`confirm_at_pilot`, `verified: false`,
`status: pending`, TODO placeholders) all map to an item here.

Legend: **P0** blocks the pilot · **P1** blocks credible full-run results ·
**P2** external dependency · **P3** analysis layer.

---

## P0 — blocks the pilot

### 1. Harbor CLI adoption — RESOLVED
- **Status:** resolved. Real Harbor (PyPI `harbor`, v0.24) is a pinned dev
  dependency (`pyproject.toml` + `pixi.toml`); `eab harbor` generates real
  `task.toml` packages, writes a JobConfig, and invokes `harbor run`. Validated
  end-to-end on `pi` and `opencode` (including the separate verifier container
  producing trusted access events). The old guess-encoded command template is
  gone.
- **Where:** `src/earth_agent_bench/harbor/`, `harbor/harbor.yaml`.
- **Remaining:** record `harbor --version` in `experiments/harnesses.yaml`. The
  earthaccess fork commit and the full agent stack are pinned in
  `src/earth_agent_bench/harbor/runtime/agent-requirements.txt` (resolved with
  `uv pip compile`).

### 2. API model IDs (4 × `confirm_at_pilot`)
- **What/why:** exact LiteLLM provider strings and context lengths for Claude
  Sonnet 5.5, GPT Sol, DeepSeek Flash 4.1, GLM 5.3 Flash are unconfirmed.
- **Where:** `experiments/models.yaml` (grep `confirm_at_pilot`).
- **Acceptance:** gateway serves all 9 models with the pinned strings;
  `confirm_at_pilot` fields deleted from the roster.

### 3. Harness pins + headless verification
- **What/why:** all four harness versions are unpinned; pi's non-interactive
  invocation is unverified (the Harbor JobConfig is validated with `--dry-run`);
  skills-mount conventions for opencode/codex/pi are unverified (claude-code's
  `.claude/skills/` is known).
- **Observed:** `opencode` can exit non-zero (`NonZeroAgentExitCodeError`) even
  when it wrote a valid deliverable; the separate verifier still scores it. Treat
  the agent exit code and the verifier `pass` as separate signals (see
  `docs/running.md` §2).
- **Where:** `experiments/harnesses.yaml` (`version: null` × 4).
- **Acceptance:** versions pinned; `eab harbor run` works headlessly for each harness;
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

### 5. Reference solutions per task — OPEN
- **What/why:** `solution/solve.sh` is still a placeholder in every generated
  package; the validity rule (each task's expert workflow must achieve its own
  gold score before the experiment) is unenforceable without them. AGENTS.md's
  `[metadata]`/labels and the dataset are in place; only the workflows are missing.
- **Where:** `src/earth_agent_bench/harbor/runtime/solve.sh` (rendered into the
  generated `solution/`); docs/archive/general-plan.md §40.
- **Acceptance:** one expert workflow per task passing primary pattern + science
  gate + efficiency envelopes; recorded reference metrics become the envelope
  calibration input (see #8). Suggested order: one per sphere (6) first.

---

## P1 — blocks credible full-run results

### 6. Access instrumentation — PARTIAL
- **Status:** partial. `eab_instrument.py` (installed into the sandbox image)
  patches `earthaccess`, `harmony`, `pydap`, `s3fs`, and `virtualizarr` and logs
  every real call to `/logs/agent/access_events.jsonl`; the verifier derives
  patterns/services/representation/validation from those events (self-report is
  only a fallback). Object counts and runtime are measured.
- **Remaining:** `bytes_read` is still self-reported; `earthaccess.open → C1` is
  coarse (cannot yet split cloud-native C1 from OPeNDAP S2); HTTP/S3-level
  logging would close both.
- **Where:** `src/earth_agent_bench/harbor/runtime/eab_instrument.py`, `src/earth_agent_bench/harbor/runtime/harbor_verify.py`,
  `src/earth_agent_bench/harbor/runtime/verify_benchmark.py`; `docs/tasks-and-evals.md` §3.2.

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

### 20. Secrets in process argv
- **What/why:** Harbor injects task env vars into the agent container via
  `docker compose exec -e VAR=value …`, so `EARTHDATA_TOKEN` and
  `LITE_LLM_API_KEY` are visible to any host user who can run `ps` while a trial
  is active. Inference-only keys limit the blast radius but this should still be
  closed before shared-host runs.
- **Where:** Harbor's docker environment (`docker compose exec`), not EAB code.
- **Mitigation:** run on a single-tenant host, use short-lived/scoped LiteLLM
  keys and an EDL token with a short expiry, or switch the runtime to a
  credential proxy (the sbx provider idea in `docs/archive/unification.md`).
- **Acceptance:** no secret appears in host `ps`/process args during a trial.

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

### 12. Batch orchestration — PARTIAL
- **Status:** `eab harbor run` now expands the full model × harness × condition ×
  task matrix from `experiments/run.yaml` (or `--models/--harnesses/--conditions`),
  enforcing harness crossing restrictions and printing `--dry-run` plans.
- **Remaining:** restart/resume that skips completed cells, `RunManifest` per
  run, and the closed-reference budget guard.
- **Where:** `src/earth_agent_bench/harbor/matrix.py`, `experiments/run.yaml`.
- **Acceptance:** relaunching the same selection skips cells whose `result.json`
  is complete and marks infrastructure failures distinctly.

### 13. Statistics + result tables
- **What/why:** the specified outputs (condition comparison, price-tier,
  knowledge×tier interaction, cost-per-success, failure taxonomy) have no
  aggregation/analysis code.
- **Where:** `docs/tasks-and-evals.md` §9–§10; docs/archive/general-plan.md §42.
- **Acceptance:** `eab`-generated reports from collected runs.

### 14. Harbor packaging depth — PARTIAL
- **Status:** packages now carry `[metadata]` labels, `[task]` authors/keywords,
  `[[artifacts]]` collection, resource caps, and a separate verifier
  (`environment_mode = "separate"`); the suite is publishable as a digest-pinned
  Harbor dataset (`eab harbor dataset`, `harbor/metric.py` selects `pass`).
- **Remaining:** infrastructure-failure accounting (docs/archive/general-plan.md §51)
  and live-vs-reproducible modes (§52 / #17).
- **Acceptance:** failure classification + a reproducible (cached/snapshot)
  mode exist.

### 15. Executor & profiler wiring — FUTURE (built, not yet used)
- **What/why:** `src/earth_agent_bench/harbor/runtime/executor.py` (run a deliverable under a
  wall/CPU/memory budget and classify `ok|error|timeout|oom`) and
  `src/earth_agent_bench/harbor/runtime/profiler.py` (scalene/memray) plus the `verify_exec.py`
  verifier exist, are unit-tested, and are reachable via `eab exec` — but
  **nothing in the live pipeline uses them**: no task verifier invokes
  `verify_exec`, `scoring/` grades observed access behavior only, and the agent
  is unaware of them (not in `instruction.md`/`skills/`).
- **Potential (once we have answers):** after the first full sweep, turn this on
  for the **Python-deliverable** tasks (SCI, EAB eval, cobol-style) as a second,
  post-correctness pass — explicit `timeout`/`oom` outcomes and line-level
  efficiency attribution. Follow the two-pass rule (never grade from the
  instrumented run; profiling perturbs timing 2–10×).
- **Where:** `src/earth_agent_bench/harbor/runtime/{executor,profiler,verify_exec}.py`,
  `docs/executor.md`, `tests/test_executor.py`.
- **Acceptance (when promoted):** code-deliverable verifiers call `verify_exec`;
  a profile artifact is recorded per *correct* cell; efficiency is reported
  separately from correctness.

### 16. FineEnvs multi-harness RL — FUTURE (assessment)
- **What/why:** train a small model with GRPO where the tool loop is run by a
  real harness through Harbor, with OpenEnv capturing the agent's tokens/logprobs
  for policy gradient. EAB is the *environment/eval* half (~60% there); the
  *RL/training* half (OpenEnv, token-capturing vLLM, TRL/GRPO, trainable weights,
  training GPUs) is ~0%.
- **Where:** `docs/archive/rl-fineenvs-assessment.md` (full gap analysis + path).
- **Acceptance (if pursued):** OpenEnv + Harbor env server deployed; a trainable
  HF model served on capturing vLLM; EAB reward ported to a scalar fn; a 2-update
  smoke passing before any long run.

---

## Deferred interoperability (post-pilot)

### 17. Sealed / offline mode
- **What/why:** Axis-Spatial-style aggregators run in sealed sandboxes with the
  data handed over in a folder. EAB is deliberately live (access-pattern
  selection over HTTPS), so it cannot yet be ingested there.
- **Plan:** a `--mode sealed` package variant: pre-fetched demo granule(s) in
  `/home/user/input` + CMR/service fixtures (cassettes or a stub sidecar), with
  `network_mode = "no-network"` (or `"allowlist"` for Earthdata hosts). Same
  verifier, recorded events only.
- **Acceptance:** one task per sphere runs with no network and grades identically
  to the live mode.

### 18. Infeasible-task variants
- **What/why:** the Axis index includes ~1 in 8 tasks the data cannot answer and
  grades refusal both ways; EAB has none.
- **Plan:** `labels.infeasible: true` + a gold that expects a refusal (no data
  access + an explicit refusal summary); the verifier must fail an attempted
  answer and pass a refusal.
- **Acceptance:** ≥1 infeasible task per sphere, validated by the oracle agent.

### 19. Long-horizon tasks
- **What/why:** long tasks are where agents fail (Axis). EAB's demo-scope design
  intentionally shortens tasks ("show the route, don't run the study").
- **Plan:** a separate `benchmark/tasks/long-horizon/` suite with a 2-hour budget.
- **Acceptance:** a parallel suite that does not complicate the pilot matrix.

## Map of scattered markers → this list

| Marker | Location | Gap |
|---|---|---|
| `confirm_at_pilot` (×4) | `experiments/models.yaml` | #2 |
| `version: null` (×4) | `experiments/harnesses.yaml` | #3 |
| `verified: false` (×28) | `benchmark/oracles/services.yaml` | #4 |
| `TODO` reference workflow | `src/earth_agent_bench/harbor/runtime/solve.sh`, generated `solution/` | #5 |
| `status: pending` | `mcp/manifest.yaml` | #10 |
| scaffold skills note | `skills/`, `docs/quickstart.md` §7 | #11 |
| dataset/publish plan | `docs/archive/unification.md` | done (`eab harbor dataset`) |
| verifier fidelity note | `docs/archive/consolidated-plan.md` §5.2 | #6/#7 |
| "not yet wired — FUTURE" note | `docs/executor.md`, `src/earth_agent_bench/harbor/runtime/*` | #15 |
| RL gap assessment | `docs/archive/rl-fineenvs-assessment.md` | #16 |
