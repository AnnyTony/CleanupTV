import base64
import copy
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import app
import personalize
import rescue
import test_app


class FeatureAdb(test_app.FakeAdb):
    def __init__(self):
        super().__init__()
        self.personal = {key: None for key in personalize.KEYS}
        self.city = {"name": None, "latitude": None, "longitude": None}
        self.pictures = {}
        self.last_upload = b""
        self.refuse_personal = False
        self.system = {self.original_home.split('/')[0]}
        self.system_homes = [self.original_home]

    def run(self, *args, **kwargs):
        if len(args) > 3 and args[2] == "push":
            self.last_upload = Path(args[3]).read_bytes()
        if args[2:6] == ("exec-out", "content", "read", "--uri"):
            return self.pictures.get(args[-1].split('/')[-1], b"")
        return super().run(*args, **kwargs)

    def shell(self, target, command, **kwargs):
        if command.startswith("content call "):
            self.calls.append(command)
            target = self.personal if "com.gathin.tvhome.cleanup" in command else self.city
            if " --method write" in command:
                values = json.loads(base64.b64decode(command.split(" --arg ")[1]))
                if not (self.refuse_personal and values.get("columns") == 7):
                    target.update(values)
            result = {"version": 1, "marketVersion": 1, "values": target}
            if target is self.personal:
                result["pictures"] = list(self.pictures)
            return "Result: Bundle[{payload=" + base64.b64encode(json.dumps(result).encode()).decode() + "}]"
        if command.startswith("content write "):
            name = command.split(" < ")[0].split('/')[-1]
            self.pictures[name] = self.last_upload
            return ""
        if command == "pm list packages -s --user 0":
            return "\n".join("package:" + name for name in self.system)
        if "query-activities" in command and "--query-flags" in command:
            return "\n".join(self.system_homes)
        if command.startswith("pm disable --user 0 ") or command.startswith("pm disable-until-used --user 0 "):
            self.calls.append(command)
            self.states[command.split()[-1]] = 2 if command.startswith("pm disable ") else 4
            return "Success"
        return super().shell(target, command, **kwargs)


