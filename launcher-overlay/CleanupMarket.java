package com.gathin.tvhome;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.JSONArray;
import org.json.JSONObject;

/** Optional Home-only cards. One process-wide worker, no service, alarm, account or WebView. */
final class CleanupMarket {
    private static final ExecutorService WORK = Executors.newSingleThreadExecutor(r -> { Thread t=new Thread(r,"CleanupMarket"); t.setDaemon(true); return t; });
    private static final AtomicBoolean BUSY = new AtomicBoolean();
    private static final long INTERVAL=15*60_000L;
    private static final long[] LAST_ATTEMPT_UPTIME={-1,-1,-1}; // accessed only by WORK
    private final Activity activity;
    private final LinearLayout row;
    private final SharedPreferences cache;
    private final TextView[] cards=new TextView[3];
    private final JSONObject[] displayed=new JSONObject[3];
    private final Handler handler=new Handler(Looper.getMainLooper());
    private volatile boolean active;
    private volatile long generation;
    private final Runnable tick=this::refresh;
    private final String currency;
    private final int zone;
    private final boolean[] enabled=new boolean[3];

    CleanupMarket(Activity activity) {
        this.activity=activity;
        row=activity.findViewById(R.id.cleanupMarket);
        cache=activity.getSharedPreferences("cleanup_market_cache_v1",Activity.MODE_PRIVATE);
        SharedPreferences choices=CleanupPreferences.prefs(activity);
        currency=choices.getString("cyt_currency","USD"); zone=choices.getInt("cyt_fuel_zone",1);
        String[] keys={"cyt_gold","cyt_fx","cyt_fuel"};
        int[] accents={0xFFFFD16D,0xFFA7CEFF,0xFF79E2BE};
        for(int i=0;i<3;i++) {
            enabled[i]=choices.getBoolean(keys[i],false); if(!enabled[i]) continue;
            final int kind=i;
            TextView card=new TextView(activity); cards[i]=card;
            card.setId(View.generateViewId()); card.setFocusable(true); card.setClickable(true);
            card.setTextColor(Color.WHITE); card.setTextSize(13); card.setPadding(dp(12),dp(9),dp(12),dp(8));
            card.setAutoSizeTextTypeUniformWithConfiguration(10,13,1,android.util.TypedValue.COMPLEX_UNIT_SP);
            card.setFontFeatureSettings("tnum"); card.setText(CleanupMarketData.TITLES[i]+"\nChưa có dữ liệu");
            LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(174),1); lp.setMargins(dp(3),dp(7),dp(3),0); row.addView(card,lp);
            card.setBackground(background(accents[i],false));
            card.setOnFocusChangeListener((v,focus)->v.setBackground(background(accents[kind],focus)));
            card.setOnClickListener(v->details(kind));
            card.setNextFocusDownId(R.id.grid);
        }
        row.setVisibility(row.getChildCount()==0 ? View.GONE : View.VISIBLE);
        if(row.getChildCount()>0) focusDown(activity.findViewById(R.id.topButtons),row.getChildAt(0).getId());
    }
    private int dp(int n) { return Math.round(n*activity.getResources().getDisplayMetrics().density); }
    private GradientDrawable background(int color,boolean focused) {
        GradientDrawable d=new GradientDrawable(); d.setColor(focused ? 0xF0283C51 : 0xE6182433); d.setCornerRadius(dp(12)); d.setStroke(dp(focused?2:1),focused?Color.WHITE:color); return d;
    }
    private void focusDown(View v,int id) { if(v==null)return; v.setNextFocusDownId(id); if(v instanceof ViewGroup) for(int i=0;i<((ViewGroup)v).getChildCount();i++) focusDown(((ViewGroup)v).getChildAt(i),id); }
    void resume() { if(row.getChildCount()==0)return; active=true; generation++; refresh(); }
    void pause() {
        active=false; generation++; handler.removeCallbacksAndMessages(null);
        // The single in-flight bounded request may finish; it cannot publish or start another fetch.
    }
    private void refresh() {
        handler.removeCallbacks(tick); if(!active)return;
        // Refresh UI age and cached values on each visit; enforce attempt limits across visits/restarts.
        if(BUSY.compareAndSet(false,true)) {
            final long ticket=generation;
            WORK.execute(()->{
                try {
                    for(int kind=0;kind<3 && active && generation==ticket;kind++) if(enabled[kind]) load(kind,ticket);
                } finally { BUSY.set(false); }
            });
        }
        handler.postDelayed(tick,60_000L);
    }
    private boolean current(long ticket) { return active && generation==ticket; }
    private void load(int kind,long ticket) {
        String prefix="board"+kind; long now=System.currentTimeMillis();
        String body=cache.getString(prefix+"body",""); long fetched=cache.getLong(prefix+"fetched",0);
        boolean failed=cache.getBoolean(prefix+"failed",false);
        publish(kind,body,fetched,failed,ticket);
        long last=cache.getLong(prefix+"attempt",0), wait=kind==2?6*60*60_000L:INTERVAL;
        long uptime=android.os.SystemClock.elapsedRealtime();
        if(!current(ticket) || now<1_735_689_600_000L || (last>0 && (now<last || now-last<wait)) ||
            (LAST_ATTEMPT_UPTIME[kind]>=0 && uptime-LAST_ATTEMPT_UPTIME[kind]<wait))return;
        // Persist before the request, including failures. Remote buttons cannot bypass the rate limit.
        cache.edit().putLong(prefix+"attempt",now).commit();
        LAST_ATTEMPT_UPTIME[kind]=uptime;
        try {
            String fresh=fetch(CleanupMarketData.url(kind),ticket);
            CleanupMarketData.parse(kind,fresh,currency,zone); // reject changed tables before replacing a good cache
            if(!current(ticket))return;
            fetched=System.currentTimeMillis();
            cache.edit().putString(prefix+"body",fresh).putLong(prefix+"fetched",fetched).putBoolean(prefix+"failed",false).commit();
            publish(kind,fresh,fetched,false,ticket);
        } catch(Exception error) {
            if(!current(ticket))return;
            cache.edit().putBoolean(prefix+"failed",true).commit();
            publish(kind,body,fetched,true,ticket);
        }
    }
    private String fetch(String address,long ticket) throws Exception {
        if(!current(ticket))throw new java.io.IOException("Paused");
        HttpURLConnection c=(HttpURLConnection)new URL(address).openConnection();
        try {
            c.setInstanceFollowRedirects(false); c.setConnectTimeout(6000); c.setReadTimeout(6000);
            c.setRequestProperty("User-Agent","CleanupTV/0.6 (public price board)");
            if(c.getResponseCode()!=200)throw new java.io.IOException("Source unavailable");
            if(c.getContentLengthLong()>300000)throw new java.io.IOException("Response too large");
            long deadline=android.os.SystemClock.elapsedRealtime()+12_000L;
            try(java.io.InputStream in=c.getInputStream(); java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream()) {
                byte[] buffer=new byte[8192]; int count;
                while((count=in.read(buffer))!=-1) {
                    if(!current(ticket) || android.os.SystemClock.elapsedRealtime()>deadline || out.size()+count>300000)throw new java.io.IOException("Response stopped");
                    out.write(buffer,0,count);
                }
                return out.toString(StandardCharsets.UTF_8.name());
            }
        } finally { c.disconnect(); }
    }
    private void publish(int kind,String body,long fetched,boolean failed,long ticket) {
        JSONObject value=null;
        try { value=CleanupMarketData.parse(kind,body,currency,zone); value.put("fetched",fetched).put("failed",failed); } catch(Exception ignored) { }
        final JSONObject data=value;
        handler.post(()->{ if(current(ticket) && !activity.isFinishing() && !activity.isDestroyed()) { displayed[kind]=data; draw(kind,data,failed); } });
    }
    private String checked(long time) {
        java.text.SimpleDateFormat f=new java.text.SimpleDateFormat("HH:mm dd/MM",java.util.Locale.ROOT); f.setTimeZone(java.util.TimeZone.getTimeZone("Asia/Ho_Chi_Minh"));
        return f.format(new java.util.Date(time))+" (VN)";
    }
    private void draw(int kind,JSONObject data,boolean failed) {
        TextView card=cards[kind]; if(card==null)return;
        String title=CleanupMarketData.TITLES[kind]+(kind==1?" · "+currency:"");
        if(data==null) { card.setText(title+"\n\nChưa có giá để hiển thị\n"+(failed?"Chưa tải được nguồn":"Đang chờ dữ liệu")+"\n"+CleanupMarketData.SOURCES[kind]+"\nOK: hướng dẫn / nguồn"); return; }
        StringBuilder text=new StringBuilder(title).append('\n').append(data.optString("unit"));
        if(kind==0)text.append("\nMua / Bán");
        JSONArray rows=data.optJSONArray("rows");
        for(int i=0;i<rows.length();i++) {
            JSONObject r=rows.optJSONObject(i);
            text.append('\n').append(r.optString("name")).append("  ").append(kind==0?r.optString("buy")+" / "+r.optString("sell"):r.optString("value"));
        }
        long age=System.currentTimeMillis()-data.optLong("fetched");
        long sourceAge=System.currentTimeMillis()-data.optLong("sourceTime");
        text.append('\n').append(CleanupMarketData.SOURCES[kind]).append(" · ").append(checked(data.optLong("sourceTime")));
        if(sourceAge<0 || sourceAge>(kind==2?45L*24*60*60_000L:36*60*60_000L)) text.append(" · MỐC CŨ/CHƯA HỢP LỆ");
        text.append('\n').append(failed?"Chưa cập nhật · bản lưu":age<0 || age>(kind==2?6*60*60_000L:INTERVAL)?"Bản lưu · cần kiểm tra":"Đã kiểm tra "+checked(data.optLong("fetched")));
        text.append("\nOK: ngày niêm yết / chi tiết");
        card.setText(text); card.setContentDescription(text.toString());
    }
    private void details(int kind) {
        JSONObject data=displayed[kind];
        StringBuilder text=new StringBuilder("Nguồn: ").append(CleanupMarketData.SOURCES[kind]).append("\n");
        if(data!=null) {
            text.append("Mốc nguồn công bố: ").append(data.optString("date")).append(kind==2?" (UTC)":kind==1?" (định dạng tháng/ngày/năm của nguồn)":" (VN)");
            text.append("\nTV tải thành công lúc: ").append(checked(data.optLong("fetched")));
            text.append("\n").append(data.optString("unit")).append("\n");
            JSONArray rows=data.optJSONArray("rows");
            for(int i=0;i<rows.length();i++) {
                JSONObject r=rows.optJSONObject(i); text.append('\n').append(r.optString("name")).append(": ");
                text.append(kind==0?"Mua "+r.optString("buy")+" · Bán "+r.optString("sell"):r.optString("value"));
                if(kind==2)text.append("\nMốc mặt hàng: ").append(r.optString("date")).append(" UTC");
            }
        } else text.append("Chưa có dữ liệu được xác minh. Không dùng giá mẫu thay cho giá thật.");
        text.append("\n\nChỉ tham khảo. Tải thành công không có nghĩa nhà cung cấp vừa thay giá. Kiểm tra mốc nguồn trước khi sử dụng. Không tự suy đoán tăng/giảm.");
        if(kind==0)text.append("\nGiữ nguyên bảng nghìn VND của BTMC tại Hà Nội; không tự quy đổi chỉ/lượng hay áp dụng cho cửa hàng khác.");
        text.append("\nTự kiểm tra khi Home đang mở: vàng/ngoại tệ mỗi 15 phút, xăng mỗi 6 giờ. Tắt trong Cá nhân hóa TV.");
        String url=kind==0?"https://btmc.vn/gia-vang-theo-ngay.html":kind==1?"https://www.vietcombank.com.vn/KHCN/Cong-cu-tien-ich/Ty-gia":"https://petrolimex.com.vn/thong-tin-khach-hang.html";
        text.append("\n\n").append(url);
        TextView content=new TextView(activity); content.setText(text); content.setTextSize(18); content.setPadding(dp(20),dp(10),dp(20),dp(10));
        android.widget.ScrollView scroll=new android.widget.ScrollView(activity); scroll.addView(content); scroll.setFocusable(true);
        new AlertDialog.Builder(activity).setTitle(CleanupMarketData.TITLES[kind]).setView(scroll).setPositiveButton("Đóng",null).setNeutralButton("Cá nhân hóa TV",(d,n)->activity.startActivity(new android.content.Intent(activity,CleanupSettingsActivity.class))).show();
    }
}
