---
name: xarray
description: Work with N-dimensional labeled Earthdata arrays (NetCDF/Zarr/GRIB) — open remote datasets lazily, subset before computing, resample/group, and write artifacts. Use for any gridded Earthdata analysis. Adapted from tondevrel/scientific-agent-skills.
---

# Xarray for Earthdata access and analysis

Xarray is the lingua franca of NASA Earthdata analysis: pandas-like labeled arrays for
`time/lat/lon/level`, with lazy Dask backing for larger-than-memory work.

## When to use

- Multi-dimensional scientific data (time, lat, lon, level, ensemble).
- NetCDF/HDF5, Zarr, GRIB, or remote (OPeNDAP/fsspec/virtual Zarr) sources.
- Broadcast/align by dimension name instead of axis index.
- Keep units and metadata attached to the data.

## Opening data — match the engine to the source

```python
xr.open_mfdataset(files, engine="h5netcdf")   # remote/streamed HDF5-NetCDF4: MUST be h5netcdf
xr.open_zarr(store)                           # native or virtual zarr
xr.open_dataset(url + "#mode=bytes", engine="netcdf4")  # OPeNDAP via netCDF4
```

The `netCDF4` engine cannot read fsspec file objects — remote NetCDF4 must use
`h5netcdf`.

## Subset before you compute

```python
da = ds["analysed_sst"].sel(
    time=slice("2023-12-01", "2024-03-31"),
    lat=slice(-25, -8), lon=slice(142, 155),
)
result = da.mean("time").compute()
```

Order matters: `.sel`/`.isel` and variable selection build a lazy view; `.compute()`
(or `.load()`, `.plot()`, `.to_netcdf()`) is when bytes actually move. Selecting the
variable and region first can reduce transfer by orders of magnitude.

## Common operations

- `ds.groupby("time.month").mean()` — climatology/monthly means.
- `ds.resample(time="MS").mean()` — calendar-aware aggregation.
- `ds.where(qa_flag == 0)` — quality masking before aggregation.
- `xr.concat(..., dim="time")` — combine granules (virtualization does this for you).
- Scale factors/offsets in attributes are applied automatically — check `ds[var].attrs`
  and `encoding` before inventing unit conversions.

## Writing artifacts

`ds.to_netcdf(path)`, `ds.to_zarr(store)`. Write the **computed, subset result**, never
a copy of the raw remote data.

## Reference

- Docs: https://docs.xarray.dev/ · tutorial: https://tutorial.xarray.dev/
- Search patterns: `xr.DataArray`, `xr.Dataset`, `ds.sel`, `ds.groupby`, `ds.resample`,
  `xr.open_dataset`, `xr.open_zarr`

Adapted from tondevrel/scientific-agent-skills (`xarray` skill).
