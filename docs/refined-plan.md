# Earthaccess-MCP Benchmark: Task Design & Evaluation Specification

**Version:** 2.1 (Multi-Pattern Access Focused)
**Companion to:** earthaccess MCP Project Proposal
**Program:** ESDS AI Innovation Call
**Team:** earthaccess collaboration team, NSIDC

**Changelog from v2.0:** Virtualization is no longer the sole "preferred" pattern. Streaming and subsetting services (OPeNDAP, Harmony, AppEEARS, Giovanni, cloud streaming) are now first-class evaluation targets. The benchmark evaluates **best available access pattern selection** given collection characteristics *and* service availability.

---

## 1. Design Philosophy

### 1.1 Virtualization Is Not the Only Answer

The original v2.0 benchmark implicitly treated virtual Zarr as the universal "preferred" access pattern. This is incorrect for three reasons:

1. **Virtualization is not always available.** The EarthDataVirtualizabilityScore explicitly documents collections that cannot be virtualized. For these, the best achievable pattern is something else.

2. **Virtualization is not always appropriate.** For small temporal windows or point queries, a Harmony subset request may transfer fewer bytes than opening a virtual Zarr datacube.

3. **NASA operates multiple access services.** Harmony, OPeNDAP (Hyrax/THREDDS), AppEEARS, Giovanni, and cloud streaming endpoints are all valid, DAAC-supported access paths. An agent that ignores them is not operationally correct.

**The revised benchmark evaluates:**

> **Given a NASA Earthdata collection and a scientific access requirement, did the agent select and execute the best available access pattern from the full set of DAAC-supported services?**

The EarthDataVirtualizabilityScore remains a critical input—but it is one oracle among several. The complete oracle is a **service availability matrix** that combines:

| Oracle Source | What It Provides |
|---|---|
| EarthDataVirtualizabilityScore | Whether virtual Zarr / Kerchunk is achievable, and why not if not |
| CMR service metadata | Which services (Harmony, OPeNDAP, AppEEARS, Giovanni, S3) are associated with the collection |
| DAAC documentation | Service-specific capabilities (subsetting axes, output formats, rate limits) |
| Live service probes | Whether the service is currently reachable and responsive |

### 1.2 The Correct Question

The benchmark now asks:

> **Did the agent discover the available access services for this collection, evaluate them against the access requirement, and select the most efficient one that satisfies the requirement?**

Not:

> Did the agent use virtual Zarr?

---

## 2. Comprehensive Access Pattern Taxonomy

### 2.1 Pattern Classes

Access patterns are organized into five families. Each family contains multiple specific patterns. Patterns are **not ranked globally**—the best pattern depends on the collection and the access requirement.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ACCESS PATTERN TAXONOMY (v2.1)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FAMILY 1: CLOUD-NATIVE DIRECT ACCESS                                       │
│  ────────────────────────────────────                                       │
│  Direct object-store access with lazy, range-request semantics.             │
│  No intermediate server. Requires cloud-optimized storage.                  │
│                                                                             │
│  1.1  Virtual Zarr / Kerchunk references                                    │
│         → References generated over existing granules                       │
│         → Requires: parser-readable, chunk-aligned, time dimension          │
│         → Oracle: EarthDataVirtualizabilityScore grade A/B                  │
│                                                                             │
│  1.2  Native Zarr                                                           │
│         → Data already stored as Zarr                                       │
│         → No references needed                                              │
│                                                                             │
│  1.3  Cloud-Optimized GeoTIFF (COG)                                         │
│         → Range requests on tiled GeoTIFF                                   │
│         → Suitable for raster-per-granule collections                       │
│                                                                             │
│  1.4  Parquet / Iceberg / Arrow                                             │
│         → For tabular or point collections                                  │
│                                                                             │
│  1.5  Cloud streaming (Zarr streaming servers, TileDB, etc.)                │
│         → Server-mediated streaming of cloud-native data                    │
│         → Distinct from direct access: server in the middle                 │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FAMILY 2: SERVER-MEDIATED SUBSETTING                                       │
│  ────────────────────────────────────                                       │
│  A NASA-operated service performs spatial, temporal, and/or variable        │
│  subsetting server-side, returning a reduced output.                        │
│                                                                             │
│  2.1  Harmony subsetting                                                    │
│         → NASA's primary subsetting service                                 │
│         → Supports spatial (bbox, polygon), temporal, variable subsetting   │
│         → Output: NetCDF4, Zarr, or GeoTIFF                                 │
│         → Discoverable via CMR service metadata                             │
│                                                                             │
│  2.2  OPeNDAP (Hyrax / THREDDS)                                             │
│         → Traditional DAP2/DAP4 subsetting                                  │
│         → Server-side slicing, dicing, and type conversion                  │
│         → Accessible via pydap, netCDF4, xarray                             │
│                                                                             │
│  2.3  OPeNDAP-in-the-Cloud (DMR++ + range requests)                         │
│         → Hybrid: DMR++ metadata enables range-request subsetting           │
│         → Requires DMR++ sidecar availability                               │
│         → No Hyrax server in the loop                                       │
│                                                                             │
│  2.4  AppEEARS                                                              │
│         → Land-process DAAC subsetting and transformation service           │
│         → Area sample, point sample, and time-series extraction             │
│         → Output: CSV, NetCDF, GeoTIFF                                      │
│                                                                             │
│  2.5  Giovanni                                                              │
│         → Atmospheric composition and model data service                    │
│         → Area-averaged time series, maps, and correlations                 │
│         → Output: NetCDF, CSV, PNG                                          │
│                                                                             │
│  2.6  Worldview / EDSC subsetting                                           │
│         → Earthdata Search client-side subsetting                           │
│         → Granule filtering before download                                 │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FAMILY 3: STREAMING / LAZY ACCESS                                          │
│  ────────────────────────────────────                                       │
│  Data is consumed as a stream without full materialization, but via         │
│  a protocol rather than direct range requests.                              │
│                                                                             │
│  3.1  OPeNDAP streaming (DAP4)                                              │
│         → Streaming reads from Hyrax                                        │
│         → Suitable for sequential access patterns                           │
│                                                                             │
│  3.2  Zarr streaming (e.g., xpublish, zarrita)                              │
│         → Streaming reads over Zarr stores                                  │
│                                                                             │
│  3.3  HTTP range streaming on COG / virtual Zarr                            │
│         → Overlaps with Family 1 but via explicit streaming client          │
│                                                                             │
│  3.4  Kafka / pub-sub streams (emerging)                                    │
│         → Not currently standard for NASA Earthdata; reserved               │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FAMILY 4: FILTERED DOWNLOAD                                                │
│  ────────────────────────────────────                                       │
│  Agent downloads granules, but filters the granule list first to avoid      │
│  unnecessary transfers. No server-side subsetting.                          │
│                                                                             │
│  4.1  Spatial granule filtering                                             │
│         → Filter by granule bounding box before download                    │
│                                                                             │
│  4.2  Temporal granule filtering                                            │
│         → Filter by acquisition time before download                        │
│                                                                             │
│  4.3  Variable-level download (per-band, per-layer)                         │
│         → Only for formats supporting partial download                      │
│                                                                             │
│  4.4  Quality-flag-based granule filtering                                  │
│         → Exclude granules by metadata before download                      │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FAMILY 5: FULL MATERIALIZATION                                             │
│  ────────────────────────────────────                                       │
│  No subsetting, no streaming, no virtualization. All bytes transferred.     │
│                                                                             │
│  5.1  Full granule download                                                 │
│         → Download all granules in the temporal window                      │
│                                                                             │
│  5.2  Full archive download                                                 │
│         → Download the entire collection                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Pattern Identifiers

