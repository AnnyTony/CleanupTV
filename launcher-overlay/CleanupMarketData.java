package com.gathin.tvhome;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.json.JSONArray;
import org.json.JSONObject;

/** Bounded, fail-closed readers for three public boards. No scripts or HTML are executed. */
final class CleanupMarketData {
    static final String[] TITLES = {"Giá vàng", "Tỷ giá ngoại tệ", "Giá xăng dầu"};
    static final String[] SOURCES = {"BTMC · Hà Nội", "Vietcombank", "Petrolimex"};
    static final String GOLD_URL = "https://btmc.vn/Home/BGiaVang";
    static final String FX_URL = "https://portal.vietcombank.com.vn/Usercontrols/TVPortal.TyGia/pXML.aspx?b=10";
    // Same public search and published-only filter used by Petrolimex's retail-price page.
    static String fuelUrl() throws Exception {
        JSONObject filter = new JSONObject(); JSONArray and = new JSONArray();
        String[] keys = {"SystemID", "RepositoryID", "RepositoryEntityID", "Status"};
        String[] values = {"6783dc1271ff449e95b74a9520964169", "a95451e23b474fe5886bfb7cf843f53c", "3801378fe1e045b1afa10de7c5776124", "Published"};
        for (int i=0; i<keys.length; i++) and.put(new JSONObject().put(keys[i], new JSONObject().put("Equals", values[i])));
        filter.put("FilterBy", new JSONObject().put("And", and));
        filter.put("SortBy", new JSONObject().put("LastModified", "Descending"));
        filter.put("Pagination", new JSONObject().put("TotalRecords", -1).put("TotalPages", 0).put("PageSize", 0).put("PageNumber", 0));
        return "https://portals.petrolimex.com.vn/~apis/portals/cms.item/search?x-request=" +
            java.util.Base64.getUrlEncoder().withoutPadding().encodeToString(filter.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }
    static String url(int kind) throws Exception { return kind==0 ? GOLD_URL : kind==1 ? FX_URL : fuelUrl(); }
    static String plain(String value) {
        return value.replaceAll("(?is)<[^>]*>", " ").replace("&nbsp;", " ").replace("&#160;", " ")
            .replace("&amp;", "&").replaceAll("\\s+", " ").trim();
    }
    static String amount(String raw, boolean commaThousands) {
        String value = raw.trim();
        if(value.length()>32) throw new IllegalArgumentException("Price too long");
        if (!value.matches(commaThousands ? "(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\\.[0-9]{1,2})?" : "[0-9]+"))
            throw new IllegalArgumentException("Invalid price");
        BigDecimal n = new BigDecimal(value.replace(",", ""));
        if (n.signum()<=0 || n.compareTo(new BigDecimal("1000000000"))>0) throw new IllegalArgumentException("Price outside range");
        java.text.NumberFormat f = java.text.NumberFormat.getNumberInstance(new Locale("vi", "VN"));
        f.setMaximumFractionDigits(2); return f.format(n);
    }
    static JSONObject parse(int kind, String body, String currency, int zone) throws Exception {
        if (body.length()>(kind==0?50000:kind==1?20000:100000) || body.contains("<!ENTITY") || body.contains("<!DOCTYPE")) throw new IllegalArgumentException("Unexpected source format");
        if (!currency.matches("USD|EUR|JPY|AUD|GBP|SGD|THB|CNY|KRW|CAD") || (zone!=1 && zone!=2)) throw new IllegalArgumentException("Invalid board choice");
        JSONArray rows = new JSONArray(); String date; String unit;
        if (kind==0) {
            String text = plain(body);
            if (!text.contains("ĐVT 1 = 1.000 VNĐ")) throw new IllegalArgumentException("Gold unit changed");
            Matcher stamp = Pattern.compile("Cập nhật lúc (\\d{2}/\\d{2}/\\d{4} \\d{2}:\\d{2})").matcher(text);
            if (!stamp.find()) throw new IllegalArgumentException("Missing gold date");
            date=stamp.group(1); unit="Nghìn VND · nguyên đơn vị BTMC";
            Matcher tr = Pattern.compile("(?is)<tr\\b[^>]*>(.*?)</tr>").matcher(body);
            while (tr.find()) {
                List<String> cells=new ArrayList<>(); Matcher td=Pattern.compile("(?is)<td\\b[^>]*>(.*?)</td>").matcher(tr.group(1));
                while(td.find()) cells.add(plain(td.group(1)));
                if(cells.size()<4) continue;
                String name=cells.get(cells.size()-4);
                String shortName=name.equals("VÀNG MIẾNG SJC") ? "Miếng SJC" : name.startsWith("NHẪN TRÒN TRƠN BẢO TÍN") ? "Nhẫn BTMC 999.9" : name.equals("TRANG SỨC VÀNG RỒNG THĂNG LONG 999.9") ? "Trang sức RTL 999.9" : null;
                if(shortName!=null) rows.put(new JSONObject().put("name",shortName).put("buy",amount(cells.get(cells.size()-2),false)).put("sell",amount(cells.get(cells.size()-1),false)));
            }
            if(rows.length()!=3) throw new IllegalArgumentException("Gold rows changed");
        } else if (kind==1) {
            Matcher stamp=Pattern.compile("<DateTime>([^<]{1,60})</DateTime>").matcher(body);
            if(!stamp.find()) throw new IllegalArgumentException("Missing FX date");
            date=stamp.group(1).trim(); unit="VND / 1 "+currency;
            Matcher row=Pattern.compile("<Exrate\\s+([^>]+)/>").matcher(body);
            while(row.find()) {
                JSONObject attrs=new JSONObject(); Matcher attr=Pattern.compile("([A-Za-z]+)=\"([^\"]*)\"").matcher(row.group(1));
                while(attr.find()) attrs.put(attr.group(1),attr.group(2));
                if(!currency.equals(attrs.optString("CurrencyCode"))) continue;
                rows.put(new JSONObject().put("name","Mua tiền mặt").put("value",fxAmount(attrs.getString("Buy"))));
                rows.put(new JSONObject().put("name","Mua chuyển khoản").put("value",fxAmount(attrs.getString("Transfer"))));
                rows.put(new JSONObject().put("name","Bán ra").put("value",fxAmount(attrs.getString("Sell"))));
            }
            if(rows.length()!=3) throw new IllegalArgumentException("Missing currency");
        } else if(kind==2) {
            validateJsonDepth(body);
            JSONArray products=new JSONObject(body).getJSONArray("Objects");
            List<JSONObject> selected=new ArrayList<>();
            for(int i=0; i<products.length() && i<40; i++) {
                JSONObject p=products.getJSONObject(i); String name=p.getString("Title");
                if(name.length()>80 || name.matches("(?s).*[\\p{Cntrl}].*")) throw new IllegalArgumentException("Invalid product name");
                // Keep the exact grade, never rename E10 to E5 or substitute a different diesel grade.
                if(name.startsWith("Xăng ") || name.equals("DO 0,05S-II")) selected.add(p);
            }
            selected.sort(java.util.Comparator.comparingInt(p -> fuelRank(p.optString("Title"))));
            date=""; unit="VND/lít · Vùng "+zone;
            for(JSONObject p:selected) {
                if(rows.length()>=3) break;
                String stamp=p.getString("LastModified");
                if(!stamp.matches("\\d{4}-\\d{2}-\\d{2}T[0-9:.]+Z")) throw new IllegalArgumentException("Invalid fuel date");
                if(date.isEmpty() || stamp.compareTo(date)<0) date=stamp;
                rows.put(new JSONObject().put("name",p.getString("Title")).put("value",amount(p.get("Zone"+zone+"Price").toString(),false)).put("date",stamp));
            }
            if(rows.length()==0) throw new IllegalArgumentException("Missing fuel rows");
        } else throw new IllegalArgumentException("Unknown board");
        long sourceTime;
        if(kind==2) sourceTime=java.time.Instant.parse(date).toEpochMilli();
        else {
            java.time.format.DateTimeFormatter format=java.time.format.DateTimeFormatter.ofPattern(kind==0?"dd/MM/uuuu HH:mm":"M/d/uuuu h:mm:ss a",Locale.US).withResolverStyle(java.time.format.ResolverStyle.STRICT);
            sourceTime=java.time.LocalDateTime.parse(date,format).atZone(java.time.ZoneId.of("Asia/Ho_Chi_Minh")).toInstant().toEpochMilli();
        }
        return new JSONObject().put("rows",rows).put("date",date).put("sourceTime",sourceTime).put("unit",unit).put("source",SOURCES[kind]);
    }
    private static String fxAmount(String s) { return s.equals("-") ? "Không niêm yết" : amount(s,true); }
    static void validateJsonDepth(String body) {
        int depth=0; boolean quoted=false, escaped=false;
        for(int i=0;i<body.length();i++) {
            char c=body.charAt(i);
            if(quoted) { if(escaped)escaped=false; else if(c=='\\')escaped=true; else if(c=='"')quoted=false; }
            else if(c=='"')quoted=true;
            else if(c=='{' || c=='[') { if(++depth>16)throw new IllegalArgumentException("JSON too deep"); }
            else if(c=='}' || c==']') { if(--depth<0)throw new IllegalArgumentException("Invalid JSON"); }
        }
        if(depth!=0 || quoted)throw new IllegalArgumentException("Invalid JSON");
    }
    private static int fuelRank(String name) {
        if(name.equals("Xăng E10 RON 95-III"))return 0;
        if(name.startsWith("Xăng E5 RON 92"))return 1;
        if(name.equals("DO 0,05S-II"))return 2;
        return 3;
    }
}
