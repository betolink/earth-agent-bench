---
name: data-virtualization
description: Create or open lazy virtual Zarr datacubes over NASA Earthdata archives with earthaccess.virtualize / write_virtual / open_virtual (VirtualiZarr ManifestArrays underneath, Icechunk persistence) without duplicating bytes. Use when a collection's archive needs repeated lazy, dimensioned access (time series, regional subsets) and its virtualizability grade is A or B.
---

# Data Virtualization (virtual Zarr over Earthdata archives)

Virtualization presents an archive of granules as **one lazy Zarr datacube** without
copying data: a reference manifest maps every chunk of the logical array to a
`(url, offset, length)` triple inside the original files. Reads become HTTP range
requests; nothing is rewritten; no server sits in the middle.

## When it is possible

Virtualizability is decided at **write time** by the archive, not by tooling. The
EarthDataVirtualizabilityScore measures it per collection by opening granules:

| Grade | Meaning | Action |
|---|---|---|
| A | no blocker | virtualize; best pattern |
| B | repairable blockers (time dim to add, some arrays unstable across granules) | virtualize over the stable variables; store build adds the time axis |
| C / D | blocked (typically chunk shapes differ across granules) | do NOT attempt; use OPeNDAP/Harmony instead; the deciding criterion names the blocker |

Common blockers: `chunk_aligned = false` (swath-length variation breaks chunk
concatenation), no time dimension declared, one array absent from some granules,
mismatched units across granules.

## How to do it

Build → persist → reopen → extend, all without copying bytes:

```python
import earthaccess

earthaccess.login()

granules = earthaccess.search_data(
    short_name="MUR-JPL-L4-GLOB-v4.1",           # or concept_id="C1996881146-POCLOUD"
    temporal=("2013-01-02", "2013-01-31"),
)

vds = earthaccess.virtualize(granules, concat_dim="time", access="indirect", load=False)
# vds variables are ManifestArrays: logical arrays whose chunks reference
# (url, offset, length) triples inside the original granules.

earthaccess.write_virtual(vds, "mur_sst", format="icechunk")   # persist the references

ds = earthaccess.open_virtual("mur_sst")       # reopen; EDL auth applied to chunk containers
region = ds["analysed_sst"].sel(lat=slice(-25, -8), lon=slice(142, 155)).mean("time").compute()
```

Extending the cube incrementally (e.g. new month arrives):

```python
delta = earthaccess.virtualize(new_granules, concat_dim="time", access="indirect", load=False)
earthaccess.write_virtual(delta, "mur_sst", format="icechunk", append_dim="time")
```

Notes:

- `access="indirect"` reads over HTTPS from anywhere; `"direct"` uses S3 URLs
  (in-region compute). `load=False` keeps reference building lazy.
- `write_virtual(..., format="icechunk")` persists to an Icechunk store; a kerchunk
  reference file is the alternative format.
- `open_virtual(store)` re-authorizes the virtual chunk containers with your EDL
  credentials automatically.
- Manual equivalent: `virtualizarr.open_virtual_dataset(...)` per granule + concat,
  or kerchunk references — same pattern, more code.

## When NOT to virtualize

- The collection's grade is C/D or unknown-but-unverified.
- You need one value from one granule — just stream it (see the
  `earthdata-streaming-vs-download` skill).
- The source format has no parser (HDF4 without GDAL VSI, GRIB without caching) — the
  reference generator will refuse, and that refusal is the measurement.
- Point/tabular collections — use Parquet-style access instead.

## Variable-level awareness

Grade B often means "a cube exists over the *stable* variables". Example: MUR SST —
`analysed_sst` chunks identically across granules (cube-able) while `dt_1km_data` does
not. Virtualize the variable you need, not the whole file list blindly.

Source: earthaccess-gallery `notebooks/virtual-datasets/icechunk_virtual.ipynb`
(kerchunk sibling: `virtual_data.ipynb`).