| ID | Pattern | Family |
|---|---|---|
| `C1` | Virtual Zarr / Kerchunk | Cloud-native |
| `C2` | Native Zarr | Cloud-native |
| `C3` | Cloud-Optimized GeoTIFF | Cloud-native |
| `C4` | Parquet / Iceberg / Arrow | Cloud-native |
| `C5` | Cloud streaming | Cloud-native |
| `S1` | Harmony subsetting | Subsetting |
| `S2` | OPeNDAP (Hyrax/THREDDS) | Subsetting |
| `S3` | OPeNDAP-in-the-Cloud (DMR++) | Subsetting |
| `S4` | AppEEARS | Subsetting |
| `S5` | Giovanni | Subsetting |
| `S6` | EDSC subsetting | Subsetting |
| `T1` | OPeNDAP streaming (DAP4) | Streaming |
| `T2` | Zarr streaming | Streaming |
| `T3` | HTTP range streaming | Streaming |
| `F1` | Spatial granule filtering | Filtered download |
| `F2` | Temporal granule filtering | Filtered download |
| `F3` | Variable-level download | Filtered download |
| `F4` | Quality-flag filtering | Filtered download |
| `M1` | Full granule download | Full materialization |
| `M2` | Full archive download | Full materialization |

### 2.3 Pattern Families Are Not Strictly Ordered

Unlike v2.0, families are not globally ranked. Instead, each pattern has a **context-dependent preference** determined by:

1. **Availability** — Is the service associated with this collection?
2. **Requirement fit** — Does the pattern satisfy the spatial/temporal/variable subsetting requirement?
3. **Efficiency** — How many bytes and objects does the pattern consume?
4. **Latency** — How long does the pattern take?
5. **Reliability** — Is the service currently operational?

The agent's job is to select the best pattern given these constraints. The verifier's job is to determine which pattern *should* have been selected.

---

## 3. Service Availability Matrix

### 3.1 The Complete Oracle

The "ground truth" for each task is no longer a single virtualizability grade. It is a **service availability matrix** derived from multiple sources.

```yaml
collection_id: ITS_LIVE_velocity_120m

service_availability:
  cloud_native:
    virtual_zarr:
      available: true
      oracle: EarthDataVirtualizabilityScore
      grade: A ⭐
      parser_readable: true
      chunk_aligned: true
      time_dim: true
      evidence: "no blocker"

    native_zarr:
      available: false

    cog:
      available: false

  subsetting:
    harmony:
      available: true
      supports:
        spatial: true
        temporal: true
        variable: true
      output_formats: [zarr, netcdf4]
      service_id: "harmony_itslive"

    opendap:
      available: false
      reason: "No Hyrax endpoint for this collection"

    opendap_cloud:
      available: false
      reason: "No DMR++ sidecar"

    appeeares:
      available: false
      reason: "Cryosphere collection not served by AppEEARS"

    giovanni:
      available: false
      reason: "Not an atmospheric composition collection"

  streaming:
    opendap_dap4:
      available: false

    zarr_streaming:
      available: false

  filtered_download:
    spatial_filtering:
      available: true
      reason: "Granule metadata includes bounding boxes"

    temporal_filtering:
      available: true

  full_materialization:
    granule_download:
      available: true

best_patterns_for_requirement:
  - pattern: C1
    reason: "Virtual Zarr satisfies all subsetting requirements lazily"
    expected_bytes: 45_000_000
  - pattern: S1
    reason: "Harmony subsetting also satisfies requirement"
    expected_bytes: 120_000_000
  - pattern: F1
    reason: "Spatial granule filtering is acceptable fallback"
    expected_bytes: 2_000_000_000
```

### 3.2 How the Matrix Is Built

| Source | Provides | Integration Method |
|---|---|---|
| EarthDataVirtualizabilityScore | Virtual Zarr / Kerchunk availability and blockers | CSV import into benchmark oracle |
| CMR service metadata | Harmony, OPeNDAP, AppEEARS, Giovanni associations | CMR API query at task build time |
| DAAC documentation | Service-specific subsetting capabilities | Manual curation per collection |
| Live probes | Current service reachability | Runtime probe before evaluation |
| Earthaccess MCP `data_taxonomy` | Normalized exposure of the above | Exposed to agent during evaluation |

### 3.3 The Agent's View

In the `MCP + Skills` condition, the agent sees the full service availability matrix normalized through `data_taxonomy`:

```json
{
  "collection": "ITS_LIVE_velocity_120m",
  "format": "Zarr",
  "access_services": [
    {
      "service": "virtual_zarr",
      "pattern_id": "C1",
      "available": true,
      "grade": "A ⭐",
      "max_pattern": true
    },
    {
      "service": "harmony",
      "pattern_id": "S1",
      "available": true,
      "supports": {
        "spatial": true,
        "temporal": true,
        "variable": true
      }
    }
  ],
  "recommended_patterns": ["C1", "S1"],
  "compatible_tools": ["xarray", "dask", "virtualizarr"]
}
```

