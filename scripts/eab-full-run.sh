#!/usr/bin/env bash
# Full EAB suite: 18 grounded tasks x 2 models x 3 harnesses x 5 conditions
# (baseline, improve, mcp, skills, mcp-skills) = 540 isolated Harbor jobs.
# baseline+improve run first per harness so the intervention delta appears early.
# Waits for any mini-benchmarks runner to finish first (GPU is single-slot).
# Agent timeout is set via harbor.yaml (agent_timeout_sec: 900).
set -uo pipefail
cd "$(dirname "$0")/.."   # earth-agent-bench repo root

LOG="runs/eab-full-$(date -u +%Y%m%d-%H%M%S).log"
echo "EAB full run log: $LOG" | tee -a "$LOG"

# 1) wait for the coding-suite runner to release the GPU
while pgrep -f 'runner/run.py' >/dev/null 2>&1; do sleep 60; done
echo "GPU free at $(date -u +%FT%TZ)" | tee -a "$LOG"

export LITELLM_API_KEY="$(cat ~/.lite-llm-key)"
export EARTHDATA_TOKEN="$(tr -d '\n' < ~/.EDL_TOKEN)"
EAB=".venv/bin/eab"

# host-side loop watchdog: end trials early when the agent repeats an access attempt
python3 scripts/loop_watchdog.py >>"$LOG" 2>&1 &
WATCHDOG=$!
trap 'kill "$WATCHDOG" 2>/dev/null' EXIT

MAPFILE_TASKS=$(find benchmark/tasks -name '*.yaml' | sort)

for m in tiel-coder-35b ornith-1.5-9b; do
  for h in pi opencode codex-cli; do
    for c in baseline improve mcp skills mcp-skills; do
      echo "=== combo $m/$h/$c  $(date -u +%FT%TZ) ===" | tee -a "$LOG"
      while read -r task; do
        [ -z "$task" ] && continue
        "$EAB" harbor run "$task" --model "$m" --harness "$h" --condition "$c" \
          >>"$LOG" 2>&1 || echo "FAILED $m/$h/$c $task" | tee -a "$LOG"
      done <<< "$MAPFILE_TASKS"
    done
  done
done
echo "ALL EAB COMBOS DONE $(date -u +%FT%TZ)" | tee -a "$LOG"
