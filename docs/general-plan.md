# earthaccess MCP: AI-Native Access Layer for NASA Earthdata

## Project, Benchmark, Golden Tests, and Evaluation Plan

**Project:** earthaccess MCP  
**Program:** ESDS AI Innovation Call  
**Team:** earthaccess collaboration team, NSIDC  
**ESDS Pillars:** Access, Analysis, Infrastructure  

---

## 1. Project Objective

AI coding assistants and autonomous agents are increasingly being used to discover datasets, write analysis code, construct data pipelines, and perform scientific analysis.

For NASA Earthdata, however, an agent needs more than knowledge of dataset names and APIs.

Efficient Earthdata workflows often depend on operational information that is difficult for a general-purpose AI system to infer:

* which processing level is appropriate
* which variables contain the requested measurement
* whether a dataset is available as a cloud-native representation
* whether virtualization is available
* how the underlying data are chunked
* whether spatial or temporal subsetting is possible
* which Earthdata service should be used
* whether data can be accessed lazily rather than downloaded
* how credentials should be propagated to distributed workers
* which scientific documentation or ATBD should be consulted
* whether an apparently valid access pattern is actually inefficient

The goal of `earthaccess-mcp` is to expose this operational knowledge to AI agents through the Model Context Protocol (MCP).

The project therefore has two related objectives:

1. Build an operational Earthdata MCP server.
2. Determine experimentally whether that additional knowledge improves AI-generated Earthdata workflows.

The central research question is:

> Does Earthdata-specific operational knowledge provided through `earthaccess-mcp` enable AI agents to construct more correct, reproducible, and efficient NASA Earthdata workflows?

The benchmark is designed to distinguish three properties that are often conflated:

1. scientific correctness
2. operational correctness
3. computational efficiency

An agent that obtains the correct scientific answer by downloading tens of gigabytes of data should not be considered equivalent to an agent that obtains the same answer through an appropriate cloud-native and subset-aware workflow.

---

## 2. Project Scope

The project will implement an MCP-compatible Python server using FastMCP.

The initial server will expose four major capabilities:

* `auth`
* `data_taxonomy`
* `related_science`
* `earthaccess_core`

The benchmark and evaluation framework will be developed alongside the MCP server.

The resulting GitHub repository will contain:

* the MCP implementation
* Earthdata skills
* benchmark tasks
* golden standards
* independent scientific reference solutions
* golden tests
* Harbor task definitions
* experiment configurations
* scoring software
* statistical analysis
* example workflows
* documentation
* reproducible experiment manifests

The benchmark is not a separate academic exercise. It is the validation layer for the central proposal claim.

---

## 3. Proposed MCP Capabilities

### 3.1 Authentication

The `auth` capability reports whether an agent is ready to access Earthdata.

It may determine:

* authentication state
* credential validity
* cloud access readiness
* required permissions
* distributed credential availability

Secrets must never be exposed through the MCP interface.

### 3.2 Data Taxonomy

`data_taxonomy` is the central innovation.

It provides structured operational metadata describing how a dataset should be accessed and represented.

Example:

```json
{
  "collection": "MODIS/Terra Surface Reflectance Daily L2G",
  "format": "HDF4",
  "variables": [
    {
      "name": "sur_refl_b01",
      "dims": ["YDim", "XDim"],
      "shape": [2400, 2400],
      "chunks": [2400, 2400],
      "dtype": "int16",
      "compression": null,
      "fill_value": -28672,
      "geo": {
        "CRS": "4326"
      }
    }
  ],
  "available_services": [
    "harmony",
    "giovanni"
  ],
  "virtualization": {
    "available": true,
    "type": "kerchunk",
    "access_urls": [
      "s3://..."
    ],
    "engine": "zarr",
    "compatible_tools": [
      "xarray",
      "dask"
    ]
  }
}
```

This allows an agent to reason about:

* data representation
* chunking
* virtualization
* cloud access
* spatial and temporal access
* compatible analysis tools
* access services

### 3.3 Related Science

`related_science` provides authoritative scientific resources associated with a dataset or variable.

Examples include:

* ATBDs
* Earthdata documentation
* science definitions
* notebooks
* examples
* GitHub repositories
* instrument documentation
* earthaccess plugins

The goal is not to create another static knowledge base. Instead, the MCP normalizes and exposes authoritative references already maintained by NASA and the scientific community.

### 3.4 Earthdata Core Operations

`earthaccess_core` exposes existing earthaccess functionality, including:

* dataset discovery
* granule discovery
* service discovery
* access operations

This allows an agent to move from:

```text
What dataset exists?
```

to:

```text
How should I access it?
```

without requiring the model to reconstruct earthaccess usage from training data.

---

## 4. Relationship to CMR MCP

CMR MCP and earthaccess MCP address complementary problems.

```text
CMR MCP
    |
    +-- What exists?
    |
    +-- Where is it?
    |
    +-- What does NASA's metadata say?
    |
    v
earthaccess MCP
    |
    +-- How should it be accessed?
    |
    +-- What representation is appropriate?
    |
    +-- Can it be virtualized?
    |
    +-- What services are available?
    |
    +-- How should it be streamed?
    |
    +-- What tools are compatible?
```

The primary experiment is intended to isolate the value of Earthdata operational knowledge.

Where practical, CMR discovery capability should therefore be held constant across experimental conditions.

A secondary experiment may evaluate:

* CMR MCP
* earthaccess MCP
* CMR MCP + earthaccess MCP

This secondary experiment demonstrates composition but should not replace the primary controlled experiment.

---

## 5. GitHub Repository

The entire implementation should be maintained in a public GitHub repository.

