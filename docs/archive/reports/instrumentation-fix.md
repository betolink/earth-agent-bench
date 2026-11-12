# Instrumentation fix — why `access_pattern` was always 0

> **Status: fixed.** Every run before this scored `access_pattern = 0` for all
> cells because the sandbox instrumentation never recorded an access event.

## Symptom
- Verifier `details.json` → `observed_patterns: []`, `objects_read: 0`, and **no
  `access_events.jsonl`** in the container.
- So `access_pattern = 0.0`, and the reward was just the validation gate
  (`0.10 × validation=1.0`). Grades were effectively meaningless.

## Root cause — a timing bug in `eab_instrument.py`
The instrumentation is loaded via a `.pth` file and installs a meta-path finder
that wraps access functions **when their library is imported** (`earthaccess.open`
→ `C1`, `earthaccess.virtualize` → `C1`, `harmony.Client.submit` → `S1`, …).

It patched inside `_Loader.exec_module`:

```python
def exec_module(self, module):
    self._loader.exec_module(module)
    _patch_top(self._top)            # top = "earthaccess"
```

The trap: `earthaccess/__init__.py` **imports its own submodules** while loading.
So the **first submodule**'s `exec_module` fired `_patch_top("earthaccess")`
**before** the top package finished — at which point `earthaccess.open` /
`earthaccess.virtualize` / `search_data` **don't exist yet**:

```python
def _patch_top(top):
    if top in _PATCHED: return
    _PATCHED.add(top)                 # marked done…
    for spec: _patch(...)             # getattr(earthaccess, "open") -> None -> no-op
```

When the real top-level package finally finished, `_patch_top` ran again but
`_PATCHED` already contained `"earthaccess"` → returned immediately. Net:
**nothing wrapped → no events → `access_pattern = 0`.**

## Fix
Patch only when the module being executed **is the top package itself**
(`fullname == top`) — i.e. after `__init__` completes and its public attributes
exist:

```python
if self._fullname == self._top:
    _patch_top(self._top)
```

Plus a stale spec: `harmony.Client.request` doesn't exist in harmony 1.8.0 →
`harmony.Client.request_as_url`.

## Verification (live, in the container)
```
after import earthaccess:      earthaccess.open._eab_wrapped == False
after re-patch:                earthaccess.open._eab_wrapped == True
                               earthaccess.virtualize._eab_wrapped == True
```
The rebuilt image contains the fix (`_fullname == self._top` present in
`/opt/eab/eab_instrument.py`).

## Why it matters
The benchmark grades **observed access behavior**. With instrumentation dead we
were blind — which is why earlier "skills vs baseline" deltas looked flat and
pattern credit never appeared. Now `earthaccess.open`/`virtualize` → `C1` (and
`harmony.submit` → `S1`) are captured, so the `access_pattern` component (0.45
weight) is live again.

## Note on the fork
The sandbox uses **`betolink/earthaccess@nextgen-virtual`** (`earthaccess[all] @
git+…`, version `1.0.0a2`, with `earthaccess.virtualize`) — see
`src/earth_agent_bench/harbor/runtime/agent-requirements.txt`.