In the `Baseline` condition, the agent must discover this through its own investigation (CMR queries, DAAC docs, trial and error).

---

## 4. Task Structure

### 4.1 Revised Task Schema

```yaml
task_id: string
science_sphere: enum

access_requirement:
  description: >
    A bounded scientific access scenario.

  spatial_extent:
    type: bbox | polygon | point
    coordinates: [...]

  temporal_extent:
    start: YYYY-MM-DD
    end: YYYY-MM-DD

  variables_of_interest:
    - variable_name

  output_format_required: netcdf | zarr | csv | geotiff

collection_options:
  preferred:
    - collection_id: ...
      service_availability:
        C1: {available: true, grade: "A ⭐"}
        S1: {available: true}
      best_patterns: [C1, S1]
  acceptable:
    - collection_id: ...
      service_availability: {...}
      best_patterns: [...]
  discouraged:
    - collection_id: ...
      reason: >
        Higher-level product exists that satisfies requirement
        with fewer bytes.
  unacceptable:
    - collection_id: ...
      reason: Wrong variable, wrong level, etc.

pattern_scoring:
  best_available: [C1, S1]
  acceptable: [S3, F1, F2]
  marginal: [F3, F4, M1]
  inefficient: [M2]

efficiency_envelope:
  C1: {max_bytes: 50_000_000, max_objects: 20}
  S1: {max_bytes: 200_000_000, max_objects: 5}
  F1: {max_bytes: 2_000_000_000, max_objects: 500}
  M1: {max_bytes: 10_000_000_000, max_objects: 5000}

validation:
  minimal_science_check:
    checks:
      - variable_present
      - spatial_extent_correct
      - temporal_extent_correct
      - units_correct

gold_standard:
  primary_pattern: C1
  acceptable_patterns: [S1]
  collection: ITS_LIVE_velocity_120m
  reasoning: >
    Virtual Zarr is available (grade A ⭐) and satisfies all
    subsetting requirements lazily. Harmony is also available
    and acceptable but transfers more bytes. Full download is
    inefficient.
```

### 4.2 Pattern Selection Decision Tree

```text
                    Access Requirement
                            |
                            v
              +-----------------------------+
              | Is virtual Zarr available?  |
              +-------------+---------------+
                            |
              +-------------+-------------+
              |                           |
             YES                          NO
              |                           |
              v                           v
    +-------------------+     +-----------------------------+
    | Use C1            |     | Is native Zarr available?   |
    +-------------------+     +-------------+---------------+
                                            |
                                  +---------+---------+
                                  |                   |
                                 YES                  NO
                                  |                   |
                                  v                   v
                        +----------------+  +-----------------------------+
                        | Use C2         |  | Is DMR++ available?         |
                        +----------------+  +-------------+---------------+
                                                        |
                                              +---------+---------+
                                              |                   |
                                             YES                  NO
                                              |                   |
                                              v                   v
                                    +----------------+  +-----------------------------+
                                    | Use S3         |  | Is Harmony available?       |
                                    +----------------+  +-------------+---------------+
                                                                      |
                                                            +---------+---------+
                                                            |                   |
                                                           YES                  NO
                                                            |                   |
                                                            v                   v
                                                  +----------------+  +---------------------+
                                                  | Use S1         |  | Is OPeNDAP          |
                                                  +----------------+  | available?          |
                                                                      +----------+----------+
                                                                                 |
                                                                       +---------+---------+
                                                                       |                   |
                                                                      YES                  NO
                                                                       |                   |
                                                                       v                   v
                                                             +----------------+  +---------------------+
                                                             | Use S2 or T1   |  | Is AppEEARS         |
                                                             +----------------+  | or Giovanni         |
                                                                                 | available?          |
                                                                                 +----------+----------+
                                                                                            |
                                                                                  +---------+---------+
                                                                                  |                   |
                                                                                 YES                  NO
                                                                                  |                   |
                                                                                  v                   v
                                                                        +----------------+  +---------------------+
                                                                        | Use S4 or S5   |  | Use F1-F4           |
                                                                        +----------------+  +----------+----------+
                                                                                                       |
                                                                                                       v
                                                                                             +---------------------+
                                                                                             | Use M1 (last resort)|
                                                                                             +---------------------+
```

---

## 5. Evaluation Framework

### 5.1 Revised Scoring Categories

| Category | Weight | What It Measures |
|---|---|---|
| **Collection selection** | 10% | Did the agent select an appropriate collection? |
| **Service discovery** | 15% | Did the agent discover the available access services? |
| **Access pattern** | **35%** | Did the agent use the best available pattern? |
| **Representation** | 15% | Did the agent use the correct data representation? |
| **Efficiency** | 15% | How efficient was the access? |
| **Minimal validation** | 10% | Does the output pass the minimal science gate? |
| **Total** | **100%** | |

### 5.2 Access Pattern Scoring

```python
def score_access_pattern(
    observed_pattern,
    available_patterns,
    requirement,
    service_availability,
):
    best_available = determine_best_available(
        available_patterns, requirement, service_availability
    )
    acceptable = determine_acceptable(
        available_patterns, requirement, service_availability
    )
    marginal = determine_marginal(
        available_patterns, requirement, service_availability
    )

    if observed_pattern == best_available:
        return 1.0
    elif observed_pattern in acceptable:
        return 0.7
    elif observed_pattern in marginal:
        return 0.3
    else:
        return 0.0
```

### 5.3 Service Discovery Scoring

```python
def score_service_discovery(trajectory, service_availability):
    discovered = set()

    for call in trajectory.mcp_calls:
        if call.tool == "data_taxonomy":
            discovered.update(call.result.get("access_services", []))

    for call in trajectory.tool_calls:
        if "harmony" in call.name.lower():
            discovered.add("harmony")
        if "opendap" in call.name.lower():
            discovered.add("opendap")
        if "virtualizarr" in call.name.lower():
            discovered.add("virtual_zarr")

    available = set(service_availability.keys())
    return len(discovered & available) / len(available)
```

### 5.4 Efficiency Scoring (Per-Pattern Envelopes)

