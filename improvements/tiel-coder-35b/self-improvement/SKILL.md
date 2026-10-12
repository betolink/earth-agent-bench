---
name: self-improvement
description: >
  Model-specific countermeasures distilled from tiel-coder-35b's failure postmortem
  on the earth-agent-bench run. READ THIS FIRST and follow it before doing
  anything else; each rule maps to a failure this exact model actually made.
generator: deterministic-digest
source_run: 20261011-005413
model: tiel-coder-35b
---

# Self-improvement — tiel-coder-35b

> Generated from the 20261011-005413 evaluation on harness `all`.
> Do these; they are the mistakes you made last time.

## Hard rules (always)

1. **Out-of-region -> HTTPS, never S3.** This runs outside AWS. `s3://...`,
   `*.s3.amazonaws.com`, `s3_credentials`, `s3fs` will not work (hang/403). Use
   the HTTPS object URL, or the HTTPS path `earthaccess.open()`/`download()` return.
2. **Inspect the inputs before writing code.** Print the real schema (columns,
   keys, units, dtypes) of every input file first. Never hardcode a column name.
3. **Match the exact acceptance criterion.** Re-read the asked quantity and units.
4. **Verify before you finish.** Run the task's own test/verifier or reproduce the
   expected output and diff it. 'Looks right' is not done.
5. **Be decisive — minimize iterations.** Prefer the answer the skills/MCP give;
   avoid long live-probing loops. Every retry costs wall-clock and grows context.
6. **Respect the output contract.** Write exactly the required artifact path(s).

## Observed failures this run

| task | condition | outcome | reward | note |
|---|---|---|---|---|
| a1-tempo-no2-florida-2024 | baseline | timeout | 0.00 | AgentTimeoutError |
| a1-tempo-no2-florida-2024 | baseline | timeout | 0.10 | AgentTimeoutError |
| a2-emit-methane-permian-2024 | baseline | timeout | 0.00 | AgentTimeoutError |
| a3-maiac-aod-eastern-us-2023 | baseline | timeout | 0.00 | AgentTimeoutError |
| b1-pnw-wildfire-recovery-2020-2023 | baseline | timeout | 0.00 | AgentTimeoutError |
| b1-pnw-wildfire-recovery-2020-2023 | baseline | timeout | 0.00 | AgentTimeoutError |
| b2-amazon-gpp-soilmoisture-2023 | baseline | timeout | 0.00 | AgentTimeoutError |
| b2-amazon-gpp-soilmoisture-2023 | baseline | timeout | 0.10 | AgentTimeoutError |
| b3-gedi-landsat-canopy-2019-2023 | baseline | timeout | 0.00 | AgentTimeoutError |
| c1-itslive-jakobshavn-2015-2024 | baseline | timeout | 0.00 | AgentTimeoutError |
| c3-amsr2-beaufort-2024 | baseline | timeout | 0.00 | AgentTimeoutError |
| l2-black-marble-ian-2022 | baseline | timeout | 0.10 | AgentTimeoutError |
| l2-black-marble-ian-2022 | baseline | timeout | 0.00 | AgentTimeoutError |
| l3-iowa-drought-2022 | baseline | timeout | 0.00 | AgentTimeoutError |
| l3-iowa-drought-2022 | baseline | timeout | 0.00 | AgentTimeoutError |
| o1-chlorophyll-ca-current-2023 | baseline | timeout | 0.00 | AgentTimeoutError |
| o2-mur-sst-gbr-2024 | baseline | timeout | 0.00 | AgentTimeoutError |
| s1-turkiye-earthquake-2023 | baseline | timeout | 0.00 | AgentTimeoutError |
| s2-reykjanes-inflation-2023-2024 | baseline | timeout | 0.00 | AgentTimeoutError |
| a2-emit-methane-permian-2024 | baseline | partial | 0.60 |  |
| a3-maiac-aod-eastern-us-2023 | baseline | partial | 0.60 |  |
| b3-gedi-landsat-canopy-2019-2023 | baseline | partial | 0.65 |  |
| c1-itslive-jakobshavn-2015-2024 | baseline | partial | 0.57 |  |
| c2-prefire-modis-greenland-2024 | baseline | partial | 0.80 |  |
| c2-prefire-modis-greenland-2024 | baseline | partial | 0.53 |  |
| c3-amsr2-beaufort-2024 | baseline | partial | 0.60 |  |
| l1-phoenix-lst-uhi-2015-2024 | baseline | partial | 0.67 |  |
| l1-phoenix-lst-uhi-2015-2024 | baseline | partial | 0.70 |  |
| o3-swot-altimetry-gulfstream-2023 | baseline | partial | 0.68 |  |
| s3-central-valley-subsidence-2015-2024 | baseline | partial | 0.10 |  |

## What went wrong, and the fix

- **You timed out on 19/30 tasks.** The dominant cause is over-exploring (repeated live probing). Answer from the skills/MCP, verify once, stop.
- **You touched S3 ~14911 times** — out of region it cannot work; use HTTPS.
- **~6715 `search_data` calls** — collapse the search loop; the skills/MCP already answer most of these.
