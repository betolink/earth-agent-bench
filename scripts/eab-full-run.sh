#!/usr/bin/env bash
# Full EAB suite: 18 grounded tasks x {models} x {pi,opencode,codex-cli}
# x {baseline,improve,mcp,skills,mcp-skills}, one isolated Harbor job per cell.
#
# - Env contract: EARTHDATA_TOKEN, LITE_LLM_ENDPOINT, LITE_LLM_API_KEY.
# - Preflight: probes the resolved gateway the agents will use; aborts if not 200.
# - Resume: reuse a run stamp (EAB_RUN_START) and skip cells already completed in
#   it (scripts/done_cells.py). Delete a broken cell's job dir to re-run it.
# - Agent cap is harbor.yaml agent_timeout_sec; the loop watchdog ends stuck
#   trials early (>WATCH_STALL idle or >WATCH_EXACT identical commands).
set -uo pipefail
cd "$(dirname "$0")/.."   # earth-agent-bench repo root

RUN_START="${EAB_RUN_START:-$(date -u +%Y%m%d-%H%M%S)}"
LOG="runs/eab-full-${RUN_START}.log"
echo "EAB full run log: $LOG  (run_start=$RUN_START)" | tee -a "$LOG"

# 1) wait for the coding-suite runner to release the GPU (single-slot)
while pgrep -f 'runner/run.py' >/dev/null 2>&1; do sleep 60; done

# 2) secrets: env vars, or an env-file (EAB_ENV_FILE, else ./.env). No loose files.
ENV_FILE="${EAB_ENV_FILE:-}"
[ -z "$ENV_FILE" ] && [ -f .env ] && ENV_FILE=".env"
if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
  echo "loading env from ${ENV_FILE}" | tee -a "$LOG"
  set -a; . "$ENV_FILE"; set +a
fi
# accept legacy alias names
export LITE_LLM_ENDPOINT="${LITE_LLM_ENDPOINT:-${LITELLM_BASE_URL:-}}"
export LITE_LLM_API_KEY="${LITE_LLM_API_KEY:-${LITELLM_API_KEY:-}}"
if [ -z "${LITE_LLM_ENDPOINT}" ] || [ -z "${LITE_LLM_API_KEY}" ] \
   || { [ -z "${EARTHDATA_TOKEN:-}" ] && [ -z "${EARTHDATA_USERNAME:-}" ]; }; then
  echo "ABORT: missing secrets. Set EARTHDATA_TOKEN, LITE_LLM_ENDPOINT, LITE_LLM_API_KEY" | tee -a "$LOG"
  echo "       (as env vars, or an env-file via EAB_ENV_FILE; copy .env.example -> .env)" | tee -a "$LOG"
  exit 1
fi
EAB=".venv/bin/eab"

# 3) run matrix from experiments/run.yaml (override with EAB_MODELS/HARNESSES/CONDITIONS/TASKS)
eval "$(.venv/bin/eab config --shell)"
echo "matrix: name=[${EAB_RUN_NAME:-eab-full}] models=[$MODELS] harnesses=[$HARNESSES] conditions=[$CONDITIONS] concurrency=${CONCURRENCY:-1}" | tee -a "$LOG"

# 3b) record a named manifest for this experiment (name -> stamp -> config)
.venv/bin/python - "$RUN_START" <<PY 2>>"$LOG"
import sys
from earth_agent_bench.runconfig import load_run_config, write_manifest
p = write_manifest(load_run_config(), sys.argv[1], log="runs/eab-full-${RUN_START}.log")
print(f"manifest: {p}")
PY

# 3c) graceful pause: `touch runs/PAUSE` pauses after the current cell; remove to resume.
PAUSE_FILE="${EAB_PAUSE_FILE:-runs/PAUSE}"
pause_gate() {
  [ -f "$PAUSE_FILE" ] || return 0
  echo "PAUSED (found $PAUSE_FILE) at $(date -u +%FT%TZ) — remove it to resume" | tee -a "$LOG"
  while [ -f "$PAUSE_FILE" ]; do sleep 15; done
  echo "RESUMED at $(date -u +%FT%TZ)" | tee -a "$LOG"
}

# 4) preflight: prove the gateway the agents will actually use is reachable
echo "resolved LITE_LLM_ENDPOINT: $LITE_LLM_ENDPOINT" | tee -a "$LOG"
code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 "${LITE_LLM_ENDPOINT}/v1/models" \
  -H "Authorization: Bearer ${LITE_LLM_API_KEY}" -H "User-Agent: earth-agent-bench/0.1")
if [ "$code" != "200" ]; then
  echo "ABORT: gateway ${LITE_LLM_ENDPOINT}/v1/models -> ${code} (check LITE_LLM_ENDPOINT/KEY)" | tee -a "$LOG"
  exit 1
fi
echo "gateway ok (200) at $(date -u +%FT%TZ)" | tee -a "$LOG"

# 5) host-side loop watchdog (single-trial; only meaningful when sequential)
if [ "${CONCURRENCY:-1}" -le 1 ]; then
  python3 scripts/loop_watchdog.py >>"$LOG" 2>&1 &
  WATCHDOG=$!
  trap 'kill "$WATCHDOG" 2>/dev/null' EXIT
else
  echo "concurrency=${CONCURRENCY}: loop watchdog disabled (parallel run)" | tee -a "$LOG"
fi

# 6) resume: skip cells already completed in this run
declare -A DONE
while IFS= read -r k; do [ -n "$k" ] && DONE["$k"]=1; done \
  < <(.venv/bin/python scripts/done_cells.py "$RUN_START")
echo "resume: ${#DONE[@]} cells already done" | tee -a "$LOG"

MAPFILE_TASKS=$(find benchmark/tasks -name '*.yaml' | sort)
CONC="${CONCURRENCY:-1}"

run_cell() {  # $1=task $2=model $3=harness $4=condition
  "$EAB" harbor run "$1" --model "$2" --harness "$3" --condition "$4" \
    >>"$LOG" 2>&1 || echo "FAILED $2/$3/$4 $1" | tee -a "$LOG"
}

for m in $MODELS; do
  for h in $HARNESSES; do
    for c in $CONDITIONS; do
      echo "=== combo $m/$h/$c  $(date -u +%FT%TZ) ===" | tee -a "$LOG"
      pause_gate
      # Before `improve`, (re)generate the model's self-improvement skill from its
      # non-improve runs, so the improve cells actually mount it. Only regenerate
      # once per model (when the first harness reaches improve).
      if [ "$c" = "improve" ] && [ "$h" = "${HARNESSES%% *}" ]; then
        echo "== postmortem $m (harness=all) $(date -u +%FT%TZ) ==" | tee -a "$LOG"
        "$EAB" postmortem "$m" --harness all >>"$LOG" 2>&1 \
          || echo "postmortem failed for $m" | tee -a "$LOG"
      fi
      while read -r task; do
        [ -z "$task" ] && continue
        id="$(basename "$task" .yaml)"
        if [ -n "${DONE["$id|$m|$h|$c"]:-}" ]; then
          echo "== skip $m/$h/$c $id (done)" | tee -a "$LOG"
          continue
        fi
        pause_gate
        run_cell "$task" "$m" "$h" "$c" &
        while [ "$(jobs -rp | wc -l)" -ge "$CONC" ]; do wait -n; done
      done <<< "$MAPFILE_TASKS"
      wait
      bash scripts/fix-perms.sh runs >/dev/null 2>&1 || true
    done
  done
done
echo "ALL EAB COMBOS DONE $(date -u +%FT%TZ)" | tee -a "$LOG"
