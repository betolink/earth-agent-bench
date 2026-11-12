You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas (pip install more if needed).

Question:
ICESat-2 ATL06 granules are HDF5 point/vector observations (land-ice height profiles). You must place the actual granule files on the local filesystem so a legacy command-line tool (which reads HDF5 files from disk paths) can process them. Which single earthaccess function should you call to persist those files to disk?

Express your answer as a single short label (one of: open, download, virtualize).

Write only that value to ./output/answer.txt, then stop.