```text
earthaccess-mcp/
│
├── README.md
├── LICENSE
├── pyproject.toml
│
├── src/
│   └── earthaccess_mcp/
│       ├── server.py
│       ├── auth.py
│       ├── taxonomy.py
│       ├── related_science.py
│       └── earthaccess_core.py
│
├── skills/
│   ├── earthdata-discovery/
│   ├── data-representation/
│   ├── access-strategies/
│   ├── virtualization/
│   ├── spatial-subsetting/
│   ├── temporal-subsetting/
│   └── scientific-analysis/
│
├── benchmark/
│   ├── README.md
│   ├── tasks/
│   │   ├── atmosphere/
│   │   ├── cryosphere/
│   │   ├── biosphere/
│   │   ├── ocean/
│   │   ├── solid-earth/
│   │   └── land-surface/
│   ├── schemas/
│   │   ├── task.yaml
│   │   ├── gold-standard.yaml
│   │   └── result.yaml
│   ├── scoring/
│   │   ├── dataset.py
│   │   ├── representation.py
│   │   ├── access.py
│   │   ├── science.py
│   │   ├── efficiency.py
│   │   └── aggregate.py
│   └── fixtures/
│
├── harbor/
│   ├── agents/
│   ├── tasks/
│   ├── environments/
│   └── configs/
│
├── experiments/
│   ├── models.yaml
│   ├── harnesses.yaml
│   ├── conditions.yaml
│   ├── pilot.yaml
│   └── full.yaml
│
├── evaluation/
│   ├── run.py
│   ├── collect.py
│   ├── aggregate.py
│   ├── statistics.py
│   └── reports/
│
├── examples/
│   ├── tempo-no2/
│   ├── its-live/
│   └── prefire-modis/
│
├── docs/
│   ├── architecture.md
│   ├── benchmark.md
│   ├── golden-tests.md
│   ├── evaluation.md
│   ├── skills.md
│   └── operations.md
│
└── results/
    └── README.md
```

GitHub is the source of truth for code, task definitions, tests, reference workflows, scoring logic, configurations, and aggregate results.

Large generated trajectories and data artifacts should be stored through appropriate GitHub release or large-file mechanisms rather than being placed directly into normal Git history.

---

## 6. Evaluation Architecture

```text
                         Scientific Task
                              |
                              v
                       +--------------+
                       |   AI Agent   |
                       +------+-------+
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
         Baseline          MCP only       Skills only
             |                |                |
             +----------------+----------------+
                              |
                         MCP + Skills
                              |
                              v
                       Agent Harness
                              |
                              v
                    Earthdata Workflow
                              |
                +-------------+-------------+
                v             v             v
             Dataset     Representation    Access
                |             |             |
                +-------------+-------------+
                              |
                              v
                    Scientific Computation
                              |
                              v
                     Produced Artifacts
                              |
                              v
                     +----------------+
                     |  Golden Tests  |
                     +-------+--------+
                             |
              +--------------+--------------+
              v              v              v
          Correctness     Efficiency    Trajectory
              |              |              |
              +--------------+--------------+
                             |
                             v
                         Final Score
```

The critical design principle is:

> The agent produces the workflow. The golden tests independently determine whether that workflow and its result are correct.

The MCP does not grade itself.

---

## 7. Experimental Factors

The full experiment has four factors:

1. language model
2. agent harness
3. Earthdata knowledge condition
4. scientific task

### 7.1 Language Models

Six models will be evaluated.

One model will be a closed Claude Sonnet model accessed through the Anthropic API.

Five models will be open-weight models running locally through:

```text
LiteLLM
    |
    v
llama-swap
    |
    v
llama.cpp
```

The local models currently achieve approximately 30 tokens/second.

The exact model versions, quantizations, context lengths, and inference parameters will be selected during the pilot and then pinned.

The Claude experiment will have a hard budget of:

```text
$50 USD
```

API credentials will be injected at runtime and will never be committed to GitHub.

---

## 8. Agent Harnesses

Four agent harnesses will be evaluated.

Each harness must be version-pinned.

```yaml
harnesses:
  - name: harness_a
    version: ...

  - name: harness_b
    version: ...

  - name: harness_c
    version: ...

  - name: harness_d
    version: ...
```

The harness is an experimental factor because it determines:

* tool invocation
* context construction
* shell access
* planning
* recovery
* tool error handling
* agent loop behavior

---

## 9. Earthdata Knowledge Conditions

| Condition | Earthdata MCP | Earthdata Skills | Purpose |
|---|---:|---:|---|
| Baseline | No | No | Measure ordinary agent capability |
| MCP only | Yes | No | Measure structured operational knowledge |
| Skills only | No | Yes | Measure procedural/domain guidance |
| MCP + Skills | Yes | Yes | Measure combined effect |

The same model, harness, task, environment, and execution limits are used across conditions.

Only the available Earthdata knowledge changes.

---

## 10. Experimental Matrix

The full experiment is:

```text
6 models
x 4 harnesses
x 4 knowledge conditions
x 18 tasks
x 5 trials
```

Therefore:

```text
6 x 4 x 4 = 96 configurations

96 x 18 = 1,728 task executions per trial

1,728 x 5 = 8,640 total executions
```

Pilot:

```text
3 representative tasks
x 6 models
x 4 harnesses
x 4 conditions
x 2 trials

= 576 pilot executions
```

The pilot determines:

* model stability
* context requirements
* harness compatibility
* task difficulty
* verifier reliability
* runtime
* API cost
* data-access reproducibility

The full experiment is run only after the pilot passes benchmark validation.

---

## 11. Scientific Task Suite

### Atmosphere

| ID | Task | Main traps |
|---|---|---|
| A1 | Monthly mean tropospheric NO₂ over Florida in 2024 | L2/L3, tropospheric/total, QA, subset, aggregation |
| A2 | Large methane plumes in the Permian Basin using EMIT | Radiance/enhancement, QA, repeat observations |
| A3 | 2023 Canadian wildfire smoke over eastern US | L2/L3, cloud filtering, QA, event aggregation |

### Cryosphere

| ID | Task | Main traps |
|---|---|---|
| C1 | Jakobshavn velocity 2015–2024 | ITS_LIVE, velocity components, virtual Zarr, lazy access |
| C2 | PREFIRE/MODIS Greenland collocation | Time, space, grids, cloud masking |
| C3 | Beaufort Sea 2024 melt onset and September minimum | Grid, concentration, missing data, masks |

### Biosphere

| ID | Task | Main traps |
|---|---|---|
| B1 | Pacific Northwest wildfire vegetation recovery | QA, composites/scenes, temporal analysis |
| B2 | Amazon GPP and SMAP soil moisture anomalies | Grids, scaling, QA, climatology |
| B3 | GEDI + Landsat forest canopy change | Footprints/raster, geolocation, fusion |

### Ocean

| ID | Task | Main traps |
|---|---|---|
| O1 | California Current chlorophyll during 2023 heatwave | L2/L3, cloud/QA, baseline |
| O2 | Great Barrier Reef thermal stress in 2024 | SST, thermal stress, temporal aggregation |
| O3 | SWOT vs conventional altimetry Gulf Stream SSH | Swath/along-track, sampling, alignment |

