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

# 2) env contract (prefer caller env; local-file fallback for the maintainer)
export LITE_LLM_ENDPOINT="${LITE_LLM_ENDPOINT:-${LITELLM_BASE_URL:-https://llm.betolink.cloud}}"
export LITE_LLM_API_KEY="${LITE_LLM_API_KEY:-${LITELLM_API_KEY:-$(cat ~/.lite-llm-key 2>/dev/null || true)}}"
export EARTHDATA_TOKEN="${EARTHDATA_TOKEN:-$(tr -d '\n' < ~/.EDL_TOKEN 2>/dev/null || true)}"
EAB=".venv/bin/eab"

# 3) preflight: prove the gateway the agents will actually use is reachable
echo "resolved LITE_LLM_ENDPOINT: $LITE_LLM_ENDPOINT" | tee -a "$LOG"
code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 "${LITE_LLM_ENDPOINT}/v1/models" \
  -H "Authorization: Bearer ${LITE_LLM_API_KEY}" -H "User-Agent: earth-agent-bench/0.1")
if [ "$code" != "200" ]; then
  echo "ABORT: gateway ${LITE_LLM_ENDPOINT}/v1/models -> ${code} (check LITE_LLM_ENDPOINT/KEY)" | tee -a "$LOG"
  exit 1
fi
echo "gateway ok (200) at $(date -u +%FT%TZ)" | tee -a "$LOG"

# 4) host-side loop watchdog
python3 scripts/loop_watchdog.py >>"$LOG" 2>&1 &
WATCHDOG=$!
trap 'kill "$WATCHDOG" 2>/dev/null' EXIT

# 5) resume: skip cells already completed in this run
declare -A DONE
while IFS= read -r k; do [ -n "$k" ] && DONE["$k"]=1; done \
  < <(python3 scripts/done_cells.py "$RUN_START")
echo "resume: ${#DONE[@]} cells already done" | tee -a "$LOG"

MAPFILE_TASKS=$(find benchmark/tasks -name '*.yaml' | sort)

for m in tiel-coder-35b ornith-1.5-9b; do
  for h in pi opencode codex-cli; do
    for c in baseline improve mcp skills mcp-skills; do
      echo "=== combo $m/$h/$c  $(date -u +%FT%TZ) ===" | tee -a "$LOG"
      while read -r task; do
        [ -z "$task" ] && continue
        id="$(basename "$task" .yaml)"
        if [ -n "${DONE["$id|$m|$h|$c"]:-}" ]; then
          echo "== skip $m/$h/$c $id (done)" | tee -a "$LOG"
          continue
        fi
        "$EAB" harbor run "$task" --model "$m" --harness "$h" --condition "$c" \
          >>"$LOG" 2>&1 || echo "FAILED $m/$h/$c $task" | tee -a "$LOG"
      done <<< "$MAPFILE_TASKS"
      bash scripts/fix-perms.sh runs >/dev/null 2>&1 || true
    done
  done
done
echo "ALL EAB COMBOS DONE $(date -u +%FT%TZ)" | tee -a "$LOG"
