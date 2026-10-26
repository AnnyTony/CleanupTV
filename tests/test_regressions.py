"""Regression scenarios from the 0.3 audit; no TV or tool downloads required."""
import copy
import json
from pathlib import Path
import re
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import app
import test_app


class RegressionTests(unittest.TestCase):
    setUp = test_app.WorkflowTests.setUp
    prepare = test_app.WorkflowTests.prepare
    create_apk_fixture = test_app.WorkflowTests.create_apk_fixture

    def read(self, rid):
        return json.loads(self.service.record_path(rid).read_text(encoding="utf-8"))

    def keep(self, rid):
        with patch("app.time.sleep"):
            return self.service.keep({"backup": rid, "checks": sorted(app.MANUAL_CHECKS)})

    def test_long_jobs_cannot_occupy_recovery_queue_during_trial(self):
        rid = self.prepare()
        self.service.apply({"backup": rid, "packages": ["com.miui.tv.analytics"]})
        for action in ("measure", "analyze", "build", "connect", "apply", "optimize", "install", "backup", "discover"):
            with self.subTest(action=action), self.assertRaises(app.UserError):
                self.service.start(action, {})
            self.assertTrue(self.service.lock.acquire(blocking=False))
            self.service.lock.release()

    def test_actual_worker_restores_expired_trial_with_long_job_rejected(self):
        rid = self.prepare()
        self.service.apply({"backup": rid, "packages": ["com.miui.tv.analytics"]})
        r = self.read(rid)
        r["trial_until"] = time.time() - 1
        app.atomic_json(self.service.record_path(rid), r)
        with self.assertRaises(app.UserError):
            self.service.start("measure", {})
        restored = threading.Event()
        original = self.adb.shell
        def shell(target, command, **kwargs):
            value = original(target, command, **kwargs)
            if command.startswith("pm default-state"):
                restored.set()
            return value
        with patch.object(self.adb, "shell", side_effect=shell):
            self.service.start_recovery()
            try:
                self.assertTrue(restored.wait(7), "Recovery worker did not run")
                # Wait for the same queue lock, not just the first restore command.
                self.assertTrue(self.service.lock.acquire(timeout=2))
                self.service.lock.release()
                self.assertTrue(self.read(rid)["restored"])
            finally:
                self.service.recovery_stop.set()

    def test_command_timeout_uses_remaining_budget_and_detects_overrun(self):
        self.service.command_deadline = 100
        with patch("app.time.monotonic", side_effect=[99, 101]), patch.object(self.adb, "run", wraps=self.adb.run) as run:
            with self.assertRaises(app.TrialExpired):
                self.service.sh("getprop ro.serialno", timeout=30)
        self.assertEqual(run.call_args.kwargs["timeout"], 1)

    def test_elapsed_budget_prevents_sending_next_command(self):
        self.service.command_deadline = 100
        count = len(self.adb.calls)
        with patch("app.time.monotonic", return_value=101), self.assertRaises(app.TrialExpired):
            self.service.sh("pm disable-user --user 0 com.miui.tv.analytics")
        self.assertEqual(len(self.adb.calls), count)

    def test_mutation_overrun_restores_and_never_sends_next_package(self):
        rid = self.prepare()
        clock = [100.0]
        original = self.adb.run
        def delayed(*args, **kwargs):
            value = original(*args, **kwargs)
            if args[-1] == "pm disable-user --user 0 com.miui.tv.analytics":
                clock[0] += 200
            return value
        with patch("app.time.monotonic", side_effect=lambda: clock[0]), patch.object(self.adb, "run", side_effect=delayed):
            with self.assertRaises(app.UserError):
                self.service.apply({"backup": rid, "packages": ["com.miui.tv.analytics", "com.xiaomi.statistic"]})
        self.assertEqual(self.adb.states["com.miui.tv.analytics"], 0)
        self.assertNotIn("pm disable-user --user 0 com.xiaomi.statistic", self.adb.calls)

    def test_expired_read_yields_queue_directly_to_rollback(self):
        rid = self.prepare()
        self.service.apply({"backup": rid, "packages": ["com.miui.tv.analytics"]})
        original = self.service.verify
        def expire(params):
            record = self.read(rid)
            record["trial_until"] = time.time() - 1
            app.atomic_json(self.service.record_path(rid), record)
            self.service.command_deadline = time.monotonic() - 1
            return original(params)
        with patch.object(self.service, "verify", side_effect=expire):
            self.service.start("verify", {})
            self.assertTrue(self.service.lock.acquire(timeout=3))
            self.service.lock.release()
        self.assertTrue(self.read(rid)["restored"])

    def test_rejected_second_operation_does_not_roll_back_active_trial(self):
        rid = self.prepare()
        self.service.apply({"backup": rid, "packages": ["com.miui.tv.analytics"]})
        before = self.read(rid)
        with self.assertRaises(app.UserError):
            self.service.optimize({"backup": rid, "preset": "invalid"})
        self.assertEqual(self.read(rid), before)
        self.assertEqual(self.adb.states["com.miui.tv.analytics"], 3)

    def test_later_failure_preserves_accepted_animations(self):
        first = self.prepare()
        self.service.optimize({"backup": first, "preset": "reduced_motion"})
        self.keep(first)
        self.adb.fail_package = "com.xiaomi.statistic"
        with self.assertRaises(app.UserError):
            self.service.apply({"backup": first, "packages": ["com.miui.tv.analytics", "com.xiaomi.statistic"]})
        self.assertTrue(all(value == "0.5" for value in self.adb.animations.values()))
        self.assertTrue(self.read(first)["confirmed"])
        self.assertFalse(self.read(first)["restored"])
        self.assertEqual(self.adb.states["com.miui.tv.analytics"], 0)

    def test_each_trial_has_checkpoint_and_undo_newest_first(self):
        first = self.prepare()
        self.service.optimize({"backup": first, "preset": "reduced_motion"})
        self.keep(first)
        second = self.service.apply({"backup": first, "packages": ["com.miui.tv.analytics"]})["backup"]
        self.assertNotEqual(first, second)
        self.assertEqual(self.read(second)["parent"], first)
        with self.assertRaisesRegex(app.UserError, "mới hơn"):
            self.service.restore({"backup": first})
        self.service.restore({"backup": second})
        self.assertTrue(all(value == "0.5" for value in self.adb.animations.values()))
        self.service.restore({"backup": first})
        self.assertTrue(all(value == "1.0" for value in self.adb.animations.values()))

    def test_validation_error_after_keep_does_not_change_accepted_state(self):
        rid = self.prepare()
        self.service.optimize({"backup": rid, "preset": "reduced_motion"})
        self.keep(rid)
        with self.assertRaises(app.UserError):
            self.service.apply({"backup": rid, "packages": ["com.android.systemui"]})
        self.assertTrue(all(value == "0.5" for value in self.adb.animations.values()))
        self.assertEqual(self.service.recovery_records(), [])

    def test_keep_requires_real_world_checklist(self):
        rid = self.prepare()
        self.service.apply({"backup": rid, "packages": ["com.miui.tv.analytics"]})
        with self.assertRaisesRegex(app.UserError, "Xác nhận"):
            self.service.keep({"backup": rid})
        self.assertTrue(self.read(rid)["trial_until"])

    def test_keep_reopens_home_when_user_is_in_settings(self):
        rid = self.prepare()
        self.service.apply({"backup": rid, "packages": ["com.miui.tv.analytics"]})
        self.adb.focus = "com.android.settings/.Settings"
        self.keep(rid)
        self.assertEqual(self.adb.focus, self.adb.home)

    def test_crashed_home_refuses_keep_and_restores_changes(self):
        rid = self.prepare()
        self.service.apply({"backup": rid, "packages": ["com.miui.tv.analytics"]})
        self.adb.crash_home = True
        with self.assertRaisesRegex(app.UserError, "khôi phục"):
            self.keep(rid)
        self.assertEqual(self.adb.states["com.miui.tv.analytics"], 0)
        self.assertFalse(self.read(rid)["confirmed"] if "confirmed" in self.read(rid) else False)

    def test_restart_loop_during_home_probe_is_rejected(self):
        self.adb.restart_home = True
        with patch("app.time.sleep"), self.assertRaisesRegex(app.UserError, "khởi động lại"):
            self.service.verify({})

    def test_failed_explicit_home_check_queues_immediate_rollback(self):
        rid = self.prepare()
        self.service.apply({"backup": rid, "packages": ["com.miui.tv.analytics"]})
        self.adb.crash_home = True
        with patch("app.time.sleep"):
            self.service.start("verify", {})
            self.assertTrue(self.service.lock.acquire(timeout=3))
            self.service.lock.release()
        self.assertTrue(self.read(rid)["restored"])
        self.assertEqual(self.adb.states["com.miui.tv.analytics"], 0)

    def test_passive_health_does_not_interrupt_video(self):
        rid = self.prepare()
        self.service.apply({"backup": rid, "packages": ["com.miui.tv.analytics"]})
        self.adb.focus = "com.netflix.ninja/.Player"
        self.adb.calls.clear()
        self.service.recover_due()
        self.assertNotIn("input keyevent 3", self.adb.calls)
        self.assertEqual(self.adb.focus, "com.netflix.ninja/.Player")

    def test_reboot_does_not_extend_trial_deadline(self):
        rid = self.prepare()
        self.service.apply({"backup": rid, "packages": ["com.miui.tv.analytics"]})
        before = self.read(rid)["trial_until"]
        self.service.reboot({})
        self.assertEqual(self.read(rid)["trial_until"], before)

    def test_model_and_header_firmware_are_not_verified_firmware(self):
        profile = {"brand": "Sony", "tv": "Sony Model Z9999", "header": "ORIGINAL_EU_123", "os": "Android 12"}
        device = {"manufacturer": "Sony", "model": "Model Z9999", "android": "12", "firmware": "totally-different-firmware"}
        self.assertEqual(app.match_profiles(device, [profile])[0]["compatibility"], "model_only")
        device["firmware"] = "ORIGINAL_EU_123"
        self.assertEqual(app.match_profiles(device, [profile])[0]["compatibility"], "model_only")

    def test_model_dependent_rule_requires_explicit_exact_firmware(self):
        item = dict(self.service.catalog[0], requireProfile=True)
        self.service.catalog = [item]
        profile = {"id": "test", "tv": "Mi Test TV", "brand": "Xiaomi", "os": "Android 12", "header": "test firmware", "source": "test", "notes": "", "packages": [{"package": item["package"]}]}
        for verified, expected in (([], 0), (["test/firmware/v1-old"], 0), (["test/firmware/v1"], 1)):
            profile["verifiedFingerprints"] = verified
            self.service.profile_match = app.match_profiles(self.service.device, [profile])
            self.assertEqual(len(self.service.analyze({})["candidates"]), expected)

    def test_reference_files_are_reused_and_guard_reads_only_identity(self):
        other = app.Service(self.temp.name, self.adb)
        self.assertIs(other.profiles, self.service.profiles)
        self.adb.calls.clear()
        self.service.guard()
        self.assertEqual(self.adb.calls, ["getprop ro.serialno", "getprop ro.build.fingerprint"])

    def test_cpu_records_three_samples_without_tv_mutation(self):
        with patch("app.time.sleep"):
            result = self.service.measure({"phase": "before"})["measurement"]
        self.assertEqual(result["cpuSamples"], 3)
        self.assertEqual(result["cpuRange"], [30.0, 30.0])

    def test_java_properties_round_trip_unicode_and_special_characters(self):
        value = "C:/TV phòng khách/日本語/😀/#SDK=!test\\dir"
        encoded = app.java_property(value)
        encoded.encode("ascii")
        # Decode Java's UTF-16 escape units, then the escaped property metacharacters.
        units = re.sub(r"\\u([0-9a-f]{4})", lambda m: chr(int(m[1], 16)), encoded)
        units = re.sub(r"\\([\\:=#! ])", r"\1", units)
        decoded = units.encode("utf-16-be", "surrogatepass").decode("utf-16-be")
        self.assertEqual(decoded, value)

    def test_full_build_preparation_in_vietnamese_directory(self):
        root = Path(self.temp.name) / "TV phòng khách"
        root.mkdir()
        manifest = {key: {"sha256": "fixture", "name": key} for key in ("jdk", "sdk", "source")}
        (root / "downloads.json").write_text(json.dumps(manifest))
        runtime = root / ".runtime"
        launcher = runtime / "source/pinned/launcher"
        for key in manifest:
            (runtime / key).mkdir(parents=True)
            (runtime / key / ".complete").write_text("fixture")
        for file in (runtime / "jdk/pinned/bin/java.exe", launcher / "gradlew.bat", runtime / "android-sdk/platforms/android-34/android.jar", runtime / "android-sdk/build-tools/34.0.0/aapt2.exe", launcher / "app/build/outputs/apk/release/app-release.apk"):
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"fixture")
        with patch("app.ROOT", root), patch("app.prepare_overlay", return_value=launcher), patch("app.subprocess.run") as run:
            run.return_value.returncode = 0
            self.service.build({"licenses": True})
        self.assertIn(r"\u00f2", (launcher / "local.properties").read_text(encoding="ascii"))
        self.assertTrue((runtime / "launcher-receipt.json").is_file())


if __name__ == "__main__":
    unittest.main()
