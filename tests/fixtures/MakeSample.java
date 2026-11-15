import com.healthmarketscience.jackcess.*;
import java.io.File;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/** Writes a small synthetic ACCDB with the cases Fieldkit must not lose: Currency with four decimals,
 *  NULL next to empty text, non-ASCII names, a keyless table with duplicate rows, and binary data. Made-up data only. */
public final class MakeSample {
  public static void main(String[] args) throws Exception {
    File target = new File(args[0]);
    try (Database db = DatabaseBuilder.create(Database.FileFormat.V2010, target)) {
      Table customers = new TableBuilder("Klanten")
          .addColumn(new ColumnBuilder("ID", DataType.LONG).setAutoNumber(true))
          .addColumn(new ColumnBuilder("Naam", DataType.TEXT))
          .addColumn(new ColumnBuilder("Gemeente", DataType.TEXT))
          .addColumn(new ColumnBuilder("Saldo", DataType.MONEY))
          .addColumn(new ColumnBuilder("Sinds", DataType.SHORT_DATE_TIME))
          .addColumn(new ColumnBuilder("Logo", DataType.OLE))
          .addIndex(new IndexBuilder(IndexBuilder.PRIMARY_KEY_NAME).addColumns("ID").setPrimaryKey())
          .toTable(db);
      customers.addRow(Column.AUTO_NUMBER, "Voorbeeld BV", "Liège", new BigDecimal("1234.5678"), LocalDateTime.of(2019, 3, 1, 0, 0), new byte[]{1, 2, 3});
      customers.addRow(Column.AUTO_NUMBER, "Démo SRL", "", new BigDecimal("-0.0001"), null, null);
      customers.addRow(Column.AUTO_NUMBER, "Zonder gemeente", null, new BigDecimal("0"), LocalDateTime.of(2026, 11, 15, 8, 30), null);

      Table log = new TableBuilder("Import log")
          .addColumn(new ColumnBuilder("Regel", DataType.TEXT))
          .addColumn(new ColumnBuilder("Aantal", DataType.INT))
          .toTable(db);
      log.addRow("dubbel", (short) 2);
      log.addRow("dubbel", (short) 2);
      log.addRow(null, null);
    }
  }
}
