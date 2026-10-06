#!/bin/bash
# Harbor verifier entrypoint (the verifier runs in the agent environment).
set -uo pipefail
python /tests/verify.py --workspace /app --logs /logs/verifier
