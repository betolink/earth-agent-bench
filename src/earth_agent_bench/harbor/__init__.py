"""Harbor integration: generate real Harbor task packages and run them.

Harbor (https://harborframework.com) ships the harness adapters directly, runs
each task in an isolated environment, and grades it with a deterministic
verifier. This package turns benchmark/eval tasks into Harbor task packages,
binds them to one agent + LiteLLM model via a JobConfig, and invokes the CLI.

Public API::

    resolve_task, resolve_tasks            # task selection
    generate_package                       # build a Harbor task package
    write_job_config, render_harbor_command, run_harbor
"""

from .config import (
    DEFAULT_JOBS,
    DEFAULT_OUT,
    HARBOR_CONFIG,
    HARBOR_DIR,
    REPO_ROOT,
    load_harbor_config,
)
from .jobs import (
    CLAUDE_LANE_MODELS,
    PI_MODEL_APIS,
    render_harbor_command,
    run_harbor,
    write_job_config,
)
from .packages import (
    EVAL_ABS_NOTE,
    HARBOR_OUTPUT_CONTRACT,
    find_gold,
    generate_package,
)
from .resolve import resolve_task, resolve_tasks

__all__ = [
    "CLAUDE_LANE_MODELS",
    "DEFAULT_JOBS",
    "DEFAULT_OUT",
    "EVAL_ABS_NOTE",
    "HARBOR_CONFIG",
    "HARBOR_DIR",
    "HARBOR_OUTPUT_CONTRACT",
    "PI_MODEL_APIS",
    "REPO_ROOT",
    "find_gold",
    "generate_package",
    "load_harbor_config",
    "render_harbor_command",
    "resolve_task",
    "resolve_tasks",
    "run_harbor",
    "write_job_config",
]
