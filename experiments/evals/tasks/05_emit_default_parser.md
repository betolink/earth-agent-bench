You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas (pip install more if needed).

Question:
When you call earthaccess.virtualize() (or open_virtual_dataset) on an EMIT L2A Reflectance granule, earthaccess selects a VirtualiZarr parser backend automatically. EMITL2ARFL granules ship with pre-computed DMR++ sidecar files. What is the name of the default parser earthaccess uses in this situation?

Work it out step by step — inspect the earthaccess.virtualize / open_virtual_dataset documentation for the `parser` parameter's default value and how it relates to DMR++ sidecars, then state the exact default parser name.

Express your answer as a single short label (the exact parser class name, e.g. the default parser string).

Answer with a single clean value: a bare number (no commas or units), a short label, yes/no, or a comma-separated list. Keep decimal precision. If there's no applicable answer, write: Not Applicable

Write only that value to ./output/answer.txt (e.g. `echo -n "<value>" > ./output/answer.txt`), then stop.