### Solid Earth

| ID | Task | Main traps |
|---|---|---|
| S1 | Türkiye 2023 earthquake displacement | SAR/InSAR vs optical, quality |
| S2 | Reykjanes 2023–2024 inflation | InSAR time series, reference frame |
| S3 | Central Valley 2015–2024 subsidence | Time-series InSAR, velocity/displacement |

### Land Surface and Human Environment

| ID | Task | Main traps |
|---|---|---|
| L1 | Phoenix summer daytime UHI 2015–2024 | LST vs air temperature, masks |
| L2 | Florida nighttime-light recovery after Hurricane Ian | Black Marble, QA, county aggregation |
| L3 | Iowa 2022 drought using soil moisture + ET | SMAP/MODIS grids, resolution, units |

---

## 12. Task Definition

Every scientific task is transformed into a bounded reproducible Harbor task.

Each task specifies:

* geographic extent
* temporal extent
* scientific objective
* expected output artifact
* expected output schema
* acceptable datasets
* preferred datasets
* acceptable representations
* preferred access strategies
* scientific requirements
* efficiency expectations
* reference result
* golden tests

The scientific question remains open with respect to dataset discovery and workflow construction.

The benchmark does not tell the agent:

```text
Use dataset X.
Use Zarr.
Call service Y.
```

Instead, it asks the scientific question and evaluates whether the resulting workflow is valid.

---

## 13. Golden Standards

Each task has a `gold.yaml`.

Example:

```yaml
task_id: tempo-no2-florida-2024

science_sphere: atmosphere

scientific_objective:
  description: >
    Compute monthly mean tropospheric NO2 over Florida
    for calendar year 2024.

dataset:
  preferred:
    - TEMPO Level 3 tropospheric NO2

  acceptable:
    - equivalent validated NASA tropospheric NO2 products

  unacceptable:
    - total column NO2 when tropospheric NO2 is required
    - unrelated atmospheric composition products

variables:
  required:
    - tropospheric_no2

representation:
  preferred:
    - zarr
    - virtual-zarr

  acceptable:
    - cloud-native chunked representation

  inefficient:
    - complete granule downloads

access:
  required:
    spatial_subset: true
    temporal_subset: true

science:
  quality_filter_required: true
  aggregation: monthly_mean

output:
  format: netcdf
  dimensions:
    - month
    - latitude
    - longitude

efficiency:
  preferred:
    max_bytes: 500000000
    max_objects: 1000

  acceptable:
    max_bytes: 5000000000
    max_objects: 10000

scoring:
  dataset: 20
  representation: 15
  access: 15
  science: 25
  code: 15
  efficiency: 10
```

The gold standard defines valid solution classes, not one exact implementation.

---

## 14. Independent Reference Solutions

Each task also contains an independently developed reference workflow.

```text
task/
├── gold.yaml
├── reference/
│   ├── reference.nc
│   ├── reference.json
│   └── provenance.yaml
└── tests/
```

The reference workflow is written independently of the MCP implementation.

This prevents circular evaluation.

```text
Independent scientific reference
             |
             v
       Reference result
             |
             v
        Golden tests
             |
             v
      Agent result
```

The MCP does not define the scientific truth.

The scientific reference and task-specific validation logic define the scientific truth.

---

## 15. Golden Test Categories

The benchmark uses six primary scoring categories.

| Category | Weight | Purpose |
|---|---:|---|
| Dataset selection | 20% | Did the agent select an appropriate NASA dataset? |
| Representation | 15% | Did it select an appropriate representation? |
| Access strategy | 15% | Did it access the required data efficiently? |
| Scientific correctness | 25% | Did it produce the correct scientific result? |
| Code/workflow correctness | 15% | Does the workflow execute and reproduce the result? |
| Efficiency | 10% | How much data and compute did it consume? |
| **Total** | **100%** | |

The individual component scores must always be retained even when an aggregate score is reported.

---

## 16. Complete Golden-Test Table

| Test | What is evaluated | Example | Automated | Partial credit |
|---|---|---|---|---|
| Dataset identity | Selected NASA dataset | TEMPO L3 tropospheric NO₂ | Yes | Yes |
| Processing level | Correct product level | L3 rather than inappropriate L2 | Yes | Yes |
| Variables | Required scientific variables | `tropospheric_no2` | Yes | Yes |
| Dimensions | Dataset structure | time/lat/lon | Yes | Yes |
| Representation | Data representation | Zarr/virtual Zarr | Yes | Yes |
| Virtualization | Use of available virtualization | Virtual Zarr | Yes | Yes |
| Access service | Appropriate service/path | Harmony, cloud object access | Yes | Yes |
| Spatial subset | Correct geographic restriction | Florida only | Yes | Yes |
| Temporal subset | Correct temporal restriction | 2024 only | Yes | Yes |
| QA filtering | Scientific quality filtering | Cloud/quality mask | Yes | Yes |
| Units | Correct units | mol m⁻² | Yes | Yes |
| CRS/geolocation | Correct spatial interpretation | Correct CRS/grid | Yes | Yes |
| Output schema | Required artifact | NetCDF/Zarr output | Yes | Yes |
| Numerical result | Agreement with reference | Within tolerance | Yes | Yes |
| Aggregation | Correct computation | Monthly mean | Yes | Yes |
| Reproducibility | Clean execution | Workflow reruns | Yes | Yes |
| Bytes transferred | Data volume | MB/GB read | Yes | Yes |
| Objects accessed | Number of remote objects | Object count | Yes | Yes |
| Runtime | Execution time | Seconds/minutes | Yes | Yes |
| Peak memory | Resource usage | MB/GB | Yes | Yes |
| Full-granule materialization | Unnecessary downloads | Full files downloaded | Yes | Task-dependent |
| Recovery behavior | Agent recovery | Corrects failed tool use | Diagnostic | No |

---

## 17. Harbor Evaluation Model

Harbor is used as the execution and evaluation harness.

Each task provides:

* an instruction
* an agent environment
* task-specific tests
* optional reference solution
* a verifier

Conceptually:

