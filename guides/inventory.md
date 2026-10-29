# Before you move a table

Get hold of the actual backend **and** every frontend copy. They're often different files. Record each version, its owner, the last modification date, the ODBC DSNs it uses, the Access/Office bitness, and the folders it reads at runtime.

Make an offline backup and checksum it. A file sitting on an active SMB share isn't necessarily a stable snapshot. Put a copy somewhere the extraction process can read without exposing the original to modifications.

Start with `access-fieldkit inspect path/to/database.accdb --out inventory`. Review `manifest.json` for keyless tables, field types, saved queries and Access-specific constructs. `inspect` deliberately counts table rows; it doesn't read or execute VBA.

Check the backend/frontend split. If linked tables live elsewhere, inspect those data sources independently. A working form can also depend on a linked Excel workbook, folder full of scans, mapped network drive or a VBA library reference.

**Windows follow-up:** open a copy in desktop Access and use Database Documenter, the VBA editor, Access Object Model and SSMA's assessment report to list forms, events, reports, macros, custom ribbons, pass-through queries and dependencies. Their absence from the Java inventory is not evidence that they don't exist.

Keep an explicit register: `object | owner | used by | data source | behavior | migration decision | sign-off`. Someone needs to answer whether an old report is still used before it gets translated or retired.

References: [Microsoft: Access to SQL Server](https://support.microsoft.com/en-us/access/migrate-an-access-database-to-sql-server), [Jackcess FAQ](https://jackcess.sourceforge.io/faq.html).
