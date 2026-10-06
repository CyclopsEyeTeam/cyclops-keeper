"""Cyclops Link V1 conformance for Keeper's own implementation (scripts/link.py, scripts/keeper_link.py,
scripts/link_view.py).

Driven by the vendored, language-neutral fixtures in tests/fixtures/cyclops-link-v1/
(copied verbatim from Cyclops Link commit 3ba5cab). Nothing here imports another presence.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "cyclops-keeper" / "scripts"))
sys.dont_write_bytecode = True
import link  # noqa: E402
import keeper_link  # noqa: E402
import link_view  # noqa: E402
import terminal  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "cyclops-link-v1"
OTHER_UID = 4242


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def make(path: Path, fs: dict, content: bytes) -> bool:
    kind = fs.get("type", "file")
    if kind == "absent":
        return True
    if kind == "dir":
        path.mkdir()
    elif kind == "symlink":
        target = path.parent.parent / ("target-" + path.name)
        target.write_bytes(content)
        os.chmod(target, 0o600)
        path.symlink_to(target)
        return True
    else:
        path.write_bytes(content)
    os.chmod(path, int(fs.get("mode", "0600"), 8))
    if fs.get("owner") == "other":
        if os.getuid() != 0:
            return False
        os.chown(path, OTHER_UID, OTHER_UID)
    return True


class Derivation(unittest.TestCase):
    def setUp(self):
        self.d = load("derivation.json")
        self.salt = bytes.fromhex(self.d["salt_hex"])

    def test_rooms(self):
        for c in self.d["room"]:
            self.assertEqual(link.derive(self.salt, "room", os.fsencode(c["project_identity"])), c["expect"])

    def test_instances(self):
        for c in self.d["instance"]:
            ident = c["host"].encode() + b"\n" + c["session_id"].encode()
            self.assertEqual(link.derive(self.salt, "instance", ident), c["expect"])

    def test_keeper_instance_helper_uses_codex_host(self):
        for c in self.d["instance"]:
            if c["host"] == "codex":
                self.assertEqual(link.instance_for(self.salt, c["session_id"]), c["expect"])

    def test_salt_validity(self):
        with tempfile.TemporaryDirectory() as t:
            for c in self.d["salt_validity"]:
                box = Path(t) / c["name"]
                box.mkdir(mode=0o700)
                if not make(box / ".salt", c["fs"], c["content"].encode()):
                    continue
                self.assertEqual(link.salt_is_valid(box / ".salt"), c["expect"] == "valid", c["name"])

    def test_directory_validity(self):
        with tempfile.TemporaryDirectory() as t:
            for c in self.d["directory_validity"]:
                holder = Path(t) / ("d-" + c["name"])
                holder.mkdir(mode=0o700)
                p = holder / "cyclops-link"
                if c["fs"]["type"] == "symlink":
                    real = holder / "real"
                    real.mkdir(mode=0o700)
                    p.symlink_to(real)
                elif not make(p, c["fs"], b""):
                    continue
                if c["expect"] == "create-0700-then-use":
                    self.assertEqual(link.prepare_dir(p, create=True), p)
                    self.assertEqual(os.lstat(p).st_mode & 0o777, 0o700)
                else:
                    before = os.lstat(p).st_mode
                    got = link.prepare_dir(p, create=True)
                    self.assertEqual(got is not None, c["expect"] == "use", c["name"])
                    self.assertEqual(os.lstat(p).st_mode, before, "an existing directory is never repaired")

    def test_new_salt_is_random_0600_and_never_published(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "link"
            d.mkdir(mode=0o700)
            salt = link.load_salt(d, create=True)
            self.assertEqual(len(salt), 32)
            self.assertEqual(os.lstat(d / ".salt").st_mode & 0o777, 0o600)
            self.assertEqual(link.load_salt(d, create=True), salt, "an existing salt is reused")


class Records(unittest.TestCase):
    def test_every_case(self):
        rc = load("records.json")
        with tempfile.TemporaryDirectory() as t:
            for c in rc["cases"]:
                ld = Path(t) / c["name"]
                ld.mkdir(parents=True, mode=0o700)
                if "record" in c:
                    content = json.dumps(c["record"]).encode()
                elif "raw_hex" in c:
                    content = bytes.fromhex(c["raw_hex"])
                else:
                    content = (c.get("raw") or "").encode()
                p = ld / c["filename"]
                if not make(p, c["fs"], content):
                    continue
                self.assertEqual(link.read_record(p) is not None, c["expect"] == "valid", c["name"])

    def test_ignored_names(self):
        rc = load("records.json")
        good = {"v": 1, "presence": "keeper", "host": "codex", "instance": rc["fixture_instances"]["keeper-1"],
                "room": rc["fixture_room"], "state": "idle", "tools": 0, "branches": 0, "reaching": [],
                "updated_at": 1000.0, "ended": False}
        with tempfile.TemporaryDirectory() as t:
            for name in rc["ignored_names"]:
                p = Path(t) / name
                p.write_text(json.dumps(good))
                os.chmod(p, 0o600)
                self.assertIsNone(link.read_record(p), name)


class Views(unittest.TestCase):
    def test_every_scenario(self):
        vs = load("views.json")
        for a in link.PRESENCES:
            for b in link.PRESENCES:
                if a != b:
                    self.assertEqual(link.bearing(a, b), vs["bearings"][f"{a}->{b}"])
        with tempfile.TemporaryDirectory() as t:
            for s in vs["scenarios"]:
                ld = Path(t) / s["name"]
                ld.mkdir(mode=0o700)
                for f in s["files"]:
                    p = ld / f["filename"]
                    p.write_text(json.dumps(f["record"]))
                    os.chmod(p, 0o600)
                records = [r for r in (link.read_record(p) for p in sorted(ld.iterdir())) if r]
                self.assertEqual(link.compose(s["self"], records, s["now"], s["policy"]), s["expect"], s["name"])

    def test_reader_paces_and_follows_atomic_updates(self):
        with tempfile.TemporaryDirectory() as t:
            env = {"CYCLOPS_LINK_DIR": str(Path(t) / "link"), "HOME": t}
            w = link.Writer("0123456789abcdef", "fedcba9876543210", env)
            self.assertTrue(w.publish("working", now=1000.0))
            r = link.Reader(env)
            self.assertEqual([x["state"] for x in r.poll(now=10.0)], ["working"])
            w.publish("stopped", now=1001.0)
            self.assertEqual([x["state"] for x in r.poll(now=10.5)], ["working"], "at most one poll a second")
            self.assertEqual([x["state"] for x in r.poll(now=11.1)], ["stopped"])
            self.assertEqual([n for n in os.listdir(Path(t) / "link") if n.endswith(".tmp")], [])


class Lifecycle(unittest.TestCase):
    def test_off_by_default_and_no_shared_switch(self):
        with tempfile.TemporaryDirectory() as t:
            env = {"HOME": t, "CYCLOPS_LINK": "1"}
            self.assertFalse(link.enabled(env))
            self.assertTrue(link.enabled(dict(env, KEEPER_LINK="1")))
            link.set_enabled(True, {"HOME": t})
            self.assertTrue(link.enabled({"HOME": t}))
            self.assertFalse(link.enabled({"HOME": t, "KEEPER_LINK": "0"}))
            self.assertEqual(link.config_path({"HOME": t}), Path(t) / ".config" / "cyclops-keeper" / "link")

    def test_heartbeat_never_ends_and_refreshes_within_five_seconds(self):
        with tempfile.TemporaryDirectory() as t:
            w = link.Writer("0123456789abcdef", "fedcba9876543210", {"CYCLOPS_LINK_DIR": str(Path(t) / "link")})
            w.publish("idle", now=100.0)
            self.assertFalse(w.heartbeat(now=102.0))
            self.assertTrue(w.heartbeat(now=104.5))
            rec = json.loads((Path(t) / "link" / "keeper-0123456789abcdef.json").read_text())
            self.assertEqual((rec["state"], rec["ended"], rec["host"]), ("idle", False, "codex"))

    def test_unsafe_directory_is_refused_and_untouched(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "link"
            d.mkdir()
            os.chmod(d, 0o777)
            w = link.Writer("0123456789abcdef", "fedcba9876543210", {"CYCLOPS_LINK_DIR": str(d)})
            self.assertFalse(w.publish("working"))
            self.assertEqual((os.lstat(d).st_mode & 0o777, os.listdir(d)), (0o777, []))

    def test_write_failure_is_silent_and_bounded(self):
        with tempfile.TemporaryDirectory() as t:
            w = link.Writer("0123456789abcdef", "fedcba9876543210", {"CYCLOPS_LINK_DIR": str(Path(t) / "link")})
            self.assertTrue(w.publish("working", now=1.0))
            with mock.patch.object(link, "write_record", return_value=False) as wr:
                for k in range(10):
                    self.assertFalse(w.publish("working", now=2.0 + k))
                self.assertEqual(wr.call_count, link.MAX_FAILURES)

    def test_a_writer_never_takes_a_raw_identity(self):
        w = link.Writer("019a1c2e-7d3b-7f21-8a90-3b4c5d6e7f80", "/home/alex/clients/acme-merger", {})
        self.assertFalse(w.publish("working"))


class Adapter(unittest.TestCase):
    def test_reaching_comes_only_from_the_program_names_of_a_shell_call(self):
        cases = {
            'claude -p "hello"': "spark", "FOO=1 timeout 30 claude --print x": "spark",
            "cd /tmp && agy --prism": "prism", "echo hi | gemini -p x": "prism", "sudo -E env agy": "prism",
            "echo claude": None, "cat notes/agy.md": None, "grep gemini README.md": None,
            "git commit -m 'ask claude'": None, "python3 claude.py": None, "": None,
        }
        for command, want in cases.items():
            self.assertEqual(keeper_link.reaching_for({"command": command}), want, command)
        self.assertEqual(keeper_link.reaching_for({"command": ["bash", "-lc", "claude -p x"]}), "spark")
        self.assertEqual(keeper_link.reaching_for({"command": ["agy", "run"]}), "prism")
        self.assertIsNone(keeper_link.reaching_for({"command": 'claude -p "unterminated'}) and None)
        self.assertIsNone(keeper_link.reaching_for(None))

    def test_states_are_keepers_own_in_links_words(self):
        self.assertEqual(keeper_link.STATE["branching"], "working")
        self.assertNotIn("unknown", keeper_link.STATE)
        for state in keeper_link.STATE.values():
            self.assertIn(state, link.STATES)


class Room:
    """A Codex session driven through Keeper's real hook, with Link on, in a private home."""

    def __init__(self, t, *, reach=False, salt_hex=None):
        self.home = Path(t)
        self.data = self.home / "data"
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / "config"),
                        XDG_STATE_HOME=str(self.home / "state"), CYCLOPS_LINK_DIR=str(self.home / "link"),
                        PLUGIN_DATA=str(self.data), KEEPER_LINK="1", KEEPER_LINK_NO_WORKER="1")
        if reach:
            self.env["KEEPER_LINK_REACH"] = "1"
        else:
            self.env.pop("KEEPER_LINK_REACH", None)
        if salt_hex:
            d = self.home / "link"
            d.mkdir(mode=0o700)
            (d / ".salt").write_text(salt_hex + "\n")
            os.chmod(d / ".salt", 0o600)

    def hook(self, payload, cwd=None):
        subprocess.run([sys.executable, str(ROOT / "plugins/cyclops-keeper/scripts/hook.py")], input=json.dumps(payload),
                       text=True, env=self.env, cwd=cwd or self.home, capture_output=True, timeout=10)

    def key(self, session):
        return keeper_link._digest(session)

    def beat(self, session, **kw):
        return keeper_link.beat(self.data, self.key(session), self.env, **kw)

    def records(self):
        return [json.loads(p.read_text()) for p in sorted((self.home / "link").glob("keeper-*.json"))]