```text
Harbor
  |
  +-- Build environment
  |
  +-- Start agent
  |
  +-- Provide task
  |
  +-- Allow agent execution
  |
  +-- Capture trajectory
  |
  +-- Collect output artifacts
  |
  +-- Execute verifier
  |
  +-- Record reward
  |
  +-- Store metrics
```

Harbor is responsible for executing the experiment.

The project provides the domain-specific verifier.

---

## 18. Harbor Task Structure

A representative task:

```text
benchmark/tasks/atmosphere/tempo-no2/
│
├── instruction.md
├── task.toml
│
├── environment/
│   └── Dockerfile
│
├── solution/
│   └── solve.sh
│
├── tests/
│   ├── Dockerfile
│   ├── test.sh
│   ├── gold.yaml
│   ├── reference.nc
│   ├── reference.json
│   ├── test_dataset.py
│   ├── test_representation.py
│   ├── test_access.py
│   ├── test_science.py
│   └── test_efficiency.py
│
└── fixtures/
```

The `solution/` directory validates the benchmark itself.

It is not the answer supplied to the agent.

---

## 19. Agent Environment

The agent receives:

```text
Task
  |
  +-- instruction.md
  |
  +-- normal Earthdata tools
  |
  +-- internet/service access appropriate to condition
  |
  +-- credentials through secret injection
  |
  +-- MCP endpoint if condition requires it
  |
  +-- skills if condition requires it
```

The agent does not receive:

```text
gold.yaml
reference.nc
golden tests
reference workflow
efficiency thresholds
```

This prevents the agent from discovering the answer through the benchmark infrastructure.

---

## 20. Verifier Environment

The golden verifier should preferably run in a separate environment.

```text
AGENT CONTAINER
────────────────────────────────

/app
  ├── generated code
  ├── workflow
  ├── downloaded data
  └── output artifacts


                 |
                 | declared artifacts
                 v


VERIFIER CONTAINER
────────────────────────────────

/tests
  ├── gold.yaml
  ├── reference.nc
  ├── reference.json
  ├── golden_tests.py
  └── scoring.py
```

The verifier has access to the ground truth.

The agent does not.

This separation is particularly important for scientific benchmark integrity.

---

## 21. Harbor Verifier

A task-level verifier can be conceptually implemented as:

```bash
#!/bin/bash

python /tests/run_golden_tests.py \
    --workspace /app \
    --gold /tests/gold.yaml \
    --reference /tests/reference

status=$?

cp /tmp/evaluation.json \
   /logs/verifier/reward.json

exit $status
```

The exact Harbor configuration will be implemented against the selected Harbor version.

The important requirement is that the verifier produces machine-readable scores and detailed metrics.

---

## 22. Golden Verifier Output

Example:

```json
{
  "reward": 0.91,

  "dataset": 1.0,
  "representation": 1.0,
  "access": 0.85,
  "science": 0.96,
  "code": 1.0,
  "efficiency": 0.65,

  "scientific_checks": {
    "variables": true,
    "units": true,
    "qa": true,
    "spatial_extent": true,
    "temporal_extent": true,
    "numerical_tolerance": true
  },

  "efficiency_metrics": {
    "bytes_read": 842341221,
    "objects_read": 184,
    "runtime_seconds": 312,
    "peak_memory_mb": 4280
  }
}
```

The final `reward` is the weighted aggregate.

The individual metrics are retained for analysis.

---

## 23. Dataset Verification

Dataset verification determines whether the agent selected an appropriate dataset.

The verifier can inspect:

* collection identifier
* product identifier
* processing level
* version
* variables
* spatial coverage
* temporal coverage

Example:

```python
def test_dataset(result, gold):
    preferred = gold["dataset"]["preferred"]
    acceptable = gold["dataset"]["acceptable"]

    assert (
        result.collection in preferred
        or result.collection in acceptable
    )
```

The test should not force one dataset if several scientifically valid NASA products satisfy the task.

---

## 24. Representation Verification

The representation verifier evaluates whether the agent selected an appropriate computational representation.

Possible classifications:

```text
preferred
acceptable
inefficient
invalid
```

For example:

```text
Virtual Zarr
    -> preferred

Cloud-native chunked representation
    -> acceptable

Download all source granules
    -> inefficient
```

A scientifically correct but operationally poor workflow therefore remains scientifically correct while receiving a lower efficiency score.

---

## 25. Access Verification

Access verification measures what the agent actually accessed.

Possible instrumentation includes:

* HTTP requests
* object-store requests
* bytes transferred
* object count
* requested byte ranges
* downloaded files
* remote versus local reads
* full-granule materialization

Example:

```python
def test_spatial_access(access_log, gold):
    if gold["access"]["required"]["spatial_subset"]:
        assert access_log.spatial_subset is True
```

The benchmark should prefer observed behavior over claims made by the agent.

For example, an agent saying:

```text
"I used spatial subsetting."
```

is not evidence.

The access instrumentation must show that only the required data were actually read.

---

## 26. Spatial and Temporal Verification

The produced output is independently checked against the task definition.

Example:

```python
def test_temporal_extent(output):
    assert output.time.min() >= "2024-01-01"
    assert output.time.max() < "2025-01-01"
```

Spatial verification may check:

* bounding box
* polygon intersection
* coordinate range
* CRS
* grid alignment
* requested region

The exact verifier depends on the scientific task.

---

## 27. Scientific Correctness

Scientific correctness is the most important individual score.

It is evaluated independently of the agent's explanation.

The verifier checks:

* required variables
* units
* QA requirements
* spatial extent
* temporal extent
* scientific transformation
* aggregation
* numerical result

Where a numerical reference is available, the agent result is compared against an independently generated reference using task-specific tolerances.

Example:

```python
def test_scientific_result(result, reference):
    np.testing.assert_allclose(
        result.monthly_mean,
        reference.monthly_mean,
        rtol=1e-4,
        atol=1e-8,
    )
```

The tolerance must be scientifically justified for each task.

---

## 28. Example Golden Test: TEMPO NO₂

Task:

```text
Compute monthly mean tropospheric NO₂ over Florida during 2024.
```

Golden tests:

```text
Dataset
    ✓ appropriate TEMPO tropospheric NO₂ product

Processing level
    ✓ appropriate processing level

Variable
    ✓ tropospheric NO₂

Spatial extent
    ✓ Florida

Temporal extent
    ✓ January–December 2024

Quality control
    ✓ required QA applied

Units
    ✓ expected units

Aggregation
    ✓ monthly mean

Output
    ✓ required dimensions
    ✓ required variables

Numerical result
    ✓ within reference tolerance

Access
    ✓ spatially restricted
    ✓ temporally restricted

Efficiency
    ✓ bytes within preferred envelope
    ✓ object count within preferred envelope
```

