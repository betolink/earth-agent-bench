You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas (pip install more if needed).

Question:
Is the MUR-JPL-L4-GLOB-v4.1 collection cloud-hosted (i.e. does it have data in the NASA Earthdata Cloud with direct S3 access)? Answer yes or no.

Work it out step by step — call earthaccess.search_datasets(short_name="MUR-JPL-L4-GLOB-v4.1", cloud_hosted=True) and confirm whether a matching collection is returned (inspect the `cloud_hosted` property or the result count), then answer yes or no.

Express your answer as yes or no.

Answer with a single clean value: a bare number (no commas or units), a short label, yes/no, or a comma-separated list. Keep decimal precision. If there's no applicable answer, write: Not Applicable

Write only that value to ./output/answer.txt (e.g. `echo -n "<value>" > ./output/answer.txt`), then stop.
