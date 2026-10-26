"""Reproducible launcher overlay and bounded customization of its private preferences."""
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import urllib.parse
import urllib.request
import zipfile

WEATHER = "io.github.sumyabazar1.weather"
LAUNCHER = "com.gathin.tvhome"
KEYS = {"columns", "rows_below_dock", "animations", "advanced_effects", "dock_opacity", "wallpaper_choice",
        "cyt_lunar", "cyt_name", "cyt_greeting", "cyt_background", "cyt_dim"}


def overlay_hash(root):
    files = [Path(__file__), *sorted(p for p in (root / "launcher-overlay").rglob("*") if p.is_file())]
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def prepare_overlay(root, source, weather=False):
    """Always patch pristine pinned files, never accumulate modifications between builds."""
    manifest = json.loads((root / "downloads.json").read_text())
    archive = root / ".runtime/source.zip"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["source"]["sha256"]:
        raise ValueError("Source không còn khớp SHA256. Xóa dấu .complete của source rồi chuẩn bị lại.")
    project = source / ("addons/weather" if weather else "launcher")
    java_dir = project / "app/src/main/java" / ("io/github/sumyabazar1/weather" if weather else "com/gathin/tvhome")
    with zipfile.ZipFile(archive) as z:
        prefix = z.namelist()[0].split("/")[0] + "/"
        def original(relative):
            return z.read(prefix + project.relative_to(source).as_posix() + "/" + relative).decode("utf-8")
        android_manifest = original("app/src/main/AndroidManifest.xml")
        if weather:
            files = ["CleanupWeatherProvider.java"]
            declaration = '<provider android:name=".CleanupWeatherProvider" android:authorities="io.github.sumyabazar1.weather.cleanup" android:exported="true" android:permission="android.permission.WRITE_SECURE_SETTINGS" />'
            vietnamese = project / "app/src/main/res/values-vi"
            vietnamese.mkdir(exist_ok=True)
            shutil.copyfile(root / "launcher-overlay/weather-vi.xml", vietnamese / "strings.xml")
            activity = original("app/src/main/java/io/github/sumyabazar1/weather/WeatherActivity.java")
            fixes = {
                "    private boolean shown;": "    private boolean active;\n    private boolean shown;",
                "        super.onResume();": "        super.onResume();\n        active = true;",
                "        super.onPause();": "        super.onPause();\n        active = false;",
                "    private void refresh() {": "    private void refresh() {\n        if (!active || isFinishing() || isDestroyed()) return;",
                "                if (isDestroyed()) return;\n                if (result != null) show(result);": "                if (isDestroyed() || !active) return;\n                if (result != null) show(result);",
            }
            for anchor, replacement in fixes.items():
                if activity.count(anchor) != 1:
                    raise ValueError("Source Weather khác phiên bản đã rà soát; chưa vá hoặc build.")
                activity = activity.replace(anchor, replacement)
            (java_dir / "WeatherActivity.java").write_text(activity, encoding="utf-8")
        else:
            files = ["CleanupPreferences.java", "CleanupProvider.java", "CleanupSettingsActivity.java"]
            declaration = '<provider android:name=".CleanupProvider" android:authorities="com.gathin.tvhome.cleanup" android:exported="true" android:permission="android.permission.WRITE_SECURE_SETTINGS" /><activity android:name=".CleanupSettingsActivity" android:exported="true" android:screenOrientation="landscape" />'
            config = original("app/src/main/java/com/gathin/tvhome/Config.java")
            anchor = "        // A festive skin comes only from a theme;"
            if config.count(anchor) != 1:
                raise ValueError("Source Config khác phiên bản đã rà soát; chưa vá hoặc build.")
            config = config.replace(anchor, '''        // CleanupTV: private choices shared by the remote controls and ADB-only provider.
        lunar = choices.getBoolean("cyt_lunar", lunar);
        if (choices.contains("cyt_lunar")) lunarOffset = 7;
        greetingName = choices.getString("cyt_name", greetingName);
        showGreeting = choices.getBoolean("cyt_greeting", showGreeting);
        if (choices.contains("cyt_background")) background = android.graphics.Color.parseColor(choices.getString("cyt_background", "#000000"));
        wallpaperDim = choices.getInt("cyt_dim", wallpaperDim);
''' + anchor)
            (java_dir / "Config.java").write_text(config, encoding="utf-8")
            activity = original("app/src/main/java/com/gathin/tvhome/LauncherSettingsActivity.java")
            anchor = "        refresh();\n        if (config.launcherSettingsButton)"
            if activity.count(anchor) != 1:
                raise ValueError("Source Settings khác phiên bản đã rà soát; chưa vá hoặc build.")
            activity = activity.replace(anchor, '''        android.widget.Button personal = new android.widget.Button(this);
        personal.setText("Cá nhân hóa TV · Lịch âm · Ảnh nền · Thời tiết");
        personal.setAllCaps(false);
        personal.setOnClickListener(v -> startActivity(new android.content.Intent(this, CleanupSettingsActivity.class)));
        ((android.widget.LinearLayout) wallpaperChoice.getParent()).addView(personal, 1);
''' + anchor)
            (java_dir / "LauncherSettingsActivity.java").write_text(activity, encoding="utf-8")
        if android_manifest.count("</application>") != 1:
            raise ValueError("Android manifest không khớp.")
        (project / "app/src/main/AndroidManifest.xml").write_text(android_manifest.replace("</application>", declaration + "\n</application>"), encoding="utf-8")
    for name in files:
        shutil.copyfile(root / "launcher-overlay" / name, java_dir / name)
    return project


