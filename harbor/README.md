# Harbor packaging

`eab harbor` turns benchmark and eval tasks into **real Harbor task packages**
(`task.toml` + `instruction.md` + `environment/Dockerfile` + `tests/` +
`solution/`) and drives the Harbor CLI.

Harbor is a third-party agent-evaluation framework (docs at
<https://harborframework.com>) installed as a project dev dependency
(`uv sync` / `pixi install -e dev`), so it is version-pinned alongside the rest
of the tooling. It ships the harness adapters directly — `harbor agent list`
includes `opencode`, `codex`, `claude-code`, and `pi` — so this repo does
**not** install or configure any harness on the Harbor path. The Earthdata MCP
servers and skills are passed to the agent through Harbor's `[environment]`
config and `--skill`.

## Commands

```bash
# generate packages (aliases: cryo-1, atmo-2; also full paths, eval ids,
# 'all', and 'pilot')
uv run eab harbor generate cryo-1,atmo-2 --condition mcp-skills

# render the harbor command without running (prints job.yaml + argv)
uv run eab harbor run experiments/evals/tasks/01_hls_open_vs_download.md \
    --model tiel-coder-35b --harness opencode --dry-run

# run for real (requires the harbor CLI installed)
uv run eab harbor run 01_hls_open_vs_download \
    --model tiel-coder-35b --harness opencode --condition baseline
```

`--harness` is the benchmark id (`pi`, `opencode`, `codex-cli`, `claude-code`);
`harbor.yaml` maps `codex-cli` → Harbor's `codex`.

## Generated package layout (`harbor/generated/<task_id>/`, gitignored)

```
task.toml                   Harbor task config (schema_version 1.4)
instruction.md              agent prompt (eval contract or benchmark brief)
environment/Dockerfile      sandbox image: earthaccess fork + scientific stack
environment/agent-requirements.txt
environment/eab_instrument.py   access instrumentation (.pth-installed)
tests/test.sh               verifier entrypoint -> /logs/verifier/reward.*
tests/verify.py             deterministic grader driver
tests/gold.json             eval gold        (correctness tasks)
tests/task.yaml             task definition  (benchmark tasks)
tests/earth_agent_bench/    vendored: evals.py or schemas/scoring, + harbor_verify.py
solution/solve.sh           oracle reference placeholder (not shown to agents)
job.yaml                    generated JobConfig binding agent + model + endpoint
```

## Source layout (`src/earth_agent_bench/harbor/`)

```
__init__.py     public API
config.py       harbor.yaml + repo paths
resolve.py      task selection (ids, sphere aliases, dirs, globs)
packages.py     generate_package: renders task.toml/instruction, vendors grader
jobs.py         JobConfig + `harbor run`
runtime/        files copied into every generated package:
  Dockerfile, agent-requirements.txt, test.sh, solve.sh
  eab_instrument.py    patches earthaccess/harmony/pydap/s3fs/virtualizarr -> events
  harbor_verify.py     shared verifier helpers (roots, event summary)
  verify_eval.py       correctness-eval grader
  verify_benchmark.py  access-pattern grader
```


## `task.toml`

- `[agent] timeout_sec = 600` and `[verifier] timeout_sec = 600` — the 10-minute
  execution budget, enforced by Harbor.
- `[environment] network_mode = "public"` and `build_timeout_sec = 1800`.
- `[[environment.mcp_servers]]` — the `mcp` / `mcp-skills` conditions declare the
  ready servers from `mcp/manifest.yaml` (via `experiments/conditions.yaml`).
- `[environment] skills_dir = "/harbor/skills"` — the `skills` / `mcp-skills`
  conditions; the run also passes `--skill <repo>/skills` so Harbor injects them.
- `[environment.env]` — `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` as `${VAR:-}`
  templates, resolved from the host at runtime (never baked into images).

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
`experiments/models.yaml`, prefixed with the provider from `harbor.yaml`:

| harness | Harbor agent | provider | model_name |
|---|---|---|---|
| `pi` | `pi` | openai | `openai/<litellm_model>` (+ `model_api: openai-completions`) |
| `opencode` | `opencode` | openai | `openai/<litellm_model>` |
| `codex-cli` | `codex` | openai | `openai/<litellm_model>` |
| `claude-code` | `claude-code` | anthropic | `anthropic/<litellm_model>` |

## Verifier behavior

- **Correctness eval** (`tests/gold.json`): the deterministic, LLM-free
  `earth_agent_bench.evals.grade` compares `output/answer.txt` to the gold; the
  reward is the fractional score (0/1, plus the FineEnvs tool bonus when
  instrumented). A missing answer is *uncovered*, not scored wrong.
- **Benchmark** (`tests/task.yaml`): grades **observed behavior**. The sandbox's
  `eab_instrument` writes one JSON line per real access call to
  `/logs/agent/access_events.jsonl` (`earthaccess`, `harmony`, `pydap`, `s3fs`,
  `virtualizarr`); the verifier derives patterns/services/representation/
  validation from those events, falling back to `output/access_summary.json`.
  Component scores go to `/logs/verifier/reward.json` (numeric only) and
  diagnostics to `details.json`.
- Exit code is 0 whenever the reward files are written; Harbor reads the reward.

## Secrets

Never baked into images or the repo. `job.yaml` carries `${LITELLM_API_KEY:-}`
and `task.toml` carries the `${EARTHDATA_*}` templates; both resolve from the
host environment at run time.
