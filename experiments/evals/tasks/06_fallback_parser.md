You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas (pip install more if needed).

Question:
A granule's collection does not provide DMR++ sidecar files, so earthaccess cannot use the DMRPPParser. According to the earthaccess.virtualize documentation, which parser does earthaccess automatically fall back to (while also emitting a UserWarning) when the pre-computed DMR++ sidecars are absent?

Work it out step by step — read the earthaccess.virtualize docstring for the `parser` parameter and the described automatic fallback behavior, then state the exact fallback parser name.

Express your answer as a single short label (the exact fallback parser class name).

Answer with a single clean value: a bare number (no commas or units), a short label, yes/no, or a comma-separated list. Keep decimal precision. If there's no applicable answer, write: Not Applicable

Write only that value to ./output/answer.txt (e.g. `echo -n "<value>" > ./output/answer.txt`), then stop.
