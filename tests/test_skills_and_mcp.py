import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / "skills"
MCP = REPO / "mcp"

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

EXPECTED_SKILLS = {
    "data-access-patterns",
    "data-virtualization",
    "earthdata-streaming-vs-download",
    "xarray",
    "dask-optimization",
}


def test_core_skills_present():
    found = {p.parent.name for p in SKILLS.rglob("SKILL.md")}
    assert EXPECTED_SKILLS <= found


def test_skills_have_valid_frontmatter():
    for path in SKILLS.rglob("SKILL.md"):
        match = FRONTMATTER.match(path.read_text())
        assert match is not None, path
        fields = yaml.safe_load(match.group(1))
        assert fields.get("name"), path
        assert fields.get("description"), path


def test_virtualization_skill_uses_current_api():
    skill = (SKILLS / "data-virtualization" / "SKILL.md").read_text()
    for call in ("earthaccess.virtualize", "earthaccess.write_virtual",
                 "earthaccess.open_virtual", "append_dim"):
        assert call in skill
    assert "virtualizarray" not in skill


def test_no_stale_virtualizarray_references():
    stale = []
    for path in REPO.rglob("*"):
        if path.suffix not in {".py", ".md", ".yaml"} or ".venv" in path.parts:
            continue
        if path.name == "test_skills_and_mcp.py":
            continue
        if "virtualizarray" in path.read_text(errors="ignore"):
            stale.append(str(path))
    assert not stale


def test_mcp_manifest():
    manifest = yaml.safe_load((MCP / "manifest.yaml").read_text())
    servers = manifest["servers"]
    assert servers["cmr-mcp"]["status"] == "ready"
    assert servers["cmr-mcp"]["url"] == "https://cmr.earthdata.nasa.gov/mcp/v1"
    assert servers["earthaccess-mcp"]["status"] == "pending"


def test_harness_wiring_examples_exist():
    for name in ("claude-code.mcp.json", "codex-config.toml",
                 "opencode.jsonc", "pi.json"):
        assert (MCP / "harnesses" / name).exists()
    claude = (MCP / "harnesses" / "claude-code.mcp.json").read_text()
    assert "https://cmr.earthdata.nasa.gov/mcp/v1" in claude


def test_conditions_wiring_matches_manifest():
    conditions = yaml.safe_load(
        (REPO / "experiments" / "conditions.yaml").read_text()
    )
    wiring = conditions["wiring"]
    assert wiring["mcp_manifest"] == "mcp/manifest.yaml"
    assert wiring["skills_dir"] == "skills/"
    assert "earthaccess-mcp" in wiring["mcp_servers"]["mcp"]
    assert wiring["skills_mounted"]["skills"] is True
    assert wiring["skills_mounted"]["baseline"] is False


def test_env_example_lists_required_secrets():
    env = (REPO / ".env.example").read_text()
    for key in ("EARTHDATA_USERNAME", "EARTHDATA_PASSWORD",
                "LITELLM_API_KEY", "ZHIPU_API_KEY", "ANTHROPIC_API_KEY"):
        assert key in env
