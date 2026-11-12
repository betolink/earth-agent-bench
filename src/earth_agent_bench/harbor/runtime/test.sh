#!/bin/bash
# Harbor verifier entrypoint. With verifier_environment_mode = "separate" this
# runs in a dedicated container: artifacts from the agent are re-materialized at
# their original paths, so verification never shares a filesystem with the agent.
set -uo pipefail
python /tests/verify.py --workspace /app --logs /logs/verifier
