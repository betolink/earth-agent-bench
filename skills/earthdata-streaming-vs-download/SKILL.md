---
name: earthdata-streaming-vs-download
description: Stream NASA Earthdata into memory with earthaccess.open() instead of downloading whole files, and know when downloading is still the right call. Use when accessing granules over HTTPS/S3, especially from laptops or out-of-region compute. Adapted from the NSIDC "Streaming NASA Earth Data with earthaccess" webinar.
---

# Streaming vs. Downloading NASA Earthdata

> **Out-of-region execution — use HTTPS, never S3.** This benchmark runs **outside AWS**
> (not in `us-west-2`). Direct **S3 access will never work here**: `s3://…` /
> `*.s3.amazonaws.com` endpoints, `s3_credentials`, `fs.s3`/`s3fs`, and
> `earthaccess.open()`-returned S3 URLs all hang or 403 out of region. Always resolve and
> use the **HTTPS** URL (`https://…` object URL, or the value returned by
> `open()`/`download()` out-of-region, which is HTTPS). If you see an S3 URL, do **not**
> try to read it directly — re-resolve to HTTPS or fall back to `earthaccess.download()`
> over HTTPS.

> **Discover through `earthaccess`, not raw CMR.** Given a DOI / `concept_id` /
> `short_name`, resolve granules, links and services with `earthaccess`
> (`search_data`, `search_services`) — **not** `https://cmr.earthdata.nasa.gov/…`
> via `requests`/`curl`. Results translate cleanly to **STAC items** when you need
> another ecosystem (e.g. `odc-stac`).

Both paths start the same: `earthaccess.search_data()` (metadata only), URL resolution
(S3 in-cloud or HTTPS out-of-cloud), authenticated connection. The difference is what
happens after the connection opens:

| | `earthaccess.download()` | `earthaccess.open()` |
|---|---|---|
| What happens | entire file bytes → local disk | `fsspec` file handles read lazily |
| Bytes land | local disk, full copy | RAM, only requested bytes |
| Bytes move | all at once, up front | on demand, in cached blocks |
| Disk footprint | one full copy per file | ~none |

Streaming is **not** "no data movement" — it moves only the bytes the analysis asks for,
lazily.

## Minimal streaming workflow (MERRA-2 example)

```python
import earthaccess, xarray as xr

earthaccess.login()  # required before search, download AND streaming

results = earthaccess.search_data(
    short_name="M2T1NXSLV", temporal=("2023-07-01", "2023-07-02")
)
files = earthaccess.open(results)                    # fast: metadata only
ds = xr.open_mfdataset(files, engine="h5netcdf")     # lazy
t2m = ds["T2M"].sel(lat=slice(37, 41), lon=slice(-110, -102)).mean("time").compute()
```

The `.sel()` subset happens **before** `.compute()` — only the T2M bytes for the region
are fetched. `open()` was fast because no science bytes moved yet.

## How the bytes actually move

`fsspec` does not issue one request per read: it fetches and caches fixed-size blocks
(earthaccess picks 4/8/16 MB adaptively from file size; overridable via `open_kwargs`).
Small reads pull a whole block; subsequent reads in the same block are free. This is
why streaming is competitive whenever you need less than the whole file.

## Choose streaming when

- running in-region on AWS (especially `us-west-2`): treat S3 as your hard drive;
- you need a subset (few variables, a region, some timesteps) of big granules;
- exploring before committing to a download;
- building virtual/aggregate datasets (VirtualiZarr/kerchunk) — you want range reads
  against the originals, not local copies.

## Choose downloading when

- outside AWS with repeated small reads (public-internet latency/TLS overhead adds up);
- you need whole files repeatedly and have the disk;
- the tool only accepts local paths, or the reader cannot stream the format;
- you need guaranteed offline/reproducible local access.

## Format support decides everything

- **Streamable (file-like objects work):** HDF5/NetCDF4 via `engine="h5netcdf"` (not
  `netCDF4`), Zarr, kerchunk references, NetCDF3 (scipy), OPeNDAP (query protocol),
  COG/GeoTIFF (GDAL `/vsicurl/`), Parquet (row-group/column reads).
- **Not streamable natively:** HDF4/HDF-EOS2 (no virtual file driver in the C library —
  use GDAL VSI, a service, or virtualization), GRIB (eccodes needs a real path),
  compressed Zip members, the `netCDF4` engine itself.

When a format is not streamable, virtualization (see the `data-virtualization` skill)
is often the workaround: chunk references bypass the native drivers entirely.

Source: NSIDC-Data-Tutorials `notebooks/streaming/earthaccess_streaming_webinar.ipynb`
(Barrett & López, NASA Earthdata webinar, Aug 2026).
