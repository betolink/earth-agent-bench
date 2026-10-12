---
name: data-access-patterns
description: Pick and execute the best Earthdata access pattern for the GIVEN dataset. Use earthaccess (login() takes no args; NEVER raw CMR): grade A/B → virtualize; else Harmony → OPeNDAP → open(). Be decisive — one search, then access and write the artifact; do not loop or retry. Read this skill.
---

# NASA Earthdata Access Patterns

The access pattern you choose usually matters more than the analysis code. A regional
monthly mean can cost 40 MB through the right pattern or 500 GB through the wrong one.
Never default to downloading whole granules.

## Use earthaccess for everything (when you have a DOI, concept_id, or short_name)

If the dataset is identified by a **DOI, CMR `concept_id`, or `short_name`**, do
**all** of the following through `earthaccess` — never the raw CMR REST API:

- **Link / granule discovery** — `earthaccess.search_data(...)`; it resolves the
  EDL-authenticated HTTPS links for each granule.
- **Service discovery (OPeNDAP, Harmony)** — `earthaccess.search_services(...)`
  and the collection's services, before writing any access code.
- **Virtualization** — `earthaccess.virtualize(...)` (see `data-virtualization`).
- **I/O** — `earthaccess.open(...)` (stream) or `earthaccess.download(...)`.

Do **not** call `https://cmr.earthdata.nasa.gov/...` with raw `requests`/`curl`:
it bypasses EDL auth handling, is not recorded, and duplicates what `earthaccess`
already does. Pin the collection by its DOI / `concept_id` / `short_name`.

If you need the results in another ecosystem, the `earthaccess` results translate
cleanly to **STAC items** (e.g. for `odc-stac` / `stac` tooling) — build the items
from the `earthaccess` results rather than re-querying CMR by hand.

## Budget discipline (do this or you time out)

The budget is small and the model is slow — act, don't explore:

- **One** `earthaccess.search_data(...)` call, then work from those results.
  Never re-query CMR or re-list granules.
- Attempt **one** pattern; if it errors, fall back to the next (Harmony → OPeNDAP
  → `open()`). Do not retry the same call.
- Write the output artifact **before** polishing — a partial answer beats a timeout.
- Target a handful of tool calls, not dozens.

## Authentication (already provided — just call `login`)

`earthaccess.login()` with **no arguments** reads `EARTHDATA_TOKEN` from the
environment and authenticates. Pass **no arguments at all** — no `strategy=`
(the strategy is automatic), no `provider=` / `client_id=`. Do not call the CMR
`/api/users/token` endpoint and do not build a token by hand. Call it once before
`search_data` / `search_services` / `open` / `download`:

```python
import earthaccess
earthaccess.login()          # uses EARTHDATA_TOKEN; no username/password, no prompt
```

## Procedure

1. **Pin the requirement.** Collection candidates, bbox (W,S,E,N), time window, variable
   names, output artifact. Everything downstream is decided by this.
2. **Discover the services** with `earthaccess` before writing access code
   (`earthaccess.search_services(...)` plus the collection's `RelatedUrls`):
   - Harmony (`has_transforms` / a Harmony service → server-side subsetting).
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
| 3 | COG (cloud-optimized GeoTIFF) | range reads via rioxarray / GDAL |
| 4 | Harmony subsetting | async server-side subset (bbox/time/variables) |
| 5 | OPeNDAP in the cloud (DMR++) | ranged reads via pydap/netCDF4 |
| 6 | OPeNDAP (Hyrax) | server-side slicing |
| 7 | HTTP subsetting / filtered download | granule-list filtering (bbox/time/QA) before transfer |
| 8 | Full granule download | last resort; never the whole archive |

AppEEARS and Giovanni are interactive / pre-aggregated apps, **not** preferred
programmatic patterns — reach for them only when nothing above fits.

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
- Confusing product levels (L2 vs L3) or column types (total vs tropospheric) — the
  dataset is given; access correctness means the right bytes from it, not just any bytes.

## Quick signals

- Collection feed `has_transforms: true` → Harmony available.
- DMR++ sidecars → ranged OPeNDAP reads without a Hyrax server.
- GES DISC / PODAAC / NSIDC / LP DAAC / ASF cloud-hosted → likely Harmony or OPeNDAP.
- HDF4 / HDF-EOS2 → not streamable natively; needs a service, GDAL VSI, or virtualization.
