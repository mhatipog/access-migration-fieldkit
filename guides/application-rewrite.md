# Forms and VBA: write down what the app actually does

A `Forms!frmOrders!CustomerID` reference is not portable SQL. Querying saved query metadata tells you *where* such references might exist; it doesn't tell you how the user's form sets the parameter or what happens on `BeforeUpdate`.

A useful approach is to run the old application in a controlled Windows copy and record the inputs and outputs of one workflow at a time. Start with an order entered by a blocked customer, a partial shipment, an invoice with a credit note, and concurrent edits. Save screen evidence and financial totals. Check whether form event handlers, `DLookup`, macros or VBA functions change the outcome.

**Example: Access form-bound query**

```sql
SELECT SalesOrderID, CustomerID FROM SalesOrders
WHERE CustomerID = Forms!frmSalesOrders!CustomerID;
```

**Example: equivalent database parameter** (PostgreSQL):

```sql
SELECT "SalesOrderID", "CustomerID"
FROM "SalesOrders"
WHERE "CustomerID" = $1;
```

The API or service supplies `$1` from its authenticated request context, not from an untrusted string inserted into SQL. The SQL rewrite is the easy half. The difficult half is preserving validation, permissions, error messages, transactions and audit trails.

Old behavior is not automatically correct. If a legacy VBA function uses an obsolete VAT rate, preserve its historical observed output but use an independently approved tax rule for *new* transactions. Document the discrepancy; don't accidentally canonize a bug.

Microsoft's own SSMA documentation says forms, reports, macros and VBA modules are not converted. [Read the migration guidance](https://support.microsoft.com/en-us/access/migrate-an-access-database-to-sql-server).
