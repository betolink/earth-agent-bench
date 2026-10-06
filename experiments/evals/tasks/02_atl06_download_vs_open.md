You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas (pip install more if needed).

Question:
ICESat-2 ATL06 granules are HDF5 point/vector observations (land-ice height profiles). You must place the actual granule files on the local filesystem so a legacy command-line tool (which reads HDF5 files from disk paths) can process them. Which single earthaccess function should you call: open, download, or virtualize?

Work it out step by step — reason about what each function does (`download` retrieves and persists files to a local path, `open` returns in-memory file-like objects, `virtualize` builds an xarray virtual dataset that references remote bytes), then pick the one that satisfies the "files on disk" requirement.

Express your answer as a single short label (one of: open, download, virtualize).

Answer with a single clean value: a bare number (no commas or units), a short label, yes/no, or a comma-separated list. Keep decimal precision. If there's no applicable answer, write: Not Applicable

Write only that value to ./output/answer.txt (e.g. `echo -n "<value>" > ./output/answer.txt`), then stop.
