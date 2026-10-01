---
name: data-access-patterns
description: Select and execute the best available NASA Earthdata access pattern for a collection and a bounded requirement (bbox/time/variables). Use whenever searching, subsetting, streaming, virtualizing, or downloading NASA Earthdata, to avoid unnecessary full-granule downloads and to justify the access choice. Core skill of the Earthdata set.
---

# NASA Earthdata Access Patterns

The access pattern you choose usually matters more than the analysis code. A regional
monthly mean can cost 40 MB through the right pattern or 500 GB through the wrong one.
Never default to downloading whole granules.

## Procedure

1. **Pin the requirement.** Collection candidates, bbox (W,S,E,N), time window, variable
   names, output artifact. Everything downstream is decided by this.
2. **Discover the services** for the candidate collection before writing access code:
   - CMR service associations (`RelatedUrls` with `GET/USE SERVICE API`, or the
     collection feed's `has_transforms` flag → Harmony-enabled).
   - OPeNDAP / DMR++ availability (cloud-hosted collections often publish DMR++ sidecars).
   - AppEEARS (LP DAAC point/area sampling), Giovanni (atmospheric composition).
   - Native Zarr endpoints published by projects (e.g. ITS_LIVE datacubes).
3. **Check virtualizability.** The EarthDataVirtualizabilityScore grades collections on
   whether their archive can be opened as a lazy virtual Zarr datacube without copying
   bytes. Grade `A`/`B` → virtualization is the best pattern (see the
   `data-virtualization` skill). Grade `C`/`D` → blocked; the recorded deciding
   criterion tells you why (usually chunk misalignment across granules).
4. **Pick from the ladder, top-down** (first available that satisfies the requirement):

| Priority | Pattern | How |
|---:|---|---|
| 1 | Virtual Zarr via `earthaccess.virtualize` | lazy datacube over the archive (needs grade A/B) |
| 2 | Native Zarr store | open directly with xarray |
| 3 | OPeNDAP in the cloud (DMR++) | ranged reads via pydap/netCDF4 |
| 4 | OPeNDAP (Hyrax) | server-side slicing |
| 5 | Harmony subsetting | async server-side subset (bbox/time/variables) |
| 6 | AppEEARS / Giovanni | point sampling / pre-aggregated products |
| 7 | Filtered download | granule-list filtering (bbox/time/QA metadata) before downloading |
| 8 | Full granule download | last resort; never the archive |

5. **Subset before you compute.** Whatever the pattern: apply the spatial/temporal/variable
   selection at access time, then compute (see the `earthdata-streaming-vs-download` and
   `xarray` skills).
6. **Justify and record.** State which pattern you used, which services you found, and
   roughly how many bytes it should move. If you cannot name the pattern you used, you
   probably used the worst one.

## Anti-patterns

- Downloading all granules "to be safe" when a subsetting service exists.
- Attempting virtualization on a collection whose grade is C/D.
- Reading every variable when the analysis needs one (e.g. MUR `analysed_sst`, not the
  misaligned `dt_1km_data`).
- Ignoring granule metadata filters (bbox, cloud cover, QA) before transfer.
- Confusing product levels (L2 vs L3) or column types (total vs tropospheric) — access
  correctness includes picking the right collection, not just the right bytes.

## Quick signals

- Collection feed `has_transforms: true` → Harmony available.
- DMR++ sidecars → ranged OPeNDAP reads without a Hyrax server.
- GES DISC / PODAAC / NSIDC / LP DAAC / ASF cloud-hosted → likely Harmony or OPeNDAP.
- HDF4 / HDF-EOS2 → not streamable natively; needs a service, GDAL VSI, or virtualization.