```python
def score_efficiency(observed_pattern, metrics, envelopes):
    envelope = envelopes[observed_pattern]

    byte_score = score_against_envelope(
        metrics.bytes_read, envelope.max_bytes
    )
    object_score = score_against_envelope(
        metrics.objects_read, envelope.max_objects
    )
    runtime_score = score_against_envelope(
        metrics.runtime_seconds, envelope.max_runtime
    )

    return (byte_score + object_score + runtime_score) / 3
```

---

## 6. Golden Tests

### 6.1 Test Categories

| Test | What It Evaluates | Automated | Partial Credit |
|---|---|---|---|
| Collection identity | Selected appropriate NASA collection | Yes | Yes |
| Processing level | Correct product level | Yes | Yes |
| Variable selection | Accessed correct variable | Yes | Yes |
| Service discovery | Discovered available access services | Yes | Yes |
| Access pattern | Observed pattern matches best available | Yes | Yes |
| Representation | Correct data representation | Yes | Yes |
| Spatial subset | Correct geographic restriction | Yes | Yes |
| Temporal subset | Correct temporal restriction | Yes | Yes |
| Bytes transferred | Within pattern-specific envelope | Yes | Yes |
| Objects accessed | Within pattern-specific envelope | Yes | Yes |
| Runtime | Within pattern-specific envelope | Yes | Yes |
| Minimal validation | Output passes minimal science gate | Yes | No (gate) |

### 6.2 Example Golden Test: C1 ITS_LIVE

```yaml
task_id: itslive-jakobshavn-2015-2024

science_sphere: cryosphere

access_requirement:
  spatial_extent:
    type: bbox
    coordinates: [-52.0, 68.5, -48.0, 70.0]
  temporal_extent:
    start: 2015-01-01
    end: 2024-12-31
  variables_of_interest:
    - vx
    - vy

collection_options:
  preferred:
    - collection_id: ITS_LIVE_velocity_120m
      service_availability:
        C1:
          available: true
          grade: "A ⭐"
          oracle: EarthDataVirtualizabilityScore
          evidence: "no blocker"
        S1:
          available: true
          supports: {spatial: true, temporal: true, variable: true}
        F1:
          available: true
        M1:
          available: true
      best_patterns: [C1]
      acceptable_patterns: [S1, S3]
  acceptable:
    - collection_id: ITS_LIVE_velocity_240m
      best_patterns: [C1]
  discouraged:
    - collection_id: ITS_LIVE_velocity_120m_GeoTIFF
      reason: "No virtual Zarr; would require F1 or M1"
  unacceptable:
    - collection_id: MODIS_velocity
      reason: "Wrong sensor"

pattern_scoring:
  best_available: [C1]
  acceptable: [S1, S3]
  marginal: [F1, F2, F3]
  inefficient: [M1, M2]

efficiency_envelope:
  C1: {max_bytes: 100_000_000, max_objects: 50, max_runtime: 300}
  S1: {max_bytes: 500_000_000, max_objects: 10, max_runtime: 600}
  F1: {max_bytes: 5_000_000_000, max_objects: 1000, max_runtime: 1800}
  M1: {max_bytes: 50_000_000_000, max_objects: 5000, max_runtime: 7200}

validation:
  minimal_science_check:
    checks:
      - variable_present: [vx, vy]
      - spatial_extent_correct: true
      - temporal_extent_correct: true
      - units_correct: m/year

gold_standard:
  primary_pattern: C1
  acceptable_patterns: [S1]
  collection: ITS_LIVE_velocity_120m
  reasoning: >
    ITS_LIVE velocity data is available as virtual Zarr (grade A ⭐)
    and via Harmony subsetting. Virtual Zarr is preferred because it
    satisfies all subsetting requirements lazily with ~45 MB transfer.
    Harmony is acceptable but transfers ~120 MB. Full download
    transfers ~500 GB and is inefficient.

  reference_access:
    C1:
      bytes_read: 45_000_000
      objects_read: 12
      runtime_seconds: 180
    S1:
      bytes_read: 120_000_000
      objects_read: 5
      runtime_seconds: 240
```

### 6.3 Example Golden Test: A1 TEMPO NO₂

```yaml
task_id: tempo-no2-florida-2024

science_sphere: atmosphere

access_requirement:
  spatial_extent:
    type: bbox
    coordinates: [-87.5, 24.5, -80.0, 31.0]
  temporal_extent:
    start: 2024-01-01
    end: 2024-12-31
  variables_of_interest:
    - tropospheric_no2

collection_options:
  preferred:
    - collection_id: TEMPO_NO2_L3
      service_availability:
        C1:
          available: true
          grade: "A ⭐"
        S1:
          available: true
          supports: {spatial: true, temporal: true, variable: true}
        S5:
          available: true
          supports: {spatial: true, temporal: true}
          output_formats: [netcdf, csv]
        M1:
          available: true
      best_patterns: [C1]
      acceptable_patterns: [S1, S5]
  acceptable:
    - collection_id: TEMPO_NO2_L2
      service_availability:
        S1: {available: true}
        S2: {available: true}
        M1: {available: true}
      best_patterns: [S1, S2]
  discouraged:
    - collection_id: OMI_NO2_L3
      reason: "Coarser resolution, different overpass"
  unacceptable:
    - collection_id: TEMPO_NO2_L2_TOTAL_COLUMN
      reason: "Total column, not tropospheric"

pattern_scoring:
  best_available: [C1]
  acceptable: [S1, S5, S2]
  marginal: [F1, F2]
  inefficient: [M1, M2]

efficiency_envelope:
  C1: {max_bytes: 50_000_000, max_objects: 20, max_runtime: 120}
  S1: {max_bytes: 200_000_000, max_objects: 5, max_runtime: 300}
  S5: {max_bytes: 100_000_000, max_objects: 3, max_runtime: 300}
  S2: {max_bytes: 500_000_000, max_objects: 10, max_runtime: 600}
  M1: {max_bytes: 5_000_000_000, max_objects: 2000, max_runtime: 3600}

validation:
  minimal_science_check:
    checks:
      - variable_present: [tropospheric_no2]
      - spatial_extent_correct: true
      - temporal_extent_correct: true
      - units_correct: mol/m²

gold_standard:
  primary_pattern: C1
  acceptable_patterns: [S1, S5]
  collection: TEMPO_NO2_L3
  reasoning: >
    TEMPO L3 NO2 is available as virtual Zarr (grade A ⭐), via
    Harmony, and via Giovanni. Virtual Zarr is preferred for
    reproducibility. Giovanni is acceptable but produces a
    pre-aggregated product that may not match the requirement
    exactly. Full download of L2 granules is inefficient.
```