---

## 29. Example Golden Test: ITS_LIVE

Task:

```text
Analyze Jakobshavn surface velocity from 2015–2024.
```

Evaluation:

| Test | Preferred outcome |
|---|---|
| Dataset | ITS_LIVE |
| Variable | velocity |
| Components | appropriate velocity components |
| Representation | virtual/cloud-native Zarr where available |
| Access | lazy regional reads |
| Spatial subset | Jakobshavn region |
| Temporal subset | 2015–2024 |
| Units | expected velocity units |
| Aggregation | scientifically appropriate |
| Result | agrees with independent reference |
| Bytes | below inefficient threshold |
| Objects | substantially below full archive access |

A baseline agent might download many NetCDF files.

The MCP-aware agent should have information allowing it to recognize a virtualized representation and construct a lazy xarray workflow.

The golden tests determine whether this actually happened.

---

## 30. Example Golden Test: PREFIRE + MODIS

Task:

```text
Co-locate PREFIRE radiance observations with
non-cloudy MODIS observations over Greenland
during winter 2024.
```

Evaluation:

| Test | Evaluation |
|---|---|
| PREFIRE dataset | Correct |
| MODIS dataset | Correct |
| Time matching | Correct |
| Spatial matching | Correct |
| MODIS cloud mask | Applied |
| Grid/resolution handling | Correct |
| Collocated output | Exists |
| Numerical result | Within tolerance |
| Access | Appropriate subsets |
| Efficiency | No unnecessary full-scene downloads |

This task tests whether an agent can reason across different NASA datasets rather than simply retrieving one product.

---

## 31. Complete Golden Examples Table

| Task | Dataset test | Representation test | Access test | Science test | Efficiency test | Key failure mode |
|---|---|---|---|---|---|---|
| A1 TEMPO NO₂ | TEMPO tropospheric NO₂ product | L3/cloud-native representation | Florida + 2024 subset | Monthly mean with QA | Avoid full granule reads | L2/L3 and tropospheric/total confusion |
| A2 EMIT methane | EMIT methane product | Appropriate geospatial scene representation | Permian Basin + overpass filtering | Methane enhancement and plume detection | Avoid unrelated scenes | Treating radiance as methane enhancement |
| A3 Smoke | Appropriate aerosol product | L2/L3 appropriate to aggregation | Eastern US + event dates | AOD/QA/plume aggregation | Avoid global/full archive reads | Wrong product level or QA |
| C1 ITS_LIVE | ITS_LIVE velocity | Virtual/cloud-native Zarr | Lazy regional reads | Velocity analysis 2015–2024 | Bytes/object reduction | Downloading thousands of files |
| C2 PREFIRE/MODIS | Correct PREFIRE + MODIS products | Compatible grids/representations | Spatial and temporal collocation | Cloud-filtered collocation | Avoid full MODIS scenes | Incorrect collocation |
| C3 Sea ice | Appropriate passive microwave concentration | Correct grid | Beaufort Sea + seasonal windows | Melt onset/minimum definition | Region/time subset | Missing data and masks |
| B1 PNW wildfire | Vegetation disturbance product | Suitable temporal composites | Fire region + recovery period | Disturbance/recovery | Avoid unnecessary scenes | Wrong QA/composite |
| B2 Amazon GPP | MOD17A2H + SMAP L4 | Compatible gridded representation | Amazon + matching periods | GPP/soil-moisture anomaly | Spatial/temporal subset | Scale factors and grid mismatch |
| B3 GEDI/Landsat | GEDI + Landsat | Footprint/raster handling | Managed forest region | Canopy/biomass change | Avoid full archive | Footprint/raster confusion |
| O1 Chlorophyll | Appropriate ocean-color product | L3 for regional time series where appropriate | California Current | 2023 vs 2018–2022 baseline | QA and spatial subset | L2/L3 misuse |
| O2 Coral bleaching | NASA SST product | Gridded time-series representation | GBR + 2024 | Thermal stress calculation | Region/time subset | SST vs accumulated stress |
| O3 SWOT SSH | SWOT + conventional altimetry | Swath/along-track handling | Gulf Stream region | SSH anomaly comparison | Avoid irrelevant swaths | Sampling/alignment mismatch |
| S1 Türkiye earthquake | SAR/InSAR product | Appropriate interferometric representation | Earthquake region + acquisition window | Ground displacement | Spatial/temporal filtering | Optical imagery substitution |
| S2 Reykjanes | InSAR time series | Time-series representation | Reykjanes + 2023–24 | Inflation/displacement | Region/time subset | Reference-frame errors |
| S3 Central Valley | Time-series InSAR | Appropriate time-series representation | Central Valley | Subsidence velocity/displacement | Avoid full archive | Velocity/displacement confusion |
| L1 Phoenix UHI | LST product | Gridded time series | Phoenix + summer daytime | UHI metric | Spatial/seasonal subset | LST treated as air temperature |
| L2 Hurricane Ian | Black Marble | Appropriate nighttime-light representation | Florida counties + recovery period | Recovery ranking | County/period subset | QA and baseline errors |
| L3 Iowa drought | SMAP + MODIS ET | Aligned grids/units | Iowa Corn Belt + 2022 | Soil moisture + ET drought analysis | Spatial/temporal subset | Grid/resolution/unit mismatch |

---

## 32. Scientific Correctness Versus Access Correctness

This distinction is fundamental.

Consider two agents.

### Agent A

```text
Correct dataset
Correct variable
Correct QA
Correct result

Downloads 80 GB
```

### Agent B

```text
Correct dataset
Correct variable
Correct QA
Correct result

Reads 400 MB through virtual Zarr
```

Both are scientifically correct.

However:

| Criterion | Agent A | Agent B |
|---|---:|---:|
| Dataset | Correct | Correct |
| Science | Correct | Correct |
| Code | Correct | Correct |
| Access | Acceptable | Preferred |
| Bytes | 80 GB | 400 MB |
| Efficiency | Poor | Excellent |
| Overall score | Lower | Higher |

