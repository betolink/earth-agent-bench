
from earth_agent_bench.tasks import load_all, load_task, render_instruction
from earth_agent_bench.scoring import score_run, score_access_pattern
from earth_agent_bench.schemas import RunObservation, PatternTiers


def test_load_all_tasks():
    tasks = load_all()
    assert len(tasks) == 18
    spheres = {task.science_sphere for task in tasks}
    assert spheres == {
        "atmosphere", "cryosphere", "biosphere",
        "ocean", "solid-earth", "land-surface",
    }


def test_every_task_has_gold_and_preferred():
    for task in load_all():
        assert task.gold.primary_patterns, task.task_id
        assert any(c.tier == "preferred" for c in task.collections), task.task_id
        assert task.pattern_tiers.best, task.task_id


def test_task_yaml_ids_are_unique():
    tasks = load_all()
    ids = [task.task_id for task in tasks]
    assert len(ids) == len(set(ids))


def test_render_instruction_hides_gold():
    task = load_task("benchmark/tasks/atmosphere/a1-tempo-no2-florida-2024.yaml")
    instruction = render_instruction(task)
    assert "tropospheric_no2_vertical_column" in instruction
    assert "gold" not in instruction.lower()
    assert "C1" not in instruction


def test_access_pattern_tier_scores():
    tiers = PatternTiers(best=["C1"], acceptable=["S1"], marginal=["F1"], inefficient=["M1"])
    assert score_access_pattern("C1", tiers) == 1.0
    assert score_access_pattern("S1", tiers) == 0.7
    assert score_access_pattern("F1", tiers) == 0.3
    assert score_access_pattern("M1", tiers) == 0.0


def test_score_run_best_path():
    task = load_task("benchmark/tasks/atmosphere/a1-tempo-no2-florida-2024.yaml")
    observation = RunObservation(
        task_id=task.task_id,
        observed_patterns=["S1"],
        collection_short_names=["TEMPO_NO2_L3"],
        discovered_services=["S1", "S3"],
        representation="lazy",
        validation_passed=True,
        metrics={"bytes_read": 45_000_000, "objects_read": 12, "runtime_seconds": 180},
    )
    result = score_run(task, observation)
    assert result.access_pattern == 1.0
    assert result.reward > 0.85


def test_score_run_full_download_is_penalized():
    task = load_task("benchmark/tasks/ocean/o2-mur-sst-gbr-2024.yaml")
    observation = RunObservation(
        task_id=task.task_id,
        observed_patterns=["M1"],
        collection_short_names=["MUR-JPL-L4-GLOB-v4.1"],
        discovered_services=[],
        representation="materialized",
        validation_passed=True,
        metrics={"bytes_read": 3_000_000_000, "objects_read": 900, "runtime_seconds": 3600},
    )
    result = score_run(task, observation)
    assert result.access_pattern == 0.0
    assert result.reward < 0.5


def test_score_efficiency_no_metrics_no_credit():
    from earth_agent_bench.scoring import score_efficiency
    from earth_agent_bench.schemas import EfficiencyMetrics

    task = load_task("benchmark/tasks/atmosphere/a1-tempo-no2-florida-2024.yaml")
    assert score_efficiency(task, EfficiencyMetrics(), ["C1"]) == 0.0
    assert score_efficiency(task, EfficiencyMetrics(bytes_read=1000), ["C1"]) == 1.0


def test_collection_selection_is_normalized():
    task = load_task("benchmark/tasks/atmosphere/a1-tempo-no2-florida-2024.yaml")
    observation = RunObservation(
        task_id=task.task_id,
        observed_patterns=["C1"],
        collection_short_names=["tempo-no2-l3"],
        discovered_services=[],
        representation="lazy",
        validation_passed=True,
        metrics={"bytes_read": 1, "objects_read": 1, "runtime_seconds": 1.0},
    )
    assert score_run(task, observation).collection_selection == 1.0
