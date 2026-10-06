You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas (pip install more if needed).

Question:
You are running a Jupyter notebook inside the AWS us-west-2 region and have cloud-hosted granules from earthaccess.search_data(). You want the S3:// object URLs for direct access. When calling `granule.data_links(...)`, which single access value should you pass to get those S3 links: "direct" or "external"?

Work it out step by step — recall the earthaccess.data_links documentation: `access="direct"` returns S3 links (usable only in AWS us-west-2), `access="external"` returns HTTPS links for on-premises archives. Given you are in us-west-2 and want S3 URLs, pick the matching value.

Express your answer as a single short label (one of: direct, external).

Answer with a single clean value: a bare number (no commas or units), a short label, yes/no, or a comma-separated list. Keep decimal precision. If there's no applicable answer, write: Not Applicable

Write only that value to ./output/answer.txt (e.g. `echo -n "<value>" > ./output/answer.txt`), then stop.