### 6.4 Example Golden Test: A3 Smoke AOD (Harmony-First)

```yaml
task_id: smoke-aod-eastern-us-2023

science_sphere: atmosphere

access_requirement:
  spatial_extent:
    type: bbox
    coordinates: [-90.0, 35.0, -70.0, 45.0]
  temporal_extent:
    start: 2023-06-01
    end: 2023-06-30
  variables_of_interest:
    - AOD_550nm

collection_options:
  preferred:
    - collection_id: MODIS_MAIAC_AOD
      service_availability:
        C1:
          available: false
          reason: "Chunk misalignment across granules blocks virtualization"
          oracle: EarthDataVirtualizabilityScore
          grade: "C"
          deciding_criterion: "chunk_aligned = false"
        S1:
          available: true
          supports: {spatial: true, temporal: true, variable: true}
          output_formats: [netcdf4]
        S2:
          available: true
        M1:
          available: true
      best_patterns: [S1]
      acceptable_patterns: [S2]
  discouraged:
    - collection_id: MODIS_MAIAC_AOD_GLOBAL
      reason: "Global product; regional subset via Harmony preferred"

pattern_scoring:
  best_available: [S1]
  acceptable: [S2]
  marginal: [F1, F2, F4]
  inefficient: [M1, M2]

efficiency_envelope:
  S1: {max_bytes: 500_000_000, max_objects: 5, max_runtime: 600}
  S2: {max_bytes: 800_000_000, max_objects: 10, max_runtime: 900}
  F1: {max_bytes: 5_000_000_000, max_objects: 500, max_runtime: 1800}
  M1: {max_bytes: 50_000_000_000, max_objects: 5000, max_runtime: 7200}

validation:
  minimal_science_check:
    checks:
      - variable_present: [AOD_550nm]
      - spatial_extent_correct: true
      - temporal_extent_correct: true
      - units_correct: dimensionless

gold_standard:
  primary_pattern: S1
  acceptable_patterns: [S2]
  collection: MODIS_MAIAC_AOD
  reasoning: >
    This collection cannot be virtualized because granules are not
    chunk-aligned across the temporal dimension. Harmony subsetting
    is the best available pattern: it performs server-side spatial
    and temporal subsetting, returning a reduced NetCDF4 file.
    OPeNDAP is also available and acceptable. Full download of
    global tiles is inefficient.
```

---

## 7. Failure Taxonomy

### 7.1 Failure Categories

#### Collection Selection Failure
```
Wrong collection
Wrong processing level
Wrong variable
Wrong sensor
```

#### Service Discovery Failure
```
Did not query CMR for services
Did not call earthaccess MCP data_taxonomy
Did not check Harmony availability
Did not check OPeNDAP availability
Did not check virtual Zarr availability
Did not check AppEEARS / Giovanni availability
```

#### Access Pattern Failure
```
Used full download when Harmony was available
Used full download when virtual Zarr was available
Used OPeNDAP when virtual Zarr was available
Used Harmony when direct virtual Zarr was available
Used a pattern that does not satisfy the subsetting requirement
```

#### Validation Failure
```
Wrong variable accessed
Wrong spatial extent
Wrong temporal extent
Wrong units
```

### 7.2 Expected Effect of MCP

The MCP should primarily reduce:

1. **Service discovery failures** — by exposing the service availability matrix via `data_taxonomy`
2. **Access pattern failures** — by recommending the best available pattern

The MCP should *not* primarily affect:

1. Collection selection failures — these are scientific knowledge, not operational knowledge
2. Validation failures — these are execution errors, not knowledge gaps

---

## 8. Research Questions

**RQ1.** Does Earthdata operational knowledge improve agents' ability to discover available access services?

**RQ2.** Does Earthdata operational knowledge improve agents' ability to select the best available access pattern?

**RQ3.** Do MCP and Earthdata skills provide complementary benefits for service discovery and pattern selection?

**RQ4.** Does the relative benefit of MCP vary by collection virtualizability grade?

**RQ5.** Do benefits generalize across different language models?

**RQ6.** Do benefits generalize across different agent harnesses?

**RQ7.** Which classes of access pattern failures (virtualization, subsetting, streaming, filtering) are most affected by Earthdata operational knowledge?

**RQ8.** Can agents learn to discover services themselves (via CMR, DAAC docs) when not given explicit service availability?

---

## 9. Hypotheses

**H1.** Agents receiving Earthdata-specific operational knowledge will discover more available access services than baseline agents.

**H2.** Agents receiving Earthdata-specific operational knowledge will select better access patterns than baseline agents.

**H3.** The combination of MCP and skills will outperform either MCP or skills independently.

**H4.** Earthdata-aware agents will reduce data transfer and unnecessary object access.

**H5.** Benefits will generalize across multiple models and agent harnesses.

**H6.** The largest improvement will occur in service discovery failures and access pattern failures, not collection selection failures.

**H7.** For collections with grade A ⭐ virtualizability, the MCP will primarily shift agents from `S1`/`S2` to `C1`.

**H8.** For collections with grade C/D virtualizability, the MCP will primarily shift agents from `M1` to `S1`/`S2`.

**H9.** For collections with Giovanni or AppEEARS availability, the MCP will increase their use relative to full download.

---

## 10. Task Suite

### 10.1 Atmosphere

| ID | Access Scenario | Expected Pattern | Why This Pattern | Key Trap |
|---|---|---|---|---|
| **A1** | TEMPO NO₂ over Florida, 2024 | `C1` (virtual Zarr) | Grade A ⭐; lazy regional reads | Agent may use `M1` (full L2 download) |
| **A2** | EMIT methane over Permian, 2024 | `S1` (Harmony) | Swath data; no virtual Zarr | Agent may use `M1` |
| **A3** | MODIS MAIAC AOD over eastern US, June 2023 | `S1` (Harmony) | Grade C; chunk misalignment | Agent may use `M1` or `F1` |

