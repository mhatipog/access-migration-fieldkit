import com.healthmarketscience.jackcess.*;
import com.healthmarketscience.jackcess.query.Query;
import java.io.*;
import java.math.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.time.*;
import java.util.*;

/** Read-only ACE/Jet inventory and loss-aware row extraction. No Access runtime emulation. */
public final class AccessReader {
  private static String j(String s) {
    StringBuilder b = new StringBuilder("\"");
    for (int i=0; i<s.length(); i++) {
      char c=s.charAt(i);
      switch(c) {
        case '\"': b.append("\\\""); break;
        case '\\': b.append("\\\\"); break;
        case '\n': b.append("\\n"); break;
        case '\r': b.append("\\r"); break;
        case '\t': b.append("\\t"); break;
        default:
          if (c<32 || (Character.isHighSurrogate(c) && (i+1 == s.length() || !Character.isLowSurrogate(s.charAt(i+1)))) || Character.isLowSurrogate(c) && (i == 0 || !Character.isHighSurrogate(s.charAt(i-1)))) {
            b.append(String.format("\\u%04x",(int)c));
          } else b.append(c);
      }
    }
    return b.append('\"').toString();
  }
  private static String val(Object v) {
    if(v==null) return "null";
    if(v instanceof byte[]) return "{\"$binary\":" + j(Base64.getEncoder().encodeToString((byte[])v)) + "}";
    if(v instanceof Boolean) return v.toString();
    if(v instanceof BigDecimal) return "{\"$decimal\":" + j(((BigDecimal)v).toPlainString()) + "}";
    if(v instanceof Number) {
      if(v instanceof Double || v instanceof Float) {
        if(!Double.isFinite(((Number)v).doubleValue())) throw new IllegalStateException("Non-finite floating point data");
        return "{\"$float\":" + j(v.toString()) + "}";
      }
      return v.toString();
    }
    if(v instanceof LocalDateTime || v instanceof LocalDate || v instanceof LocalTime || v instanceof OffsetDateTime) return j(v.toString());
    if(v instanceof java.util.Date) return j(((java.util.Date)v).toInstant().atZone(ZoneOffset.UTC).toLocalDateTime().toString());
    if(v instanceof CharSequence || v instanceof Character) return j(v.toString());
    throw new IllegalArgumentException("Unsupported Access value type " + v.getClass().getName() + "; no silent string coercion");
  }
  private static String array(List<String> parts) { return "[" + String.join(",",parts) + "]"; }
  private static String sha(Path p) throws Exception {
    MessageDigest md=MessageDigest.getInstance("SHA-256");
    try(InputStream in=Files.newInputStream(p)) { byte[] block=new byte[65536]; int n; while((n=in.read(block))!=-1) md.update(block,0,n); }
    StringBuilder s=new StringBuilder(); for(byte b: md.digest()) s.append(String.format("%02x",b & 255)); return s.toString();
  }
  private static void inspect(Path source,Path target,boolean export) throws Exception {
    if(!Files.isRegularFile(source)) throw new IOException("Missing Access database: " + source);
    Files.createDirectories(target);
    List<String> tables=new ArrayList<>(), queries=new ArrayList<>(), warnings=new ArrayList<>();
    long total=0;
    try(Database db=new DatabaseBuilder(source.toFile()).setReadOnly(true).open()) {
      int serial=0;
      for(String name:db.getTableNames()) {
        Table table=db.getTable(name);
        String file=String.format(Locale.ROOT,"table-%04d.jsonl",++serial);
        List<String> cols=new ArrayList<>(), keys=new ArrayList<>();
        boolean complex=false, lacksPk=true;
        for(Column c:table.getColumns()) {
          String t=c.getType().name();
          if(t.equals("COMPLEX_TYPE") || t.equals("UNKNOWN_0D") || t.equals("UNSUPPORTED_VARLEN")) complex=true;
          cols.add("{\"name\":" + j(c.getName()) + ",\"type\":" + j(t) + ",\"length\":" + c.getLength() + ",\"auto_number\":"+c.isAutoNumber()+"}");
        }
        for(Index idx:table.getIndexes()) {
          List<String> names=new ArrayList<>();
          for(Index.Column c:idx.getColumns()) names.add(j(c.getName()));
          keys.add("{\"name\":"+j(idx.getName())+",\"primary\":"+idx.isPrimaryKey()+",\"unique\":"+idx.isUnique()+",\"columns\":"+array(names)+"}");
          if(idx.isPrimaryKey()) lacksPk=false;
        }
        if(lacksPk) warnings.add("No primary key: " + name + "; retain source ordinals for duplicates");
        if(complex) warnings.add("Complex/attachment field: " + name + "; inspection only; export may require Access on Windows");
        long count=0;
        Path dest=target.resolve(file);
        try(BufferedWriter out=export ? Files.newBufferedWriter(dest,StandardCharsets.UTF_8) : null) {
          for(Row row:table) {
            count++;
            if(export) {
              List<String> values=new ArrayList<>();
              for(Column col:table.getColumns()) {
                try { values.add(val(row.get(col.getName()))); }
                catch(Exception ex) { throw new IOException("Unsupported value at " + name + " row " + count + " column " + col.getName() + ": " + ex.getMessage(),ex); }
              }
              out.write(array(values)); out.newLine();
            }
          }
        }
        total+=count;
        String data=export?",\"data_file\":"+j(file)+",\"sha256\":"+j(sha(dest)):"";
        tables.add("{\"name\":"+j(name)+",\"rows\":"+count+",\"columns\":"+array(cols)+",\"indexes\":"+array(keys)+data+"}");
      }
      try {
        for(Query q:db.getQueries()) {
          String sql;
          try { sql=q.toSQLString(); } catch(RuntimeException ex) { sql=null; warnings.add("Unparsable saved query: " + q.getName()); }
          queries.add("{\"name\":"+j(q.getName())+",\"type\":"+j(q.getType().toString())+",\"sql\":"+(sql==null?"null":j(sql))+"}");
        }
      } catch(Exception ex) { warnings.add("Unable to inventory saved queries: " + ex.getClass().getSimpleName()); }
      List<String> warningsJson=new ArrayList<>(); for(String s:warnings) warningsJson.add(j(s));
      String schema="{\"format\":\"access-fieldkit-v1\",\"source_name\":"+j(source.getFileName().toString())+
        ",\"file_sha256\":"+j(sha(source))+",\"access_format\":"+j(db.getFileFormat().name())+
        ",\"exported\":"+export+",\"tables\":"+array(tables)+",\"queries\":"+array(queries)+
        ",\"total_rows\":"+total+",\"warnings\":"+array(warningsJson)+"}";
      Files.writeString(target.resolve("manifest.json"),schema+"\n",StandardCharsets.UTF_8);
      System.out.println("Access read-only " + (export ? "export" : "inspection") + ": " + tables.size() + " tables, " + total + " rows, " + queries.size() + " queries");
    }
  }
  public static void main(String[] args) throws Exception {
    TimeZone.setDefault(TimeZone.getTimeZone("UTC"));
    if(args.length!=3 || !(args[0].equals("inspect") || args[0].equals("export")))
      throw new IllegalArgumentException("Usage: AccessReader inspect|export source.accdb output-directory");
    inspect(Paths.get(args[1]),Paths.get(args[2]),args[0].equals("export"));
  }
}