This is precisely the behavior the MCP is intended to improve.

---

## 33. Efficiency Evaluation

Efficiency is measured independently from scientific correctness.

Metrics include:

* bytes transferred
* number of objects accessed
* runtime
* peak memory
* local storage
* number of complete granules downloaded
* number of unnecessary tool calls
* unnecessary materialization

Primary measures:

```text
data reduction =
baseline bytes / knowledge-aware bytes

object reduction =
baseline objects / knowledge-aware objects

runtime reduction =
baseline runtime / knowledge-aware runtime
```

Efficiency should be reported separately as well as contributing to the aggregate score.

---

## 34. Efficiency Envelopes

Efficiency should not normally be binary.

Each task can define:

```yaml
efficiency:
  preferred:
    max_bytes: 500000000
    max_objects: 1000

  acceptable:
    max_bytes: 5000000000
    max_objects: 10000

  inefficient:
    max_bytes: 50000000000
```

This produces classifications such as:

```text
Preferred
Acceptable
Inefficient
Invalid
```

A scientifically correct but inefficient workflow therefore remains scientifically correct.

---

## 35. Code and Workflow Correctness

The code score measures whether the produced workflow is actually executable.

Tests include:

* required files exist
* code imports successfully
* dependencies are available
* workflow executes
* output artifact is created
* output is readable
* workflow can be rerun
* no manual intervention is required

Example:

```bash
python workflow.py

test -f output.nc

python verify_output.py output.nc
```

A workflow that only describes what should be done but does not execute successfully cannot receive full code credit.

---

## 36. Reproducibility

The benchmark should distinguish:

1. live operational validation
2. reproducible benchmark execution

The reproducible benchmark mode should use controlled inputs, cached responses, fixed snapshots, or controlled service endpoints where necessary.

The live validation mode can exercise actual NASA Earthdata services.

This distinction is necessary because external service availability, authentication, network conditions, and changing datasets can otherwise make the scientific benchmark nondeterministic.

---

## 37. Golden Tests Should Be Deterministic Where Possible

Preferred verification hierarchy:

```text
1. Programmatic numerical comparison
2. Structured metadata comparison
3. Execution tests
4. Access instrumentation
5. Deterministic resource metrics
6. Static workflow inspection
7. LLM-as-judge
```

LLM-as-judge should only be used when a property genuinely cannot be evaluated programmatically.

It should not be the primary mechanism for determining scientific correctness.

---

## 38. Trajectory Analysis

The agent trajectory is collected separately from the correctness score.

It provides diagnostic information about why an agent succeeded or failed.

Metrics include:

* datasets considered
* tools invoked
* MCP calls
* number of tool calls
* data structure inspection
* virtualization discovery
* service discovery
* failed attempts
* retries
* recovery attempts
* unnecessary exploration
* final workflow

This enables analysis of whether the MCP changes the agent's reasoning process.

---

## 39. Failure Taxonomy

Failures are classified into three major categories.

### Discovery failure

The agent selects the wrong dataset.

```text
Wrong product
Wrong processing level
Wrong variable
```

### Operational knowledge failure

The agent finds the right dataset but accesses it incorrectly.

```text
Wrong representation
Wrong service
No virtualization
Full download
Incorrect subsetting
Incorrect chunk strategy
```

### Scientific reasoning failure

The agent has the correct data and access strategy but performs the science incorrectly.

```text
Wrong aggregation
Wrong units
Wrong QA
Wrong interpretation
Wrong statistical calculation
```

The expectation is that `earthaccess-mcp` should primarily reduce operational knowledge failures.

---

## 40. Oracle / Reference Validation

The reference workflow is also used to validate the benchmark.

Before running any model:

```text
Reference workflow
        |
        v
Reference output
        |
        v
Golden verifier
        |
        v
Expected full score
```

Every benchmark task must pass its own golden tests using the expert reference workflow.

If the reference workflow cannot achieve the expected score, the benchmark task is considered invalid and must be corrected before the experiment proceeds.

This protects against broken tests, incorrect reference data, and inappropriate tolerances.

---

## 41. Experimental Run Artifact

Every execution produces a complete machine-readable record.

```text
run/
├── task.yaml
├── model.yaml
├── harness.yaml
├── condition.yaml
├── trial.yaml
│
├── trajectory.jsonl
├── stdout.log
├── stderr.log
│
├── workflow/
├── artifacts/
│
├── access/
│   ├── http.jsonl
│   ├── objects.jsonl
│   └── bytes.json
│
├── metrics.json
└── score.json
```

Example:

```yaml
task: tempo-no2-florida-2024
model: local-model-a
harness: harness-a
condition: mcp-skills
trial: 3

dataset:
  score: 1.0

representation:
  score: 1.0

access:
  score: 0.90

science:
  score: 0.96

code:
  score: 1.0

efficiency:
  score: 0.82

metrics:
  bytes_read: 842341221
  objects_read: 184
  runtime_seconds: 312
  peak_memory_mb: 4280
  tool_calls: 27
  failed_attempts: 2
  recovery_attempts: 1

success: true
```

---

## 42. Statistical Analysis

The primary analysis should treat knowledge condition as the main experimental treatment.

A basic model is:

```text
score ~
    knowledge_condition
    + model
    + harness
    + science_sphere
    + knowledge_condition:model
    + knowledge_condition:harness
```

Repeated observations should be accounted for by task and model as appropriate.

The main comparisons are:

```text
MCP only      vs Baseline
Skills only   vs Baseline
MCP + Skills  vs Baseline
MCP + Skills  vs MCP only
MCP + Skills  vs Skills only
```

The central result is the treatment effect of Earthdata knowledge.

Model leaderboard performance is secondary.

---

## 43. Research Questions

### RQ1

Does Earthdata operational knowledge improve agent performance on NASA Earthdata tasks?

### RQ2

Do MCP and Earthdata skills provide complementary benefits?

### RQ3

Does Earthdata knowledge improve access efficiency?

### RQ4

Do benefits generalize across different language models?

### RQ5

Do benefits generalize across different agent harnesses?

### RQ6

Which classes of agent failure are most affected by Earthdata operational knowledge?

---

## 44. Hypotheses

### H1

Agents receiving Earthdata-specific operational knowledge will achieve higher scientific workflow scores than baseline agents.

### H2

The combination of MCP and skills will outperform either MCP or skills independently.

