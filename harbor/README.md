# Harbor packaging

`eab harbor` turns benchmark and eval tasks into **real Harbor task packages**
(`task.toml` + `instruction.md` + `environment/Dockerfile` + `tests/` +
`solution/`) and drives the Harbor CLI. Harbor is the **only** execution path.

Harbor is a third-party agent-evaluation framework (docs at
<https://harborframework.com>) installed as a project dev dependency
(`uv sync` / `pixi install -e dev`), so it is version-pinned alongside the rest
of the tooling. It ships the harness adapters directly — `harbor agent list`
includes `opencode`, `codex`, `claude-code`, and `pi` — so this repo does
**not** install or configure any harness on the Harbor path.

## Commands

```bash
# generate packages (aliases: cryo-1, atmo-2; also full paths, eval ids,
# 'all', and 'pilot')
uv run eab harbor generate cryo-1,atmo-2 --condition mcp-skills

# render the harbor command without running (prints job.yaml + argv)
uv run eab harbor run benchmark/tasks/correctness/01_hls_open_vs_download.md \
    --model tiel-coder-35b --harness opencode --dry-run

# run for real (requires the harbor CLI installed)
uv run eab harbor run 01_hls_open_vs_download \
    --model tiel-coder-35b --harness opencode --condition baseline

# write a digest-pinned dataset (dataset.toml + metric.py) for publishing
uv run eab harbor dataset all
```

`--harness` is the benchmark id (`pi`, `opencode`, `codex-cli`, `claude-code`);
`harbor/harbor.yaml` maps `codex-cli` → Harbor's `codex`.

## Generated package layout (`harbor/generated/<task_id>/`, gitignored)

```
task.toml                   Harbor task config (schema_version 1.4)
instruction.md              agent prompt (eval contract or benchmark brief)
environment/Dockerfile      sandbox image: earthaccess fork + scientific stack
environment/agent-requirements.txt  fully pinned (uv pip compile) + fork commit
environment/eab_instrument.py   access instrumentation (.pth-installed)
tests/test.sh               verifier entrypoint -> /logs/verifier/reward.*
tests/verify.py             deterministic grader driver
tests/gold.json             eval gold        (correctness tasks)
tests/task.yaml             task definition  (benchmark tasks)
tests/earth_agent_bench/    vendored: evals.py or schemas/scoring, + harbor_verify.py
solution/solve.sh           oracle runner: executes solution/reference_workflow.py
job.yaml                    generated JobConfig binding agent + model + endpoint
```

## `task.toml`

- `[task]` — `name`, `version`, `description`, `authors`, `keywords`; the root
  `source` field records provenance (the task YAML's repo path).
- `[metadata]` — flat interoperability labels: `suite` (`benchmark` /
  `correctness`), `sphere`, `kind`, `data_type`, `processing_level`,
  `length_class`, `infeasible`, `difficulty`, gold/acceptable patterns,
  collections + `concept_id`s, and the demo scope.
- `[agent] timeout_sec = 720` and `[verifier] timeout_sec = 600` — the execution
  budget, enforced by Harbor.
- `[verifier] environment_mode = "separate"` — the verifier runs in its own
  container, so the agent never shares a filesystem with the answer key.
- `[environment] network_mode = "public"`, `build_timeout_sec = 1800`,
  `cpus` / `memory_mb` / `storage_mb` caps.
- `[[environment.mcp_servers]]` — the `mcp` / `mcp-skills` conditions declare the
  ready servers from `mcp/manifest.yaml` (via `experiments/conditions.yaml`).
- `[environment] skills_dir = "/harbor/skills"` — the `skills` / `mcp-skills`
  conditions; the run also passes `--skill <repo>/skills` so Harbor injects them.
- `[environment.env]` — `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` /
  `EARTHDATA_TOKEN` as `${VAR:-}` templates, resolved from the host at runtime
  (never baked into images).
- `[[artifacts]]` — `/app/output`, `/app/work`, `/app/access.py`, `/logs/agent`.
  They are collected after the agent phase and re-materialized at the same paths
  in the verifier container, which makes verification reproducible and keeps the
  deliverable auditable.

## JobConfig (`job.yaml`)

`eab harbor run` writes one JobConfig per run and invokes:

```bash
harbor run --config <task>/job.yaml --jobs-dir <runs>/harbor --yes
```

Each run gets a **unique job directory** (`runs/harbor/<job_name>`, timestamped)
so a re-run after a config change never trips Harbor's "job directory already
exists and cannot be resumed with a different config" check, and history is
preserved. Use `--job-name NAME` for a fixed, reproducible path and `--force` to
delete an existing directory of that name first.

The config sets `n_attempts: 1`, the agent (`name` + `model_name`), and the
LiteLLM endpoint. Model names are the gateway ids from
`experiments/models.yaml`, prefixed with the provider from `harbor/harbor.yaml`:

| harness | Harbor agent | provider | model_name |
|---|---|---|---|
| `pi` | `pi` | openai | `openai/<litellm_model>` (+ `model_api: openai-completions`) |
| `opencode` | `opencode` | openai | `openai/<litellm_model>` |
| `codex-cli` | `codex` | openai | `openai/<litellm_model>` |
| `claude-code` | `claude-code` | anthropic | `anthropic/<litellm_model>` |

## Verifier behavior

- **Correctness eval** (`tests/gold.json`): the deterministic, LLM-free
  `earth_agent_bench.evals.grade` compares `output/answer.txt` to the gold;
  `reward.json` carries `reward` and `pass` (the same 0/1 value). A missing
  answer is *uncovered*, not scored wrong.
- **Benchmark** (`tests/task.yaml`): grades **observed behavior**. The verifier
  re-runs `access.py` in its own container with `EAB_ACCESS_LOG` pointing at
  `/logs/verifier/access_events.jsonl` (so evidence cannot be pre-seeded), and
  falls back to the agent's instrumented events under `/logs/agent`. It never
  scores `access_summary.json`.
- `reward.json` carries `pass` (all-or-nothing headline), `reward` (= `pass`, for
  monokey tooling), `score` (weighted partial credit) and the component scores;
  `reward.txt` carries `pass`; diagnostics go to `details.json`.
- `pass` requires: re-run `exec_status == "ok"`, sanctioned code (no raw CMR),
  a best/acceptable dominant pattern, and real access events.
- Exit code is 0 whenever the reward files are written; Harbor reads the reward.

## Dataset (`dataset.toml` + `metric.py`)

`eab harbor dataset all` generates the packages, pins each by content digest, and
writes `harbor/dataset.toml` with `harbor/metric.py` as a dataset-level file. The
metric reads one JSON line per attempt and reports the mean `pass` (falling back
to `reward`), which is what Harbor's dataset leaderboards consume — the built-in
metric rejects the multi-key dictionaries benchmark tasks write.

Publish / consume with Harbor:

```bash
harbor publish                         # from this repo's dataset
harbor datasets download eab/earth-agent-bench
```

Regenerate the dataset whenever a task or the generator changes.

## Secrets

Never baked into images or the repo. `job.yaml` carries `${LITE_LLM_API_KEY:-}`
and `task.toml` carries the `${EARTHDATA_*}` templates; both resolve from the
host environment at run time.
