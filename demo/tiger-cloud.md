# Tiger Cloud in Haven

## What we used it for

**Tiger Cloud** is Haven's managed **Postgres** database, with the **TimescaleDB** extension. It does two jobs:

1. **Persistence for the app.** Renter profiles, saved reports, upload records and saved homes survive restarts and follow the user across devices.
2. **Time-series data.** The Scottish Government's private sector rent statistics for Lothian (2010 to 2025, by bedroom count) are loaded into a TimescaleDB **hypertable**.

## How it works

### Application records: `haven_records`

```text
haven_records
  kind        text  ─┐ primary key      profile | report | upload | saved_homes
  id          text  ─┘
  owner_sub   text  (indexed)           Auth0 user ID of the creator
  created_at  timestamptz
  data        json                      the validated Pydantic model
```

- One table for all record types, keyed by `(kind, id)`, storing each record as the **same Pydantic model** the API returns. Adding a field to a model needs no migration.
- `owner_sub` links each record to its **Auth0** user. Lists are filtered by owner, other users get `404`, and `DELETE /v1/me` removes everything a user owns.
- Created automatically on startup (`SQLModel.metadata.create_all`).
- Code: `backend/haven/store/records.py` (`SqlRecordStore`), `backend/haven/store/db.py`.

### Rent statistics: the `rent_stats` hypertable

```sql
CREATE TABLE IF NOT EXISTS rent_stats (
    brma text, beds text, period_end date, year integer,
    lower_quartile_gbp_pcm numeric, median_gbp_pcm numeric,
    mean_gbp_pcm numeric, upper_quartile_gbp_pcm numeric,
    n_records integer, is_sample boolean,
    PRIMARY KEY (brma, beds, period_end)
);
SELECT create_hypertable('rent_stats', 'period_end', if_not_exists => TRUE,
                         chunk_time_interval => INTERVAL '5 years');
```

- Generated from the official statistics by `backend/scripts/build_seeds.py` into `data/sql/rent_stats.sql` (with source and licence in the header), and safe to re-run (`IF NOT EXISTS` + `ON CONFLICT`).
- Loaded with `uv run python scripts/load_db.py`; `--ping` just checks the connection.
- Queried with `haven.datasets.db.rent_series("2_bed")`, which falls back to the bundled seed file if the database isn't configured or the table is empty. The rent context currently shown in the app reads the same Lothian figures from reference YAML, so the hypertable is the base for live and historical rent queries as the data grows.

### Setup

```env
# backend/.env
HAVEN_DATABASE_URL="postgres://...tsdb.cloud.timescale.com:.../tsdb?sslmode=require"
```

Tiger Cloud's "Service URL" works as is: Haven rewrites `postgres://` to the psycopg 3 driver (`postgresql+psycopg://`) and uses a 5-second connect timeout. Docker Compose passes the same `backend/.env` to the API container.

## Designed to degrade gracefully

| Situation | Behaviour |
| --- | --- |
| `HAVEN_DATABASE_URL` set and reachable | Records persist in Tiger Cloud |
| Not set | Records live in memory for the session; the app runs fully offline |
| Set but unreachable at startup | Logged as an error and falls back to memory; the API still starts |
| `rent_stats` missing or empty | `rent_series` reads the bundled seed file |

Tests run on **SQLite** through the same `SqlRecordStore`, so the persistence code is covered without a network.

## Impact on the project

- **Profiles and reports became real.** Before Tiger Cloud, everything was lost on restart. Now a renter can save a report, come back on another device, and delete it all whenever they want.
- **No database operations work for the team.** Managed Postgres meant no servers, backups or TLS setup to run during a hackathon. We pasted a connection string and got a production-grade database.
- **Postgres plus time series in one place.** TimescaleDB let us keep relational app data and the time-indexed rent series in the **same database**, with ordinary SQL, instead of adding a separate time-series store.
- **Ready for richer rent data.** The rent series is annual today. The hypertable (5-year chunks on `period_end`) is ready for quarterly or monthly feeds and listing-level asking-rent data, so we could show **trends** (for example how fast rents are rising in an area) without changing the schema.
- **Ownership and privacy built in.** Storing `owner_sub` alongside each record made per-user access control and "delete all my data" simple and reliable.
- **Simple schema.** Storing validated Pydantic models as JSON kept the database in step with the OpenAPI contract while the API changed quickly.

## Next steps

- Move uploaded files from local disk to object storage (only their records are in Tiger Cloud today).
- Point the app's rent context at `rent_stats` and add trend views (year-on-year change by bedroom count).
- Add continuous aggregates when finer-grained rent data arrives.
- Proper migrations (for example Alembic) once the schema settles.