### 10.2 Cryosphere

| ID | Access Scenario | Expected Pattern | Why This Pattern | Key Trap |
|---|---|---|---|---|
| **C1** | ITS_LIVE Jakobshavn, 2015–2024 | `C1` (virtual Zarr) | Grade A ⭐; lazy regional reads | Agent may download GeoTIFFs (`M1`) |
| **C2** | PREFIRE + MODIS collocation, winter 2024 | `S1` + `S1` | Both collections Harmony-enabled | Agent may use `M1` for both |
| **C3** | AMSR2 sea ice, Beaufort 2024 | `S1` (Harmony) | Grade B; Arctic subset | Agent may download global granules (`M1`) |

### 10.3 Biosphere

| ID | Access Scenario | Expected Pattern | Why This Pattern | Key Trap |
|---|---|---|---|---|
| **B1** | Landsat ARD PNW recovery, 2020–2023 | `C1` or `S1` | Landsat ARD is cloud-optimized | Agent may download full scenes (`M1`) |
| **B2** | MOD17A2H + SMAP L4 Amazon, 2023 | `C1` + `S1` | Mixed availability | Agent may use `M1` for both |
| **B3** | GEDI + Landsat canopy, 2019–2023 | `S1` + `C1` | GEDI footprints via Harmony; Landsat ARD virtual | Agent may confuse footprint/raster access |

### 10.4 Ocean

| ID | Access Scenario | Expected Pattern | Why This Pattern | Key Trap |
|---|---|---|---|---|
| **O1** | MODIS Aqua L3 chlorophyll, 2023 | `S1` (Harmony) | Grade B; regional time series | Agent may use `M1` |
| **O2** | MUR SST GBR, 2024 | `C1` (virtual Zarr) | Grade A ⭐ | Agent may download global grids (`M1`) |
| **O3** | SWOT + AVISO Gulf Stream, 2023 | `S1` + `S1` | Swath + gridded; Harmony-enabled | Agent may use `M1` |

### 10.5 Solid Earth

| ID | Access Scenario | Expected Pattern | Why This Pattern | Key Trap |
|---|---|---|---|---|
| **S1** | Sentinel-1 Türkiye earthquake, Feb 2023 | `S1` (Harmony) | SAR; no virtual Zarr | Agent may use `M1` |
| **S2** | Sentinel-1 Reykjanes, 2023–2024 | `S1` (Harmony) | Time-series SAR | Agent may use `M1` |
| **S3** | Sentinel-1 Central Valley, 2015–2024 | `S1` (Harmony) | Long time series | Agent may use `M1` |

### 10.6 Land Surface & Human Environment

| ID | Access Scenario | Expected Pattern | Why This Pattern | Key Trap |
|---|---|---|---|---|
| **L1** | MODIS LST Phoenix, 2015–2024 | `S1` (Harmony) | Grade B; urban subset | Agent may use `M1` |
| **L2** | Black Marble Florida, 2022 | `C1` (virtual Zarr) | Grade A ⭐ | Agent may use `M1` |
| **L3** | SMAP + MODIS ET Iowa, 2022 | `C1` + `S1` | Mixed availability | Agent may use `M1` for both |

### 10.7 Pattern Coverage

| Pattern Family | Tasks |
|---|---|
| Cloud-native direct (`C1`, `C2`, `C3`) | A1, C1, B1, B3, O2, L2, L3 |
| Server-mediated subsetting (`S1`, `S2`, `S3`) | A2, A3, C2, C3, B1, B2, B3, O1, O3, S1, S2, S3, L1, L3 |
| Streaming (`T1`, `T2`, `T3`) | (Reserved for future extension) |
| Filtered download (`F1`–`F4`) | Fallback patterns for all tasks |
| Full materialization (`M1`, `M2`) | Inefficient baseline for all tasks |

---

## 11. MCP Capabilities

### 11.1 Revised `data_taxonomy` Schema

```json
{
  "collection": "MODIS_MAIAC_AOD",
  "format": "HDF4",
  "variables": [],

  "virtualizability": {
    "grade": "C",
    "parser_readable": true,
    "consolidated_md": false,
    "grid_aligned": true,
    "chunk_aligned": false,
    "time_dim": false,
    "deciding_criterion": "chunk_aligned = false",
    "max_access_pattern": null,
    "reason": "Chunk misalignment across granules blocks virtualization"
  },

  "access_services": [
    {
      "service": "harmony",
      "pattern_id": "S1",
      "available": true,
      "supports": {
        "spatial": true,
        "temporal": true,
        "variable": true
      },
      "output_formats": ["netcdf4"],
      "endpoint": "https://harmony.earthdata.nasa.gov"
    },
    {
      "service": "opendap",
      "pattern_id": "S2",
      "available": true,
      "endpoint": "https://opendap.earthdata.nasa.gov"
    },
    {
      "service": "virtual_zarr",
      "pattern_id": "C1",
      "available": false,
      "reason": "chunk_aligned = false"
    }
  ],

  "recommended_patterns": ["S1", "S2"],
  "compatible_tools": ["xarray", "netCDF4", "harmony-py"]
}
```

### 11.2 Required MCP Tools

| Tool | Purpose |
|---|---|
| `data_taxonomy.get_collection` | Returns full taxonomy including service availability |
| `data_taxonomy.get_virtualizability` | Returns virtualizability grade and evidence |
| `data_taxonomy.get_services` | Returns available access services |
| `data_taxonomy.recommend_patterns` | Returns recommended patterns for a given requirement |
| `earthaccess_core.search_services` | CMR service discovery |
| `earthaccess_core.search_granules` | Granule discovery with spatial/temporal filters |

---

## 12. Evaluation Architecture

