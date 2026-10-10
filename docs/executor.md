# Executor & profiler (harness-side code execution)

Gives every agent run an **explicit outcome** instead of an ambiguous 0/1:

| status | meaning |
|---|---|
| `ok` | exited 0 within the wall / CPU / memory budget |
| `error` | exited non-zero (the deliverable raised) |
| `timeout` | exceeded the wall-clock budget (killed) |
| `oom` | exceeded the memory budget (RLIMIT_AS / SIGKILL 137) |

Correctness is graded by the caller (the task's tests or typed-equality); the
executor owns *execution* and *resource attribution* only.

## Modules

- `src/earth_agent_bench/harbor/runtime/executor.py` — `run_script(...) -> ExecResult`
  (subprocess + `RLIMIT_AS`/`RLIMIT_CPU` + wall timeout via process-group kill;
  reports wall, CPU, peak RSS, and classifies the status).
- `src/earth_agent_bench/harbor/runtime/profiler.py` — scalene / memray command
  construction + availability.
- `src/earth_agent_bench/harbor/runtime/verify_exec.py` — verifier that runs the
  deliverable, grades it (`--expected` byte-compare or `--gold` typed-equality),
  and writes reward + `details.json` with the execution profile.

## CLI

```bash
eab exec script.py --timeout 60 --mem-mb 512 --json
eab exec script.py --profile scalene --out profile.json      # line-level CPU/mem
eab exec script.py --profile memray  --out profile.bin       # allocations
```

## Two-pass rule (important)

Profiling perturbs timing (scalene ~2–10×; memray heavier). So:

1. **Clean pass** → decides `correct | incorrect` and `timeout | oom` (grading).
2. **Profile pass** (optional, only if correct) → line-level artifacts + efficiency.

Never grade efficiency from the instrumented run.

## Scope

Applies where the deliverable is **Python code** (SCI, EAB eval, cobol-style
tasks). SWE (repo patch) and Terminal (CLI/DB state) have their own graders and
different failure surfaces.

The profilers ship in the task image (`runtime/agent-requirements.txt`:
`scalene`, `memray`).

## Verifier use

A task can swap its verifier for `verify_exec.py`:

```
python /tests/verify.py \
  --script /app/program.py --workdir /app \
  --artifact output/answer.txt --expected /tests/expected.bin \
  --timeout 600 --mem-mb 2048 --profile scalene --profile-out /logs/verifier/profile.json
```

It writes `/logs/verifier/reward.{txt,json}` and `details.json` including
`exec_status`, `wall_s`, `peak_rss_mb`, and the profile path.
