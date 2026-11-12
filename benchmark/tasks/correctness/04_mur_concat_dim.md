You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas (pip install more if needed).

Question:
You want to stack 5 daily MUR-JPL-L4-GLOB-v4.1 granules into a single virtual xarray.Dataset using earthaccess virtualize with the default "nested" combine. What value must you pass to the concat_dim parameter so the granules are concatenated along their shared temporal coordinate?

Express your answer as a single short label (the exact dimension name).

Write only that value to ./output/answer.txt, then stop.
