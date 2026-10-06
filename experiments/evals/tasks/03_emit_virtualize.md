You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas (pip install more if needed).

Question:
EMIT L2A Reflectance (short_name EMITL2ARFL) granules are cloud-hosted NetCDF files. You want to combine 30 granules into a single logical xarray.Dataset and analyze them without downloading any files. Which single earthaccess function should you call: open, download, or virtualize?

Work it out step by step — reason about what each function does (`virtualize` builds a VirtualiZarr xarray.Dataset whose variables reference remote bytes, `open` returns a list of separate file-like objects, `download` writes files to disk), then pick the one that yields one logical dataset across many granules with no local storage.

Express your answer as a single short label (one of: open, download, virtualize).

Answer with a single clean value: a bare number (no commas or units), a short label, yes/no, or a comma-separated list. Keep decimal precision. If there's no applicable answer, write: Not Applicable

Write only that value to ./output/answer.txt (e.g. `echo -n "<value>" > ./output/answer.txt`), then stop.
