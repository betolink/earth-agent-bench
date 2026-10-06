You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas (pip install more if needed).

Question:
You want to stack 5 daily MUR-JPL-L4-GLOB-v4.1 granules into a single virtual xarray.Dataset along the time dimension using earthaccess.open_virtual_mfdataset (or virtualize) with the default "nested" combine. What value must you pass to the concat_dim parameter so the granules are concatenated along their shared temporal coordinate?

Work it out step by step — inspect the earthaccess virtualize/open_virtual_mfdataset signature and the MUR dataset's coordinate names (the daily dimension is named "time"), then state the exact string for concat_dim.

Express your answer as a single short label (the exact dimension name).

Answer with a single clean value: a bare number (no commas or units), a short label, yes/no, or a comma-separated list. Keep decimal precision. If there's no applicable answer, write: Not Applicable

Write only that value to ./output/answer.txt (e.g. `echo -n "<value>" > ./output/answer.txt`), then stop.
