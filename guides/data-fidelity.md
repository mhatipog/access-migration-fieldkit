# Data that passes row counts and still breaks

## Currency

Access Currency stores four decimal places. Converting values through JavaScript `Number`, JSON floating point, or an SQL `FLOAT` can change monetary results. Keep Currency as a decimal string during extraction and use an exact decimal column (for example PostgreSQL `NUMERIC(19,4)` or SQL Server `DECIMAL(19,4)`) in the final target. In SQLite landing we use TEXT and leave business arithmetic to an exact-decimal layer.

Do not "fix" historical invoices by recalculating the VAT rate from the current calendar. Preserve posted amounts and separately define the new calculation rule with the business owner.

## Duplicate rows and primary keys

Rows with no stable key cannot be made safely updateable just by copying them. Two physically distinct rows may have identical values. Keep every source row with a staging ordinal. Work with the application owner to identify a natural identifier or introduce a new key with a documented mapping. Don't infer a key from row order when planning incremental updates.

## NULL vs empty

Keep `NULL`, `''`, `0` and `False` distinct. Some Access schemas explicitly allow zero-length text; others don't. Confirm source properties before rewriting user-facing validation and lookups.

## Dates

Some Access dates predate the 1753 minimum of SQL Server's legacy `datetime`. Use `date` or `datetime2` when appropriate and do not let a migration tool clamp old dates. Determine whether a field represents a local wall-clock time, a UTC timestamp, or simply a date without a timezone. These aren't interchangeable.

## Orphans

A newly enforced foreign key might reject old rows that Access never constrained. Land all original records unchanged first. Put invalid links in a remediation ledger with a record count and source checksum. Decide to repair, archive or quarantine *with an approver*; silent drops are data loss.

## Files outside Access

The database can store `S:\...` or `\\\\fileserver\\...` paths without owning the files. An inventory of paths is not a document migration. Migrate and hash the actual file bytes, then re-check access rights with a real user account.
