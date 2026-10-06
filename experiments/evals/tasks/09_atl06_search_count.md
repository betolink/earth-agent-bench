You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas (pip install more if needed).

Question:
Using earthaccess, search for ICESat-2 ATL06 granules over the McMurdo Dry Valleys region of Antarctica for July 2019. The region is defined by bounding_box=(160.0, -78.0, 164.0, -76.0) and the window by temporal=("2019-07-01","2019-07-31"). How many granules does the search return? Report the total number of matches.

Express your answer as a single integer (bare number, no commas or units).

Write only that value to ./output/answer.txt, then stop.
