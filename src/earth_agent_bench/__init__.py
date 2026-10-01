"""earth-agent-bench: access-pattern selection benchmark for NASA Earthdata agents."""

__version__ = "0.1.0"

from .patterns import PATTERNS, SELECTION_LADDER
from .schemas import Task

__all__ = ["PATTERNS", "SELECTION_LADDER", "Task", "__version__"]
