#!/bin/bash
# Oracle reference solution runner. Copied to /solution and run only by
# Harbor's OracleAgent (never shown to the graded agent).
#
# Put the task's expert workflow at solution/reference_workflow.py (generated
# packages) or point EAB_REFERENCE_SOLUTION at it. Until then the oracle run
# fails loudly rather than silently scoring nothing.
set -euo pipefail

ref="${EAB_REFERENCE_SOLUTION:-/solution/reference_workflow.py}"
if [ -f "$ref" ]; then
  cd /app
  exec python "$ref"
fi

echo "No reference solution for this task yet." >&2
echo "Add solution/reference_workflow.py (see docs/gaps.md #5)." >&2
exit 2