```text
                         Access Requirement
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
              Service Discovery + Pattern Selection
                              |
                +-------------+-------------+
                v             v             v
           Collection     Access Pattern   Representation
           Selection      Selection        Selection
                |             |             |
                +-------------+-------------+
                              |
                              v
                    Minimal Validation Output
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

---

## 13. Verifier Output

```json
{
  "reward": 0.86,

  "collection_selection": 1.0,
  "service_discovery": 0.75,
  "access_pattern": 0.85,
  "representation": 1.0,
  "efficiency": 0.82,
  "validation": 1.0,

  "access_pattern_details": {
    "observed_pattern": "S1",
    "pattern_name": "Harmony subsetting",
    "available_patterns": ["C1", "S1", "S2", "M1"],
    "best_available": "C1",
    "acceptable_patterns": ["S1", "S2"],
    "gap_reason": "Agent used Harmony instead of virtual Zarr"
  },

  "service_discovery_details": {
    "discovered": ["harmony", "opendap"],
    "available": ["virtual_zarr", "harmony", "opendap"],
    "not_discovered": ["virtual_zarr"],
    "discovery_rate": 0.67
  },

  "validation": {
    "variable_present": true,
    "spatial_extent_correct": true,
    "temporal_extent_correct": true,
    "units_correct": true,
    "passed": true
  },

  "efficiency_metrics": {
    "bytes_read": 118000000,
    "objects_read": 5,
    "runtime_seconds": 240,
    "pattern_envelope": "S1",
    "data_reduction": 4.2,
    "object_reduction": 10.0
  },

  "trajectory_metrics": {
    "tool_calls": 22,
    "mcp_calls": 15,
    "failed_attempts": 1,
    "recovery_attempts": 1
  }
}
```

---

## 14. Pilot Experiment

### 14.1 Pilot Tasks

| Task | Primary Pattern | Challenge |
|---|---|---|
| A1 — TEMPO NO₂ | `C1` | Virtual Zarr available but must be discovered |
| A3 — MODIS MAIAC AOD | `S1` | Virtual Zarr unavailable; Harmony is best |
| C1 — ITS_LIVE | `C1` | Virtual Zarr vs. GeoTIFF confusion |

### 14.2 Pilot Configuration

```text
3 tasks
× 6 models
× 4 harnesses
× 4 conditions
× 2 trials
= 576 pilot executions
```

### 14.3 Pilot Evaluates

- Benchmark validity
- Agent stability
- MCP functionality
- Skills functionality
- Harbor integration
- Golden test reliability
- Service discovery classification accuracy
- Access pattern classification accuracy
- Virtualizability oracle integration
- Harmony / OPeNDAP availability integration
- Runtime
- Local inference behavior
- Claude API cost
- Earthdata access reproducibility

---

## 15. Full Experiment

### 15.1 Configuration

```text
6 models
× 4 harnesses
× 4 conditions
× 18 tasks
× 5 trials
= 8,640 task executions
```

### 15.2 Experimental Conditions

| Condition | Earthdata MCP | Earthdata Skills | Purpose |
|---|---:|---:|---|
| Baseline | No | No | Measure ordinary agent capability |
| MCP only | Yes | No | Measure structured operational knowledge |
| Skills only | No | Yes | Measure procedural/domain guidance |
| MCP + Skills | Yes | Yes | Measure combined effect |

---

## 16. Result Tables

### 16.1 Overall Condition Comparison

| Knowledge condition | Overall | Collection | Service Discovery | Access Pattern | Representation | Efficiency | Validation |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | ... | ... | ... | ... | ... | ... | ... |
| MCP only | ... | ... | ... | ... | ... | ... | ... |
| Skills only | ... | ... | ... | ... | ... | ... | ... |
| MCP + Skills | ... | ... | ... | ... | ... | ... | ... |

### 16.2 Access Pattern Distribution

| Condition | C1 | C2 | C3 | S1 | S2 | S3 | S4 | S5 | T1 | T2 | F1-F4 | M1 | M2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |
| MCP only | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |
| Skills only | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |
| MCP + Skills | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

### 16.3 Efficiency by Pattern

| Condition | Median bytes | Median objects | Median runtime | Data reduction |
|---|---:|---:|---:|---:|
| Baseline | ... | ... | ... | 1.0x |
| MCP only | ... | ... | ... | ... |
| Skills only | ... | ... | ... | ... |
| MCP + Skills | ... | ... | ... | ... |

### 16.4 Failure Mode Breakdown

| Failure type | Baseline | MCP | Skills | MCP + Skills |
|---|---:|---:|---:|---:|
| Collection selection failure | ... | ... | ... | ... |
| Service discovery failure | ... | ... | ... | ... |
| Access pattern failure | ... | ... | ... | ... |
| Validation failure | ... | ... | ... | ... |

### 16.5 Service Discovery Breakdown

| Condition | Virtual Zarr discovered | Harmony discovered | OPeNDAP discovered | AppEEARS discovered | Giovanni discovered |
|---|---:|---:|---:|---:|---:|
| Baseline | ... | ... | ... | ... | ... |
| MCP only | ... | ... | ... | ... | ... |
| Skills only | ... | ... | ... | ... | ... |
| MCP + Skills | ... | ... | ... | ... | ... |

---

## 17. Repository Structure

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
│   │   ├── collection.py
│   │   ├── service_discovery.py
│   │   ├── access_pattern.py
│   │   ├── representation.py
│   │   ├── efficiency.py
│   │   └── aggregate.py
│   ├── oracles/
│   │   ├── virtualizability.py
│   │   ├── services.py
│   │   ├── daac_docs.py
│   │   ├── live_probes.py
│   │   └── service_matrix.py
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
│   ├── access-patterns.md
│   ├── service-matrix.md
│   ├── virtualizability.md
│   ├── evaluation.md
│   ├── skills.md
│   └── operations.md
│
└── results/
    └── README.md
```

---

## 18. Integration with EarthDataVirtualizabilityScore

### 18.1 Oracle Integration

