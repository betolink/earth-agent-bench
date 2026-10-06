You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas (pip install more if needed).

Question:
When earthaccess.virtualize() is called on an EMIT L2A Reflectance (EMITL2ARFL) granule, earthaccess selects a VirtualiZarr parser backend automatically. What is the name of the default parser earthaccess uses for this granule?

Express your answer as a single short label (the exact parser class name).

Write only that value to ./output/answer.txt, then stop.
