# Assessment — earth-agent-bench vs FineEnvs for access-pattern effectiveness scoring

Question: which substrate is more viable for the goal — *score how effective access
patterns are under the control mechanisms (MCP, skills) for different models, with
setups `model+MCP` and `model+MCP+skills`* — and if the answer is hybrid, what must be
implemented in earth-agent-bench to make it runnable today?

> **Implementation status (updated).** The verdict holds and most prioritized
> items are done: real Harbor is adopted (`eab harbor run`, v0.24 pinned), access
> is instrumented (`harbor/runtime/eab_instrument.py` →
> `/logs/agent/access_events.jsonl`), and the 10 eval tasks have a deterministic
> grader (`eab eval`). Still open: the `earthaccess-mcp` endpoint (P0 #4),
> reference solutions, and byte-level instrumentation.

## 1. Verdict

**Use earth-agent-bench. It is not a hybrid in any architectural sense — the
FineEnvs contribution is a thin evaluation-protocol layer, not a substrate.**

The goal as stated *is* earth-agent-bench's core research question, verbatim
(docs/archive/consolidated-plan.md §6):

> does giving it operational knowledge about available access services — including
> whether the archive can be virtualized — cause it to select a more efficient,
> justified access pattern?

FineEnvs (`05-multi-harness-rl`) is an RL-*training* methodology whose scoring axis
is **answer correctness** ("write a single clean value"), not access-pattern quality.
It has no notion of access patterns, MCP servers, skills, or knowledge conditions.
To realize the goal on FineEnvs you would have to re-build the entire Earthdata domain
(the taxonomy, the oracles, the selection ladder, the MCP/skills interventions) from
scratch. earth-agent-bench already has all of it.

## 2. Why earth-agent-bench wins for this goal

| Requirement | earth-agent-bench | FineEnvs |
|---|---|---|
| Access-pattern taxonomy (C1/S1/S2/…/M2) + selection ladder | ✅ `patterns.py`, `docs/archive/consolidated-plan.md` §2 | ❌ absent |
| "MCP + skills" as knowledge conditions | ✅ `conditions.yaml` (baseline/mcp/skills/mcp-skills) | ❌ absent |
| Service-availability oracle (EDVS parquet + curated + live CMR) | ✅ `oracles/` | ❌ absent |
| Multi-model / multi-harness roster + cost/token accounting | ✅ `experiments/`, `RunManifest` | ⚠️ harness loop only, no domain |
| Weighted access-pattern scoring (pattern 35%, efficiency 15%…) | ✅ `scoring/` | ❌ absent |
| Deterministic grader + pass@1 + coverage + tool bonus | ⚠️ absent (its gate is "artifact present") | ✅ the one reusable piece |

The only things worth borrowing from FineEnvs are **evaluation hygiene**:
(1) deterministic grader, (2) pass@1 reported **with coverage** (infra-failure excluded,
not scored wrong), (3) the tool-efficiency bonus `correct × (1 + 0.1·15/(15+tool_calls))`.
That is a scoring-detail transplant onto earth-agent-bench's existing grader, not a
second substrate.

## 3. If "hybrid", what to implement in earth-agent-bench

Prioritized. "Runnable today" = items 1–4; items 5–7 are what makes the *result
credible*; items 8+ are the intervention under test.

### P0 — runnable today

1. **LiteLLM gateway + confirmed model IDs.** The only external config. Fill
   `experiments/litellm.example.yaml` → `litellm.yaml`, export
   `LITELLM_BASE_URL`/`LITELLM_API_KEY`, and resolve the four `confirm_at_pilot`
   provider strings in `experiments/models.yaml` (gaps #2). Nothing else is external.
2. **Harbor is adopted (was: "use the direct runner").** Real Harbor (PyPI
   `harbor`, v0.24) is a pinned dev dependency; `eab harbor` generates
   `task.toml` packages and runs them (`eab harbor run`), validated end-to-end
   on `pi`. The direct runner (`eab run`) remains for host-side smoke tests.
3. **Pin one harness now (opencode), one local + one API model.** This de-risks the
   headless loop (`runner.py` + harness config) without waiting on all four harnesses.
4. **Ship a minimal `earthaccess-mcp`** (HTTP, `transport: http` per `mcp/manifest.yaml`)
   exposing the two surfaces below (§5). This is what turns `model+MCP` and
   `model+MCP+skills` from "cmr-only discovery" into the operational-knowledge
   intervention the experiment is actually about. Back it with the existing oracles —
   do **not** hand-write knowledge the oracle already has.

### P1 — credibility of the measurement

5. **Instrument access, don't infer it — DONE (partial).** `eab_instrument`
   patches `earthaccess` / `harmony` / `pydap` / `s3fs` / `virtualizarr` and logs
   every real call to `/logs/agent/access_events.jsonl`; the verifier derives
   pattern/service/representation/validation from those events. Remaining: byte
   counts (still self-reported) and cloud-vs-OPeNDAP disambiguation.
6. **Deterministic grader for the 10 eval tasks — DONE.**
   `experiments/evals/suite.yaml` + `earth_agent_bench.evals`
   (`eab eval grade` / `eab eval report`) implement the FineEnvs-style grader
   with pass@1/coverage.
7. **Per-task minimal-science gate** (gaps #7): programmatic variable/extent/units/aggregation
   checks replacing "artifact exists".

### P2 — correctness of the oracle

8. **Verify the curated service catalog** (28 × `verified: false`, gaps #4) against
   `eab matrix <short_name> --cmr` — one live-CMR contradiction already found.
9. **Reference solutions per task** (gaps #5) to calibrate efficiency envelopes.

## 4. Runnable-today path (exact)

```bash
# repo setup
uv sync                     # bench tooling + Harbor (dev group)
uv run python scripts/build_virtualizability_parquet.py

# credentials (resolved from the host at run time)
export LITELLM_API_KEY=... EARTHDATA_USERNAME=... EARTHDATA_PASSWORD=...
#   (or EARTHDATA_TOKEN)

# smoke one cell on the Harbor path (isolated + auto-scored)
uv run eab harbor run benchmark/tasks/cryosphere/c1-itslive-jakobshavn-2015-2024.yaml \
    --model lfm2.5-2.6b --harness pi --condition baseline --dry-run   # then drop --dry-run

# host-side smoke remains available: uv run eab run <task> --model ... --harness ...

# conditions today: baseline / skills / mcp (cmr-only) / mcp-skills (cmr-only)
# "model+MCP" and "model+MCP+skills" become the real experiment the moment the
# earthaccess-mcp endpoint is wired into mcp/manifest.yaml
```

Today you can run **baseline**, **skills**, and the two MCP conditions at
**discovery-level only** (cmr-mcp live; earthaccess-mcp pending). The two setups the
goal names — `model+MCP` and `model+MCP+skills` — are the operational-MCP conditions,
so their full value depends on item 4.

## 5. Tools for the NASA Earth MCP (data taxonomy + data services)

The MCP is the *intervention*: it should expose exactly the operational knowledge the
benchmark's oracle already encodes, so the experiment isolates "does the agent *use*
this knowledge". Organized under the two current aims.

### 5.1 Data taxonomy (what exists, and what *type* it is)

| Tool | Returns | Why it matters for access selection |
|---|---|---|
| `find_collections` / `search_collections` | short_name, concept_id, version, DAAC/provider, instrument, platform, science keywords, spatial/temporal extent | the entry point; must take the same filters as `earthaccess.search_datasets` |
| `get_collection` (concept_id) | full UMM-C: DOI, processing level, related URLs, abstract, data center | grounds the "which collection" decision |
| `get_collection_variables` | UMM-Var: names, long names, units, dims | the "right variable + units" gate |
| `collection_data_type` | gridded / point / swath / vector + level (L2/L3/L4) | **the single highest-leverage taxonomy field** — it decides whether C1 virtualization even applies (gridded L3+ yes; point/vector no) |
| `search_granules` / `get_granule` | granule count, URs, file URLs, sizes, checksums | window correctness + downstream access |
| `list_daacs` / `list_providers` | provider catalog | resolves provider codes |

### 5.2 Data services (how it can be accessed — the operational knowledge)

This is the axis the benchmark actually scores, so these tools should mirror the
selection ladder (`docs/archive/consolidated-plan.md` §2.1) and be backed by the oracles, not by
recalled knowledge:

| Tool | Returns | Maps to |
|---|---|---|
| `get_access_options(collection, bbox, temporal, variables)` | ranked pattern list + justification (C1→S3→S2→S1→…→M1) | the whole ladder in one call — the top-value tool |
| `virtualizability(collection)` | EDVS grade A/B/C/D + deciding criterion + DMR++ presence | oracle `virtualizability.py`; decides C1 vs S3 |
| `is_cloud_hosted(collection)` | cloud-hosted + direct S3 | `data_links(access=…)` selection |
| `get_data_links(granule, access)` | direct (S3) vs external (HTTPS) | `earthaccess.DataGranule.data_links` |
| `harmony_available` / `opendap_endpoints` / `dmrpp_available` | per-service availability | S1 / S2 / S3 checks |
| `edl_status` | authenticated? token available? | gates any authenticated access |

### 5.3 What *not* to build into the MCP yet

- **Execution tools** (run the download/open/virtualize). The MCP is the knowledge
  channel; the harness/agent executes via `earthaccess` in its own sandbox. Keep the
  MCP read-only metadata + recommendations — otherwise you entangle the intervention
  with the measurement.
- **Byte/cost accounting** — that belongs in the harness instrumentation (item 5), not
  the MCP.

## 6. Bottom line

Build the experiment **on earth-agent-bench** (it already encodes the exact research
question, the taxonomy, the oracles, and the MCP/skills conditions). Borrow from
FineEnvs only the *grading hygiene* (deterministic grader, pass@1+coverage, tool bonus)
for the 10 correctness tasks. To be runnable today you need only the LiteLLM key and a
minimal `earthaccess-mcp`; the two highest-leverage implementation items are
**instrumented access (not inferred)** and an MCP that exposes **data taxonomy +
access options** backed by the existing oracles.