```python
# benchmark/oracles/virtualizability.py

import pandas as pd
from pathlib import Path

class VirtualizabilityOracle:
    """
    Interface to the EarthDataVirtualizabilityScore dataset.
    Provides ground-truth virtualizability information.
    """

    def __init__(self, scores_path: Path):
        self.scores = pd.read_csv(scores_path)

    def get_grade(self, collection_id: str) -> str:
        row = self.scores[self.scores['collection_id'] == collection_id]
        if row.empty:
            return None
        return row.iloc[0]['grade']

    def is_virtualizable(self, collection_id: str) -> bool:
        grade = self.get_grade(collection_id)
        return grade in ('A', 'B')

    def get_blocker(self, collection_id: str) -> str:
        row = self.scores[self.scores['collection_id'] == collection_id]
        if row.empty:
            return None
        return row.iloc[0]['deciding_criterion']

    def get_evidence(self, collection_id: str) -> dict:
        row = self.scores[self.scores['collection_id'] == collection_id]
        if row.empty:
            return {}
        return {
            'parser_readable': row.iloc[0]['parser_readable'],
            'consolidated_md': row.iloc[0]['consolidated_md'],
            'grid_aligned': row.iloc[0]['grid_aligned'],
            'chunk_aligned': row.iloc[0]['chunk_aligned'],
            'time_dim': row.iloc[0]['time_dim'],
            'chunk_shape': row.iloc[0]['chunk_shape'],
            'chunk_mb': row.iloc[0]['chunk_mb'],
            'dmrpp_available': row.iloc[0]['dmrpp_available'],
        }
```

### 18.2 CMR Service Metadata Integration

```python
# benchmark/oracles/services.py

class CMRServiceOracle:
    """
    Queries CMR for service associations per collection.
    """

    def get_services(self, collection_id: str) -> dict:
        response = cmr_query(
            f"/search/services.umm_json"
            f"?collection_concept_id={collection_id}"
        )

        services = {}
        for item in response['items']:
            service_type = item['umm']['Type']
            services[service_type] = {
                'available': True,
                'service_id': item['meta']['concept-id'],
                'endpoint': item['umm'].get('URL', {}).get('URLValue'),
            }
        return services
```

### 18.3 Combined Service Matrix

```python
# benchmark/oracles/service_matrix.py

class ServiceAvailabilityMatrix:
    """
    Combines virtualizability, CMR services, DAAC docs, and live probes
    into a single service availability matrix per collection.
    """

    def __init__(self, virtualizability, cmr_services, daac_docs, live_probes):
        self.virt = virtualizability
        self.cmr = cmr_services
        self.docs = daac_docs
        self.probes = live_probes

    def get_matrix(self, collection_id: str) -> dict:
        return {
            'virtual_zarr': self._virtual_zarr_entry(collection_id),
            'native_zarr': self._native_zarr_entry(collection_id),
            'cog': self._cog_entry(collection_id),
            'harmony': self._harmony_entry(collection_id),
            'opendap': self._opendap_entry(collection_id),
            'opendap_cloud': self._dmrpp_entry(collection_id),
            'appeeares': self._appeeares_entry(collection_id),
            'giovanni': self._giovanni_entry(collection_id),
            'filtered_download': self._filtered_entry(collection_id),
            'full_download': {'available': True},
        }

    def best_patterns_for(self, collection_id: str, requirement: dict) -> list:
        matrix = self.get_matrix(collection_id)
        candidates = []

        for pattern_id, entry in PATTERN_MAP.items():
            if not matrix.get(entry['service'], {}).get('available'):
                continue
            if not self._satisfies_requirement(entry, requirement):
                continue
            candidates.append({
                'pattern': pattern_id,
                'expected_bytes': entry['expected_bytes'],
            })

        candidates.sort(key=lambda c: c['expected_bytes'])
        return [c['pattern'] for c in candidates]
```

---

## 19. Timeline

### Months 1–2: Planning and Requirements
- Finalize access pattern taxonomy
- Integrate EarthDataVirtualizabilityScore
- Integrate CMR service metadata
- Define task schemas
- Establish representative workflows per discipline
- Define golden-test framework
- Establish Harbor integration approach

### Months 2–3: Core MCP
- Implement FastMCP server
- Authentication
- Earthdata core tools
- Initial taxonomy with service availability integration
- Related-science capability
- Initial documentation

### Months 4–7: Access Optimization
- Expand data taxonomy
- Implement service availability matrix
- Integrate access pattern classification
- Develop skills focused on access patterns
- Build benchmark tasks
- Implement access instrumentation

### Months 7–9: Evaluation
- Complete golden tests
- Validate Oracle solutions
- Run pilot
- Finalize models/harnesses
- Run full benchmark
- Statistical analysis

### Months 9–12: Release and Dissemination
- Public release
- Benchmark documentation
- Examples
- Community hackathon
- Final evaluation report
- Technical demonstration
- Recommendations for operational adoption

---

## 20. Deliverables

1. Public `earthaccess-mcp` GitHub repository.
2. Functional MCP server with `data_taxonomy` capability.
3. Authentication capability.
4. Related-science capability.
5. Earthdata core operations.
6. Reusable Earthdata skills focused on access patterns.
7. **18-task multi-pattern access benchmark** (grounded in representative workflows).
8. Golden standards for every task (access pattern focused).
9. **Integration with EarthDataVirtualizabilityScore** as one oracle.
10. **Integration with CMR service metadata** as a second oracle.
11. **Live service probes** as a third oracle.
12. **Combined service availability matrix**.
13. Programmatic golden tests for service discovery and access pattern classification.
14. Harbor-compatible task environments.
15. Automated scoring with revised weights.
16. Efficiency instrumentation per pattern.
17. Pilot evaluation.
18. Full multi-model evaluation.
19. Public benchmark documentation.
20. Example notebooks demonstrating access pattern selection.
21. Public evaluation results.
22. One-day community hackathon.
23. Final technical report.
24. Public benchmark and evaluation methodology for reuse by other ESDS projects.

---

## 21. Core Evaluation Principle

The project ultimately answers one concrete question:

> **When an AI agent is asked to access a NASA Earthdata collection, does giving it operational knowledge about available access services and their byte-level characteristics cause it to select a more efficient access pattern?**

A "better access pattern" means:

```text
Correct collection
        +
Best available service discovered
        +
Best available pattern selected
        +
Correct representation
        +
Minimal data transfer
        +
Reproducible workflow
```

The MCP is the intervention.

The skills are a complementary intervention.

The **service availability matrix** (combining EarthDataVirtualizabilityScore, CMR service metadata, DAAC docs, and live probes) is the ground-truth oracle.

The models and harnesses are experimental factors.

The **18 access scenarios** are the workload.

The golden tests establish objective service discovery and access pattern correctness.

Harbor provides the controlled execution environment.

The resulting benchmark provides the evidence for whether `earthaccess-mcp` delivers measurable value by improving service discovery and access pattern selection—across virtualization, subsetting, streaming, and filtered download.
