"""Limited assistance for TVs changed by another tool; never claims factory restoration."""
import re

HOME_INTENT = "-a android.intent.action.MAIN -c android.intent.category.HOME"
COMPONENT_RE = re.compile(r"[A-Za-z_][\w.]*/[\w.$]+\Z")
WARNING = ("Không tìm thấy bản sao lưu của Thanh Tùng Tiên Sinh Cleanup trên máy tính này. "
           "Nếu trước đây bạn dùng công cụ khác hoặc đã mất bản lưu, chương trình không thể biết chính xác trạng thái ban đầu. "
           "Chỉ hỗ trợ kiểm tra và thử chuyển về Màn hình chính hệ thống còn trên TV; không khôi phục toàn bộ hoặc cài đặt gốc.")


class RescueMixin:
    def rescue_inspect(self, p):
        self.guard()
        system = {line[8:].strip() for line in self.sh("pm list packages -s --user 0").splitlines() if line.startswith("package:")}
        # MATCH_DISABLED_COMPONENTS: include Home handlers disabled by a previous tool.
        raw = self.sh("cmd package query-activities --brief --user 0 --query-flags 0x200 " + HOME_INTENT)
        candidates = []
        for line in raw.splitlines():
            comp = line.strip()
            package = comp.split("/")[0]
            if not COMPONENT_RE.fullmatch(comp) or package not in system or re.search(r"factory|test|setup|wizard|resolver|recovery|diagnos|provision", comp, re.I):
                continue
            detail = self.sh("dumpsys package " + package)
            state = re.search(r"User 0:[^\r\n]*\benabled=(\d+)", detail)
            if not state or int(state[1]) not in range(5):
                continue
            if comp not in {item["component"] for item in candidates}:
                candidates.append({"component": comp, "package": package, "state": int(state[1]), "disabled": int(state[1]) in (2,3,4)})
        try:
            current, _ = self.homes()
        except self.error:
            current = ""
        self.rescue_candidates = candidates
        has_backup = bool(self.records())
        return {"candidates": candidates, "currentHome": current, "hasBackup": has_backup,
                "message": ("Có bản lưu trên máy. Ưu tiên Khôi phục bằng đúng bản lưu nếu phù hợp. " if has_backup else WARNING),
                "canTrial": bool(current),
                "limitation": "Không tự bật lại hàng loạt gói đã tắt, không tải launcher gốc thay thế và không factory reset. Nếu không xác minh được Home hiện tại, chỉ chẩn đoán và hướng dẫn thủ công."}

    def rescue_home(self, p):
        if p.get("acknowledgeLimitedRecovery") is not True:
            raise self.error("Xác nhận đã hiểu giới hạn: chỉ thử chuyển Home, không phục hồi toàn bộ trạng thái ban đầu.")
        return self.transaction(p, self.rescue_changes)

    def rescue_changes(self, p):
        path, record = self.load_record(p.get("backup"))
        info = self.rescue_inspect({})
        selected = next((item for item in info["candidates"] if item["component"] == p.get("component")), None)
        if selected is None or not info["canTrial"]:
            raise self.error("Không đủ bằng chứng để thử Home hệ thống an toàn. Chưa thay đổi TV; xem hướng dẫn thủ công.")
        if selected["component"] == info["currentHome"] and not selected["disabled"]:
            raise self.error("Màn hình chính này đã đang được chọn. Không cần thay đổi.")
        self.begin_trial(path, record)
        record["rescue_change"] = dict(selected, status="pending")
        record["home_pending"] = True
        self.write_record(path, record)
        if selected["disabled"]:
            self.sh("pm enable --user 0 " + selected["package"])
            detail = self.sh("dumpsys package " + selected["package"])
            actual = re.search(r"User 0:[^\r\n]*\benabled=(\d+)", detail)
            if not actual or int(actual[1]) != 1:
                raise self.error("TV chưa bật lại Home hệ thống. Dừng và hoàn tác lần hỗ trợ này.")
        self.set_home(selected["component"])
        record["rescue_change"]["status"] = "changed"
        self.write_record(path, record)
        return {"backup": record["id"], "message": "Đang thử Home hệ thống trong 3 phút. Giữ nếu hoạt động ổn. Hoàn tác chỉ quay về trạng thái trước lần hỗ trợ này, không phải trạng thái trước khi dùng công cụ khác."}

    def rescue_undo(self, path, record):
        change = record.get("rescue_change")
        if not change or change.get("status") == "restored":
            return
        # Return to the prior working Home BEFORE restoring a disabled OEM package state.
        if record.get("home_pending"):
            self.set_home(record["home_before"])
            record["home_pending"] = False
            self.write_record(path, record)
        package, state = change["package"], change["state"]
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+", package) or type(state) is not int or state not in range(5):
            raise self.error("Nhật ký hỗ trợ Home không hợp lệ.")
        if state in (2,3,4):
            command = {2: "disable", 3: "disable-user", 4: "disable-until-used"}[state]
            self.sh("pm " + command + " --user 0 " + package)
            raw = self.sh("dumpsys package " + package)
            actual = re.search(r"User 0:[^\r\n]*\benabled=(\d+)", raw)
            if not actual or int(actual[1]) != state:
                raise self.error("Chưa xác minh trạng thái Home sau hoàn tác. Giữ ứng dụng mở để thử lại.")
        change["status"] = "restored"
        self.write_record(path, record)
