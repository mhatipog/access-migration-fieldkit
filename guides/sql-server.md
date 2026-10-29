# Access → SQL Server / Azure SQL

For SQL Server, prefer Microsoft SQL Server Migration Assistant (SSMA) for Access over a custom converter. Run it from a supported Windows environment with access to the source, the correct ACE/ODBC drivers and a disposable SQL Server/Azure SQL target.

1. Run Fieldkit's `inspect` and `assess` first, to catch keyless tables, monetary fields, historical dates and queries tied to forms.
2. Run the SSMA **assessment report**. Save the native XML and an inventory of objects that did not convert. An SSMA project isn't a replacement for backups.
3. Review type mappings: Currency → exact decimal; DateTime → datetime2/date as appropriate; Yes/No → bit; long text → nvarchar(max); identify attachment and multivalue fields for dedicated migration.
4. Create a new target database. Migrate schema and data, then compare all relevant rows and business aggregates.
5. If keeping the Access front end temporarily, link its tables to SQL Server. Add real primary keys and use a `rowversion` column for updateable linked tables when needed. Measure network roundtrips for complex joins.
6. Rewrite form-bound parameter queries, VBA and reports independently. Document exception decisions and owner sign-off.

**Avoid claiming success from SSMA's conversion percentage.** A report with all tables migrated can still leave the original user interface unusable or silently change a calculation.

References: [Microsoft: SSMA for Access](https://learn.microsoft.com/en-us/sql/ssma/access/getting-started-with-sql-server-migration-assistant-for-access-accesstosql), [Microsoft: Access to SQL Server](https://support.microsoft.com/en-us/access/migrate-an-access-database-to-sql-server).
