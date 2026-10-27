package com.gathin.tvhome;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.util.Base64;
import org.json.JSONObject;

/** Protected by WRITE_SECURE_SETTINGS in the manifest. No network or arbitrary file API. */
public final class CleanupProvider extends ContentProvider {
    @Override public Bundle call(String method, String arg, Bundle extras) {
        Bundle result = new Bundle();
        try {
            if ("write".equals(method)) {
                if (arg == null || arg.length() > 8192) throw new IllegalArgumentException("Invalid payload");
                CleanupPreferences.write(getContext(), new JSONObject(new String(Base64.decode(arg, Base64.DEFAULT), java.nio.charset.StandardCharsets.UTF_8)));
            } else if (!"read".equals(method)) throw new IllegalArgumentException("Unknown method");
            JSONObject value = new JSONObject().put("version", 1).put("marketVersion", 1).put("values", CleanupPreferences.read(getContext()));
            Config config = Config.load(getContext());
            value.put("effective", new JSONObject().put("columns",config.columns).put("cyt_lunar",config.lunarDate)
                .put("cyt_name",config.greetingName).put("cyt_greeting",config.showGreeting).put("animations",config.animations)
                .put("cyt_background",String.format(java.util.Locale.ROOT,"#%06X",config.backgroundColor & 0xffffff)).put("cyt_dim",config.wallpaperDim));
            java.io.File folder = new java.io.File(Config.dir(getContext()), "wallpapers");
            org.json.JSONArray pictures = new org.json.JSONArray();
            java.io.File[] files = folder.listFiles((dir, name) -> name.matches("[A-Za-z0-9_.-]+\\.(jpg|jpeg|png|webp)"));
            if (files != null) for (java.io.File file : files) if (pictures.length() < 100) pictures.put(file.getName());
            value.put("pictures", pictures);
            result.putString("payload", Base64.encodeToString(value.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8), Base64.NO_WRAP));
        } catch (Exception error) { result.putString("error", error.getMessage()); }
        return result;
    }
    @Override public boolean onCreate() { return true; }
    @Override public String getType(Uri uri) { return null; }
    @Override public Cursor query(Uri u, String[] p, String s, String[] a, String o) { return null; }
    @Override public Uri insert(Uri u, ContentValues v) { return null; }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { return 0; }
    @Override public int delete(Uri u, String s, String[] a) { return 0; }
}
