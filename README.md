# earth-agent-bench

Access-pattern selection benchmark for AI agents working with NASA Earthdata.

> **Given a NASA Earthdata collection (with its CMR `concept_id`) and a bounded
> access requirement, did the agent select and execute the best access route —
> and could it justify why?**

EAB does **not** score scientific novelty, and it does **not** test collection
discovery (that belongs to the project's semantic-discovery work). Each task
names the dataset it must use and wraps a thin, representative computation
around the real evaluation surface: **access-pattern selection**, service
discovery, representation, and efficiency.

## What it measures

Access patterns are ranked **data virtualization first**, then streaming, then
server-side subsetting, then download:

`C1` virtual zarr · `C2` native zarr · `C3` COG · `S1` Harmony · `S2`/`S3`
OPeNDAP/DMR++ · `F*` filtered download · `M1`/`M2` full download
(AppEEARS/Giovanni are not ranked as "good" routes).

The benchmark runs outside AWS, so direct S3 is unavailable: tasks are won over
**HTTPS**. An EDVS parquet oracle decides virtualization availability; live CMR
decides Harmony/OPeNDAP; a curated catalog covers the rest.

## Quickstart

```bash
uv sync
uv run python scripts/build_virtualizability_parquet.py

export EARTHDATA_TOKEN=... LITE_LLM_ENDPOINT=https://... LITE_LLM_API_KEY=...
uv run eab doctor                                   # validate the contract
uv run eab validate                                 # 18 task YAMLs
uv run eab harbor run cryo-1 --model deepseek-flash-4.1 --harness opencode
```

Harbor is the **only** execution path: `eab harbor run` generates a standard
Harbor task package, writes a JobConfig, and invokes the `harbor` CLI. Add
`--dry-run` to print the command without running.

## Choose models (master config)

Two files, by design:

| File | Question | Edit it to… |
|---|---|---|
| `experiments/models.yaml` | **who exists** | add/remove models (`tier`, `litellm_model`, context…) |
| `experiments/run.yaml` | **which to benchmark** | pick roster ids, harnesses, conditions, tasks |

```bash
eab models list          # roster + served name + whether run.yaml selects it
eab models discover      # what the gateway actually serves
eab harbor run           # run the run.yaml selection
eab harbor run --models tiel-coder-35b,ornith-1.5-9b --harnesses pi,opencode
eab harbor run all --conditions baseline --dry-run
```

`eab harbor run` expands the task × model × harness × condition matrix, applies
the `harnesses.yaml` crossing restrictions, and reports skipped cells. Env vars
(`EAB_MODELS`, `EAB_HARNESSES`, `EAB_CONDITIONS`, `EAB_TASKS`) override
`run.yaml`; flags override both.

## Inspect runs

Harbor ships a local web viewer (bundled UI) for current and previous runs —
trajectories, tool calls, rewards, verifier logs, and cross-run comparison:

```bash
eab view                 # http://127.0.0.1:8080/ over runs/harbor
eab view runs/archive    # archived runs
eab view --host 0.0.0.0  # reachable remotely
```

For tables and trace review:

```bash
eab index                    # runs/index.jsonl (one record per trial)
eab report --model <id>      # per-model reward + token table
eab trajectory -t a3 -m <id> -H pi
eab analyze --model <id> --harness pi   # judge-model postmortem over traces
eab archive                  # shelve the newest jobs under runs/archive/
```

## Grading

Benchmark tasks emit two numbers:

- **`pass`** (headline, all-or-nothing): the verifier re-ran the deliverable in
  its own container, the code used a sanctioned path, the dominant observed
  pattern is best/acceptable, and real instrumented access occurred.
- **`score`** (weighted): access pattern **45%** · service discovery 15% ·
  representation 15% · efficiency 15% · validation gate 10%. Collection choice
  is not scored — the dataset is given.

The agent's self-reported summary is never scored; only instrumented access
events count. Correctness evals are deterministic 0/1 typed-equality.

## Tasks and layout

- **18 grounded tasks** (`benchmark/tasks/`) across atmosphere, cryosphere,
  biosphere, ocean, solid-earth, and land-surface — real collections, regions,
  event windows, resolved `concept_id`s.
- **10 correctness evals** (`experiments/evals/`) — cheap single-value screen.
- **Scope: NASA Earthdata only.** There is no general coding/reasoning/SWE/
  Terminal task set in this repo; general capability is out of scope.
- **Layout: default Harbor.** Every task is a standard Harbor package
  (`instruction.md`, `task.toml` schema 1.4, `environment/Dockerfile`,
  `solution/solve.sh`, `tests/test.sh`), extended with `[metadata]` labels,
  `[[artifacts]]`, resource caps, and `[verifier] environment_mode = "separate"`.
  See [harbor/README.md](harbor/README.md).

The suite is publishable as a digest-pinned Harbor dataset:

```bash
eab harbor dataset all
harbor datasets download eab/earth-agent-bench
```

## Documentation

- [docs/](docs/README.md) — index of all current docs
- [Quickstart](docs/quickstart.md) · [Running & observing](docs/running.md) ·
  [Adding tasks](docs/adding-tasks.md) (both suites) · [Tasks & evals](docs/tasks-and-evals.md)
- [Harbor packaging](harbor/README.md) · [Executor](docs/executor.md) ·
  [Gaps](docs/gaps.md)
- Historical plans and reports: [docs/archive/](docs/archive/)

## Repository layout

```
benchmark/tasks/     18 grounded task YAMLs (schema-validated)
benchmark/oracles/   curated service catalog
benchmark/data/      virtualizability.parquet (EDVS oracle)
experiments/         models.yaml (roster) · run.yaml (selection) · evals/
skills/              5 Earthdata knowledge skills
harbor/              harbor.yaml · dataset.toml · metric.py · generated/
src/earth_agent_bench/
  tasks.py           task loading + instruction rendering
  scoring/           access-pattern, discovery, representation, efficiency
  evals.py           deterministic correctness grader
  harbor/            packages · matrix · dataset · runtime verifiers/executor
  oracles/           virtualizability, services, CMR, matrix
  index/trajectory/report/archive/analyze   run inspection
scripts/             EDVS build, concept-id resolver, collection verification
tests/               unit + Harbor conformance tests
```

## Status (0.1.0)

Working: the grounded suite + oracles + scoring, Harbor as the single runner
(packages, matrix, isolated verifier with artifacts, digest-pinned dataset),
model roster/selection, the web viewer and run-inspection tools, the correctness
evals, and the code executor.

EAB is self-contained — no hard-coded hosts/paths; set `EARTHDATA_TOKEN`,
`LITE_LLM_ENDPOINT`, `LITE_LLM_API_KEY` and run `eab doctor`. Remaining work:
reference solutions, byte-level instrumentation, earthaccess-mcp, sealed/offline
mode, infeasible-task variants, batch resume — see [gaps](docs/gaps.md).
