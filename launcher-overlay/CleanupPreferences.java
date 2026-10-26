package com.gathin.tvhome;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/** The same bounded preference keys are used by the remote UI and the shell-only provider. */
final class CleanupPreferences {
    static final String[] KEYS = {"columns", "rows_below_dock", "animations", "advanced_effects",
        "dock_opacity", "wallpaper_choice", "cyt_lunar", "cyt_name", "cyt_greeting", "cyt_background", "cyt_dim"};
    private static final Set<String> ALLOWED = new HashSet<>(Arrays.asList(KEYS));
    static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(Config.SETTINGS_NAME, Context.MODE_PRIVATE);
    }
    static JSONObject read(Context context) throws Exception {
        Config.load(context); // synchronize any externally changed theme first
        SharedPreferences p = prefs(context);
        JSONObject json = new JSONObject();
        for (String key : KEYS) json.put(key, p.contains(key) ? p.getAll().get(key) : JSONObject.NULL);
        return json;
    }
    static void validate(String key, Object value) throws Exception {
        if (!ALLOWED.contains(key)) throw new IllegalArgumentException("Unsupported preference");
        if (value == JSONObject.NULL) return;
        if (Arrays.asList("animations", "advanced_effects", "cyt_lunar", "cyt_greeting").contains(key)) {
            if (!(value instanceof Boolean)) throw new IllegalArgumentException("Boolean required");
        } else if (Arrays.asList("columns", "rows_below_dock", "dock_opacity", "cyt_dim").contains(key)) {
            if (!(value instanceof Integer)) throw new IllegalArgumentException("Integer required");
            int n = (Integer) value;
            if ((key.equals("columns") && (n < 4 || n > 7)) ||
                (key.equals("rows_below_dock") && (n < 0 || n > 3)) ||
                (key.equals("dock_opacity") && (n < 30 || n > 100)) ||
                (key.equals("cyt_dim") && (n < 0 || n > 90))) throw new IllegalArgumentException("Out of range");
        } else {
            if (!(value instanceof String)) throw new IllegalArgumentException("String required");
            String s = (String) value;
            if (key.equals("cyt_name") && (s.length() > 60 || s.matches("(?s).*[\\p{Cntrl}].*"))) throw new IllegalArgumentException("Invalid name");
            if (key.equals("cyt_background") && !s.matches("#[0-9a-fA-F]{6}")) throw new IllegalArgumentException("Invalid colour");
            if (key.equals("wallpaper_choice") && !s.equals("none") && !s.matches("[A-Za-z0-9_.-]+\\.(jpg|jpeg|png|webp)")) throw new IllegalArgumentException("Invalid wallpaper");
        }
    }
    static void write(Context context, JSONObject json) throws Exception {
        for (java.util.Iterator<String> it = json.keys(); it.hasNext();) {
            String key = it.next(); validate(key, json.get(key));
        }
        SharedPreferences p = prefs(context);
        SharedPreferences.Editor e = p.edit();
        for (java.util.Iterator<String> it = json.keys(); it.hasNext();) {
            String key = it.next(); Object value = json.get(key);
            if (value == JSONObject.NULL) e.remove(key);
            else if (value instanceof Boolean) e.putBoolean(key, (Boolean) value);
            else if (value instanceof Integer) e.putInt(key, (Integer) value);
            else e.putString(key, (String) value);
        }
        e.putLong(Config.SETTINGS_REVISION_KEY, p.getLong(Config.SETTINGS_REVISION_KEY, 0) + 1);
        if (!e.commit()) throw new IllegalStateException("Cannot save preferences");
    }
    static String importPicture(Context context, android.net.Uri uri) throws Exception {
        BitmapFactory.Options options = new BitmapFactory.Options(); options.inJustDecodeBounds = true;
        try (java.io.InputStream in = context.getContentResolver().openInputStream(uri)) { BitmapFactory.decodeStream(in, null, options); }
        if (options.outWidth <= 0 || options.outHeight <= 0 || (long)options.outWidth * options.outHeight > 100_000_000L)
            throw new IllegalArgumentException("Ảnh không hợp lệ hoặc quá lớn.");
        options.inJustDecodeBounds = false;
        options.inSampleSize = 1;
        while (options.outWidth / options.inSampleSize > 1920 || options.outHeight / options.inSampleSize > 1080) {
            options.inSampleSize = options.inSampleSize < 1 ? 2 : options.inSampleSize * 2;
        }
        Bitmap bitmap;
        try (java.io.InputStream in = context.getContentResolver().openInputStream(uri)) { bitmap = BitmapFactory.decodeStream(in, null, options); }
        if (bitmap == null) throw new IllegalArgumentException("Không đọc được ảnh.");
        java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
        try { bitmap.compress(Bitmap.CompressFormat.JPEG, 80, bytes); } finally { bitmap.recycle(); }
        byte[] data = bytes.toByteArray();
        if (data.length > 1_000_000) throw new IllegalArgumentException("Ảnh sau thu nhỏ vẫn quá lớn.");
        StringBuilder hash = new StringBuilder();
        for (byte b : MessageDigest.getInstance("SHA-256").digest(data)) hash.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
        String name = "cyt-" + hash.substring(0, 24) + ".jpg";
        File folder = new File(Config.dir(context), "wallpapers");
        if (!folder.isDirectory() && !folder.mkdirs()) throw new IllegalStateException("Không lưu được ảnh.");
        File[] current = folder.listFiles((d, n) -> n.startsWith("cyt-"));
        File target = new File(folder, name);
        if (!target.exists() && current != null && current.length >= 12) throw new IllegalStateException("Đã có 12 ảnh cá nhân. Dùng ảnh đã lưu.");
        try (FileOutputStream out = new FileOutputStream(target)) { out.write(data); }
        write(context, new JSONObject().put("wallpaper_choice", name));
        return name;
    }
}
