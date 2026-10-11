# Quickstart: test the waters, then scale up

This is the operational runbook: prerequisites → one trial run → the four
knowledge conditions → scaling to the pilot. Two execution paths exist:

- **Direct** (`eab run`) — builds a workspace and launches a harness on your host.
  Fastest way to test the waters; no Harbor required.
- **Harbor** (`eab harbor`) — generates Harbor task packages (isolated agent
  environment + verifier) and invokes the `harbor` CLI. This is the path that
  scales to the pilot/full matrices.

Task ids accept aliases everywhere: `cryo-1`, `atmo-2`, `solid-3`, `o1`, `l1`
(or full ids, or `pilot` / `all` for whole suites).

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

## 2. Quick trial — direct path (one task · one model · one condition)

```bash
uv run eab run benchmark/tasks/cryosphere/c1-itslive-jakobshavn-2015-2024.yaml \
    --model tiel-coder-35b --harness opencode --condition mcp-skills --dry-run
```

Remove `--dry-run` to launch: the runner creates
`runs/<task>/<model>/<harness>/<condition>/trial-1/` containing the rendered
instruction (gold standard hidden), AGENTS.md with an output contract, harness
MCP/model config, a `manifest.json`, and an `observation.template.json`.
The agent must write artifacts to `./output/` and an
`./output/access_summary.json`.

After the run, fill `observation.json` from what the agent *did* (never what it
claims), then score:

```bash
cp runs/.../observation.template.json runs/.../observation.json   # edit
uv run eab score runs/.../observation.json
```

`observed_patterns` codes: `C1` virtualization · `C2` native zarr · `C3` COG ·
`S1` Harmony · `S2`/`S3` OPeNDAP/DMR++ · `S4` AppEEARS · `S5` Giovanni ·
`F1`–`F4` filtered download · `M1`/`M2` full download.

## 3. Quick trial — Harbor path (isolated + auto-scored)

```bash
uv run eab harbor run cryo-1 --model tiel-coder-35b --harness opencode --dry-run
# drop --dry-run to run; add --job-name NAME --force for a stable, overwritable job dir
```

The generated package (see `harbor/README.md`) contains the agent environment
Dockerfile (earthaccess fork + scientific stack baked in; secrets injected at
runtime via env templates), condition wiring in `task.toml` (MCP servers,
skills), and a deterministic verifier that:

- runs in the agent environment (shared) and grades **observed behavior**:
  `eab_instrument` logs the agent's real `earthaccess` / `harmony` / `pydap` /
  `s3fs` / `virtualizarr` calls to `/logs/agent/access_events.jsonl`, and the
  verifier derives patterns/services/representation/validation from them
  (falling back to `output/access_summary.json`);
- writes component scores to `/logs/verifier/reward.json` (numeric) and
  diagnostics to `details.json`;
- for the 10 eval tasks, grades `output/answer.txt` with the deterministic
  `earth_agent_bench.evals.grade`.

`eab harbor run` writes a JobConfig per run and invokes
`harbor run --config <task>/job.yaml --jobs-dir runs/harbor --yes`; results land
in `runs/harbor/<job_name>/`.

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
- [ ] a gateway model completes a task end-to-end in a harness (`eab run`)
- [ ] the artifact passes the task's minimal science gate
- [ ] an observation scores, and the pattern recorded matches the trajectory
- [ ] the same task runs under baseline and one MCP/skills condition with only
      that variable changed
- [ ] (Harbor path) `eab harbor run cryo-1 ... --dry-run` prints a command your
      installed `harbor` CLI accepts — fix the template in `harbor/harbor.yaml`
      if flags differ

## 6. Scaling up: pilot, then full

Both paths loop naturally once a single run works:

```bash
# direct: repeat eab run per matrix cell
# harbor: the pilot suite resolves as a task list
uv run eab harbor run pilot --model tiel-coder-35b --harness opencode --condition mcp-skills
```

The matrices themselves live in `experiments/pilot.yaml` (108 + 12 runs) and
`experiments/full.yaml` (5,832 + 216 runs at 3 trials, budget-guarded for
closed references). A batch orchestrator that walks those matrices and writes a
`RunManifest` per run is still to be built (§7).

## 7. What exists vs. what is missing

Authoritative backlog with acceptance criteria per gap: **`docs/gaps.md`**.

**Exists now:** 18 validated tasks + gold standards · 10 eval tasks +
deterministic grader (`eab eval`) · EDVS parquet oracle + curated service
catalog + live CMR discovery · scoring CLI + schemas (incl. `RunManifest`) ·
experiment matrices · 5 skills · MCP wiring (cmr-mcp live) · direct single-run
runner (`eab run`) · Harbor package generation + JobConfig + instrumented
auto-scoring verifier (`eab harbor`) · this runbook.

**Missing before the full run (in priority order):**

1. **Harbor pinning** — adopted and validated; record `harbor --version` in
   `experiments/harnesses.yaml` and pin the earthaccess fork commit
   (`harbor/runtime/agent-requirements.txt`).
2. **Access instrumentation fidelity** — observed calls are instrumented
   (`eab_instrument`); remaining: measure `bytes_read` (still self-reported) and
   disambiguate `earthaccess.open` (cloud C1 vs OPeNDAP S2).
3. **Minimal-science-gate depth** — programmatic artifact checks per task
   (variable/extent/units/aggregation), not just artifact presence.
4. **Reference solutions** — expert workflows per task (`solution/` is a
   placeholder) to validate gold standards before the experiment.
5. **earthaccess-mcp endpoint** — pending; until then MCP conditions are
   discovery-level only.
6. **Final skills** — current skills are scaffolds; the full set arrives with
   the earthaccess MCP work.
7. **Batch orchestration + statistics** — walk the pilot/full matrices, collect
   `RunManifest`s, produce the condition/tier result tables.
