#!/usr/bin/env bash
# Make Harbor usable with the BetoLink LiteLLM gateway + local models.
#
# Harbor's bundled adapters assume OpenAI/Anthropic upstreams. Two small patches
# are needed so the namespaced `local/<model>` ids survive to the gateway:
#
#   * codex:  keep the id after the provider prefix (openai/local/X -> local/X)
#   * claude: when a custom base URL is set, strip only the provider prefix
#             (anthropic/local/X -> local/X) instead of passing it through.
#
# (opencode/codex provider *config* lives in harbor/harbor.yaml, not here.)
#
# Idempotent; run after `uv sync` / `pixi install` (or any Harbor reinstall).
set -euo pipefail
cd "$(dirname "$0")/.."

SITE="$(.venv/bin/python - <<'PY'
import harbor, os
print(os.path.dirname(harbor.__file__))
PY
)"
CODEX="$SITE/agents/installed/codex.py"
CLAUDE="$SITE/agents/installed/claude_code.py"

patch_codex() {
  python3 - "$CODEX" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
old = '        model = self.model_name.split("/")[-1]\n'
new = ('        # patch-harbor: keep the id after the provider prefix '
       '(openai/local/X -> local/X)\n'
       '        model = self.model_name.split("/", 1)[-1]\n')
if 'self.model_name.split("/", 1)[-1]' in s:
    print("codex: already patched"); raise SystemExit
assert old in s, "codex: expected model line not found (Harbor changed?)"
open(p, "w").write(s.replace(old, new, 1)); print("codex: patched")
PY
}

patch_claude() {
  python3 - "$CLAUDE" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
old = ('            if access.configured_base_url:\n'
       '                return self.model_name\n')
new = ('            if access.configured_base_url:\n'
       '                # patch-harbor: strip only the provider prefix '
       '(anthropic/local/X -> local/X)\n'
       '                return self.model_name.split("/", 1)[-1]\n')
if 'return self.model_name.split("/", 1)[-1]' in s:
    print("claude: already patched"); raise SystemExit
assert old in s, "claude: expected model-resolution block not found (Harbor changed?)"
open(p, "w").write(s.replace(old, new, 1)); print("claude: patched")
PY
}

patch_codex
patch_claude
echo "patch-harbor: done ($SITE)"