def valid_preferences(values):
    if not isinstance(values, dict) or not set(values) <= KEYS:
        raise ValueError("Có mục giao diện không được hỗ trợ.")
    ranges = {"columns": (4, 7), "rows_below_dock": (0, 3), "dock_opacity": (30, 100), "cyt_dim": (0, 90)}
    for key, value in values.items():
        if value is None:
            continue
        if key in ranges:
            low, high = ranges[key]
            if type(value) is not int or not low <= value <= high:
                raise ValueError("Giá trị giao diện ngoài phạm vi: " + key)
        elif key in {"animations", "advanced_effects", "cyt_lunar", "cyt_greeting"}:
            if type(value) is not bool:
                raise ValueError("Giá trị bật/tắt không hợp lệ.")
        elif not isinstance(value, str):
            raise ValueError("Nội dung giao diện không hợp lệ.")
        elif key == "cyt_name" and (len(value.encode("utf-16-le")) > 120 or any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise ValueError("Tên hiển thị tối đa 60 ký tự, không có ký tự điều khiển.")
        elif key == "cyt_background" and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("Màu nền phải có dạng #RRGGBB.")
        elif key == "wallpaper_choice" and value != "none" and not re.fullmatch(r"[A-Za-z0-9_.-]+\.(jpg|jpeg|png|webp)", value):
            raise ValueError("Tên ảnh nền không hợp lệ.")
    return values


def jpeg_size(data):
    if not data.startswith(b"\xff\xd8") or len(data) > 500_000:
        raise ValueError("Chỉ nhận ảnh JPEG đã thu nhỏ, tối đa 500 KB.")
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 255:
            break
        marker = data[pos+1]
        pos += 2
        if marker == 255:
            pos -= 1
            continue
        if marker in (0xD8, 0xD9):
            continue
        size = int.from_bytes(data[pos:pos+2], "big")
        if size < 2 or pos + size > len(data):
            break
        if marker in (0xC0, 0xC1, 0xC2) and size >= 8:
            height = int.from_bytes(data[pos+3:pos+5], "big")
            width = int.from_bytes(data[pos+5:pos+7], "big")
            if 0 < width <= 1920 and 0 < height <= 1920 and width * height <= 2_073_600:
                return width, height
            break
        pos += size
    raise ValueError("Không đọc được kích thước ảnh nền hoặc ảnh vượt giới hạn Full HD.")


class PersonalizationMixin:
    def personal_call(self, target, method="read", values=None):
        if target not in {"appearance", "weather"} or method not in {"read", "write"}:
            raise self.error("Loại thiết lập cá nhân không hợp lệ.")
        uri = "content://" + (LAUNCHER if target == "appearance" else WEATHER) + ".cleanup"
        command = "content call --uri " + uri + " --method " + method
        if method == "write":
            encoded = base64.b64encode(json.dumps(values, ensure_ascii=False, allow_nan=False).encode()).decode()
            command += " --arg " + encoded
        raw = self.sh(command)
        match = re.search(r"payload=([A-Za-z0-9+/=]+)", raw)
        if not match:
            raise self.error("Chưa đọc được phần Cá nhân hóa/Thời tiết. Build và cập nhật đúng mô-đun CleanupTV trước; chưa thay đổi thiết lập.")
        result = json.loads(base64.b64decode(match[1]).decode())
        if result.get("version") != 1 or not isinstance(result.get("values"), dict):
            raise self.error("Phiên bản phần cá nhân hóa chưa tương thích.")
        return result

    def personal_read(self, p):
        self.guard()
        result = self.personal_call("appearance")
        try:
            result["weather"] = self.personal_call("weather")["values"]
        except self.error:
            result["weather"] = None
        return result

    def personal_open(self, p):
        self.guard()
        if p.get("weather") is True:
            package, activity = WEATHER, "WeatherActivity"
        else:
            package, activity = LAUNCHER, "CleanupSettingsActivity"
        result = self.sh("am start -n " + package + "/." + activity)
        if re.search(r"Error|Exception|does not exist", result):
            raise self.error("Chưa mở được phần thiết lập. Cập nhật launcher hoặc cài mô-đun trước.")
        return {"message": "Đã mở trên TV. Dùng điều khiển để chỉnh; bấm Xong hoặc Home khi hoàn tất."}

    def city_search(self, p):
        name = p.get("name", "")
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 80:
            raise self.error("Nhập tên tỉnh/thành phố từ 2 đến 80 ký tự.")
        url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode({"name": name.strip(), "count": 8, "language": "vi", "format": "json"})
        with urllib.request.urlopen(url, timeout=10) as response:
            body = response.read(200_001)
        if len(body) > 200_000:
            raise self.error("Dữ liệu địa điểm quá lớn. Thử tìm tên ngắn hơn.")
        locations = []
        for item in json.loads(body).get("results", [])[:8]:
            locations.append({"name": ", ".join(str(item[k]) for k in ("name", "admin1", "country") if item.get(k)),
                              "latitude": item["latitude"], "longitude": item["longitude"]})
        self.city_results = locations
        return {"cities": locations, "message": "Chọn đúng địa điểm. Nguồn địa danh: Open-Meteo / GeoNames."}

    def personal_apply(self, p):
        return self.transaction(p, self.personal_changes)

    def personal_changes(self, p):
        path, record = self.load_record(p.get("backup"))
        try:
            values = valid_preferences(p.get("values", {}))
        except ValueError as error:
            raise self.error(str(error))
        city = p.get("city")
        if city is not None and city not in getattr(self, "city_results", []):
            raise self.error("Tìm và chọn lại thành phố từ kết quả vừa nhận.")
        changes = []
        if values:
            before = self.personal_call("appearance")["values"]
            changes.append({"target": "appearance", "before": before, "after": dict(before, **values), "status": "pending"})
        if city is not None:
            before = self.personal_call("weather")["values"]
            changes.append({"target": "weather", "before": before, "after": city, "status": "pending"})
        if not changes:
            raise self.error("Chọn ít nhất một thay đổi giao diện hoặc thành phố.")
        self.begin_trial(path, record)
        record["personal_changes"] = changes
        self.write_record(path, record)
        for change in changes:
            result = self.personal_call(change["target"], "write", change["after"])
            if result["values"] != change["after"]:
                raise self.error("TV chưa lưu đúng thiết lập cá nhân. Dừng và tự hoàn tác.")
            change["status"] = "changed"
            self.write_record(path, record)
        self.probe_home(record["home_before"].split("/")[0])
        return {"backup": record["id"], "message": "Đang thử thiết lập cá nhân trong 3 phút. Trên TV, thử giao diện rồi chọn Giữ hoặc Hoàn tác."}

    def personal_upload(self, p):
        self.guard()
        try:
            data = base64.b64decode(p.get("data", ""), validate=True)
            jpeg_size(data)
        except (ValueError, TypeError) as error:
            raise self.error(str(error))
        info = self.personal_call("appearance")
        name = "cyt-" + hashlib.sha256(data).hexdigest()[:24] + ".jpg"
        existing = info.get("pictures", [])
        if name not in existing and sum(s.startswith("cyt-") for s in existing) >= 12:
            raise self.error("Đã có 12 ảnh cá nhân. Chọn lại ảnh đã lưu trên TV.")
        temp = self.data / "wallpaper-upload.jpg"
        temp.write_bytes(data)
        self.run_adb("-s", self.target, "push", str(temp), "/data/local/tmp/cleanuptv-picture.jpg", timeout=20)
        try:
            self.sh("content write --uri content://com.gathin.tvhome.theme/wallpapers/" + name + " < /data/local/tmp/cleanuptv-picture.jpg")
            # Verify bytes through the same provider; no permission-changing cp fallback.
            result = self.run_adb("-s", self.target, "exec-out", "content", "read", "--uri", "content://com.gathin.tvhome.theme/wallpapers/" + name, binary=True)
        finally:
            self.sh("rm -f /data/local/tmp/cleanuptv-picture.jpg")
        if result != data:
            raise self.error("Chưa xác minh ảnh gửi lên TV. Giữ nguyên ảnh nền đang dùng.")
        return {"picture": name, "message": "Đã thêm ảnh vào bộ sưu tập trên TV. Bấm Thử thiết lập để dùng ảnh này; ảnh chưa tự áp dụng."}