### H3

Earthdata-aware agents will reduce data transfer and unnecessary object access.

### H4

Benefits will generalize across multiple models and agent harnesses.

### H5

The largest improvement will occur in operational knowledge failures rather than fundamental scientific reasoning failures.

---

## 45. Primary Metrics

The primary metrics are:

| Metric | Description |
|---|---|
| Overall score | Weighted aggregate |
| Scientific correctness | Agreement with independent scientific reference |
| Dataset correctness | Correct product/dataset selection |
| Representation score | Quality of chosen representation |
| Access score | Correctness of access strategy |
| Efficiency score | Resource efficiency |
| Execution success | Whether workflow completed |
| Data volume | Bytes transferred |
| Object count | Remote objects accessed |
| Runtime | End-to-end execution time |

Secondary metrics include:

* tool calls
* MCP calls
* failed attempts
* recovery attempts
* context/token usage
* memory
* local storage
* API cost

---

## 46. Model and Harness Independence

The benchmark should not be optimized around a single model or harness.

The MCP must be exposed through a standard interface.

The skills must be ordinary files or structured resources.

The tasks must be executable independently of the MCP implementation.

The golden tests must not depend on the model.

This ensures that the benchmark can later be reused by:

* other Earthdata projects
* other MCP servers
* other models
* other agent frameworks
* other NASA DAACs
* community benchmarks

---

## 47. Local Inference Architecture

The local evaluation setup is:

```text
Harbor
   |
   v
Agent Harness
   |
   v
LiteLLM
   |
   v
llama-swap
   |
   v
llama.cpp
   |
   v
Local Model
```

The same LiteLLM endpoint provides a common interface across local models.

The benchmark records:

* model identifier
* quantization
* context length
* inference parameters
* token usage where available
* runtime
* generation statistics

The benchmark should not assume that all models have identical context lengths or inference capabilities.

---

## 48. Claude Evaluation

Claude Sonnet is evaluated through an API key.

The key is provided through runtime secret injection.

Example conceptual configuration:

```text
ANTHROPIC_API_KEY=<runtime secret>
```

The key is never stored in:

* Git
* benchmark task files
* logs
* result artifacts

The Claude experiment has a hard budget of:

```text
$50 USD
```

Every API execution must record:

* model identifier
* input tokens if available
* output tokens if available
* estimated cost
* cumulative experiment cost

The benchmark runner must stop further Claude executions when the configured budget is reached.

---

## 49. Pilot Experiment

The pilot uses three representative tasks.

Recommended pilot tasks:

```text
A1 — TEMPO NO₂
C1 — ITS_LIVE
L3 — Iowa drought
```

These provide different access and science characteristics.

The pilot evaluates:

* benchmark validity
* agent stability
* MCP functionality
* skills functionality
* Harbor integration
* golden test reliability
* runtime
* local inference behavior
* Claude API cost
* Earthdata access reproducibility

Pilot results must be reviewed before starting the full experiment.

---

## 50. Full Experiment

After pilot validation:

```text
6 models
× 4 harnesses
× 4 conditions
× 18 tasks
× 5 trials
```

Total:

```text
8,640 task executions
```

Each execution produces:

* trajectory
* workflow
* output artifact
* verifier output
* efficiency metrics
* configuration manifest

The experiment runner should be restartable.

If one run fails because of an infrastructure problem, that failure must be distinguishable from an agent failure.

---

## 51. Infrastructure Failures Versus Agent Failures

The benchmark must distinguish:

```text
Agent failure
    |
    +-- wrong dataset
    +-- wrong access
    +-- wrong science
    +-- failed code

Infrastructure failure
    |
    +-- Earthdata unavailable
    +-- authentication failure
    +-- network failure
    +-- container failure
    +-- model server failure
    +-- API budget exhausted
```

Infrastructure failures should not be counted as model failures.

Such runs should be marked:

```yaml
status: infrastructure_failure
```

and rerun according to predefined rules.

---

## 52. Live and Reproducible Evaluation Modes

Two execution modes should be supported.

### Reproducible benchmark mode

Uses:

* fixed dataset snapshots
* controlled object storage where required
* recorded metadata
* deterministic fixtures
* fixed reference outputs

Purpose:

* scientific comparison
* regression testing
* reproducibility

### Live Earthdata mode

Uses:

* actual Earthdata services
* current metadata
* real authentication
* current cloud access

Purpose:

* operational validation
* demonstration
* deployment testing

The same task and golden-test definitions should be reused where possible.

---

## 53. Example End-to-End Run

A single run conceptually proceeds as follows:

```text
1. Select task
       |
       v
2. Select model
       |
       v
3. Select harness
       |
       v
4. Select knowledge condition
       |
       v
5. Build Harbor environment
       |
       v
6. Inject credentials
       |
       v
7. Start model endpoint
       |
       v
8. Start MCP if required
       |
       v
9. Mount skills if required
       |
       v
10. Give task to agent
       |
       v
11. Agent discovers Earthdata
       |
       v
12. Agent constructs workflow
       |
       v
13. Agent executes workflow
       |
       v
14. Capture trajectory/access metrics
       |
       v
15. Agent produces output
       |
       v
16. Run golden tests
       |
       v
17. Produce score.json
       |
       v
18. Store run artifacts
       |
       v
19. Aggregate results
```

---

## 54. Example Run Command

The actual command-line interface will be implemented by the project, but conceptually:

```bash
uv run benchmark run \
    --task tempo-no2-florida-2024 \
    --model local-model-a \
    --harness harness-a \
    --condition mcp-skills \
    --trial 1
```

Pilot:

```bash
uv run benchmark run \
    --suite pilot \
    --models all \
    --harnesses all \
    --conditions all \
    --trials 2
```

Full experiment:

```bash
uv run benchmark run \
    --suite full \
    --models all \
    --harnesses all \
    --conditions all \
    --trials 5
```

Aggregation:

```bash
uv run benchmark aggregate results/
```

Report generation:

```bash
uv run benchmark report results/
```

These commands are the intended project interface; exact CLI names and Harbor integration will be finalized during implementation.

---

## 55. Evaluation Outputs

The evaluation system should produce:

```text
results/
├── raw/
├── task-level/
├── model-level/
├── harness-level/
├── condition-level/
├── science-sphere/
├── efficiency/
├── statistics/
└── reports/
```

