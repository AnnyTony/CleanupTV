import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import app


class FakeAdb:
    """Models device state, including vendors that report success without changing it."""
    path = Path(__file__)

    def __init__(self):
        self.states = {"com.miui.tv.analytics": 0, "com.xiaomi.statistic": 1,
                       "com.google.android.apps.tv.launcherx": 0}
        self.original_home = "com.google.android.apps.tv.launcherx/.MainActivity"
        self.home = self.original_home
        self.focus = self.home
        self.serial = "private-test-device"
        self.manufacturer = "Xiaomi"
        self.model = "Mi Test TV"
        self.codename = ""
        self.calls = []
        self.silent_refusal = False
        self.drop_after_disable = False
        self.network_down = False
        self.fail_package = ""
        self.dangerous_input = False
        self.reject_home = False
        self.empty_settings = False
        self.animations = {key:"1.0" for key in app.ANIMATION_KEYS}
        self.refuse_animation = ""
        self.crash_home = False
        self.restart_home = False

    def run(self, *args, **kwargs):
        if len(args) == 4 and args[2] == "shell":
            return self.shell(args[1], args[3], **kwargs)
        self.calls.append(args)
        if args[0] == "connect":
            return "connected to " + args[1]
        if "get-state" in args:
            return "device"
        if args[0] == "pair":
            return "Successfully paired"
        if args[:2] == ("mdns", "services"):
            return "test _adb-tls-connect._tcp 192.168.1.50:37555"
        return ""

    def shell(self, target, cmd, **kwargs):
        if self.network_down:
            raise app.UserError("TV currently unreachable")
        self.calls.append(cmd)
        if cmd.startswith("getprop "):
            key = cmd.split()[-1]
            return {"ro.product.manufacturer": self.manufacturer, "ro.product.model": self.model,
                "ro.product.brand":self.manufacturer, "ro.product.device":self.codename,
                "ro.build.version.release": "12", "ro.build.version.sdk": "31", "ro.build.fingerprint": "test/firmware/v1",
                "ro.serialno": self.serial, "ro.adb.secure": "1"}.get(key, "")
        if cmd == "getprop":
            return "[ro.product.model]: [Mi Test TV]"
        if cmd == "pm list features":
            return "feature:android.software.leanback"
        if cmd == "pm list packages --user 0":
            return "\n".join("package:" + p for p in self.states)
        if cmd == "pm list packages -d --user 0":
            return "\n".join("package:" + p for p,s in self.states.items() if s in (2,3,4))
        if "query-activities" in cmd:
            return self.original_home + "\n" + app.COMPONENT
        if "resolve-activity" in cmd:
            return self.home
        if cmd.startswith("dumpsys package "):
            p = cmd.split()[-1]
            if p not in self.states:
                return "Unable to find package"
            return f"Package [{p}]\n User 0: installed=true hidden=false enabled={self.states[p]}\n" + ("android.permission.TV_INPUT_HARDWARE" if self.dangerous_input else "")
        if cmd.startswith("settings list "):
            return "" if self.empty_settings else "some_setting=value"
        if cmd.startswith("settings get global "):
            return self.animations.get(cmd.split()[-1],"null")
        if cmd.startswith("settings put global "):
            _,_,_,key,value=cmd.split()
            if key!=self.refuse_animation:
                self.animations[key]=value
            return ""
        if cmd.startswith("settings delete global "):
            self.animations.pop(cmd.split()[-1],None)
            return ""
        if cmd == "cat /proc/stat":
            count=sum(1 for c in self.calls if c==cmd)
            return f"cpu  {100+20*(count-1)} 0 {100+10*(count-1)} {800+70*(count-1)} 0 0 0 0\n"
        if cmd.startswith("pidof "):
            if self.crash_home:
                return ""
            return str(100 + (len(self.calls) if self.restart_home else 0))
        if cmd == "cat /proc/meminfo":
            return "MemTotal: 2048000 kB\nMemAvailable: 512000 kB\n"
        if cmd == "df -k /data":
            return "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/block/data 8192000 4096000 4096000 50% /data\n"
        if cmd.startswith("pm disable-user"):
            if not self.silent_refusal and cmd.split()[-1] != self.fail_package:
                self.states[cmd.split()[-1]] = 3
            if self.drop_after_disable:
                self.network_down = True
                raise app.UserError("Network disconnected after mutation")
            return "Success"
        if cmd.startswith("pm default-state") or cmd.startswith("pm enable "):
            self.states[cmd.split()[-1]] = 0 if "default-state" in cmd else 1
            return "Success"
        if cmd.startswith("pm install -r "):
            self.states[app.PACKAGE] = 0
            return "Success"
        if cmd.startswith("cmd package set-home-activity"):
            if not self.reject_home or cmd.split()[-1] == self.original_home:
                self.home = cmd.split()[-1]
            return "Success"
        if cmd == "input keyevent 3":
            self.focus = self.home
            return ""
        if cmd == "dumpsys activity activities":
            return "mResumedActivity: ActivityRecord { " + self.focus + " }"
        return ""


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.adb = FakeAdb()
        self.service = app.Service(self.temp.name, self.adb)
        self.service.connect({"host":"192.168.1.50", "port":5555,"consent":True})

    def prepare(self):
        self.service.analyze({})
        return self.service.backup({})["backup"]

    def test_model_detected_without_user_input(self):
        self.assertEqual(self.service.device["model"], "Mi Test TV")
        self.assertNotIn("serial", self.service.device)

    def test_disabled_at_factory_not_offered_or_changed(self):
        self.adb.states["com.xiaomi.statistic"] = 3
        r = self.service.analyze({})
        self.assertEqual([x["package"] for x in r["candidates"]], ["com.miui.tv.analytics"])
        rid = self.service.backup({})["backup"]
        self.service.apply({"backup":rid, "packages":["com.miui.tv.analytics"]})
        self.service.restore({"backup":rid})
        self.assertEqual(self.adb.states["com.xiaomi.statistic"], 3)

    def test_restore_exact_default_and_explicit_enable(self):
        before = copy.deepcopy(self.adb.states)
        rid = self.prepare()
        self.service.apply({"backup":rid, "packages":["com.miui.tv.analytics", "com.xiaomi.statistic"]})
        self.assertEqual(self.adb.states["com.miui.tv.analytics"], 3)
        self.service.restore({"backup":rid})
        self.assertEqual(self.adb.states, before)

    def test_write_ahead_record_survives_network_loss(self):
        rid = self.prepare()
        self.adb.drop_after_disable = True
        with self.assertRaises(app.UserError):
            self.service.apply({"backup":rid, "packages":["com.miui.tv.analytics", "com.xiaomi.statistic"]})
        record = json.loads(self.service.record_path(rid).read_text(encoding="utf-8"))
        self.assertEqual(record["changes"], [{"package":"com.miui.tv.analytics", "before":0,"status":"pending"}])
        self.adb.drop_after_disable = False
        self.adb.network_down = False
        self.service.restore({"backup":rid})
        self.assertEqual(self.adb.states["com.miui.tv.analytics"], 0)
        self.assertEqual(self.adb.states["com.xiaomi.statistic"], 1)

    def test_silent_failure_stops_next_package(self):
        rid = self.prepare()
        self.adb.silent_refusal = True
        with self.assertRaisesRegex(app.UserError, "không cho tắt"):
            self.service.apply({"backup":rid, "packages":["com.miui.tv.analytics", "com.xiaomi.statistic"]})
        mutations = [x for x in self.adb.calls if isinstance(x,str) and x.startswith("pm disable-user")]
        self.assertEqual(len(mutations), 1)

    def test_ambiguous_failure_blocks_further_mutations_until_restore(self):
        rid = self.prepare()
        self.adb.drop_after_disable = True
        with self.assertRaises(app.UserError):
            self.service.apply({"backup":rid, "packages":["com.miui.tv.analytics"]})
        self.adb.drop_after_disable = False
        self.adb.network_down = False
        with self.assertRaisesRegex(app.UserError,"chưa xác nhận"):
            self.service.apply({"backup":rid, "packages":["com.xiaomi.statistic"]})
        with self.assertRaisesRegex(app.UserError,"khôi phục|chưa xác nhận"):
            self.service.install({"backup":rid})
        self.assertEqual(self.adb.states["com.xiaomi.statistic"],1)
        self.service.recover_due()
        self.assertTrue(json.loads(self.service.record_path(rid).read_text(encoding="utf-8"))["restored"])

    def test_other_device_cannot_restore(self):
        rid = self.prepare()
        self.adb.serial = "another-tv"
        with self.assertRaises(app.UserError):
            self.service.restore({"backup":rid})
        self.assertFalse(any(isinstance(x,str) and x.startswith("pm enable") for x in self.adb.calls))

    def test_backup_failure_prevents_changes(self):
        self.adb.empty_settings = True
        with self.assertRaises(app.UserError):
            self.service.backup({})
        self.assertEqual(list(Path(self.temp.name).glob("backups/*/record.json")), [])

    def test_unreviewed_package_is_rejected(self):
        rid = self.prepare()
        with self.assertRaises(app.UserError):
            self.service.apply({"backup":rid,"packages":["com.android.systemui"]})

    def test_input_permission_blocks_even_catalog_entry(self):
        self.adb.dangerous_input = True
        self.assertEqual(self.service.analyze({})["candidates"], [])

    def test_input_permission_rechecked_before_apply(self):
        rid = self.prepare()
        self.adb.dangerous_input = True
        with self.assertRaisesRegex(app.UserError, "bảo vệ"):
            self.service.apply({"backup":rid,"packages":["com.miui.tv.analytics"]})

    def test_backup_required(self):
        self.service.analyze({})
        with self.assertRaises(app.UserError):
            self.service.apply({"backup":"does-not-exist", "packages":["com.miui.tv.analytics"]})

    def test_home_success_requires_real_focus(self):
        with patch("app.time.sleep"):
            self.service.set_home(app.COMPONENT)
            self.assertEqual(self.adb.home, app.COMPONENT)
            self.adb.reject_home = True
            self.adb.home = self.adb.original_home
            with self.assertRaises(app.UserError):
                self.service.set_home(app.COMPONENT)

    def test_restore_home_without_uninstall_or_disabling_stock(self):
        rid = self.prepare()
        path = self.service.record_path(rid)
        r = json.loads(path.read_text(encoding="utf-8"))
        r["home_pending"] = True
        app.atomic_json(path, r)
        self.adb.home = app.COMPONENT
        with patch("app.time.sleep"):
            self.service.restore({"backup":rid})
        self.assertEqual(self.adb.home, self.adb.original_home)
        self.assertFalse(any(isinstance(x,str) and "uninstall" in x for x in self.adb.calls))

    def test_restart_finds_existing_backups_only_for_same_device(self):
        rid = self.prepare()
        fresh = app.Service(self.temp.name, self.adb)
        fresh.connect({"host":"192.168.1.51","port":5555,"consent":True})
        self.assertEqual(fresh.records()[0]["id"], rid)
        self.adb.serial = "another-tv"
        fresh.connect({"host":"192.168.1.52","port":5555,"consent":True})
        self.assertEqual(fresh.records(), [])

    def test_closed_port_timeout_is_not_success(self):
        with patch("app.socket.create_connection", side_effect=TimeoutError):
            self.assertIsNone(self.service.closed({"host":"192.168.1.50","port":5555})["closed"])
        with patch("app.socket.create_connection", side_effect=ConnectionRefusedError):
            self.assertTrue(self.service.closed({"host":"192.168.1.50","port":5555})["closed"])

    def test_sony_recognition_and_catalog_without_model_prompt(self):
        self.adb.manufacturer = "Sony"
        self.adb.model = "BRAVIA_VH2_TEST"
        self.adb.states.update({"tv.samba.ssm":0,"com.sony.dtv.promos":3,"com.sonyericsson.idd.agent":1})
        self.service.connect({"host":"192.168.1.50","port":5555,"consent":True})
        candidates = {c["package"] for c in self.service.analyze({})["candidates"]}
        self.assertEqual(candidates, {"tv.samba.ssm","com.sonyericsson.idd.agent"})
        self.assertEqual(self.service.device["model"],"BRAVIA_VH2_TEST")

    def create_apk_fixture(self):
        root = Path(self.temp.name) / "fixture"
        runtime = root / ".runtime"
        runtime.mkdir(parents=True)
        data = b"test-only-apk"
        (runtime / "launcher.apk").write_bytes(data)
        app.atomic_json(runtime / "launcher-receipt.json", {"sha256":app.hashlib.sha256(data).hexdigest(), "overlay":app.overlay_hash(root)})
        return root

    def test_install_rolls_back_when_vendor_ignores_home_preference(self):
        rid = self.prepare()
        root = self.create_apk_fixture()
        self.adb.reject_home = True
        with patch("app.ROOT",root), patch("app.time.sleep"):
            with self.assertRaisesRegex(app.UserError,"trở lại Home gốc"):
                self.service.install({"backup":rid})
        record = json.loads(self.service.record_path(rid).read_text(encoding="utf-8"))
        self.assertTrue(record["launcher_installed"])
        self.assertFalse(record["home_pending"])
        self.assertTrue(record["restored"])
        self.assertEqual(self.adb.home,self.adb.original_home)
        self.assertFalse(any(isinstance(x,str) and x.startswith("pm disable-user") for x in self.adb.calls))

    def test_install_refuses_apk_modified_after_build(self):
        rid = self.prepare()
        root = self.create_apk_fixture()
        (root / ".runtime/launcher.apk").write_bytes(b"modified")
        with patch("app.ROOT",root):
            with self.assertRaisesRegex(app.UserError,"APK thay đổi"):
                self.service.install({"backup":rid})

    def test_install_journals_home_before_preference_change(self):
        rid = self.prepare()
        root = self.create_apk_fixture()
        original = self.service.set_home
        def checked(component):
            record = json.loads(self.service.record_path(rid).read_text(encoding="utf-8"))
            self.assertTrue(record["home_pending"])
            return original(component)
        with patch("app.ROOT",root), patch("app.time.sleep"), patch.object(self.service,"set_home",side_effect=checked):
            self.service.install({"backup":rid})
        self.assertEqual(self.adb.home, app.COMPONENT)

    def test_failure_automatically_restores_earlier_packages(self):
        before = copy.deepcopy(self.adb.states)
        rid = self.prepare()
        self.adb.fail_package = "com.xiaomi.statistic"
        with self.assertRaisesRegex(app.UserError,"Đã tự khôi phục"):
            self.service.apply({"backup":rid,"packages":["com.miui.tv.analytics","com.xiaomi.statistic"]})
        self.assertEqual(self.adb.states,before)
        self.assertTrue(json.loads(self.service.record_path(rid).read_text(encoding="utf-8"))["restored"])

    def test_trial_expiry_restores_without_user_action(self):
        before = copy.deepcopy(self.adb.states)
        rid = self.prepare()
        self.service.apply({"backup":rid,"packages":["com.miui.tv.analytics"]})
        r = json.loads(self.service.record_path(rid).read_text(encoding="utf-8"))
        self.service.recover_due(r["trial_until"]+1)
        self.assertEqual(self.adb.states,before)
        self.assertEqual(self.service.recovery_records(),[])

    def test_keep_change_cancels_deadline_but_preserves_manual_restore(self):
        rid = self.prepare()
        self.service.apply({"backup":rid,"packages":["com.miui.tv.analytics"]})
        with patch("app.time.sleep"):
            self.service.keep({"backup":rid, "checks": sorted(app.MANUAL_CHECKS)})
        self.service.recover_due(app.time.time()+1000)
        self.assertEqual(self.adb.states["com.miui.tv.analytics"],3)
        self.service.restore({"backup":rid})
        self.assertEqual(self.adb.states["com.miui.tv.analytics"],0)

    def test_restart_resumes_pending_rollback_after_connection_returns(self):
        rid = self.prepare()
        self.adb.drop_after_disable = True
        with self.assertRaises(app.UserError):
            self.service.apply({"backup":rid,"packages":["com.miui.tv.analytics"]})
        r = json.loads(self.service.record_path(rid).read_text(encoding="utf-8"))
        self.assertTrue(r["recovery_pending"])
        fresh = app.Service(self.temp.name,self.adb)
        fresh.recover_due()
        self.assertFalse(json.loads(fresh.record_path(rid).read_text(encoding="utf-8"))["restored"])
        self.adb.network_down = False
        fresh.recover_due()
        self.assertEqual(self.adb.states["com.miui.tv.analytics"],0)
        self.assertTrue(json.loads(fresh.record_path(rid).read_text(encoding="utf-8"))["restored"])

    def test_reconnecting_same_device_updates_recovery_ip(self):
        rid=self.prepare()
        self.service.apply({"backup":rid,"packages":["com.miui.tv.analytics"]})
        self.service.connect({"host":"192.168.1.88","port":5555,"consent":True})
        r=json.loads(self.service.record_path(rid).read_text(encoding="utf-8"))
        self.assertEqual(r["target"],"192.168.1.88:5555")
        self.service.recover_due(r["trial_until"]+1)
        self.assertEqual(self.adb.states["com.miui.tv.analytics"],0)

    def test_recovery_does_not_touch_other_tv_at_reused_ip(self):
        rid = self.prepare()
        self.service.apply({"backup":rid,"packages":["com.miui.tv.analytics"]})
        r=json.loads(self.service.record_path(rid).read_text(encoding="utf-8"))
        self.adb.serial = "different-device-at-same-ip"
        self.service.recover_due(r["trial_until"]+1)
        self.assertEqual(self.adb.states["com.miui.tv.analytics"],3)
        r=json.loads(self.service.record_path(rid).read_text(encoding="utf-8"))
        self.assertTrue(r["recovery_pending"])
        self.assertFalse(r["restored"])

    def test_trial_health_failure_triggers_restore(self):
        rid = self.prepare()
        self.service.apply({"backup":rid,"packages":["com.miui.tv.analytics"]})
        self.adb.home = "com.other.home/.MainActivity"
        with patch("app.time.sleep"):
            self.service.recover_due()
            # A failed check queues recovery, then the next recovery cycle attempts rollback.
            self.service.recover_due()
        self.assertEqual(self.adb.states["com.miui.tv.analytics"],0)

    def test_fresh_backup_blocked_until_trial_decision(self):
        rid=self.prepare()
        self.service.apply({"backup":rid,"packages":["com.miui.tv.analytics"]})
        with self.assertRaisesRegex(app.UserError,"lần thử"):
            self.service.backup({})

    def test_animation_trial_restores_exact_original_and_absent_values(self):
        self.adb.animations={"window_animation_scale":"2.0","animator_duration_scale":"0"}
        before=copy.deepcopy(self.adb.animations)
        rid=self.prepare()
        self.service.optimize({"backup":rid,"preset":"reduced_motion"})
        self.assertEqual(self.adb.animations['window_animation_scale'],'0.5')
        self.assertEqual(self.adb.animations['animator_duration_scale'],'0')
        self.service.restore({"backup":rid})
        self.assertEqual(self.adb.animations,before)

    def test_animation_failure_restores_preceding_settings(self):
        before=copy.deepcopy(self.adb.animations)
        rid=self.prepare()
        self.adb.refuse_animation='transition_animation_scale'
        with self.assertRaisesRegex(app.UserError,'Đã tự khôi phục'):
            self.service.optimize({"backup":rid,"preset":"reduced_motion"})
        self.assertEqual(self.adb.animations,before)

    def test_animation_expiry_is_automatically_restored(self):
        before=copy.deepcopy(self.adb.animations)
        rid=self.prepare()
        self.service.optimize({"backup":rid,"preset":"reduced_motion"})
        r=json.loads(self.service.record_path(rid).read_text(encoding='utf-8'))
        self.service.recover_due(r['trial_until']+1)
        self.assertEqual(self.adb.animations,before)

    def test_resource_measurements_do_not_modify_tv(self):
        before=copy.deepcopy(self.adb.states)
        with patch('app.time.sleep'):
            result=self.service.measure({'phase':'before'})['measurement']
        self.assertEqual(result['cpuPercent'],30.0)
        self.assertEqual(result['memoryAvailableMiB'],500.0)
        self.assertEqual(result['storageFreeMiB'],4000.0)
        self.assertEqual(self.adb.states,before)
        self.assertIn('before',self.service.measurement_report())

    def test_unsupported_metrics_are_unknown_not_zero(self):
        result=app.parse_resources('Permission denied','not supported')
        self.assertIsNone(result['memoryAvailableMiB'])
        self.assertIsNone(result['storageFreeMiB'])
        self.assertIsNone(app.cpu_ticks('Permission denied'))