class Privacy(unittest.TestCase):
    def test_adversarial_codex_payloads_become_exactly_the_fixture_record(self):
        pv = load("privacy.json")
        facts = pv["host_facts"]
        with tempfile.TemporaryDirectory() as t:
            room = Room(t, reach=True, salt_hex=pv["salt_hex"])
            base = {"session_id": facts["session_id"], "cwd": facts["cwd"], "model": facts["model"],
                    "transcript_path": facts["paths"][0], "user": facts["user"]}
            room.hook(dict(base, hook_event_name="SessionStart", source="startup"))
            room.hook(dict(base, hook_event_name="UserPromptSubmit", turn_id="t1", prompt=facts["prompt"]))
            room.hook(dict(base, hook_event_name="PreToolUse", turn_id="t1", tool_name="Bash", tool_use_id=facts["call_id"],
                           tool_input={"command": facts["command"], "argv": facts["arguments"]}))
            self.assertEqual(room.beat(facts["session_id"], max_seconds=.3, poll=.05), "timeout")
            records = room.records()
            self.assertEqual(len(records), 1)
            got = {k: v for k, v in records[0].items() if k != "updated_at"}
            self.assertEqual(got, pv["expect_record"])
            # Nothing of the session leaves Keeper: not in Link, not in his own private Link facts
            everything = "".join(p.read_text(errors="replace") for p in (room.home / "link").iterdir() if p.is_file())
            everything += "".join(p.read_text(errors="replace") for p in (room.data / "link").iterdir() if p.is_file())
            for bad in pv["forbidden_substrings"]:
                self.assertNotIn(bad, everything)

    def test_without_reach_keeper_never_looks_at_the_command(self):
        pv = load("privacy.json")
        facts = pv["host_facts"]
        with tempfile.TemporaryDirectory() as t:
            room = Room(t, reach=False)
            with mock.patch.object(keeper_link, "reaching_for", side_effect=AssertionError("read a command")):
                for event in ({"hook_event_name": "UserPromptSubmit", "turn_id": "t1"},
                              {"hook_event_name": "PreToolUse", "turn_id": "t1", "tool_name": "Bash",
                               "tool_use_id": "c1", "tool_input": {"command": facts["command"]}}):
                    payload = dict(event, session_id="s1", cwd=t)
                    from activity import update
                    update(room.data, payload)
                    keeper_link.observe(room.data, payload, room.env)
            room.beat("s1", max_seconds=.2, poll=.05)
            self.assertEqual([r["reaching"] for r in room.records()], [[]])
            self.assertEqual([r["state"] for r in room.records()], ["tool"])

    def test_link_off_writes_nothing_at_all(self):
        with tempfile.TemporaryDirectory() as t:
            room = Room(t)
            room.env.pop("KEEPER_LINK")
            room.hook({"hook_event_name": "SessionStart", "source": "startup", "session_id": "s", "cwd": t})
            self.assertFalse((room.home / "link").exists())
            self.assertFalse((room.data / "link").exists())


