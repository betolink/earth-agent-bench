You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas (pip install more if needed).

Question:
EMIT L2A Reflectance (short_name EMITL2ARFL) granules are cloud-hosted NetCDF files. You want to combine 30 granules into a single logical xarray.Dataset and analyze them without persisting any files. Which single earthaccess function should you call?

Express your answer as a single short label (one of: open, download, virtualize).

Write only that value to ./output/answer.txt, then stop.
