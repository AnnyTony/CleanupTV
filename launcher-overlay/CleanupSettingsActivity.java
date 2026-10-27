package com.gathin.tvhome;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.widget.*;
import org.json.JSONObject;

/** Small remote-friendly controls. Calendar is offline; weather is a separate optional app. */
public final class CleanupSettingsActivity extends Activity {
    private LinearLayout body;
    private static final int PICK_IMAGE = 51;
    @Override public void onCreate(Bundle state) { super.onCreate(state); render(); }
    private void row(String title, Runnable action) {
        Button button = new Button(this); button.setText(title); button.setAllCaps(false);
        button.setTextSize(21); button.setOnClickListener(v -> action.run());
        body.addView(button, new LinearLayout.LayoutParams(-1, -2));
    }
    private void save(String key, Object value) {
        try { CleanupPreferences.write(this, new JSONObject().put(key, value)); render(); }
        catch (Exception error) { message(error.getMessage()); }
    }
    private void message(String text) { Toast.makeText(this, text, Toast.LENGTH_LONG).show(); }
    private void render() {
        ScrollView scroll = new ScrollView(this); scroll.setBackgroundColor(Color.rgb(16,20,25));
        body = new LinearLayout(this); body.setOrientation(LinearLayout.VERTICAL);
        int pad = (int)(36 * getResources().getDisplayMetrics().density); body.setPadding(pad,pad,pad,pad);
        scroll.addView(body); setContentView(scroll);
        Config config = Config.load(this);
        TextView title = new TextView(this); title.setText("Cá nhân hóa TV"); title.setTextSize(30); title.setTextColor(Color.WHITE); body.addView(title);
        row("Bố cục · " + config.columns + " cột", () -> new AlertDialog.Builder(this).setTitle("Số ứng dụng mỗi hàng").setItems(new String[]{"4 cột", "5 cột", "6 cột", "7 cột"}, (d,n) -> save("columns", n+4)).show());
        row("Lịch âm Việt Nam · " + (config.lunarDate ? "Bật" : "Tắt"), () -> save("cyt_lunar", !config.lunarDate));
        row("Lời chào · " + (config.showGreeting ? "Bật" : "Tắt"), () -> save("cyt_greeting", !config.showGreeting));
        row("Tên trong lời chào", () -> {
            EditText name = new EditText(this); name.setSingleLine(true); name.setText(config.greetingName);
            name.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(60)});
            new AlertDialog.Builder(this).setTitle("Tên hiển thị").setView(name).setPositiveButton("Lưu", (d,n) -> save("cyt_name", name.getText().toString().trim())).setNegativeButton("Hủy",null).show();
        });
        row("Màu nền", () -> new AlertDialog.Builder(this).setTitle("Màu nền").setItems(new String[]{"Đen", "Xanh đậm", "Xanh lá đậm", "Nâu đậm"}, (d,n) -> save("cyt_background", new String[]{"#000000","#101827","#10251E","#261C17"}[n])).show());
        row("Chọn ảnh nền đã lưu / tắt ảnh", this::pictures);
        row("Thêm ảnh từ TV hoặc USB", () -> {
            try { startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("image/*"), PICK_IMAGE); }
            catch (android.content.ActivityNotFoundException error) { message("TV không có trình chọn ảnh. Dùng CleanupTV trên máy tính để gửi ảnh."); }
        });
        row("Độ tối ảnh nền · " + config.wallpaperDim + "%", () -> new AlertDialog.Builder(this).setTitle("Độ tối ảnh nền").setItems(new String[]{"0%", "20%", "40%", "60%", "80%"}, (d,n) -> save("cyt_dim", n*20)).show());
        row("Thời tiết · chọn hoặc đổi thành phố", () -> {
            try { startActivity(new Intent().setClassName("io.github.sumyabazar1.weather", "io.github.sumyabazar1.weather.WeatherActivity")); }
            catch (android.content.ActivityNotFoundException error) { message("Chưa cài mô-đun Thời tiết. Chuẩn bị bằng CleanupTV trên máy tính."); }
        });
        SharedPreferencesHolder prices = new SharedPreferencesHolder(this);
        TextView note = new TextView(this); note.setText("Bảng giá trên Home · tùy chọn. Khi bật, TV gửi yêu cầu HTTPS đến BTMC, Vietcombank và Petrolimex. Không cần máy tính; chỉ tải khi Home đang mở. Nguồn và mốc niêm yết nằm trong từng bảng. Giá chỉ tham khảo."); note.setTextColor(Color.LTGRAY); note.setTextSize(17); body.addView(note);
        priceToggle("Giá vàng · BTMC Hà Nội", "cyt_gold", prices);
        priceToggle("Tỷ giá ngoại tệ · Vietcombank", "cyt_fx", prices);
        priceToggle("Giá xăng dầu · Petrolimex", "cyt_fuel", prices);
        row("Ngoại tệ · " + prices.p.getString("cyt_currency", "USD"), () -> {
            String[] currencies = {"USD","EUR","JPY","AUD","GBP","SGD","THB","CNY","KRW","CAD"};
            new AlertDialog.Builder(this).setTitle("Ngoại tệ hiển thị").setItems(currencies,(d,n)->save("cyt_currency",currencies[n])).show();
        });
        row("Giá xăng dầu · Vùng " + prices.p.getInt("cyt_fuel_zone",1), () -> new AlertDialog.Builder(this).setTitle("Khu vực giá Petrolimex").setMessage("Vùng 2 là địa bàn theo danh mục của Petrolimex, không phải miền Bắc/Nam. Kiểm tra cửa hàng đang mua trước khi chọn.").setPositiveButton("Vùng 1",(d,n)->save("cyt_fuel_zone",1)).setNeutralButton("Vùng 2",(d,n)->save("cyt_fuel_zone",2)).setNegativeButton("Hủy",null).show());
        row("Theo giao diện mặc định", () -> new AlertDialog.Builder(this).setTitle("Bỏ các lựa chọn cá nhân?").setMessage("Giữ ứng dụng và ảnh đã lưu. Dùng lại thiết lập của giao diện đang có.").setPositiveButton("Khôi phục", (d,n) -> {
            try { JSONObject empty = new JSONObject(); for (String key : CleanupPreferences.KEYS) empty.put(key, JSONObject.NULL); CleanupPreferences.write(this, empty); render(); } catch (Exception error) { message(error.getMessage()); }
        }).setNegativeButton("Hủy",null).show());
        row("Xong · về Màn hình chính", () -> { startActivity(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)); finish(); });
    }
    private static final class SharedPreferencesHolder {
        final android.content.SharedPreferences p;
        SharedPreferencesHolder(Activity a) { p=CleanupPreferences.prefs(a); }
    }
    private void priceToggle(String title, String key, SharedPreferencesHolder holder) {
        boolean on=holder.p.getBoolean(key,false);
        row(title+" · "+(on?"Bật":"Tắt"), () -> {
            if(on) save(key,false);
            else new AlertDialog.Builder(this).setTitle("Bật "+title+"?").setMessage("TV sẽ truy cập nguồn giá công khai qua Internet khi Home mở. Giá có thể chậm hoặc chưa tải được; không thay cho niêm yết tại nơi giao dịch. Có thể tắt lại bất cứ lúc nào.").setPositiveButton("Bật",(d,n)->save(key,true)).setNegativeButton("Hủy",null).show();
        });
    }
    private void pictures() {
        java.io.File dir = Config.dir(this);
        java.util.List<java.io.File> files = WallpaperRotation.images(new java.io.File(dir, "wallpapers"));
        String[] names = new String[files.size()+2]; names[0] = "Không dùng ảnh nền"; names[1] = "Theo giao diện mặc định";
        for(int i=0;i<files.size();i++) names[i+2]=files.get(i).getName();
        new AlertDialog.Builder(this).setTitle("Ảnh nền").setItems(names, (d,n) -> save("wallpaper_choice", n==0 ? "none" : n==1 ? JSONObject.NULL : names[n])).show();
    }
    @Override public void onActivityResult(int request, int result, Intent intent) {
        super.onActivityResult(request,result,intent);
        if(request==PICK_IMAGE && result==RESULT_OK && intent!=null && intent.getData()!=null) {
            try { CleanupPreferences.importPicture(this,intent.getData()); render(); }
            catch(Exception error) { message("Chưa nhập được ảnh: " + error.getMessage()); }
        }
    }
}
