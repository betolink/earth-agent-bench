# Quickstart: test the waters, then scale up

This is the operational runbook: prerequisites → one trial run → the four
knowledge conditions → scaling to the pilot. **Harbor is the only execution
path**: `eab harbor` generates Harbor task packages (isolated agent environment +
verifier) and invokes the `harbor` CLI.

Task ids accept aliases everywhere: `cryo-1`, `atmo-2`, `solid-3`, `o1`, `l1`
(or full ids, or `all` for the whole suite).

---

## 1. Prerequisites

1. **NASA Earthdata Login (EDL) account** — create one at
   https://urs.earthdata.nasa.gov/users/new (free). Some collections require
   approving DAAC license terms on first granule access. `earthaccess.login()`
   writes `~/.netrc` for you on first use; never commit credentials.
2. **Python environment + oracle data:**

   ```bash
   uv sync                     # bench tooling + Harbor (dev group); or: pixi install -e dev
   uv run python scripts/build_virtualizability_parquet.py
   uv run eab validate         # 18 tasks should validate
   ```

3. **LiteLLM gateway** — all models (local + API) are served through one gateway.

   ```bash
   cp experiments/litellm.example.yaml litellm.yaml   # adjust to your deployment
   ```

   Exact provider strings for the API models are confirmed at pilot burn-in
   (`confirm_at_pilot` entries in `experiments/models.yaml`).

### Environment contract

Running EAB needs exactly three environment variables (plus whatever the `harbor`
CLI and the agent harnesses need). Nothing is hard-coded to a path or host:

| var | purpose |
|---|---|
| `EARTHDATA_TOKEN` | Earthdata Login token (or `EARTHDATA_USERNAME` + `EARTHDATA_PASSWORD`) |
| `LITE_LLM_ENDPOINT` | LiteLLM gateway base URL, e.g. `https://llm.example.org` |
| `LITE_LLM_API_KEY` | gateway bearer token used by the agent harnesses |

Legacy names `LITELLM_BASE_URL` / `LITELLM_API_KEY` are still accepted as
fallbacks. Validate before a run:

```bash
export EARTHDATA_TOKEN=... LITE_LLM_ENDPOINT=https://... LITE_LLM_API_KEY=...
uv run eab doctor
```

`eab doctor` checks the three vars, probes `/v1/models`, and reports whether the
key may read LiteLLM **spend/logs**.

> **Observability note.** Token/cost accounting that reads LiteLLM logs (spend
> endpoints) needs a key with **log/admin scope**. Inference-only keys return
> `401/403` on `/spend/logs`; `eab doctor` flags this so you can supply a
> separate admin key for reporting. If you don't need LiteLLM-side accounting,
> EAB's own reports use the per-trial token counts from Harbor run artifacts and
> the gateway is used for inference only.
4. **Harnesses** — install pi / opencode / codex cli / claude code; pin
   versions and record them in `RunManifest.harness_version`.
5. **Harbor** — installed as a pinned dev dependency (`uv sync` / `pixi install
   -e dev`); no separate install. `eab harbor` generates a `task.toml` package +
   JobConfig and calls `harbor run` (agent/model/endpoint config lives in
   `harbor/harbor.yaml`).

## 2. Quick trial — one task · one model · one condition

```bash
uv run eab harbor run cryo-1 --model tiel-coder-35b --harness opencode \
    --condition mcp-skills --dry-run
# drop --dry-run to run; add --job-name NAME --force for a stable, overwritable job dir
```

## 3. What the run produces

The generated package (see `harbor/README.md`) contains the agent environment
Dockerfile (earthaccess fork + scientific stack baked in; secrets injected at
runtime via env templates), condition wiring in `task.toml` (MCP servers,
skills), and a deterministic verifier that:

- runs in a **separate verifier container** and grades **observed behavior**:
  it re-runs `access.py` with `eab_instrument` writing a verifier-owned log to
  `/logs/verifier/access_events.jsonl` (falling back to the agent's instrumented
  events under `/logs/agent`), and derives patterns/services/representation/
  validation from them. The agent's `access_summary.json` is never scored;
- writes `pass` (all-or-nothing headline) and `score` (weighted) to
  `/logs/verifier/reward.json`, plus diagnostics to `details.json`;
