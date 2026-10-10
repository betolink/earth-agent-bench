# Unification plan — EAB as the umbrella

**Goal:** one place to run every local-model evaluation we've built — the
Earthdata access-pattern benchmark, the SWE/Terminal/scientific-Python suite, and
the general agentic suite — against the same model roster, harnesses,
conditions, runner, and report. **EAB becomes the umbrella; Harbor is the runner;
sbx-kits is the environment provider.**

## 1. Where we are today (three parallel efforts)

| effort | repo | what it measures | how it runs |
|---|---|---|---|
| **earth-agent-bench (EAB)** | `~/github/betolink/earth-agent-bench` | NASA Earthdata access-pattern selection (18 rubric tasks) + 10 deterministic correctness evals | `eab` CLI → Harbor task packages (+5 conditions: baseline/mcp/skills/mcp-skills) |
| **intelligence-index** | `clusterfunk/intelligence-index` | general agentic suite (6 base + 5 hard) + **serving** characterization (ctx/KV/tok-s/tokens) | bespoke harness (`scripts/bench-models.py`) → llama-swap + OpenClaw |
| **mini-benchmarks** | `~/github/betolink/mini-benchmarks` | 10-task coding suite (4 SWE-bench + 3 Terminal-Bench + 3 custom SCI) | `runner/run.py` → Harbor |
| **sbx-kits** | `~/github/betolink/sbx-kits` | — (infrastructure) | Docker Sandboxes kits: agent boxes (opencode/codex/claude/pi) + LiteLLM credential proxy + MCP/skills/pixi/LSP/memory |

These share a substrate (LiteLLM gateway, the same local models, the same 4
harnesses) but each has its own roster, runner, and report.

## 2. Target architecture — three layers

```
EAB         umbrella: roster, suites, conditions, report, doctor, scoring
  └ Harbor  runner:   task packaging, isolation, verifier/reward, manifests, budget
      └ sbx   runtime: the agent box (LiteLLM proxy, MCP, skills, pixi, LSP, memory)
```

- **EAB** decides *what* runs and *how it's scored*.
- **Harbor** orchestrates and verifies.
- **sbx** provides the sandbox the agent executes in.
- **Nothing moves the verifier/reward/oracles/manifests out of EAB/Harbor** — sbx
  cannot score.

## 3. Core abstraction: **Suite**

A suite is a self-contained benchmark = Harbor task packages + a grader +
default run settings. Everything else (roster, harnesses, conditions, runner,
report) is shared.

```
earth-agent-bench/
  suites/
    earthdata/   suite.toml + tasks/ (18 rubric + 10 eval)   # existing
    coding/      suite.toml + tasks/ (SWE/Term/SCI, 10)       # <- from mini-benchmarks
    agentic/     suite.toml + tasks/ (6 base + 5 hard)        # <- from intelligence-index
  probes/
    serving/     probe.toml + run.py                          # <- bench-models.py speed/ctx
  experiments/   models.yaml, harnesses.yaml, conditions.yaml
  harbor/        harbor.yaml (providers), runtime/
  reports/       one aggregated store
```

`suite.toml`:
```toml
id = "agentic"
tasks_glob = "tasks/*/*"
scorer = "content_check"        # content_check | typed_equality | rubric | test_based
default_harnesses = ["pi", "opencode", "codex-cli", "claude-code"]
default_conditions = ["baseline"]
timeout_sec = 600
earthdata = false
```

## 4. Core abstraction: **Probe** (non-Harbor measurements)

The serving characterization (max ctx/KV that fits, tok/s, tokens) is not a
Harbor task. Model it as a **probe** that writes into the same results store:

```
probes/serving/run.py   # port of clusterfunk/intelligence-index/scripts/bench-models.py
                        #   - reuse the live-snapshot runner-rewrite + capacity probe
                        #   - llama-benchy for tok/s; llama-swap activity + LiteLLM
                        #     SpendLogs for token accounting
```
`eab serve --models …` runs it; results land in `reports/` tagged `suite="serving"`.

## 5. Core abstraction: **Runtime provider**

Add `runtime` to suites/jobs, with two providers:

| runtime | environment step | notes |
|---|---|---|
| `harbor-docker` (default) | Harbor builds the task's `environment/Dockerfile` | current behaviour; SWE/Terminal need this |
| `sbx` | agent runs inside a Docker Sandbox kit (mixins) | credential proxy, MCP/skills as kit-args |

Select via `suite.toml` or `eab run --runtime sbx`.

### Why sbx matters here
- **Credential proxy:** the LiteLLM key and `EARTHDATA_TOKEN` never enter the
  sandbox (host proxy injects them) — satisfies EAB's "never bake/print secrets"
  rule.
- **Conditions map 1:1 to kit-args:** `baseline` = `--no-tools --no-skills`,
  `mcp` = `--tools cmr,earthaccess`, `skills` = `--skills …`,
  `mcp-skills` = both. Same axis, implemented by the environment.
