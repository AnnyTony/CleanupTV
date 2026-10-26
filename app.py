"""CleanupTV: dependency-free, loopback-only Android TV assistant."""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import statistics
import sys
import subprocess
import threading
import time
import urllib.request
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))  # local modules also work with portable Python's -I mode
from personalize import PersonalizationMixin, WEATHER, prepare_overlay, overlay_hash
from rescue import RescueMixin
COMPONENT = "com.gathin.tvhome/.MainActivity"
PACKAGE = "com.gathin.tvhome"
TRIAL_SECONDS = 180
ANIMATION_KEYS = ("window_animation_scale", "transition_animation_scale", "animator_duration_scale")
MANUAL_CHECKS = {"remote", "video", "audio", "inputs", "network"}
HOME = "-a android.intent.action.MAIN -c android.intent.category.HOME"
PKG_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+\Z")
COMP_RE = re.compile(r"[A-Za-z_][\w.]*/[\w.$]+\Z")


class UserError(Exception):
    pass


class TrialExpired(UserError):
    pass


@lru_cache(maxsize=4)
def reference_data(root):
    """Read immutable community reference files once per application directory."""
    return (json.loads((root / "catalog.json").read_text(encoding="utf-8")),
            json.loads((root / "profiles.json").read_text(encoding="utf-8"))["profiles"])


def java_property(value):
    """ASCII Java .properties, including surrogate pairs and Windows path escapes."""
    result = []
    for char in str(value):
        if char in "\\:=#! " or char in "\t\n\r\f":
            result.append({"\t": r"\t", "\n": r"\n", "\r": r"\r", "\f": r"\f"}.get(char, "\\" + char))
        elif 32 <= ord(char) <= 126:
            result.append(char)
        else:
            encoded = char.encode("utf-16-be")
            result.extend("\\u" + encoded[i:i+2].hex() for i in range(0, len(encoded), 2))
    return "".join(result)


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    # Windows readers/antivirus can briefly deny replacement of an open record.
    # Keep the old durable record and retry rather than losing the undo journal.
    for attempt in range(40):
        try:
            tmp.replace(path)
            break
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(0.025)


