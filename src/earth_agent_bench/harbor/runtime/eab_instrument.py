"""Record the data-access calls an agent actually makes.

Installed into the sandbox image via a .pth file, so it patches the access
libraries whenever they are imported and appends one JSON line per call to
``$EAB_ACCESS_LOG`` (default ``/logs/agent/access_events.jsonl``). Each event
carries the canonical ``service`` and access ``pattern`` the call represents, so
the verifier can grade observed behavior instead of self-report. Best-effort:
instrumentation must never break the agent.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
from pathlib import Path

LOG = os.environ.get("EAB_ACCESS_LOG", "/logs/agent/access_events.jsonl")

# (module, attribute path, canonical service, access pattern)
# service/pattern are None for pure discovery calls.
SPECS: tuple[tuple[str, str, str | None, str | None], ...] = (
    ("earthaccess", "open", None, "C1"),
    ("earthaccess", "download", "filtered_download", "F1"),
    ("earthaccess", "virtualize", "virtual_zarr", "C1"),
    ("earthaccess", "search_data", None, None),
    ("earthaccess", "search_datasets", None, None),
    ("earthaccess", "search_services", None, None),
    ("harmony", "Client.request", "harmony", "S1"),
    ("harmony", "Client.submit", "harmony", "S1"),
    ("pydap.client", "open_url", "opendap", "S2"),
    ("pydap.client", "open_file", "opendap", "S2"),
    ("s3fs", "S3FileSystem.open", None, "C1"),
    ("s3fs", "S3FileSystem.cat", None, "C1"),
    ("s3fs", "S3FileSystem.get", "filtered_download", "F1"),
    ("virtualizarr", "open_virtual_dataset", "virtual_zarr", "C1"),
    ("virtualizarr", "open_virtual_mfdataset", "virtual_zarr", "C1"),
)

_TOP_LEVEL = {spec[0].split(".")[0] for spec in SPECS}
_PATCHED: set[str] = set()


def _record(event: dict) -> None:
    try:
        path = Path(LOG)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as handle:
            handle.write(json.dumps(event, default=str) + "\n")
    except Exception:
        pass


def _count(value: object) -> int | None:
    try:
        return len(value)  # type: ignore[arg-type]
    except Exception:
        return None


def _wrap(original, name: str, service: str | None, pattern: str | None):
    def logged(*args, **kwargs):
        started = time.time()
        result = None
        error = None
        try:
            result = original(*args, **kwargs)
            return result
        except BaseException as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            event = {
                "function": name,
                "service": service,
                "pattern": pattern,
                "timestamp": started,
                "duration_s": round(time.time() - started, 3),
                "args": repr(args)[:800],
                "kwargs": repr(kwargs)[:800],
                "n_result": _count(result),
                "error": error,
            }
            if "short_name" in kwargs:
                event["short_name"] = kwargs["short_name"]
            if "concept_id" in kwargs:
                event["concept_id"] = kwargs["concept_id"]
            _record(event)

    return logged


def _resolve(module_name: str, attribute: str):
    target = importlib.import_module(module_name)
    parts = attribute.split(".")
    for part in parts[:-1]:
        target = getattr(target, part)
    return target, parts[-1]


def _patch(module_name: str, attribute: str, service, pattern) -> None:
    try:
        owner, name = _resolve(module_name, attribute)
        original = getattr(owner, name, None)
    except Exception:
        return
    if callable(original) and not getattr(original, "_eab_wrapped", False):
        wrapper = _wrap(original, f"{module_name}.{attribute}", service, pattern)
        wrapper._eab_wrapped = True  # type: ignore[attr-defined]
        try:
            setattr(owner, name, wrapper)
        except Exception:
            pass


def _patch_top(top: str) -> None:
    if top in _PATCHED:
        return
    _PATCHED.add(top)
    for module_name, attribute, service, pattern in SPECS:
        if module_name.split(".")[0] == top:
            _patch(module_name, attribute, service, pattern)


class _Loader:
    def __init__(self, loader, top: str):
        self._loader = loader
        self._top = top

    def create_module(self, spec):
        return self._loader.create_module(spec)

    def exec_module(self, module):
        self._loader.exec_module(module)
        _patch_top(self._top)


class _Finder:
    def find_spec(self, fullname, path=None, target=None):
        top = fullname.split(".")[0]
        if top not in _TOP_LEVEL:
            return None
        for finder in sys.meta_path:
            if finder is self:
                continue
            spec = finder.find_spec(fullname, path, target)
            if spec is not None and spec.loader is not None:
                spec.loader = _Loader(spec.loader, top)
                return spec
        return None


def install() -> None:
    if not any(isinstance(finder, _Finder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _Finder())


install()