class ProfileTests(unittest.TestCase):
    def test_brand_alone_is_not_a_model_match(self):
        profiles=json.loads((app.ROOT/'profiles.json').read_text(encoding='utf-8'))['profiles']
        self.assertEqual(app.match_profiles({'manufacturer':'Sony','model':'Unknown','android':'12'},profiles),[])

    def test_sony_device_code_and_android_match_real_database(self):
        profiles=json.loads((app.ROOT/'profiles.json').read_text(encoding='utf-8'))['profiles']
        found=app.match_profiles({'manufacturer':'Sony','model':'BRAVIA 4K VH2','codename':'BRAVIA_VH2','android':'12','firmware':'BRAVIA_VH2_EU-user'},profiles)
        self.assertTrue(found)
        self.assertIn('sony-bravia-4k-vh2',{r['id'] for r in found})
        self.assertTrue(all(r['brand']=='Sony' for r in found))

    def test_wrong_android_version_is_not_a_match(self):
        profile={'brand':'Sony','tv':'Sony Unique Model Z9999','header':'# device codename_xyz123','os':'Android TV 12'}
        self.assertEqual(app.match_profiles({'manufacturer':'Sony','model':'Unique Model Z9999','android':'14'},[profile]),[])

    def test_other_brand_with_same_device_code_is_not_a_match(self):
        profile={'brand':'Sony','tv':'Sony Model Z9999','header':'# device codename_xyz123','os':'Android TV 12'}
        self.assertEqual(app.match_profiles({'manufacturer':'TCL','codename':'codename_xyz123','android':'12'},[profile]),[])

    def test_all_curated_rules_have_upstream_provenance(self):
        profiles=json.loads((app.ROOT/'profiles.json').read_text(encoding='utf-8'))['profiles']
        rules=json.loads((app.ROOT/'catalog.json').read_text(encoding='utf-8'))
        sources={p['source']:{e['package'] for e in p['packages']} for p in profiles}
        for rule in rules:
            self.assertIn(rule['package'],sources[rule['source']])


