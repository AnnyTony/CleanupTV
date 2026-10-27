package com.gathin.tvhome;

import org.junit.Test;
import static org.junit.Assert.*;
import org.json.JSONObject;

public class CleanupMarketDataTest {
    private String gold() {
        StringBuilder s=new StringBuilder("ĐVT 1 = 1.000 VNĐ Cập nhật lúc 26/10/2026 09:01<table>");
        for(String name:new String[]{"VÀNG MIẾNG SJC","NHẪN TRÒN TRƠN BẢO TÍN MINH CHÂU","TRANG SỨC VÀNG RỒNG THĂNG LONG 999.9"})
            s.append("<tr><td>").append(name).append("</td><td>999.9</td><td><b>12345</b></td><td>12789</td></tr>");
        return s.append("</table>").toString();
    }
    private String fx(String buy) { return "<ExrateList><DateTime>10/27/2026 6:45:18 AM</DateTime><Exrate Sell=\"26,000.50\" CurrencyCode=\"USD\" Buy=\""+buy+"\" Transfer=\"25,500.25\" /></ExrateList>"; }
    @Test public void goldKeepsRawThousandUnitAndFiltersExactRows() throws Exception {
        JSONObject p=CleanupMarketData.parse(0,gold(),"USD",1);
        assertEquals(3,p.getJSONArray("rows").length());
        assertEquals("12.345",p.getJSONArray("rows").getJSONObject(0).getString("buy"));
        assertTrue(p.getString("unit").startsWith("Nghìn VND"));
        assertTrue(p.getLong("sourceTime")>0);
    }
    @Test(expected=Exception.class) public void goldRejectsChangedUnits() throws Exception { CleanupMarketData.parse(0,gold().replace("1.000 VNĐ","VND/lượng"),"USD",1); }
    @Test(expected=Exception.class) public void goldRejectsMissingTimestamp() throws Exception { CleanupMarketData.parse(0,gold().replace("Cập nhật lúc","Date"),"USD",1); }
    @Test(expected=Exception.class) public void goldRejectsPartialTable() throws Exception { CleanupMarketData.parse(0,gold().replace("VÀNG MIẾNG SJC","Khác"),"USD",1); }
    @Test public void fxDistinguishesThreeQuotesAndMissingCash() throws Exception {
        JSONObject p=CleanupMarketData.parse(1,fx("-"),"USD",1);
        assertEquals("Không niêm yết",p.getJSONArray("rows").getJSONObject(0).getString("value"));
        assertEquals("25.500,25",p.getJSONArray("rows").getJSONObject(1).getString("value"));
        assertEquals("26.000,5",p.getJSONArray("rows").getJSONObject(2).getString("value"));
    }
    @Test(expected=Exception.class) public void fxRejectsWrongCurrency() throws Exception { CleanupMarketData.parse(1,fx("25,000"),"EUR",1); }
    @Test(expected=Exception.class) public void rejectsEntities() throws Exception { CleanupMarketData.parse(1,"<!ENTITY x 'abc'>"+fx("25,000"),"USD",1); }
    @Test(expected=Exception.class) public void rejectsInvalidNumbers() throws Exception { CleanupMarketData.parse(1,fx("NaN"),"USD",1); }
    @Test(expected=Exception.class) public void rejectsInvalidSourceDate() throws Exception { CleanupMarketData.parse(1,fx("25,000").replace("10/27/2026","99/99/2026"),"USD",1); }
    @Test public void fuelPreservesGradeRegionAndPerProductDates() throws Exception {
        String source="{\"Objects\":[{\"Title\":\"Xăng E10 RON 95-III\",\"Zone1Price\":24000,\"Zone2Price\":24500,\"LastModified\":\"2026-10-22T07:55:21Z\"}]}";
        JSONObject p=CleanupMarketData.parse(2,source,"USD",2);
        JSONObject r=p.getJSONArray("rows").getJSONObject(0);
        assertEquals("Xăng E10 RON 95-III",r.getString("name"));
        assertEquals("24.500",r.getString("value")); assertTrue(p.getString("unit").endsWith("Vùng 2"));
        assertEquals("2026-10-22T07:55:21Z",r.getString("date"));
    }
    @Test(expected=Exception.class) public void fuelDoesNotInventEmptyPrices() throws Exception { CleanupMarketData.parse(2,"{\"Objects\":[]}","USD",1); }
    @Test public void fuelRequestUsesOnlyPublishedPublicFilter() throws Exception {
        String url=CleanupMarketData.fuelUrl(); assertTrue(url.startsWith("https://portals.petrolimex.com.vn/~apis/portals/cms.item/search?x-request="));
        String json=new String(java.util.Base64.getUrlDecoder().decode(url.split("x-request=")[1]),java.nio.charset.StandardCharsets.UTF_8);
        assertTrue(json.contains("Published")); assertFalse(json.contains("token"));
    }
    @Test(expected=Exception.class) public void rejectsDeepJsonBeforeAndroidParser() throws Exception {
        CleanupMarketData.validateJsonDepth("[".repeat(17)+"]".repeat(17));
    }
    @Test public void jsonDepthIgnoresQuotedBracesAndEscapedQuotes() {
        CleanupMarketData.validateJsonDepth("{\"name\":\"[[[\\\"{{{\"}");
    }
    @Test(expected=Exception.class) public void rejectsUnboundedNumericField() {
        CleanupMarketData.amount("9".repeat(1000),true);
    }
}
