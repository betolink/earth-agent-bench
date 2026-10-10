from pathlib import Path

import pytest
import yaml

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"


@pytest.fixture(scope="module")
def models():
    return yaml.safe_load((EXPERIMENTS / "models.yaml").read_text())


@pytest.fixture(scope="module")
def harnesses():
    return yaml.safe_load((EXPERIMENTS / "harnesses.yaml").read_text())


def test_roster_size_and_tiers(models):
    roster = models["models"]
    assert len(roster) == 11
    tiers = [m["tier"] for m in roster.values()]
    assert tiers.count("local") == 7
    assert tiers.count("frontier_open") == 2
    assert tiers.count("closed_reference") == 2


def test_local_models_fit_24gb(models):
    for model_id, model in models["models"].items():
        if model["tier"] != "local":
            continue
        assert "repo" in model, model_id
        assert model["vram_estimate_gb"] <= 24.0, model_id


def test_closed_tier_has_budget_cap(models):
    budget = models["budget"]["closed_reference"]
    assert budget["shared_cap_usd"] > 0
    assert budget["hard_stop"] is True


def test_crossing_rules(harnesses, models):
    restricted = harnesses["crossing"]["restricted"]["claude-code"]
    assert set(restricted["models"]) == {"claude-sonnet-5-5"}
    assert "claude-sonnet-5-5" in models["models"]


def test_conditions_complete():
    conditions = yaml.safe_load((EXPERIMENTS / "conditions.yaml").read_text())["conditions"]
    assert set(conditions) == {"baseline", "mcp", "skills", "mcp-skills", "improve"}
    assert conditions["mcp-skills"] == {"mcp": True, "skills": True,
                                        "description": "combined intervention"}
    assert conditions["improve"]["improvement"] is True


def test_pilot_references_valid_models(models):
    pilot = yaml.safe_load((EXPERIMENTS / "pilot.yaml").read_text())
    roster = set(models["models"])
    assert set(pilot["models"]) <= roster
    lane_models = set(pilot["lanes"]["claude-reference"]["models"])
    assert lane_models <= roster


def test_full_run_arithmetic():
    full = yaml.safe_load((EXPERIMENTS / "full.yaml").read_text())
    main = 9 * 3 * 4 * 18 * full["trials"]
    assert full["main_runs"] == main
    lane = 1 * 1 * 4 * 18 * full["trials"]
    lane_entry = full["lanes"]["claude-reference"]
    assert lane_entry["lane_runs"] == lane
    assert full["total_runs"] == main + lane


def test_pilot_run_arithmetic():
    pilot = yaml.safe_load((EXPERIMENTS / "pilot.yaml").read_text())
    main = len(pilot["models"]) * len(pilot["harnesses"]) * 4 * len(pilot["tasks"]) * pilot["trials"]
    assert pilot["main_runs"] == main
    lane_entry = pilot["lanes"]["claude-reference"]
    lane = 1 * 1 * 4 * len(pilot["tasks"]) * lane_entry["trials"]
    assert lane_entry["lane_runs"] == lane


def test_gateway_example_covers_roster(models):
    gateway = yaml.safe_load((EXPERIMENTS / "litellm.example.yaml").read_text())
    served = {entry["model_name"] for entry in gateway["model_list"]}
    assert served == set(models["models"])


def test_run_manifest_schema():
    from earth_agent_bench.schemas import RunManifest

    manifest = RunManifest(
        task_id="atmosphere/a1-tempo-no2-florida-2024",
        model_id="tiel-coder-35b",
        model_tier="local",
        harness="opencode",
        condition="mcp-skills",
        quantization="IQ4_XS",
        input_tokens=150_000,
        output_tokens=8_000,
        tokens_per_second=41.2,
        vram_gb=19.8,
    )
    assert manifest.cost_usd == 0.0