class ValidationTests(unittest.TestCase):
    def test_atomic_journal_retries_transient_windows_file_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'record.json'
            original=Path.replace
            attempts=[]
            def replace(src,dest):
                attempts.append(1)
                if len(attempts)==1:
                    raise PermissionError('Windows file temporarily open')
                return original(src,dest)
            with patch.object(Path,'replace',replace), patch('app.time.sleep'):
                app.atomic_json(path,{'state':'durable'})
            self.assertEqual(json.loads(path.read_text()),{'state':'durable'})
            self.assertEqual(len(attempts),2)

    def test_endpoint_rejects_shell_public_and_loopback(self):
        for host in ("127.0.0.1","8.8.8.8","192.168.1.50;id","tv.local",None):
            with self.subTest(host=host), self.assertRaises(app.UserError):
                app.endpoint(host,5555)
        for port in ("5555&calc",0,65536,True):
            with self.subTest(port=port), self.assertRaises(app.UserError):
                app.endpoint("192.168.1.50",port)

    def test_critical_packages_protected(self):
        for pkg in ("com.android.systemui","com.google.android.permissioncontroller","com.google.android.overlay.modules.foo",
                    "com.android.providers.media","com.android.vending","com.google.android.gms","com.vendor.factorymenu",
                    "com.google.android.tungsten.setupwraith","com.vendor.updateservice"):
            with self.subTest(pkg=pkg):
                self.assertTrue(app.protected(pkg,"",set()))
        self.assertTrue(app.protected("com.foo.home", "", {"com.foo.home"}))
        self.assertTrue(app.protected("com.foo;reboot", "", set()))

    def test_unknown_enabled_state_fails_closed(self):
        for raw in ("", "Success", "User 10: installed=true enabled=0", "User 0: enabled=9"):
            with self.subTest(raw=raw), self.assertRaises(app.UserError):
                app.enabled_state(raw)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = app.Service(self.tmp.name, FakeAdb())
        self.server = app.make_server(self.service)
        self.port = self.server.server_port
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1",self.port,timeout=5)
        self.addCleanup(c.close)
        c.request(method,path,body,headers or {})
        r = c.getresponse()
        return r.status, r.read(), dict(r.headers)

    def test_loopback_only_and_static_assets(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        for route in ("/", "/app.js", "/style.css"):
            status,body,headers = self.request("GET",route)
            self.assertEqual(status,200)
            self.assertTrue(body)
            self.assertIn("frame-ancestors 'none'",headers["Content-Security-Policy"])

    def test_dns_rebinding_host_rejected(self):
        self.assertEqual(self.request("GET","/api/session",headers={"Host":"attacker.example"})[0],403)

    def test_csrf_rejected_even_with_token(self):
        _,body,_ = self.request("GET","/api/session")
        token = json.loads(body)["token"]
        self.assertEqual(self.request("POST","/api/discover","{}",{"Origin":"https://attacker.example","X-CleanupTV-Token":token})[0],403)
        self.assertEqual(self.request("POST","/api/discover","{}",{"Origin":f"http://127.0.0.1:{self.port}"})[0],403)

    def test_traversal_and_unknown_actions_rejected(self):
        self.assertEqual(self.request("GET","/../app.py")[0],404)
        _,body,_ = self.request("GET","/api/session")
        headers={"Origin":f"http://127.0.0.1:{self.port}","X-CleanupTV-Token":json.loads(body)["token"]}
        self.assertEqual(self.request("POST","/api/exec","{}",headers)[0],404)
        self.assertEqual(self.request("POST","/api/connect","[]",headers)[0],400)


if __name__ == "__main__":
    unittest.main()
