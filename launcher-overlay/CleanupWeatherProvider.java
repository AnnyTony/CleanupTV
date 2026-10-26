package io.github.sumyabazar1.weather;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.util.Base64;
import org.json.JSONObject;

/** ADB-only, city preferences only. No arbitrary URLs, paths or application settings. */
public final class CleanupWeatherProvider extends ContentProvider {
    @Override public Bundle call(String method, String arg, Bundle extras) {
        Bundle result = new Bundle();
        try {
            android.content.SharedPreferences p = getContext().getSharedPreferences("place", Context.MODE_PRIVATE);
            if ("write".equals(method)) {
                if (arg == null || arg.length() > 4096) throw new IllegalArgumentException("Invalid city");
                JSONObject city = new JSONObject(new String(Base64.decode(arg, Base64.DEFAULT), java.nio.charset.StandardCharsets.UTF_8));
                for (java.util.Iterator<String> it=city.keys();it.hasNext();) {
                    if (!java.util.Arrays.asList("name","latitude","longitude").contains(it.next())) throw new IllegalArgumentException("Unknown field");
                }
                android.content.SharedPreferences.Editor edit = p.edit();
                if (city.isNull("name")) edit.remove("name").remove("lat").remove("lon");
                else {
                    String name=city.getString("name"); double lat=city.getDouble("latitude"),lon=city.getDouble("longitude");
                    if(name.isEmpty() || name.length()>120 || !Double.isFinite(lat) || !Double.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) throw new IllegalArgumentException("Invalid city");
                    edit.putString("name",name).putLong("lat",Double.doubleToLongBits(lat)).putLong("lon",Double.doubleToLongBits(lon));
                }
                if(!edit.commit()) throw new IllegalStateException("Cannot save city");
            } else if (!"read".equals(method)) throw new IllegalArgumentException("Unknown method");
            JSONObject city = new JSONObject().put("name",p.contains("name")?p.getString("name",""):JSONObject.NULL)
                .put("latitude",p.contains("lat")?Double.longBitsToDouble(p.getLong("lat",0)):JSONObject.NULL)
                .put("longitude",p.contains("lon")?Double.longBitsToDouble(p.getLong("lon",0)):JSONObject.NULL);
            JSONObject value = new JSONObject().put("version",1).put("values",city);
            result.putString("payload",Base64.encodeToString(value.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8),Base64.NO_WRAP));
        } catch(Exception error) { result.putString("error",error.getMessage()); }
        return result;
    }
    @Override public boolean onCreate() { return true; }
    @Override public String getType(Uri uri) { return null; }
    @Override public Cursor query(Uri u,String[] p,String s,String[] a,String o) { return null; }
    @Override public Uri insert(Uri u,ContentValues v) { return null; }
    @Override public int update(Uri u,ContentValues v,String s,String[] a) { return 0; }
    @Override public int delete(Uri u,String s,String[] a) { return 0; }
}
