# Access → PostgreSQL

A simple repeatable landing process when the end goal isn't SQL Server.

```bash
pip install . psycopg[binary]
access-fieldkit export ./legacy.accdb --out ./export-2026-10
access-fieldkit assess ./export-2026-10 --out ./assessment.md
python examples/load_postgres.py ./export-2026-10 \
  --dsn 'postgresql://user:password@localhost:5432/disposable_db' \
  --schema access_landing_1
```

The example script creates a **new schema** and refuses to run if that schema already exists. Access Currency maps to PostgreSQL `NUMERIC(19,4)`; date-times map to `TIMESTAMP WITHOUT TIME ZONE`, leaving timezone meaning for the migration owner to resolve. Source records retain the ordinal they had when extracted, including duplicates and orphaned references.

This is still *staging*. Define proper keys, referential integrity, indexes and application-specific types in a separate final model. Don't make a source ordinal into a permanent business identifier.

If users keep editing Access during migration, take a stable snapshot and schedule a write freeze or instrument every frontend write. Access doesn't provide a universal change stream that a read-only extractor can replay safely.
