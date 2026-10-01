---
name: dask-optimization
description: Keep lazy Earthdata workflows efficient — persist wisely, align chunks with the access pattern, avoid unnecessary shuffles and full materialization. Use when streamed/virtualized xarray workflows are slow, memory-hungry, or dying with KilledWorker/OOM. Adapted from tondevrel/scientific-agent-skills.
---

# Dask optimization for Earthdata workflows

Remote Earthdata access is Dask whether you asked for it or not: streamed and virtual
datasets are lazy, and the graph is only as good as the chunk layout it was built from.
Parallelism is not free — data movement and scheduling can dominate compute.

## When to use

- Jobs fail with `KilledWorker`/OOM or crawl on "gray" idle time.
- Datasets 10x–100x larger than RAM (or just larger than your patience on one core).
- Custom pipelines with `dask.delayed`/futures.
- Tuning threads vs processes for IO-bound remote reads.

## Rules of thumb for remote reads

1. **Subset the graph before computing** — `.sel()`, variable selection, and dtype
   casting all shrink the task graph before any bytes move.
2. **Chunks follow the access pattern.** Time series at a point → chunks that don't
   span the whole spatial grid; regional maps → don't force reading every timestep.
   If rechunking, do it once, early: `ds = ds.chunk(time=...)`.
3. **Small reads are latency-bound.** A value-per-chunk access pattern turns into one
   network round trip per chunk (fsspec caches 4–16 MB blocks — see the
   `earthdata-streaming-vs-download` skill). Read contiguous slices, not scattered
   points, when you can.
4. **`persist()` deliberately** — only when the same lazy slice feeds many downstream
   computations; otherwise it's a disguised full load.
5. **Avoid shuffles** (arbitrary `groupby` keys, merges on unaligned dims). Pre-sort,
   use `map_blocks`, or aggregate along existing chunked dims.
6. **One worker, many threads for IO**-bound streaming; processes only for GIL-heavy
   Python UDFs.

## Diagnosing

- Dashboard: lots of red (communication) or gray (idle) → rechunk or repartition.
- Task stream stripes of tiny tasks → coarsen chunks/blocks.
- `da.compute(optimize_graph=True)` (default) is fine; `dask.config` optimizations
  (fuse, cull) are already on.

## Reference

- Best practices: https://docs.dask.org/en/latest/best-practices.html
- Diagnosing performance: https://distributed.dask.org/en/latest/diagnosing-performance.html
- Memory management: https://distributed.dask.org/en/latest/worker.html#memory-management
- Search patterns: `client.persist`, `repartition`, `chunk`, `cull`, `fuse`

Adapted from tondevrel/scientific-agent-skills (`dask-optimization` skill).