- for the 10 eval tasks, grades `output/answer.txt` with the deterministic
  `earth_agent_bench.evals.grade`.

`eab harbor run` writes a JobConfig per run and invokes
`harbor run --config <task>/job.yaml --jobs-dir runs/harbor --yes`; results land
in `runs/harbor/<job_name>/`.

Watch runs live in Harbor's bundled web viewer:

```bash
eab view          # http://127.0.0.1:8080/ over runs/harbor
```

Pick models in `experiments/models.yaml` (the roster) and
`experiments/run.yaml` (the selection); `eab models list` shows both sides.

## 4. Running the four knowledge conditions

Per condition, the runner/generator wires the workspace for you — only the
knowledge input changes; model, harness and limits stay identical:

| Condition | MCP servers registered | Skills mounted |
|---|---|---|
| baseline | none | no |
| mcp | cmr (+ earthaccess when it ships) | no |
| skills | none | yes |
| mcp-skills | cmr (+ earthaccess) | yes |

`cmr-mcp` is live at `https://cmr.earthdata.nasa.gov/mcp/v1`; `earthaccess-mcp`
is pending — until it ships, MCP conditions test discovery-level knowledge only
(`mcp/README.md`, `mcp/manifest.yaml`).

## 5. Test-the-waters checklist

- [ ] EDL auth works (`earthaccess.login()` prints `Authenticated: True`)
- [ ] `eab validate` passes; `eab matrix <short_name>` matches reality
- [ ] a gateway model completes a task end-to-end (`eab harbor run …`)
- [ ] the verifier re-ran the deliverable and observed real access events
- [ ] `pass`/`score` and the observed pattern match the trajectory
- [ ] the same task runs under baseline and one MCP/skills condition with only
      that variable changed
- [ ] `eab harbor run cryo-1 … --dry-run` prints a command your installed
      `harbor` CLI accepts — adjust the agent mapping in `harbor/harbor.yaml`
      if flags differ

## 6. Scaling up: screen, then the full matrix

Once one run works, loop over the matrix (`experiments/run.yaml`: models ×
harnesses × conditions × tasks):

```bash
uv run eab harbor run --models tiel-coder-35b --harnesses opencode --conditions mcp-skills
```

**Screen candidate models first** on `experiments/evals/tasks` (cheap
correctness), then run the full matrix on `benchmark/tasks` — see
`benchmark/tasks/README.md`. To publish the suite as a Harbor dataset:

```bash
uv run eab harbor dataset all
harbor datasets download eab/earth-agent-bench
```

## 7. What exists vs. what is missing

Authoritative backlog with acceptance criteria per gap: **`docs/gaps.md`**.

**Exists now:** 18 validated tasks + gold standards · 10 eval tasks +
deterministic grader (`eab eval`) · EDVS parquet oracle + curated service
catalog + live CMR discovery · scoring CLI + schemas (incl. `RunManifest`) ·
experiment matrices · 5 skills · MCP wiring (cmr-mcp live) · Harbor package
generation + JobConfig + isolated instrumented verifier + digest-pinned dataset
(`eab harbor`) · this runbook.

**Missing before the full run (in priority order):**

1. **Harness pins** — record `harbor --version` and each harness version in
   `experiments/harnesses.yaml`. The earthaccess fork and agent stack are
   already pinned in `src/earth_agent_bench/harbor/runtime/agent-requirements.txt`.
2. **Access instrumentation fidelity** — observed calls are instrumented
   (`eab_instrument`); remaining: real `bytes_read` (not self-reported) and
   disambiguating `earthaccess.open` (cloud C1 vs OPeNDAP S2).
3. **Minimal-science-gate depth** — programmatic artifact checks per task
   (variable/extent/units/aggregation), not just real-access presence.
4. **Reference solutions** — expert workflows (`solution/reference_workflow.py`)
   to validate gold standards before the experiment.
5. **earthaccess-mcp endpoint** — pending; until then MCP conditions are
   discovery-level only.
6. **Final skills** — current skills are scaffolds; the full set arrives with
   the earthaccess MCP work.
7. **Batch resume + statistics** — the matrix runs today, but restart/resume,
   `RunManifest` rollups, and the condition/tier result tables are still to do.