class FeatureTests(unittest.TestCase):
    def setUp(self):
        test_app.WorkflowTests.setUp(self)
        self.adb = FeatureAdb()
        self.service = app.Service(self.temp.name, self.adb)
        self.service.connect({"host": "192.168.1.50", "port": 5555, "consent": True})

    prepare = test_app.WorkflowTests.prepare

    def read(self, rid):
        return json.loads(self.service.record_path(rid).read_text(encoding="utf-8"))

    def test_personalization_uses_exact_absent_preferences_on_restore(self):
        rid = self.prepare()
        self.service.personal_apply({"backup": rid, "values": {"cyt_name": "Gia đình tôi", "cyt_lunar": True, "columns": 6}})
        self.assertEqual(self.adb.personal["columns"], 6)
        self.service.restore({"backup": rid})
        self.assertTrue(all(value is None for value in self.adb.personal.values()))

    def test_personalization_failure_preserves_accepted_package_change(self):
        first = self.prepare()
        self.service.apply({"backup": first, "packages": ["com.miui.tv.analytics"]})
        with patch("app.time.sleep"):
            self.service.keep({"backup": first, "checks": list(app.MANUAL_CHECKS)})
        self.adb.refuse_personal = True
        with self.assertRaises(app.UserError):
            self.service.personal_apply({"backup": first, "values": {"columns": 7}})
        self.assertEqual(self.adb.states["com.miui.tv.analytics"], 3)
        self.assertTrue(all(value is None for value in self.adb.personal.values()))

    def test_personalization_journal_written_before_provider_mutation(self):
        rid = self.prepare()
        original = self.service.personal_call
        def check(target, method="read", values=None):
            if method == "write":
                self.assertTrue(self.read(rid)["personal_changes"])
            return original(target, method, values)
        with patch.object(self.service, "personal_call", side_effect=check), patch("app.time.sleep"):
            self.service.personal_apply({"backup": rid, "values": {"cyt_lunar": True}})

    def test_personalization_expiry_is_recovered_after_restart(self):
        rid = self.prepare()
        with patch("app.time.sleep"):
            self.service.personal_apply({"backup": rid, "values": {"columns": 6}})
            fresh = app.Service(self.temp.name, self.adb)
            fresh.recover_due(self.read(rid)["trial_until"] + 1)
        self.assertIsNone(self.adb.personal["columns"])
        self.assertTrue(self.read(rid)["restored"])

    def test_name_payload_is_encoded_not_interpolated_into_shell(self):
        with patch("app.time.sleep"):
            self.service.personal_apply({"backup": self.prepare(), "values": {"cyt_name": "Tùng'; reboot; #"}})
        calls = [call for call in self.adb.calls if isinstance(call, str) and call.startswith("content call")]
        self.assertTrue(calls)
        self.assertTrue(all("reboot" not in command for command in calls))

    def test_rejects_unknown_keys_types_paths_and_ranges(self):
        for values in ({"shell": "reboot"}, {"columns": True}, {"columns": 99}, {"cyt_lunar": "true"}, {"wallpaper_choice": "../x.jpg"}, {"cyt_background": "red;id"}, {"cyt_name": "x\ny"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                personalize.valid_preferences(values)

    def test_market_preferences_restore_absence_and_previous_choices(self):
        self.adb.personal.update(cyt_gold=False, cyt_currency="JPY", cyt_fuel_zone=2)
        before=copy.deepcopy(self.adb.personal)
        with patch("app.time.sleep"):
            rid=self.prepare()
            self.service.personal_apply({"backup":rid,"values":{"cyt_gold":True,"cyt_fx":True,"cyt_fuel":True,"cyt_currency":"USD","cyt_fuel_zone":1}})
            self.assertTrue(self.adb.personal["cyt_gold"])
            self.assertEqual(self.adb.personal["cyt_currency"],"USD")
            self.service.restore({"backup":rid})
        self.assertEqual(self.adb.personal,before)

    def test_market_choices_reject_wrong_types_urls_and_unknown_currencies(self):
        for values in ({"cyt_gold":"true"},{"cyt_fx":1},{"cyt_fuel":[]},{"cyt_fuel_zone":True},{"cyt_fuel_zone":3},{"cyt_currency":"https://evil.example"},{"cyt_currency":"usd"},{"cyt_currency":"BTC"}):
            with self.subTest(values=values),self.assertRaises(ValueError):
                personalize.valid_preferences(values)

    def test_weather_city_is_taken_only_from_search_results(self):
        rid = self.prepare()
        city = {"name": "Test City", "latitude": 10.0, "longitude": 106.0}
        with self.assertRaises(app.UserError):
            self.service.personal_apply({"backup": rid, "city": city})
        self.service.city_results = [city]
        with patch("app.time.sleep"):
            self.service.personal_apply({"backup": rid, "city": city})
            self.assertEqual(self.adb.city, city)
            self.service.restore({"backup": rid})
        self.assertIsNone(self.adb.city["name"])

    def test_search_endpoint_cannot_be_replaced_by_user_url(self):
        body = json.dumps({"results": [{"name": "Test", "country": "Vietnam", "latitude": 10, "longitude": 106}]}).encode()
        with patch("personalize.urllib.request.urlopen") as open_url:
            open_url.return_value.__enter__.return_value.read.return_value = body
            self.service.city_search({"name": "https://evil.example/?x=1"})
        self.assertTrue(open_url.call_args.args[0].startswith("https://geocoding-api.open-meteo.com/v1/search?"))

    def test_invalid_wallpaper_does_not_reach_tv(self):
        calls = len(self.adb.calls)
        with self.assertRaises(app.UserError):
            self.service.personal_upload({"data": base64.b64encode(b"not a jpeg").decode()})
        self.assertEqual(len(self.adb.calls)-calls, 2)  # identity guard only

    def test_jpeg_dimensions_are_bounded(self):
        # SOF0 marker with 1920x1080 dimensions; structural parsing only.
        data = bytes.fromhex("ffd8ffc00008080438078003")
        self.assertEqual(personalize.jpeg_size(data), (1920, 1080))
        with self.assertRaises(ValueError):
            personalize.jpeg_size(bytes.fromhex("ffd8ffc00008082000200003"))

    def test_other_app_preferences_are_not_exposed_by_provider(self):
        with self.assertRaises(app.UserError):
            self.service.personal_call("com.other.application", "write", {})

    def prepare_rescue(self, disabled=3):
        self.adb.home = self.adb.focus = "org.example.otherhome/.MainActivity"
        self.adb.states["org.example.otherhome"] = 0
        self.adb.states[self.adb.original_home.split('/')[0]] = disabled
        return self.service.backup({})["backup"]

    def test_rescue_disclaimer_does_not_claim_factory_restore(self):
        info = self.service.rescue_inspect({})
        self.assertFalse(info["hasBackup"])
        self.assertIn("Thanh Tùng Tiên Sinh Cleanup", info["message"])
        self.assertIn("không thể biết chính xác", info["message"])
        self.assertNotIn("pm enable", str(self.adb.calls))

    def test_rescue_filters_non_system_and_factory_home(self):
        self.adb.system_homes += ["org.evil.app/.Home", "com.vendor.factory/.Home"]
        self.adb.system.add("com.vendor.factory")
        info = self.service.rescue_inspect({})
        self.assertEqual([x["component"] for x in info["candidates"]], [self.adb.original_home])

    def test_rescue_requires_explicit_acknowledgement(self):
        rid = self.prepare_rescue()
        with self.assertRaises(app.UserError):
            self.service.rescue_home({"backup": rid, "component": self.adb.original_home})
        self.assertEqual(self.adb.states[self.adb.original_home.split('/')[0]], 3)

    def test_rescue_enables_only_selected_home_and_can_keep_it(self):
        rid = self.prepare_rescue()
        before = copy.deepcopy(self.adb.states)
        with patch("app.time.sleep"):
            self.service.rescue_home({"backup": rid, "component": self.adb.original_home, "acknowledgeLimitedRecovery": True})
            self.service.keep({"backup": rid, "checks": list(app.MANUAL_CHECKS)})
        self.assertEqual(self.adb.home, self.adb.original_home)
        for package in before:
            if package != self.adb.original_home.split('/')[0]:
                self.assertEqual(before[package], self.adb.states[package])

    def test_rescue_undo_restores_home_before_disabling_oem(self):
        for disabled in (2, 3, 4):
            with self.subTest(disabled=disabled):
                rid = self.prepare_rescue(disabled)
                with patch("app.time.sleep"):
                    self.service.rescue_home({"backup": rid, "component": self.adb.original_home, "acknowledgeLimitedRecovery": True})
                    self.adb.calls.clear()
                    self.service.restore({"backup": rid})
                self.assertEqual(self.adb.home, "org.example.otherhome/.MainActivity")
                self.assertEqual(self.adb.states[self.adb.original_home.split('/')[0]], disabled)
                commands = [s for s in self.adb.calls if isinstance(s, str)]
                switch = next(i for i,s in enumerate(commands) if s.startswith("cmd package set-home-activity"))
                disable = next(i for i,s in enumerate(commands) if s.startswith("pm disable"))
                self.assertLess(switch, disable)

    def test_failed_return_home_never_disables_last_working_home(self):
        rid = self.prepare_rescue()
        with patch("app.time.sleep"):
            self.service.rescue_home({"backup": rid, "component": self.adb.original_home, "acknowledgeLimitedRecovery": True})
        self.adb.calls.clear()
        with patch.object(self.service, "set_home", side_effect=app.UserError("Cannot return")), self.assertRaises(app.UserError):
            self.service.restore({"backup": rid})
        self.assertFalse(any(isinstance(s,str) and s.startswith("pm disable") for s in self.adb.calls))
        self.assertTrue(self.read(rid)["recovery_pending"])

    def test_no_current_home_is_diagnosis_only(self):
        rid = self.prepare_rescue()
        with patch.object(self.service, "homes", side_effect=app.UserError("Unknown Home")):
            self.assertFalse(self.service.rescue_inspect({})["canTrial"])
            with self.assertRaises(app.UserError):
                self.service.rescue_home({"backup": rid, "component": self.adb.original_home, "acknowledgeLimitedRecovery": True})
        self.assertEqual(self.adb.states[self.adb.original_home.split('/')[0]], 3)

    def test_identical_jobs_have_distinct_ids_for_browser_polling(self):
        with patch("app.time.sleep"):
            self.service.start("verify", {})
            self.assertTrue(self.service.lock.acquire(timeout=3)); self.service.lock.release()
            first = self.service.job["id"]
            self.service.start("verify", {})
            self.assertTrue(self.service.lock.acquire(timeout=3)); self.service.lock.release()
        self.assertNotEqual(first, self.service.job["id"])


if __name__ == "__main__":
    unittest.main()