- **One canonical box** for all four harnesses (EAB's exact harness set) with
  pixi/LSP/git-over-SSH/Basic Memory.

### Why not sbx-only runtime
SWE-bench/Terminal tasks ship Docker environments + test harnesses; porting them
to sbx is a large conversion and loses Harbor's verifier/manifest/budget
plumbing. Use `harbor-docker` for those, `sbx` where it wins (agentic/earthdata
conditions, credential proxy).

## 6. Shared dimensions

- **Roster** — `experiments/models.yaml` (single source of truth). Local models
  namespaced `local/…`; add `serving:`/`findings:` blocks.
- **Harnesses** — `experiments/harnesses.yaml`; real wiring in `harbor/harbor.yaml`
  (+ `scripts/patch-harbor.sh` for the codex/claude model-id fixes).
- **Conditions** — `experiments/conditions.yaml`; unchanged semantically, wired
  either via Harbor `[[environment.mcp_servers]]`/`--skill` or sbx kit-args.
- **Instrumentation** — `eab_instrument.py` (access events) for earthdata; token
  capture for serving; suite-specific verifiers otherwise.

## 7. Commands (unified CLI)

```bash
eab doctor                                   # gateway + models + mcp preflight
eab serve --models lfm2.5-2.6b,deepseek-qwen3.5-9b-mtp   # serving probe
eab run --suite earthdata --conditions all --models ...
eab run --suite coding   --models tiel-coder-35b --harnesses pi,opencode
eab run --suite agentic  --models ... --conditions baseline --runtime sbx
eab report --by suite,model,harness          # one table across everything
```

## 8. Unified results + report

Every run writes a record:
```json
{"suite":"coding","model":"tiel-coder-35b","harness":"pi","condition":"baseline",
 "task":"SWE-03","reward":1.0,"in_tokens":…,"out_tokens":…,"run":"…"}
```
`eab report --by suite,model,harness` produces the cross-suite matrix
(reuse the aggregator already added: `src/earth_agent_bench/report.py`).

## 9. Migration plan (phased)

**Phase 0 — foundations (done / trivial).**
- Roster + harness wiring + `patch-harbor.sh` (done).
- `eab models doctor`, `eab mcp doctor`, `eab report` (done).

**Phase 1 — suite layer (small).**
1. Create `suites/{earthdata,coding,agentic}/` + `suite.toml`.
2. Move mini-benchmarks `tasks/` → `suites/coding/tasks/`; mini `manifest.yaml`
   → `suites/coding/suite.toml`.
3. Convert intelligence-index `tasks/*.json` + `check` specs → Harbor packages
   under `suites/agentic/` (grader = content_check).
4. `eab run --suite …` selects the suite's tasks + grader; tag runs with `suite`.

**Phase 2 — serving probe.**
5. Port `bench-models.py` → `probes/serving/`. `eab serve`. Same results store.

**Phase 3 — runtime provider.**
6. Add `runtime` abstraction; implement `harbor-docker` (current) and a stub
   `sbx` provider that emits sbx kit-args from conditions.
7. Build `earthdata` + `coding`/`agentic` sbx mixins (agent box + creds proxy +
   MCP/skills). Move non-SWE suites onto `sbx`; keep SWE/Terminal on
   `harbor-docker`.

**Phase 4 — publish + unify reports.**
8. Publish suites as EAB/Harbor **datasets** (`eab publish` / `harbor dataset`)
   so any Harbor install can pull them.
9. One `eab report` across all suites; retire the standalone
   `mini-benchmarks/runner` and `intelligence-index` reports.

## 10. Risks / open questions

- **Runtime portability:** sbx/Docker-Sandboxes framing vs Harbor's
  Dockerfile+`tests/verify.py` lifecycle — needs an adapter; validate on one
  suite first.
- **SWE/Terminal envs:** keep on `harbor-docker`; don't port.
- **Grading parity:** keep each suite's grader; do not force one scorer.
- **`earthaccess-mcp` is still pending** — the `mcp`/`mcp-skills` conditions
  currently wire `cmr-mcp` + skills only.
- **MCP stateful-session limit** (LiteLLM) — raise limit/TTL; per-turn MCP
  preflight before scored runs.
- **Token budgets:** some models (Turbo-Brilliance) over-reason and never emit a
  tool call inside an agent turn; document per-model `max_tokens`/reuse notes.

## 11. Definition of done

- `eab run --suite <s> --runtime <r>` runs any of the three suites on the shared
  roster/harnesses/conditions.
- `eab serve` characterizes a model's ctx/throughput into the same store.
- `eab report` renders one cross-suite matrix.
- sbx is the environment provider for agentic/earthdata (credential proxy, MCP/skills);
  SWE/Terminal stay on Harbor's Docker runtime.
