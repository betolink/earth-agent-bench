You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas (pip install more if needed).

Question:
Using earthaccess, find the HLS Sentinel-2 Surface Reflectance collection (short_name HLSS30) and report its collection concept-id (a value of the form C##########-LPCLOUD).

Work it out step by step — call earthaccess.search_datasets(short_name="HLSS30") and read the concept-id from the returned DataCollection (e.g. via the `concept_id` property or the `meta.concept-id` field), then report that exact identifier.

Express your answer as a single short label (the exact concept-id string).

Answer with a single clean value: a bare number (no commas or units), a short label, yes/no, or a comma-separated list. Keep decimal precision. If there's no applicable answer, write: Not Applicable

Write only that value to ./output/answer.txt (e.g. `echo -n "<value>" > ./output/answer.txt`), then stop.