class Worker(unittest.TestCase):
    def drive(self, room, session, *events):
        from activity import update
        for e in events:
            payload = dict(e, session_id=session, cwd=str(room.home))
            update(room.data, payload)
            keeper_link.observe(room.data, payload, room.env)

    def test_heartbeats_while_codex_lives_and_ends_truthfully_when_it_goes(self):
        with tempfile.TemporaryDirectory() as t:
            room = Room(t)
            self.drive(room, "s", {"hook_event_name": "SessionStart", "source": "startup"})
            clock = [1000.0]
            alive = [True]
            with mock.patch.object(keeper_link, "host_alive", side_effect=lambda h: alive[0]):
                def sleep(dt):
                    clock[0] += dt
                    if clock[0] > 1030:
                        alive[0] = False
                result = room.beat("s", clock=lambda: clock[0], sleep=sleep, poll=1.0)
            self.assertEqual(result, "ended")
            self.assertEqual(room.records(), [], "own file removed after the grace period")

    def test_ended_record_is_kept_for_the_grace_then_removed(self):
        with tempfile.TemporaryDirectory() as t:
            room = Room(t)
            self.drive(room, "s", {"hook_event_name": "SessionStart", "source": "startup"})
            seen = []
            clock = [500.0]
            calls = [0]

            def sleep(dt):
                clock[0] += dt
                calls[0] += 1
                if calls[0] == 3:
                    self.drive(room, "s", {"hook_event_name": "SessionEnd"})
                if room.records():
                    seen.append((round(clock[0]), room.records()[0]["state"], room.records()[0]["ended"]))
            with mock.patch.object(keeper_link, "host_alive", return_value=True):
                self.assertEqual(room.beat("s", clock=lambda: clock[0], sleep=sleep, poll=1.0), "ended")
            ended = [s for s in seen if s[2]]
            self.assertTrue(ended)
            self.assertGreaterEqual(ended[-1][0] - ended[0][0], 59)
            self.assertEqual(room.records(), [])

    def test_switching_link_off_ends_what_was_published(self):
        with tempfile.TemporaryDirectory() as t:
            room = Room(t)
            self.drive(room, "s", {"hook_event_name": "SessionStart", "source": "startup"})
            clock = [10.0]

            def sleep(dt):
                clock[0] += dt
                if 12 < clock[0] < 13.5:
                    room.env["KEEPER_LINK"] = "0"
                    self.assertEqual(room.records()[0]["ended"], False)
                if 14 < clock[0] < 15.5:
                    self.assertEqual((room.records()[0]["state"], room.records()[0]["ended"]), ("ended", True))
            with mock.patch.object(keeper_link, "host_alive", return_value=True):
                self.assertEqual(room.beat("s", clock=lambda: clock[0], sleep=sleep, poll=.5), "ended")

    def test_without_a_known_host_keeper_claims_no_end_and_lets_the_record_go_stale(self):
        with tempfile.TemporaryDirectory() as t:
            room = Room(t)
            self.drive(room, "s", {"hook_event_name": "SessionStart", "source": "startup"})
            clock = [0.0]
            with mock.patch.object(keeper_link, "host_alive", return_value=None):
                result = room.beat("s", clock=lambda: clock[0], sleep=lambda dt: clock.__setitem__(0, clock[0] + dt), poll=1)
            self.assertEqual(result, "no-host")
            self.assertEqual([(r["state"], r["ended"]) for r in room.records()], [("idle", False)])