Reports should include:

* overall condition comparison
* per-model comparison
* per-harness comparison
* per-science-sphere comparison
* per-task performance
* efficiency comparison
* failure taxonomy
* statistical significance
* confidence intervals
* effect sizes
* API cost
* local inference resource usage

---

## 56. Main Result

The primary result should look conceptually like:

| Knowledge condition | Overall | Science | Dataset | Representation | Access | Efficiency |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | ... | ... | ... | ... | ... | ... |
| MCP only | ... | ... | ... | ... | ... | ... |
| Skills only | ... | ... | ... | ... | ... | ... |
| MCP + Skills | ... | ... | ... | ... | ... | ... |

The key scientific comparison is:

```text
MCP + Skills
      vs
Baseline
```

with the other two conditions explaining the source of the improvement.

---

## 57. Secondary Result: Efficiency

A separate table should show:

| Condition | Median bytes | Median objects | Median runtime | Data reduction |
|---|---:|---:|---:|---:|
| Baseline | ... | ... | ... | 1.0x |
| MCP only | ... | ... | ... | ... |
| Skills only | ... | ... | ... | ... |
| MCP + Skills | ... | ... | ... | ... |

This directly tests whether operational Earthdata knowledge produces more efficient workflows.

---

## 58. Secondary Result: Failure Modes

Another key result should be:

| Failure type | Baseline | MCP | Skills | MCP + Skills |
|---|---:|---:|---:|---:|
| Discovery failure | ... | ... | ... | ... |
| Operational failure | ... | ... | ... | ... |
| Scientific failure | ... | ... | ... | ... |

The expectation is that MCP should have its strongest effect on operational failures.

---

## 59. Expert Workflow Is the Oracle, Not an Experimental Condition

The expert-written workflow is used to:

* establish the scientific reference
* establish valid solution classes
* determine expected output
* determine efficiency envelopes
* validate golden tests
* validate the benchmark itself

It is not counted as one of the four agent conditions.

Therefore:

```text
Experimental conditions

1. Baseline
2. MCP
3. Skills
4. MCP + Skills


Independent reference

5. Expert/Oracle workflow
```

The Oracle is used for validation, not comparison as an AI agent.

---

## 60. Why This Evaluation Is Stronger Than an LLM Judge

A conventional benchmark might ask:

```text
Did the model produce a good answer?
```

and then send the answer to another language model.

This benchmark instead asks:

```text
Did the produced workflow:

1. select valid Earthdata?
2. select appropriate variables?
3. use an appropriate representation?
4. access the appropriate data?
5. apply required QA?
6. produce the correct scientific result?
7. execute reproducibly?
8. remain within the expected efficiency envelope?
```

These questions can largely be answered programmatically.

This makes the benchmark:

* reproducible
* auditable
* scientifically defensible
* independent of a particular judge model
* useful for regression testing

LLM-as-judge remains a fallback for qualitative properties that cannot reasonably be automated.

---

## 61. Deliverables

The project will deliver:

1. Public `earthaccess-mcp` GitHub repository.
2. Functional MCP server.
3. `data_taxonomy` capability.
4. Authentication capability.
5. Related-science capability.
6. Earthdata core operations.
7. Reusable Earthdata skills.
8. 18-task scientific benchmark.
9. Golden standards for every task.
10. Independent scientific reference workflows.
11. Programmatic golden tests.
12. Harbor-compatible task environments.
13. Automated scoring.
14. Efficiency instrumentation.
15. Pilot evaluation.
16. Full multi-model evaluation.
17. Public benchmark documentation.
18. Example notebooks.
19. Public evaluation results.
20. One-day community hackathon.
21. Final technical report.
22. Public benchmark and evaluation methodology for reuse by other ESDS projects.

---

## 62. Timeline

### Months 1–2: Planning and Requirements

* finalize benchmark design
* identify representative collections
* define task schemas
* establish scientific references
* define golden-test framework
* establish Harbor integration approach

### Months 2–3: Core MCP

* implement FastMCP server
* authentication
* Earthdata core tools
* initial taxonomy
* related-science capability
* initial documentation

### Months 4–7: Access Optimization

* expand data taxonomy
* implement virtualization metadata
* integrate access strategies
* develop skills
* build benchmark tasks
* implement access instrumentation

### Months 7–9: Evaluation

* complete golden tests
* validate Oracle solutions
* run pilot
* finalize models/harnesses
* run full benchmark
* statistical analysis

### Months 9–12: Release and Dissemination

* public release
* benchmark documentation
* examples
* community hackathon
* final evaluation report
* technical demonstration
* recommendations for operational adoption

---

## 63. Operational Path

The project is intended to remain useful after the funded period.

Potential operational paths include:

* co-distribution with earthaccess
* PyPI and conda-forge distribution
* integration with CMR MCP
* integration with NASA Earthdata Cloud services
* integration with Jupyter environments
* use by CryoCloud and GeoJupyter
* adoption by DAACs
* reuse by other ESDS projects

The benchmark itself should remain independently useful even if the MCP implementation evolves.

---

## 64. Long-Term Architecture

The longer-term ESDS architecture can evolve toward:

```text
                         AI Agent
                            |
             +--------------+--------------+
             |                             |
             v                             v
         CMR MCP                     earthaccess MCP
             |                             |
       Discovery                    Operational Access
             |                             |
             +--------------+--------------+
                            |
                            v
                      Earthdata Cloud
                            |
                +-----------+-----------+
                |           |           |
              DAACs      Harmony     Virtual
                                    Representations
```

The benchmark provides a mechanism for evaluating whether this architecture actually improves scientific workflows rather than merely adding tools to an agent.

---

## 65. Core Evaluation Principle

The project should ultimately answer one concrete question:

> **When an AI agent is asked to solve a real NASA Earthdata science problem, does giving it operational knowledge about how NASA data are represented and accessed cause it to produce a better workflow?**

A "better workflow" means:

```text
Scientifically correct
        +
Operationally correct
        +
Reproducible
        +
Efficient
```

The MCP is the intervention.

The skills are a complementary intervention.

The models and harnesses are experimental factors.

The 18 scientific tasks are the workload.

The expert workflows establish independent ground truth.

The golden tests establish objective correctness.

Harbor provides the controlled execution environment.

The resulting benchmark provides the evidence for whether `earthaccess-mcp` delivers measurable value.
