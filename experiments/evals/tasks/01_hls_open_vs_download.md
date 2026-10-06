You are a data-analysis agent working in a sandbox. Use your code-execution tool to inspect the data and compute the answer.

Files (in /home/user/input, no subfolders): none — this task queries NASA Earthdata cloud-hosted data remotely. Earthdata Login credentials are pre-configured (EARTHDATA_USERNAME / EARTHDATA_PASSWORD environment variables or ~/.netrc).

Installed: earthaccess (with virtualizarr, stac, geo extras), xarray, dask, numpy, pandas, matplotlib, fsspec, s3fs, requests, h5py, h5netcdf, netCDF4, kerchunk, zarr, icechunk, shapely, geopandas, rioxarray (pip install more if needed).

Question:
HLS (HLSS30) granules are cloud-hosted Cloud-Optimized GeoTIFF files. You want to compute a band statistic for a single HLSS30 granule in memory, without writing any file to disk. Which single earthaccess function should you call to obtain file-like objects for that granule: open, download, or virtualize?

Work it out step by step — reason about what each function does (`open` streams file-like objects via fsspec, `download` writes files to a local path, `virtualize` builds a VirtualiZarr dataset for NetCDF/HDF/DMR++ sources), then pick the one that matches a cloud-native GeoTIFF read with no disk writes.

Express your answer as a single short label (one of: open, download, virtualize).

Answer with a single clean value: a bare number (no commas or units), a short label, yes/no, or a comma-separated list. Keep decimal precision. If there's no applicable answer, write: Not Applicable

Write only that value to ./output/answer.txt (e.g. `echo -n "<value>" > ./output/answer.txt`), then stop.
