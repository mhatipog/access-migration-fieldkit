# Access Fieldkit

Tools for the first awkward week of an Access migration: finding out what's in the file, getting the rows out without quietly changing them, and checking that a landing copy still matches.

The most common mistake is treating a row count as a completed migration. An Access database can carry keyless tables, embedded SQL tied to forms, four-decimal Currency values, unsaved business rules in VBA, and paths to files that don't live in the database. Moving tables doesn't fix any of that.

Fieldkit does **not** claim to convert an Access application. It's a read-only source inspector, exporter, SQLite staging loader, and per-value reconciliation tool. It also includes a PostgreSQL loading example and a runbook for SQL Server/SSMA migrations.

## Quick start

Requires Python 3.10+, Java JDK 11+, and an Internet connection for the first run to retrieve Jackcess 5.0.4 from Maven Central. The downloaded JAR is checked against the pinned SHA-256. You can also pass a verified local JAR with `--jackcess-jar`.

```bash
python -m pip install .

# Makes only a manifest. Does not export rows.
access-fieldkit inspect ./legacy.accdb --out ./work/inventory

# Copies table rows into numbered JSONL files, plus a manifest with SHA-256 checksums.
access-fieldkit export ./legacy.accdb --out ./work/export

# What will need attention before someone changes the database or its front end?
access-fieldkit assess ./work/export --out ./work/assessment.md

# Optional: compare the native inventory with MDB Tools, if installed.
access-fieldkit probe-tools ./legacy.accdb ./work/export --out ./work/tool-probes.json

# Creates a new disposable landing database with original table/column names.
access-fieldkit load-sqlite ./work/export ./work/landing.sqlite

# Compares every exported value to the SQLite landing copy.
access-fieldkit reconcile ./work/export ./work/landing.sqlite
```

Both `inspect` and `export` open the Access file **read-only**. Existing output folders are not overwritten. The SQLite loader creates its target through a temporary file and refuses to replace an existing database unless `--force` is given; don't point it at production.

## What the export contains

`manifest.json` records original table and column names, Access field types, indexes, row counts, saved queries when readable, the source file checksum, and individual table-file checksums. Each `table-0001.jsonl` holds one row per line in the original column order. The file names are numbered on purpose: original Access object names must never become unchecked filesystem paths.

Raw rows are kept in order. No artificial primary keys are introduced into source data, no duplicates are collapsed, and NULL is different from an empty string. Currency and decimal values use an explicit text tag so that an intermediate JSON float never rounds the number. Binary values use base64. Unsupported object values cause extraction to fail with a table/row/column location rather than disappear.

The SQLite target is a **landing zone**, not a finalized relational schema: it retains every original column and adds an internal source-row ordinal. Access Currency maps to SQLite TEXT, because SQLite has no exact fixed-decimal type. Use a deliberate target schema and business-approved conversions before building a production application.

## Where it fits

- **SQLite / local web API:** Run `load-sqlite`, then see `examples/serve_sqlite.py` for a read-only local HTTP view of the landing tables.
- **PostgreSQL:** `examples/load_postgres.py` uses psycopg 3 to create a fresh schema and load the extracted values, including Currency as `NUMERIC(19,4)`.
- **SQL Server / Azure SQL:** Use SSMA for the bulk SQL Server path; apply the decisions in [guides/sql-server.md](guides/sql-server.md). This repository does not pretend to be SSMA.
- **Modern application rewrite:** Inventory saved queries here. Use desktop Access on Windows to document forms, events, macros and VBA before moving those workflows into an API or new UI.

## Guides

- [Start with an inventory](guides/inventory.md)
- [Currency, NULLs, dates and difficult data](guides/data-fidelity.md)
- [Saved queries, VBA and forms](guides/application-rewrite.md)
- [SQL Server and SSMA](guides/sql-server.md)
- [PostgreSQL landing](guides/postgresql.md)
- [Cutover and rollback](guides/cutover.md)

## Limits worth knowing

Encrypted `.accdb` files may need additional codec support; this tool doesn't try to bypass encryption. Attachments, multivalue columns, linked tables, and Access UI objects require separate inspection. If an Access object is unsupported, don't interpret an incomplete export as proof of a complete application migration. A Windows Access/SSMA run remains necessary for those parts.

This code grew out of repeatable migrations of real-format ACE files and documented Microsoft/Jackcess limitations, **not production client migrations**. The included examples use made-up data only. Use backups, permission reviews and a write freeze when assessing an actual customer database.

MIT licensed. See [LICENSE](LICENSE).

Maintained by [Vecture](https://vecture.be). Contributions and field reports are welcome via [GitHub issues](https://github.com/mhatipog/access-migration-fieldkit/issues).