def endpoint(host, port):
    try:
        ip = ipaddress.IPv4Address(str(host))
        allowed = any(ip in ipaddress.ip_network(n) for n in
                      ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
        if not allowed or isinstance(port, bool) or not str(port).isdigit() or not 1 <= int(port) <= 65535:
            raise ValueError()
        return f"{ip}:{int(port)}"
    except (ValueError, TypeError):
        raise UserError("Nhập IP nội bộ của TV (ví dụ 192.168.1.50) và cổng từ 1 đến 65535.")


def package_set(raw):
    return {p[8:].strip() for p in raw.splitlines() if p.startswith("package:")}


def component(raw):
    return next((s.strip() for s in reversed(raw.splitlines()) if COMP_RE.fullmatch(s.strip())), "")


def enabled_state(raw):
    m = re.search(r"User 0:[^\r\n]*\benabled=(\d+)", raw)
    if not m or int(m[1]) not in range(5):
        raise UserError("Không đọc được trạng thái gói cho user 0. Dừng để giữ nguyên TV.")
    return int(m[1])


def cpu_ticks(raw):
    match = re.search(r"(?m)^cpu\s+([0-9 ]+)$", raw)
    if not match:
        return None
    values = [int(x) for x in match[1].split()][:8]
    if len(values) < 4:
        return None
    return sum(values), values[3] + (values[4] if len(values) > 4 else 0)


def parse_resources(memory, storage):
    values = {k: int(v) for k, v in re.findall(r"(?m)^(MemTotal|MemAvailable):\s+(\d+)\s+kB", memory)}
    free = total = None
    for line in storage.splitlines():
        fields = line.split()
        if len(fields) >= 4 and all(v.isdigit() for v in fields[1:4]):
            total, free = int(fields[1]) / 1024, int(fields[3]) / 1024
    return {"memoryTotalMiB": round(values["MemTotal"] / 1024, 1) if "MemTotal" in values else None,
        "memoryAvailableMiB": round(values["MemAvailable"] / 1024, 1) if "MemAvailable" in values else None,
        "storageTotalMiB": round(total, 1) if total is not None else None,
        "storageFreeMiB": round(free, 1) if free is not None else None}


def normalized(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def match_profiles(device, profiles):
    """Require a real model/device identifier; a shared manufacturer is never a match."""
    scored = []
    brands = {normalized(device.get("manufacturer", "")), normalized(device.get("brand", ""))} - {""}
    generic = {"android tv", "google tv", "smart tv", "tv", "atv", "g10", "mtk", "realtek"}
    for profile in profiles:
        pbrand = normalized(profile["brand"])
        if not any(brand == pbrand or (len(pbrand) > 3 and pbrand in brand) for brand in brands):
            continue
        version = re.search(r"\d+", profile["os"])
        current_version = str(device.get("android", "")).split(".")[0]
        if version and current_version and version[0] != current_version:
            continue
        evidence = normalized(profile["tv"] + " " + profile["header"])
        score = 0
        for key, weight in (("model", 12), ("codename", 10), ("product", 8)):
            value = normalized(device.get(key, ""))
            if len(value.replace(" ", "")) >= 5 and value not in generic and re.search(r"(?<![a-z0-9])" + re.escape(value) + r"(?![a-z0-9])", evidence):
                score += weight
        if not score:
            continue
        scored.append((score, profile))
    if not scored:
        return []
    highest = max(score for score, _ in scored)
    fingerprint = device.get("firmware", "")
    return [dict(profile, compatibility=("firmware_verified" if fingerprint and
        fingerprint in profile.get("verifiedFingerprints", []) else "model_only"))
        for score, profile in scored if score == highest]


def protected(pkg, detail, homes):
    # Fail closed: candidates are also restricted to the small reviewed catalog.
    if not PKG_RE.fullmatch(pkg):
        return True
    if pkg in homes or pkg == PACKAGE or pkg in {"com.android.vending", "com.google.android.gms"}:
        return True
    if pkg.startswith(("com.android.", "com.google.android.permissioncontroller",
                       "com.google.android.packageinstaller", "com.google.android.ext.",
                       "com.google.android.modulemetadata", "com.google.android.overlay.modules")):
        return True
    if re.search(r"factory|hkcfac|setupwraith|bluetooth|inputmethod|keyboard|updat|launcher|tvhome", pkg, re.I):
        return True
    return any(x in detail for x in ("android.permission.TV_INPUT_HARDWARE",
        "android.media.tv.TvInputService", "android.view.InputMethod",
        "android.permission.BIND_INPUT_METHOD", "android.permission.BIND_ACCESSIBILITY_SERVICE"))


class Adb:
    def __init__(self):
        self.path = ROOT / ".runtime/adb/platform-tools/adb.exe"

    def run(self, *args, timeout=30, stdin=None, binary=False):
        if not self.path.is_file():
            raise UserError("Chưa có ADB. Đóng giao diện rồi chạy START.bat để tự chuẩn bị.")
        try:
            p = subprocess.run([str(self.path), *args], input=stdin, capture_output=True,
                timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            raise UserError("TV chưa phản hồi. Xem TV có đang hỏi Cho phép gỡ lỗi/cài ứng dụng không, rồi thử lại.")
        if p.returncode:
            out = (p.stdout + p.stderr).decode("utf-8", "replace")
            if "unauthorized" in out:
                raise UserError("Hãy chọn Cho phép / Allow USB debugging trên màn hình TV, rồi bấm kết nối lại.")
            if "offline" in out or "not found" in out:
                raise UserError("TV mất kết nối. Kiểm tra IP, giữ TV bật và kết nối lại ở bước 2.")
            raise UserError("ADB: " + out[-1200:])
        return p.stdout if binary else p.stdout.decode("utf-8", "replace").strip()

    def shell(self, serial, cmd, timeout=30):
        return self.run("-s", serial, "shell", cmd, timeout=timeout)


class Service(PersonalizationMixin, RescueMixin):
    error = UserError
    write_record = staticmethod(atomic_json)
    def __init__(self, data=None, adb=None):
        self.data = Path(data or ROOT / ".local")
        self.adb = adb or Adb()
        self.target = ""
        self.device = None
        self.identity = ""
        self.catalog, self.profiles = reference_data(ROOT)
        self.profile_match = []
        self.candidates = []
        self.lock = threading.Lock()
        self.job = None
        self.log = []
        self.last_result = None
        self.recovery_stop = threading.Event()
        self.recovery_active = False
        self.command_deadline = None

    def note(self, message):
        self.log.append({"time": time.strftime("%H:%M:%S"), "text": message})
        self.log = self.log[-100:]

    def start(self, action, params):
        if not self.lock.acquire(blocking=False):
            raise UserError("Đang thực hiện một bước. Chờ kết quả rồi tiếp tục.")
        try:
            trials = self.recovery_records()
            # Long work cannot enter the serialized device queue during a trial.
            if trials:
                pending = any(r.get("recovery_pending") or r.get("trial_until", 0) <= time.time() for _, r in trials)
                allowed = {"restore", "connect", "pair"} if pending else {"restore", "keep", "verify", "screenshot", "reboot"}
                if action not in allowed:
                    raise UserError("Giữ hoặc hoàn tác lần thử trước khi chạy bước khác. Ưu tiên thời gian cho tự khôi phục.")
        except Exception:
            self.lock.release()
            raise
        self.job = {"id": secrets.token_hex(8), "action": action, "status": "running", "error": "", "result": None}
        self.note("Bắt đầu: " + action)
        def work():
            try:
                if trials and action in {"connect", "pair"}:
                    # Reconnection is allowed for pending recovery, with a finite budget.
                    self.command_deadline = time.monotonic() + (15 if action == "connect" else 25)
                if action in {"keep", "verify", "screenshot", "reboot"}:
                    active = [r for _, r in self.recovery_records() if r["identity"] == self.identity]
                    if active:
                        self.set_deadline(min(r["trial_until"] for r in active), cap=12)
                result = getattr(self, action)(params)
                self.last_result = result
                self.job.update(status="done", result=result)
                self.note("Hoàn tất: " + action)
            except Exception as e:
                msg = str(e) if isinstance(e, UserError) else f"{type(e).__name__}: {e}"
                self.job.update(status="error", error=msg)
                self.note("Dừng: " + msg)
                if action == "verify":
                    for path, record in self.recovery_records():
                        if record["identity"] == self.identity:
                            record["recovery_pending"] = True
                            record["recovery_reason"] = msg[:1500]
                            atomic_json(path, record)
            finally:
                self.command_deadline = None
                # An expired read or check gives the device queue straight to recovery.
                try:
                    self.recover_due(only_due=True)
                except Exception as error:
                    self.note("Khôi phục sẽ thử lại: " + str(error))
                self.lock.release()
        threading.Thread(target=work, daemon=True).start()

    def set_deadline(self, until, cap=None):
        seconds = max(0, until - time.time())
        if cap is not None:
            seconds = min(seconds, cap)
        self.command_deadline = time.monotonic() + seconds

    def run_adb(self, *args, timeout=30, **kwargs):
        if self.command_deadline is not None:
            remaining = self.command_deadline - time.monotonic()
            if remaining <= 0:
                raise TrialExpired("Đã hết thời gian dành cho bước kiểm tra/thử. Chuyển sang tự khôi phục.")
            timeout = min(timeout, remaining)
        result = self.adb.run(*args, timeout=timeout, **kwargs)
        if self.command_deadline is not None and time.monotonic() >= self.command_deadline:
            raise TrialExpired("Đã hết thời gian thử. Chuyển sang tự khôi phục.")
        return result

    def sh(self, cmd, timeout=30):
        if not self.target:
            raise UserError("Kết nối TV ở bước 2 trước.")
        return self.run_adb("-s", self.target, "shell", cmd, timeout=timeout)

    def read_identity(self):
        # No serial number or IP is exposed in the public device summary.
        values = {k: self.sh("getprop " + k) for k in ("ro.product.manufacturer", "ro.product.model",
            "ro.build.version.release", "ro.build.version.sdk", "ro.build.fingerprint", "ro.serialno",
            "ro.product.device", "ro.product.name", "ro.product.brand")}
        serial = values["ro.serialno"]
        if not serial or serial.lower() in ("unknown", "null"):
            serial = self.sh("settings get secure android_id")
        if not serial or serial.lower() in ("unknown", "null"):
            raise UserError("TV không trả mã nhận diện ổn định; chưa thể tạo khôi phục đúng thiết bị.")
        identity = hashlib.sha256((serial + "|" + values["ro.build.fingerprint"]).encode()).hexdigest()
        return identity, {"manufacturer": values["ro.product.manufacturer"], "model": values["ro.product.model"],
            "brand": values["ro.product.brand"] or values["ro.product.manufacturer"],
            "android": values["ro.build.version.release"], "sdk": int(values["ro.build.version.sdk"] or "0"),
            "codename": values["ro.product.device"], "product": values["ro.product.name"],
            "firmware": values["ro.build.fingerprint"], "secure": self.sh("getprop ro.adb.secure") != "0"}

    def guard(self):
        serial = self.sh("getprop ro.serialno")
        if not serial or serial.lower() in ("unknown", "null"):
            serial = self.sh("settings get secure android_id")
        fingerprint = self.sh("getprop ro.build.fingerprint")
        identity = hashlib.sha256((serial + "|" + fingerprint).encode()).hexdigest()
        if not self.identity or identity != self.identity:
            raise UserError("Thiết bị hoặc firmware đã đổi. Kết nối và phân tích lại; không dùng bản sao lưu của TV khác.")

    def connect(self, p):
        if p.get("consent") is not True:
            raise UserError("Xác nhận đây là TV bạn được phép quản lý.")
        self.target = endpoint(p.get("host"), p.get("port", 5555))
        self.device = None
        self.identity = ""
        self.candidates = []
        out = self.adb.run("connect", self.target, timeout=15)
        if "connected" not in out.lower():
            raise UserError("Chưa kết nối được. " + out + " Kiểm tra IP, cổng và tùy chọn gỡ lỗi trên TV.")
        if self.adb.run("-s", self.target, "get-state", timeout=10) != "device":
            raise UserError("Hãy chấp nhận thông báo Cho phép gỡ lỗi trên TV và kết nối lại.")
        features = self.sh("pm list features")
        if "android.software.leanback" not in features and "android.hardware.type.television" not in features:
            raise UserError("Thiết bị này không tự nhận là Android TV/Google TV. Dừng trước khi thay đổi.")
        if "amazon" in self.sh("getprop ro.product.manufacturer").lower():
            raise UserError("Fire TV cần quy trình riêng. Bản này dành cho Android TV và Google TV.")
        self.identity, self.device = self.read_identity()
        self.profile_match = match_profiles(self.device, self.profiles)
        for path, record in self.recovery_records():
            if record["identity"] == self.identity and record.get("target") != self.target:
                record["target"] = self.target
                atomic_json(path, record)
        return self.device

    def pair(self, p):
        if p.get("consent") is not True:
            raise UserError("Xác nhận đây là TV bạn được phép quản lý.")
        address = endpoint(p.get("host"), p.get("pairPort"))
        code = str(p.get("code", ""))
        if not re.fullmatch(r"\d{6}", code):
            raise UserError("Mã ghép đôi gồm 6 chữ số đang hiện trên TV.")
        out = self.adb.run("pair", address, stdin=(code + "\n").encode(), timeout=25)
        if "successfully paired" not in out.lower():
            raise UserError("Ghép đôi chưa thành công. Mở lại cửa sổ mã ghép đôi trên TV và thử mã mới.")
        return {"message": "Đã ghép đôi. Điền CỔNG KẾT NỐI ở màn hình Gỡ lỗi không dây chính rồi bấm Kết nối TV."}

    def discover(self, p):
        raw = self.adb.run("mdns", "services", timeout=12)
        found = []
        for line in raw.splitlines():
            if "_adb-tls-connect._tcp" in line:
                m = re.search(r"(\d+\.\d+\.\d+\.\d+):(\d+)", line)
                if m:
                    try:
                        endpoint(m[1], m[2])
                        found.append({"host": m[1], "port": int(m[2])})
                    except UserError:
                        pass
        return {"devices": found, "message": "Chọn đúng IP đang hiện trên TV. Nếu không tìm thấy, nhập IP thủ công."}

    def homes(self):
        raw = self.sh("cmd package query-activities --brief " + HOME)
        found = {line.strip().split("/")[0] for line in raw.splitlines() if COMP_RE.fullmatch(line.strip())}
        current = component(self.sh("cmd package resolve-activity --brief " + HOME))
        if not current or not found:
            raise UserError("Không xác minh được màn hình Home hiện tại. Giữ nguyên TV; chưa thực hiện dọn.")
        return current, found | {current.split("/")[0]}

    def analyze(self, p):
        self.guard()
        installed = package_set(self.sh("pm list packages --user 0"))
        disabled = package_set(self.sh("pm list packages -d --user 0"))
        _, homes = self.homes()
        found = []
        for item in self.catalog:
            pkg = item["package"]
            if pkg not in installed or pkg in disabled:
                continue
            if item.get("brand") and not any(item["brand"].lower() in self.device.get(key, "").lower() for key in ("manufacturer", "brand")):
                continue
            if self.profile_match and not all(any(e["package"] == pkg for e in profile["packages"]) for profile in self.profile_match):
                continue
            if item.get("requireProfile") and (not self.profile_match or
                    not all(profile["compatibility"] == "firmware_verified" for profile in self.profile_match)):
                continue
            detail = self.sh("dumpsys package " + pkg)
            if not detail.strip() or "Unable to find" in detail or protected(pkg, detail, homes):
                continue
            enabled_state(detail)
            found.append(item)
        self.candidates = found
        return {"candidates": found, "installed": len(installed), "disabled": len(disabled),
            "profiles": [{k: profile[k] for k in ("id", "tv", "brand", "os", "notes", "source", "compatibility")} for profile in self.profile_match],
            "message": "Chỉ liệt kê các gói trong quy tắc đã rà soát và thực sự có trên TV. Không suy đoán theo tên hãng."}

    def record_path(self, record_id):
        if not re.fullmatch(r"[0-9a-f]{24}", str(record_id)):
            raise UserError("Mã sao lưu không hợp lệ.")
        return self.data / "backups" / record_id / "record.json"

    def records(self):
        found = []
        for path in sorted((self.data / "backups").glob("*/record.json"), reverse=True):
            try:
                r = json.loads(path.read_text(encoding="utf-8"))
                if r["identity"] == self.identity:
                    found.append({"id": r["id"], "created": r["created"], "model": r["model"],
                        "createdOrder": r.get("created_ns", 0),
                        "changes": len(r["changes"]), "home": bool(r.get("home_pending")), "restored": r.get("restored", False),
                        "trialUntil": r.get("trial_until", 0), "recoveryPending": r.get("recovery_pending", False)})
                    found[-1]["settings"] = len(r.get("settings_changes", []))
                    found[-1]["settings"] += len(r.get("personal_changes", []))
            except (OSError, ValueError, KeyError):
                pass
        return sorted(found, key=lambda r: (r["created"], r["createdOrder"]), reverse=True)

    def backup(self, p):
        self.guard()
        if any(r["trialUntil"] or r["recoveryPending"] for r in self.records() if not r["restored"]):
            raise UserError("Giữ hoặc hoàn tác lần thử đang chạy trước khi tạo bản lưu mới.")
        current, _ = self.homes()
        rid = secrets.token_hex(12)
        path = self.record_path(rid)
        path.parent.mkdir(parents=True, exist_ok=True)
        for name, command in {"packages": "pm list packages --user 0", "disabled": "pm list packages -d --user 0",
            "properties": "getprop", "settings-global": "settings list global", "settings-secure": "settings list secure",
            "settings-system": "settings list system"}.items():
            self.note("Đang lưu " + name)
            raw = self.sh(command)
            if (not raw.strip() and name != "disabled") or re.search(r"(?im)^(error|exception|permission denial)", raw):
                raise UserError("Không sao lưu được " + name + ". Chưa thay đổi TV.")
            (path.parent / (name + ".txt")).write_text(raw, encoding="utf-8")
        previous = next((r["id"] for r in self.records() if not r["restored"] and (r["changes"] or r["settings"] or r["home"])), None)
        record = {"id": rid, "identity": self.identity, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "application": "Thanh Tùng Tiên Sinh Cleanup", "createdVersion": "0.5.0",
            "created_ns": time.time_ns(), "parent": previous,
            "model": self.device["model"], "home_before": current, "changes": [], "home_pending": False,
            "restored": False, "launcher_installed": False, "target": self.target,
            "trial_until": 0, "recovery_pending": False}
        record["settings_changes"] = []
        atomic_json(path, record)
        return {"backup": rid, "message": "Đã sao lưu thông tin và trạng thái. Đây không phải bản sao firmware hay dữ liệu ứng dụng."}

    def load_record(self, rid):
        self.guard()
        path = self.record_path(rid)
        try:
            r = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise UserError("Không đọc được bản sao lưu. Giữ thư mục .local cạnh ứng dụng.")
        if r["identity"] != self.identity:
            raise UserError("Bản sao lưu thuộc TV hoặc firmware khác. Không thực hiện.")
        if r.get("restored"):
            raise UserError("Bản này đã khôi phục. Tạo bản sao lưu mới trước khi thay đổi tiếp.")
        return path, r

    def begin_trial(self, path, record):
        if record.get("recovery_pending") or any(c["status"] == "pending" for c in record["changes"] + record.get("settings_changes", [])):
            raise UserError("Có thay đổi chưa xác nhận. Khôi phục trước khi bắt đầu lần thử mới.")
        record["target"] = self.target
        record["trial_until"] = time.time() + TRIAL_SECONDS
        record["recovery_pending"] = False
        record["health_grace"] = 0
        atomic_json(path, record)
        self.set_deadline(record["trial_until"])
        self.note("Bắt đầu thử 3 phút. Không bấm Giữ thay đổi thì sẽ tự hoàn tác.")

    def transaction(self, p, operation):
        # Reject before entering the failure/rollback handler: no new mutation exists.
        if self.recovery_records():
            raise UserError("Có lần thử chưa xác nhận. Giữ hoặc khôi phục trước khi thử tiếp.")
        path, record = self.load_record(p.get("backup"))
        p = dict(p)
        if record.get("confirmed"):
            # A new durable baseline preserves everything the user already accepted.
            p["backup"] = self.backup({})["backup"]
        try:
            result = operation(p)
            result.setdefault("backup", p["backup"])
            return result
        except Exception as error:
            self.command_deadline = None
            try:
                path = self.record_path(p.get("backup"))
                record = json.loads(path.read_text(encoding="utf-8"))
            except (UserError, OSError, ValueError):
                raise error
            if record.get("identity") != self.identity or record.get("restored") or not record.get("trial_until"):
                raise error
            record["recovery_pending"] = True
            record["recovery_reason"] = str(error)[:1500]
            atomic_json(path, record)
            self.note("Bước thử thất bại. Đang tự khôi phục riêng lần thử này.")
            try:
                self.restore({"backup": record["id"]})
            except Exception:
                raise UserError(str(error) + " Chưa thể tự khôi phục vì TV chưa phản hồi/xác minh chưa đạt. Giữ ứng dụng mở; sẽ tự thử lại mỗi 5 giây khi kết nối trở lại.") from error
            raise UserError(str(error) + " Đã tự khôi phục các thay đổi của lần thử này.") from error
        finally:
            self.command_deadline = None

    def apply(self, p):
        return self.transaction(p, self.apply_changes)

    def apply_changes(self, p):
        path, r = self.load_record(p.get("backup"))
        if any(c["status"] == "pending" for c in r["changes"]):
            raise UserError("Lần trước có thao tác chưa xác nhận xong. Khôi phục bản này rồi tạo bản lưu mới trước khi dọn tiếp.")
        selected = p.get("packages")
        if not isinstance(selected, list) or not selected or len(selected) > 20 or any(not isinstance(x, str) for x in selected):
            raise UserError("Chọn ít nhất một gói trong danh sách đã phân tích.")
        allowed = {item["package"] for item in self.candidates}
        if not set(selected) <= allowed:
            raise UserError("Danh sách đã thay đổi. Phân tích TV lại trước khi chọn gói.")
        _, homes = self.homes()
        plan = []
        for pkg in dict.fromkeys(selected):
            detail = self.sh("dumpsys package " + pkg)
            if protected(pkg, detail, homes):
                raise UserError("Giữ lại gói được bảo vệ: " + pkg)
            state = enabled_state(detail)
            if state not in (0, 1):
                continue
            if any(x["package"] == pkg for x in r["changes"]):
                continue
            plan.append((pkg, state))
        if plan:
            self.begin_trial(path, r)
        for pkg, state in plan:
            # Write-ahead journal includes ambiguous outcomes after power/network loss.
            change = {"package": pkg, "before": state, "status": "pending"}
            r["changes"].append(change)
            atomic_json(path, r)
            self.note("Tắt và xác minh: " + pkg)
            self.sh("pm disable-user --user 0 " + pkg)
            if pkg not in package_set(self.sh("pm list packages -d --user 0")):
                raise UserError("TV không cho tắt " + pkg + ". Đã dừng; bạn có thể khôi phục các gói vừa thực hiện.")
            change["status"] = "disabled"
            atomic_json(path, r)
        return {"changed": len(plan), "backup": r["id"]}

    def optimize(self, p):
        return self.transaction(p, self.optimize_changes)

    def optimize_changes(self, p):
        path, record = self.load_record(p.get("backup"))
        if p.get("preset") != "reduced_motion":
            raise UserError("Chỉ hỗ trợ tùy chọn giảm hiệu ứng chuyển động 0,5 lần.")
        if any(c["status"] == "pending" for c in record["changes"]) or any(c["status"] == "pending" for c in record.get("settings_changes", [])):
            raise UserError("Có thay đổi chưa xác nhận; cần khôi phục trước khi tiếp tục.")
        if record.get("settings_changes"):
            raise UserError("Bản lưu này đã có thay đổi hiệu ứng. Giữ hoặc khôi phục trước khi thử tiếp.")
        existing = {}
        for key in ANIMATION_KEYS:
            value = self.sh("settings get global " + key).strip()
            if value != "null" and not re.fullmatch(r"\d+(?:\.\d+)?", value):
                raise UserError("Không đọc được hiệu ứng gốc. Giữ nguyên thiết lập TV.")
            # Do not increase motion when the owner already chose 0 or a smaller value.
            if value == "null" or float(value) > 0.5:
                existing[key] = value
        if not existing:
            return {"message": "Hiệu ứng hiện đã ở mức 0,5 lần hoặc thấp hơn. Không thay đổi thiết lập."}
        self.begin_trial(path, record)
        for key, value in existing.items():
            change = {"key": key, "before": value, "after": "0.5", "status": "pending"}
            record["settings_changes"].append(change)
            atomic_json(path, record)
            self.note("Giảm hiệu ứng và xác minh: " + key)
            self.sh("settings put global " + key + " 0.5")
            after = self.sh("settings get global " + key).strip()
            if not re.fullmatch(r"\d+(?:\.\d+)?", after) or float(after) != 0.5:
                raise UserError("TV không chấp nhận thay đổi hiệu ứng. Dừng và tự khôi phục.")
            change["status"] = "changed"
            atomic_json(path, record)
        return {"backup": record["id"], "message": "Đang thử hiệu ứng chuyển động 0,5 lần trong 3 phút. Thao tác chuyển màn hình có thể ngắn hơn; đây không phải tăng tốc CPU hoặc phát video."}

    def restore(self, p):
        self.command_deadline = None
        path, r = self.load_record(p.get("backup"))
        # Older records remain usable, but undo checkpoints newest first.
        others = {item["id"]: json.loads(self.record_path(item["id"]).read_text(encoding="utf-8")) for item in self.records()}
        for other in others.values():
            if other.get("restored") or not (other["changes"] or other.get("settings_changes") or other.get("personal_changes") or other.get("home_pending")):
                continue
            parent, visited = other.get("parent"), set()
            while parent and parent not in visited:
                if parent == r["id"]:
                    raise UserError("Khôi phục lần thay đổi mới hơn trước, rồi mới quay về bản lưu này.")
                visited.add(parent)
                parent = others.get(parent, {}).get("parent")
        # Manual restoration must also survive a failure or an application restart.
        r["recovery_pending"] = True
        r["target"] = self.target
        atomic_json(path, r)
        self.rescue_undo(path, r)
        for change in reversed(r.get("personal_changes", [])):
            if change["status"] == "restored":
                continue
            result = self.personal_call(change["target"], "write", change["before"])
            if result["values"] != change["before"]:
                raise UserError("Chưa xác minh khôi phục giao diện/thời tiết. Sẽ thử lại.")
            change["status"] = "restored"
            atomic_json(path, r)
        if r.get("personal_changes"):
            self.probe_home(r["home_before"].split("/")[0])
        for change in reversed(r.get("settings_changes", [])):
            if change.get("status") == "restored":
                continue
            key, before = change["key"], change["before"]
            if key not in ANIMATION_KEYS or (before != "null" and not re.fullmatch(r"\d+(?:\.\d+)?", before)):
                raise UserError("Nhật ký thiết lập hiệu ứng không hợp lệ.")
            command = "settings delete global " + key if before == "null" else "settings put global " + key + " " + before
            self.sh(command)
            actual = self.sh("settings get global " + key).strip()
            equal = actual == before or (actual != "null" and before != "null" and re.fullmatch(r"\d+(?:\.\d+)?", actual) and float(actual) == float(before))
            if not equal:
                raise UserError("Chưa xác minh khôi phục hiệu ứng " + key + ". Sẽ thử lại khi TV phản hồi.")
            change["status"] = "restored"
            atomic_json(path, r)
        for change in reversed(r["changes"]):
            if change.get("status") == "restored":
                continue
            pkg = change["package"]
            if not PKG_RE.fullmatch(pkg) or change["before"] not in (0, 1):
                raise UserError("Nhật ký khôi phục có dữ liệu không hợp lệ.")
            cmd = "default-state" if change["before"] == 0 else "enable"
            self.note("Khôi phục: " + pkg)
            self.sh("pm " + cmd + " --user 0 " + pkg)
            if enabled_state(self.sh("dumpsys package " + pkg)) != change["before"]:
                raise UserError("Chưa xác nhận khôi phục " + pkg + ". Có thể thử lại bản này.")
            change["status"] = "restored"
            atomic_json(path, r)
        if r.get("home_pending"):
            self.set_home(r["home_before"])
            r["home_pending"] = False
            atomic_json(path, r)
        r["restored"] = True
        r["trial_until"] = 0
        r["recovery_pending"] = False
        atomic_json(path, r)
        return {"message": "Đã khôi phục các trạng thái được ghi lại. Launcher cài thêm vẫn được giữ trong Ứng dụng."}

    def check_trial(self, record):
        self.guard()
        for change in record.get("personal_changes", []):
            if change["status"] == "changed" and self.personal_call(change["target"])["values"] != change["after"]:
                raise UserError("Thiết lập cá nhân đã đổi trong thời gian thử.")
        for change in record.get("settings_changes", []):
            if change["status"] == "changed":
                value = self.sh("settings get global " + change["key"]).strip()
                if not re.fullmatch(r"\d+(?:\.\d+)?", value) or float(value) != 0.5:
                    raise UserError("Thiết lập hiệu ứng không còn đúng trong lần thử.")
        disabled = package_set(self.sh("pm list packages -d --user 0"))
        if any(c["status"] == "disabled" and c["package"] not in disabled for c in record["changes"]):
            raise UserError("Một gói không còn ở trạng thái đã xác minh trong lần thử.")
        home, _ = self.homes()
        expected = (record.get("rescue_change", {}).get("package", PACKAGE) if record.get("home_pending") else record["home_before"].split("/")[0])
        if home.split("/")[0] != expected:
            raise UserError("Home đã đổi ngoài kế hoạch trong thời gian thử.")
        if record.get("home_pending"):
            self.home_process(expected)

    def keep(self, p):
        path, record = self.load_record(p.get("backup"))
        if not isinstance(p.get("checks"), list) or not MANUAL_CHECKS <= set(x for x in p["checks"] if isinstance(x, str)):
            raise UserError("Xác nhận đã thử điều khiển, video, âm thanh, đầu vào và mạng trước khi Giữ.")
        if record.get("recovery_pending") or not record.get("trial_until") or record["trial_until"] <= time.time():
            raise UserError("Lần thử đã hết hạn hoặc đang khôi phục. Chờ hoàn tác xong trước khi thử lại.")
        try:
            self.set_deadline(record["trial_until"], cap=12)
            self.check_trial(record)
            expected = (record.get("rescue_change", {}).get("package", PACKAGE) if record.get("home_pending") else record["home_before"].split("/")[0])
            self.probe_home(expected)
            if time.time() >= record["trial_until"]:
                raise TrialExpired("Lần thử đã hết hạn trong khi kiểm tra; không giữ thay đổi.")
        except Exception as error:
            self.command_deadline = None
            record["recovery_pending"] = True
            record["recovery_reason"] = str(error)
            atomic_json(path, record)
            try:
                self.restore({"backup":record["id"]})
            except Exception:
                raise UserError("Kiểm tra chưa đạt. Đã xếp hàng tự khôi phục khi TV kết nối lại.")
            raise UserError("Kiểm tra chưa đạt. Đã tự khôi phục.")
        record["trial_until"] = 0
        record["confirmed"] = True
        atomic_json(path, record)
        self.command_deadline = None
        return {"message": "Đã giữ thay đổi sau kiểm tra. Bạn vẫn có thể mở Khôi phục để quay lại bản lưu."}

    def recovery_records(self):
        records = []
        for path in (self.data / "backups").glob("*/record.json"):
            try:
                r = json.loads(path.read_text(encoding="utf-8"))
                if not r.get("restored") and (r.get("trial_until") or r.get("recovery_pending")):
                    records.append((path, r))
            except (OSError, ValueError):
                continue
        return records

    def recover_due(self, now=None, only_due=False):
        """Called with the service lock held; durable records also survive app restarts."""
        now = time.time() if now is None else now
        for path, record in self.recovery_records():
            target = record.get("target", "")
            try:
                host, port = target.split(":")
                endpoint(host, port)
            except (ValueError, UserError):
                continue
            recovery = Service(self.data, self.adb)
            recovery.target = target
            recovery.identity = record["identity"]
            recovery.note = self.note
            due = record.get("recovery_pending") or record.get("trial_until", 0) <= now
            if only_due and not due:
                continue
            if not due and record.get("health_grace", 0) > now:
                continue
            try:
                if not due:
                    recovery.set_deadline(record["trial_until"], cap=8)
                recovery.run_adb("connect", target, timeout=8)
                if not due:
                    recovery.check_trial(record)
                    continue
                self.recovery_active = True
                recovery.restore({"backup":record["id"]})
                self.note("Đã tự khôi phục lần thử trên " + record["model"] + ".")
            except Exception:
                if not record.get("recovery_pending"):
                    record["recovery_pending"] = True
                    record["recovery_reason"] = "Hết thời gian thử hoặc mất xác minh kết nối/Home."
                    atomic_json(path, record)
                    self.note("Đang chờ TV " + record["model"] + " để tự khôi phục. Không thể bảo đảm phục hồi khi TV mất ADB.")
            finally:
                self.recovery_active = False

    def start_recovery(self):
        def loop():
            while not self.recovery_stop.wait(5):
                if self.lock.acquire(blocking=False):
                    try:
                        self.recover_due()
                    except Exception:
                        pass  # Leave durable recovery intent intact for the next attempt.
                    finally:
                        self.lock.release()
        threading.Thread(target=loop, daemon=True).start()

    def set_home(self, value):
        if not COMP_RE.fullmatch(value):
            raise UserError("Không có component Home hợp lệ để khôi phục.")
        self.sh("cmd package set-home-activity --user 0 " + value)
        self.probe_home(value.split("/")[0])

    def home_process(self, package):
        if not PKG_RE.fullmatch(package):
            raise UserError("Tên ứng dụng Home không hợp lệ.")
        pids = self.sh("pidof " + package).split()
        if not pids or any(not pid.isdigit() for pid in pids):
            raise UserError("Không xác minh được tiến trình Home đang chạy. Giữ nguyên hoặc hoàn tác.")
        return set(pids)

    def probe_home(self, package):
        """An explicit Home test; background health checks never steal video focus."""
        self.sh("input keyevent 3")
        previous = None
        for _ in range(2):
            time.sleep(1)
            resolved = component(self.sh("cmd package resolve-activity --brief " + HOME))
            focus = self.sh("dumpsys activity activities")
            focused_lines = "\n".join(line for line in focus.splitlines() if re.search(r"mResumedActivity|topResumedActivity|mFocusedApp", line))
            if resolved.split("/")[0] != package or package + "/" not in focused_lines or re.search(r"AppErrorDialog|AppNotRespondingDialog|Application (?:Error|Not Responding)", focus, re.I):
                raise UserError("TV chưa chuyển Home như yêu cầu hoặc Home đang báo lỗi. Hãy kiểm tra Cài đặt Home trên TV.")
            current = self.home_process(package)
            if previous is not None and previous != current:
                raise UserError("Home khởi động lại giữa hai lần kiểm tra. Chưa giữ thay đổi.")
            previous = current

    def install(self, p):
        return self.transaction(p, self.install_changes)

    def install_changes(self, p):
        path, r = self.load_record(p.get("backup"))
        if any(c["status"] == "pending" for c in r["changes"]):
            raise UserError("Có thay đổi gói chưa xác nhận. Khôi phục trước khi cài launcher.")
        if self.device["sdk"] < 26:
            raise UserError("Launcher này cần Android 8 trở lên. Bạn vẫn có thể dùng phần dọn gói.")
        apk = ROOT / ".runtime/launcher.apk"
        receipt = ROOT / ".runtime/launcher-receipt.json"
        if not apk.is_file() or not receipt.is_file():
            raise UserError("Build launcher trước khi cài.")
        metadata = json.loads(receipt.read_text())
        if hashlib.sha256(apk.read_bytes()).hexdigest() != metadata["sha256"] or metadata.get("overlay") != overlay_hash(ROOT):
            raise UserError("APK thay đổi hoặc chưa có phần cá nhân hóa đúng bản. Build lại trước khi cài.")
        existing = PACKAGE in package_set(self.sh("pm list packages --user 0"))
        if existing and not r.get("launcher_installed") and not (p.get("update") is True and metadata.get("overlay") == overlay_hash(ROOT)):
            raise UserError("TV đã có CleanYourTV. Bản này giữ nguyên launcher đã có; bạn có thể chọn nó trong Cài đặt Home của TV.")
        self.note("Gửi launcher lên TV. Hãy xác nhận cài đặt nếu TV hỏi.")
        self.begin_trial(path, r)
        self.run_adb("-s", self.target, "push", str(apk), "/data/local/tmp/cleanuptv-launcher.apk", timeout=90)
        out = self.sh("pm install -r /data/local/tmp/cleanuptv-launcher.apk", timeout=120)
        if "Success" not in out:
            raise UserError("TV từ chối cài launcher: " + out[-1000:] + ". Home gốc vẫn được giữ.")
        r["launcher_installed"] = True
        # Persist rollback intent BEFORE the Home preference changes.
        r["home_pending"] = True
        atomic_json(path, r)
        try:
            self.set_home(COMPONENT)
        except UserError as first:
            try:
                self.set_home(r["home_before"])
                r["home_pending"] = False
                atomic_json(path, r)
            except UserError:
                raise UserError(str(first) + " Chưa xác nhận trở lại Home gốc. Dùng nút Khôi phục khi kết nối còn hoạt động.")
            raise UserError(str(first) + " Đã trở lại Home gốc; bản này không tắt launcher gốc hoặc setup wizard.")
        return {"backup": r["id"], "message": "Đã cài và xác minh Home mới đang hiển thị. Đang thử 3 phút: thử nút Home thật rồi bấm Giữ thay đổi nếu hoạt động bình thường."}

    def update_launcher(self, p):
        return self.install(dict(p, update=True))

    def build_weather(self, p):
        return self.build(dict(p, component="weather"))

    def install_weather(self, p):
        if self.recovery_records():
            raise UserError("Giữ hoặc hoàn tác lần thử trước khi cài mô-đun.")
        self.guard()
        if self.device["sdk"] < 26:
            raise UserError("Mô-đun cần Android 8 trở lên.")
        apk = ROOT / ".runtime/weather.apk"
        receipt = ROOT / ".runtime/weather-receipt.json"
        if not apk.is_file() or not receipt.is_file():
            raise UserError("Build mô-đun Thời tiết trước khi cài.")
        metadata = json.loads(receipt.read_text())
        if metadata.get("overlay") != overlay_hash(ROOT) or hashlib.sha256(apk.read_bytes()).hexdigest() != metadata.get("sha256"):
            raise UserError("APK không còn khớp bản build. Build lại trước khi cài.")
        self.run_adb("-s", self.target, "push", str(apk), "/data/local/tmp/cleanuptv-weather.apk", timeout=90)
        result = self.sh("pm install -r /data/local/tmp/cleanuptv-weather.apk", timeout=120)
        if "Success" not in result:
            raise UserError("TV từ chối cài Thời tiết: " + result[-1000:])
        if WEATHER not in package_set(self.sh("pm list packages --user 0")):
            raise UserError("Chưa xác minh mô-đun Thời tiết đã cài.")
        self.personal_call("weather")
        return {"message": "Đã cài Thời tiết, giữ dữ liệu nếu là cập nhật. Mô-đun không đổi Home; có thể tắt trong phần Ứng dụng trên TV."}

    def build(self, p):
        if self.recovery_records():
            raise UserError("Giữ hoặc hoàn tác lần thử đang chạy trước khi build launcher, để việc tự khôi phục không bị chờ quá lâu.")
        if p.get("licenses") is not True:
            raise UserError("Đọc và chấp nhận giấy phép Android SDK trước khi tải công cụ build.")
        manifest = json.loads((ROOT / "downloads.json").read_text())
        runtime = ROOT / ".runtime"
        runtime.mkdir(exist_ok=True)
        for key in ("jdk", "sdk", "source"):
            item = manifest[key]
            dest = runtime / key
            marker = dest / ".complete"
            if marker.is_file() and marker.read_text() == item["sha256"]:
                continue
            archive = runtime / (key + ".zip")
            self.note("Tải và kiểm tra SHA256: " + item["name"])
            if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != item["sha256"]:
                with urllib.request.urlopen(item["url"], timeout=60) as response, archive.open("wb") as f:
                    while chunk := response.read(1024 * 1024):
                        f.write(chunk)
            if hashlib.sha256(archive.read_bytes()).hexdigest() != item["sha256"]:
                raise UserError("SHA256 không khớp: " + key + ". Chưa chạy tệp tải về.")
            dest.mkdir(exist_ok=True)
            with zipfile.ZipFile(archive) as z:
                for name in z.namelist():
                    if not (dest / name).resolve().is_relative_to(dest.resolve()):
                        raise UserError("Đường dẫn ZIP không hợp lệ.")
                z.extractall(dest)
            marker.write_text(item["sha256"])
        jdks = list((runtime / "jdk").glob("*/bin/java.exe"))
        sources = list((runtime / "source").glob("*/launcher/gradlew.bat"))
        if not jdks or not sources:
            raise UserError("Không tìm được JDK hoặc source sau giải nén.")
        java = jdks[0].parent.parent
        weather = p.get("component") == "weather"
        launcher = prepare_overlay(ROOT, sources[0].parent.parent, weather=weather)
        sdk = runtime / "android-sdk"
        sdk.mkdir(exist_ok=True)
        env = os.environ.copy()
        env.update(JAVA_HOME=str(java), ANDROID_HOME=str(sdk), ANDROID_SDK_ROOT=str(sdk),
                   GRADLE_USER_HOME=str(runtime / "gradle"))
        env["PATH"] = str(java / "bin") + os.pathsep + env.get("PATH", "")
        sdkmanager = runtime / "sdk/cmdline-tools/bin/sdkmanager.bat"
        # Batch files are fixed, trusted paths; no user strings enter these commands.
        def run_batch(args, name, stdin=None):
            self.note(name)
            log = self.data / "build.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("ab") as f:
                f.write(("\n--- " + name + " ---\n").encode())
                f.flush()
                try:
                    result = subprocess.run(args, cwd=launcher, env=env, input=stdin, stdout=f, stderr=f,
                        timeout=1200, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except subprocess.TimeoutExpired:
                    raise UserError("Build quá thời gian. Xem .local/build.log rồi thử lại khi mạng ổn định.")
            if result.returncode:
                raise UserError("Bước build thất bại: " + name + ". Chi tiết trong .local/build.log (có thể thử lại).")
        run_batch([str(sdkmanager), "--sdk_root=" + str(sdk), "platforms;android-34", "build-tools;34.0.0"], "Chuẩn bị Android SDK 34", b"y\n" * 100)
        if not (sdk / "platforms/android-34/android.jar").is_file() or not (sdk / "build-tools/34.0.0/aapt2.exe").is_file():
            raise UserError("SDK chưa cài đầy đủ. Xem .local/build.log rồi thử lại.")
        (launcher / "local.properties").write_text("sdk.dir=" + java_property(sdk.as_posix()) + "\n", encoding="ascii")
        run_batch([str(launcher / "gradlew.bat"), "--no-daemon", "--console=plain", "testReleaseUnitTest", "lintRelease", "assembleRelease"], "Build và kiểm tra " + ("Thời tiết" if weather else "launcher") + " từ source đã khóa phiên bản")
        apk = launcher / "app/build/outputs/apk/release/app-release.apk"
        if not apk.is_file():
            raise UserError("Build không tạo APK.")
        output = runtime / ("weather.apk" if weather else "launcher.apk")
        output.write_bytes(apk.read_bytes())
        atomic_json(runtime / ("weather-receipt.json" if weather else "launcher-receipt.json"), {"sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "source": manifest["source"]["name"], "overlay": overlay_hash(ROOT)})
        return {"message": "Đã build và kiểm tra APK. Bước này chưa cài gì lên TV."}

    def verify(self, p):
        self.guard()
        current, _ = self.homes()
        self.probe_home(current.split("/")[0])
        return {"home": current, "disabled": sorted(package_set(self.sh("pm list packages -d --user 0"))),
            "message": "Đã mở Home và kiểm tra focus/tiến trình qua hai lần lấy mẫu. Âm thanh, HDMI, ứng dụng xem phim và điều khiển cần thử trực tiếp; phép kiểm tra ngắn chưa bảo đảm ổn định lâu dài."}

    def measure(self, p):
        self.guard()
        phase = p.get("phase")
        if phase not in ("before", "after"):
            raise UserError("Chọn đo trước hoặc sau thay đổi.")
        samples = []
        first = cpu_ticks(self.sh("cat /proc/stat"))
        for _ in range(3):
            time.sleep(1)
            second = cpu_ticks(self.sh("cat /proc/stat"))
            if first and second and second[0] > first[0] and second[1] >= first[1]:
                samples.append(max(0, min(100, 100 * (1 - (second[1] - first[1]) / (second[0] - first[0])))))
            first = second
        result = parse_resources(self.sh("cat /proc/meminfo"), self.sh("df -k /data"))
        cpu = round(statistics.median(samples), 1) if samples else None
        result.update(cpuPercent=cpu, cpuSamples=len(samples), cpuRange=[round(min(samples), 1), round(max(samples), 1)] if samples else None,
            measured=time.strftime("%Y-%m-%d %H:%M:%S"))
        path = self.data / "measurements" / (self.identity + ".json")
        report = self.measurement_report()
        report[phase] = result
        atomic_json(path, report)
        return {"message": "Đã ghi nhận tài nguyên tại thời điểm đo. Đây không phải phép đo tốc độ mở ứng dụng, độ mượt hoặc phần trăm tăng tốc.", "measurement": result}

    def measurement_report(self):
        if not self.identity:
            return {}
        path = self.data / "measurements" / (self.identity + ".json")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def screenshot(self, p):
        self.guard()
        image = self.run_adb("-s", self.target, "exec-out", "screencap", "-p", timeout=30, binary=True)
        if not image.startswith(b"\x89PNG\r\n\x1a\n") or len(image) > 20_000_000:
            raise UserError("TV không trả ảnh PNG hợp lệ. Một số nội dung DRM không chụp được.")
        self.data.mkdir(parents=True, exist_ok=True)
        (self.data / "screen.png").write_bytes(image)
        return {"image": "/api/screenshot-image?t=" + str(time.time())}

    def reboot(self, p):
        self.guard()
        for path, record in self.recovery_records():
            if record["identity"] == self.identity and not record.get("recovery_pending"):
                record["health_grace"] = min(time.time() + 90, record["trial_until"])
                atomic_json(path, record)
        self.run_adb("-s", self.target, "reboot", timeout=15)
        return {"message": "Đã gửi khởi động lại. Chờ TV lên rồi kết nối lại và kiểm tra Home/ứng dụng."}

    def closed(self, p):
        address = endpoint(p.get("host"), p.get("port", 5555))
        host, port = address.split(":")
        try:
            with socket.create_connection((host, int(port)), timeout=4):
                return {"closed": False, "message": "Cổng vẫn mở. Tắt các tùy chọn gỡ lỗi trên TV rồi kiểm tra lại."}
        except ConnectionRefusedError:
            return {"closed": True, "message": "TV đã từ chối kết nối ở cổng vừa kiểm tra. Kiểm tra thêm các cổng ADB khác nếu đã dùng."}
        except (TimeoutError, OSError):
            return {"closed": None, "message": "Chưa kết luận được: TV không phản hồi (có thể đang tắt hoặc đổi IP). Không coi đây là xác nhận đã đóng ADB."}

    def status(self):
        def ready(name):
            try:
                metadata = json.loads((ROOT / (".runtime/" + name + "-receipt.json")).read_text())
                return (ROOT / (".runtime/" + name + ".apk")).is_file() and metadata.get("overlay") == overlay_hash(ROOT)
            except (OSError, ValueError):
                return False
        return {"device": self.device, "target": self.target, "job": self.job, "log": self.log,
            "candidates": self.candidates, "backups": self.records() if self.identity else [],
            "database": {"profiles": len(self.profiles), "brands": len({p["brand"] for p in self.profiles}), "rules": len(self.catalog)},
            "profiles": [{k: p[k] for k in ("id", "tv", "os", "notes", "source", "compatibility")} for p in self.profile_match],
            "trials": [{"id": r["id"], "model":r["model"], "until":r.get("trial_until",0),
                "pending":r.get("recovery_pending",False), "sameDevice":r["identity"]==self.identity} for _,r in self.recovery_records()],
            "recoveryActive": self.recovery_active,
            "measurements": self.measurement_report(),
            "weatherReady": ready("weather"),
            "adbReady": self.adb.path.is_file(), "launcherReady": ready("launcher")}


ACTIONS = {"connect", "pair", "discover", "analyze", "backup", "apply", "optimize", "measure", "restore", "keep", "build", "install", "verify", "screenshot", "reboot", "closed"}
ACTIONS |= {"personal_read", "personal_apply", "personal_upload", "personal_open", "city_search", "build_weather", "install_weather", "update_launcher"}
ACTIONS |= {"rescue_inspect", "rescue_home"}


def make_server(service, port=0):
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass

        def send(self, status, body, content_type="application/json; charset=utf-8"):
            data = json.dumps(body, ensure_ascii=False).encode() if isinstance(body, (dict, list)) else body
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; img-src 'self' data:; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(data)

        def valid_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {"error": "Invalid Host"})
            path = urlsplit(self.path).path
            if path == "/api/session":
                return self.send(200, {"token": token})
            if path == "/api/status":
                return self.send(200, service.status())
            if path == "/api/screenshot-image":
                shot = service.data / "screen.png"
                if shot.is_file():
                    return self.send(200, shot.read_bytes(), "image/png")
            if path == "/api/build-log":
                log = service.data / "build.log"
                return self.send(200, log.read_bytes()[-30000:] if log.is_file() else b"Chua co log build.", "text/plain; charset=utf-8")
            assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/personalize.js": ("personalize.js", "text/javascript; charset=utf-8"),
                "/rescue.js": ("rescue.js", "text/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path in assets:
                name, mime = assets[path]
                return self.send(200, (ROOT / "web" / name).read_bytes(), mime)
            return self.send(404, {"error": "Không tìm thấy."})

        def do_POST(self):
            allowed_origins = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            try:
                length = int(self.headers.get("Content-Length", "0"))
                limit = 700000 if urlsplit(self.path).path == "/api/personal_upload" else 16384
                if length <= 0 or length > limit:
                    raise UserError("Yêu cầu quá lớn hoặc rỗng.")
                # Drain a bounded body before refusing it; unread TCP bytes can reset
                # the socket on Windows and hide a 403 response from the client.
                body = self.rfile.read(length)
                if not self.valid_host() or self.headers.get("Origin") not in allowed_origins or not secrets.compare_digest(self.headers.get("X-CleanupTV-Token", ""), token):
                    return self.send(403, {"error": "Chỉ nhận thao tác từ giao diện CleanupTV đang mở."})
                p = json.loads(body)
                if not isinstance(p, dict):
                    raise UserError("Yêu cầu không hợp lệ.")
                action = urlsplit(self.path).path.removeprefix("/api/")
                if action not in ACTIONS:
                    return self.send(404, {"error": "Thao tác không có trong ứng dụng."})
                service.start(action, p)
                return self.send(202, {"accepted": True})
            except (ValueError, UserError) as e:
                return self.send(400, {"error": str(e)})
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    service = Service()
    service.data.mkdir(parents=True, exist_ok=True)
    instance_lock = (service.data / "app.lock").open("a+b")
    if instance_lock.tell() == 0:
        instance_lock.write(b"0")
        instance_lock.flush()
    instance_lock.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(instance_lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(instance_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        try:
            existing_port = int(json.loads((service.data / "server.json").read_text())["port"])
            if not 1 <= existing_port <= 65535:
                raise ValueError()
            existing_url = f"http://127.0.0.1:{existing_port}"
            print("CleanupTV dang chay: " + existing_url, flush=True)
            if args.open:
                webbrowser.open(existing_url)
        except (OSError, ValueError, KeyError):
            print("CleanupTV dang khoi dong o cua so khac. Hay doi vai giay.", flush=True)
        instance_lock.close()
        return
    server = make_server(service, args.port)
    atomic_json(service.data / "server.json", {"port":server.server_port})
    service.start_recovery()
    url = f"http://127.0.0.1:{server.server_port}"
    print("CleanupTV: " + url, flush=True)
    print("Giu cua so nay. Ctrl+C de dung.", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.recovery_stop.set()
        server.server_close()
        instance_lock.close()


if __name__ == "__main__":
    main()