class Shows(unittest.TestCase):
    def put(self, t, presence, host, session, state, reaching=(), room=None):
        env = {"CYCLOPS_LINK_DIR": str(Path(t) / "link")}
        d = link.prepare_dir(Path(env["CYCLOPS_LINK_DIR"]), create=True)
        salt = link.load_salt(d, create=True)
        rec = {"v": 1, "presence": presence, "host": host,
               "instance": link.derive(salt, "instance", (host + "\n" + session).encode()),
               "room": room or link.room_for(salt, os.getcwd()), "state": state, "tools": 0, "branches": 0,
               "reaching": list(reaching), "updated_at": __import__("time").time(), "ended": False}
        self.assertTrue(link.write_record(d, rec))
        return dict(env, KEEPER_LINK="1")

    def frame(self, env, t, width=90, height=26, **kw):
        watch = link_view.Watch(Path(t) / "data", env)
        view = watch.view(None)
        base = terminal.render("working", width, height, unicode=kw.get("unicode", True), colour=kw.get("colour", True),
                               truecolour=True)
        return view, base, link_view.overlay(base, width, height, view, watch.sheets, now=1.0,
                                             truecolour=True, **kw)

    def test_prism_upper_left_spark_left_in_their_own_looks_over_keepers_frame(self):
        with tempfile.TemporaryDirectory() as t:
            self.put(t, "spark", "claude-code", "s", "tool", reaching=["keeper"])
            env = self.put(t, "prism", "antigravity", "p", "working")
            view, base, frame = self.frame(env, t, colour=True)
            self.assertEqual({p["presence"]: p["bearing"] for p in view["peers"]}, {"prism": 120, "spark": 180})
            self.assertEqual(view["threads"], [{"from": "spark", "to": "keeper"}])
            lines = [link_view.SGR.sub("", l) for l in frame.split("\n")]
            prism_row = next(i for i, l in enumerate(lines) if "prism · working" in l)
            spark_row = next(i for i, l in enumerate(lines) if "spark · tool" in l)
            self.assertLess(prism_row, spark_row)
            self.assertTrue(lines[prism_row].startswith(" prism"))
            body = "\n".join(lines[prism_row:])
            self.assertIn("⟨", body)                         # Prism's own faceted core
            self.assertTrue(any(c in body for c in "▀▄"))    # Spark's own half-blocks
            self.assertEqual(lines[-1], [link_view.SGR.sub("", l) for l in base.split("\n")][-1], "status line untouched")

    def test_off_or_alone_leaves_keepers_frame_exactly_as_it_was(self):
        with tempfile.TemporaryDirectory() as t:
            env = self.put(t, "spark", "claude-code", "s", "tool")
            env.pop("KEEPER_LINK")
            view, base, frame = self.frame(env, t)
            self.assertIsNone(view)
            self.assertEqual(frame, base)

    def test_plain_ascii_stays_ascii(self):
        with tempfile.TemporaryDirectory() as t:
            self.put(t, "spark", "claude-code", "s", "tool", reaching=["keeper"])
            env = self.put(t, "prism", "antigravity", "p", "working")
            view, base, frame = self.frame(env, t, unicode=False, colour=False)
            self.assertTrue(all(ord(c) < 128 for c in frame))


class Commands(unittest.TestCase):
    def test_keeper_link_on_off_status_and_reach(self):
        with tempfile.TemporaryDirectory() as t:
            env = dict(os.environ, HOME=t, XDG_CONFIG_HOME=t + "/config", CYCLOPS_LINK_DIR=t + "/link", KEEPER_DATA=t + "/data")
            for k in ("KEEPER_LINK", "KEEPER_LINK_REACH"):
                env.pop(k, None)
            run = lambda *a: subprocess.run([str(ROOT / "keeper"), "link", *a], capture_output=True, text=True, env=env,
                                            timeout=10).stdout
            self.assertIn("Keeper Link: off", run("status"))
            self.assertIn("Keeper Link on", run("on"))
            self.assertIn("reach off", run("status"))
            self.assertIn("Keeper reach on", run("reach", "on"))
            self.assertIn("reach on", run("status"))
            self.assertIn("Keeper Link off", run("off"))
            self.assertIn("Keeper Link: off", run("status"))


if __name__ == "__main__":
    unittest.main()
