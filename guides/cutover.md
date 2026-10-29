# Cutover without the pleasant surprises

A successful initial migration is not a completed cutover. At least one salesperson will have a frontend you didn't know existed.

1. Map **every** writable frontend, linked backend and shared file path. Confirm owners and last-write times.
2. Take a read-only copy. Record the file SHA-256 and the exact observation time. Run the export and reconcile it into a new landing zone.
3. Characterize business workflows in the Access frontend while the original is still available. Signed-off examples should include balances, corrections and unhappy paths, not just happy-path row counts.
4. Decide between a write freeze and instrumentation of all writes. If you cannot prove all writes are captured, use a freeze; timestamps alone are not reliable change data capture.
5. Rehearse the cutover on a copy: restore, export, reconcile, switch test clients, verify permissions, recreate reports, exercise concurrent edits, then roll back.
6. At cutover, freeze writes, capture the final source, migrate the delta or repeat the load, reconcile, check permissions, switch clients and watch errors.
7. Keep old systems read-only for the agreed period. Plan who can authorize rollback and how to avoid two writable copies diverging.

Record checksums, object inventories, row totals, financial aggregate comparisons, signed-off business scenarios, the final backup and the person who approved the cutover. A clean JSON reconciliation report does not replace application acceptance.
