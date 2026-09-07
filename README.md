# USDA Data Mirror

Auditable snapshots of selected public USDA transportation datasets, fetched by GitHub Actions so downstream research can consume stable `raw.githubusercontent.com` URLs with Git revision history.

## Datasets

| Key | USDA dataset | Socrata ID | Output |
|---|---|---|---|
| `downbound_grain_barge_rates` | Downbound Grain Barge Rates | `deqi-uken` | `data/deqi-uken.json` |
| `one_month_future_barge_rates` | One Month Future Barge Rates | `svms-9yya` | `data/svms-9yya.json` |

Dataset identifiers were previously discovered from USDA/Socrata metadata and must still pass the workflow's live metadata and freshness checks. A successful HTTP response alone is not accepted as valid data.

## Integrity contract

Each run performs these gates before replacing a snapshot:

1. HTTP request succeeds.
2. Response parses as a non-empty JSON array.
3. Socrata metadata is captured and its resource ID matches the configured ID.
4. Row count cannot silently collapse below 50% of the previous snapshot.
5. A canonical schema hash and SHA-256 are written to `meta/`.
6. `meta/manifest.json` records retrieval time, source URL, row count, columns, and hashes.
7. Git commits only when data or metadata changes.

The mirror records what GitHub's runner could retrieve; it does not change USDA semantics or guarantee that the newest observation is current. Consumers must inspect source date fields before treating a dataset as fresh.

## Running

The workflow supports manual dispatch and a weekly schedule. To run locally:

```bash
python scripts/fetch_usda.py
```

Optional environment variables:

```text
USDA_APP_TOKEN   Socrata application token; not required for a low-frequency smoke run
```

## Raw URLs

```text
https://raw.githubusercontent.com/Billibilli/usda-data-mirror/main/data/deqi-uken.json
https://raw.githubusercontent.com/Billibilli/usda-data-mirror/main/data/svms-9yya.json
https://raw.githubusercontent.com/Billibilli/usda-data-mirror/main/meta/manifest.json
```

## Scope

This repository is a public-data acquisition and provenance layer, not an investment signal or trading system.
