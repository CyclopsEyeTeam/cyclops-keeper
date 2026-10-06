import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/cyclops-keeper/scripts"))
import terminal


def record(state="idle", **extra):
    return {"schema":"activity-face/v1", "state":state, "event":"SessionStart",
            "updated_at":1000, "sequence":1, "active_tools":[],
            "active_subagents":[], "transitions":[], **extra}


def body(value):
    return value.rsplit("\n", 1)[0]


class TerminalIdentityTests(unittest.TestCase):
    def test_unicode_uses_smooth_subcell_curves(self):
        frame=terminal.render(record(),100,32,mode="focus",reduced_motion=True)
        self.assertGreater(sum(0x2801 <= ord(c) <= 0x28ff for c in body(frame)),50)
        self.assertEqual(set(map(len,frame.splitlines())),{100})

    def test_unobserved_and_stale_apertures_are_hollow(self):
        live=terminal.render(record("tool"),100,32,mode="focus",reduced_motion=True)
        missing=terminal.render(record("unknown"),100,32,mode="focus",reduced_motion=True)
        old=terminal.render(record("tool",stale=True),100,32,mode="focus",reduced_motion=True)
        self.assertNotEqual(body(live),body(missing))
        self.assertEqual(body(missing),body(old))

    def test_stale_relations_freeze_including_recent_event_gestures(self):
        snapshot=record("tool",stale=True,active_tools=[{"key":"a"*64,"kind":"execute","sequence":2}],
                        transitions=[{"sequence":2,"event":"PreToolUse","at":1000,"key":"a"*64,"kind":"execute"}])
        first=terminal.render(snapshot,100,32,mode="focus",now=1000.1)
        later=terminal.render(snapshot,100,32,mode="focus",now=1000.4)
        self.assertEqual(first,later)

    def test_ascii_stale_tool_and_branch_starts_freeze(self):
        snapshot=record("branching",stale=True,
            active_tools=[{"key":"a"*64,"kind":"execute","sequence":2}],
            active_subagents=[{"key":"b"*64,"sequence":3}],
            transitions=[{"sequence":2,"event":"PreToolUse","at":1000,"key":"a"*64,"kind":"execute"},
                         {"sequence":3,"event":"SubagentStart","at":1000,"key":"b"*64,"kind":None}])
        first=terminal.render(snapshot,100,32,mode="focus",now=1000.1,unicode=False)
        later=terminal.render(snapshot,100,32,mode="focus",now=1000.4,unicode=False)
        self.assertTrue(first==later,"stale ASCII relations must not extend between old observations")

    def test_exact_late_returns_remain_visible_after_session_end(self):
        baseline=record("ended")
        returned=record("ended",transitions=[
            {"sequence":2,"event":"PostToolUse","at":1000,"key":"a"*64,"kind":"execute"},
            {"sequence":3,"event":"SubagentStop","at":1000,"key":"b"*64,"kind":None}])
        for unicode in (True,False):
            a=terminal.render(baseline,100,32,mode="focus",now=1000.2,unicode=unicode)
            b=terminal.render(returned,100,32,mode="focus",now=1000.2,unicode=unicode)
            self.assertTrue(body(a)!=body(b),"an observed late return must retract its own ended-session anchor")

    def test_full_relation_keys_determine_routes(self):
        first=record("tool",active_tools=[{"key":"0"*63+"1","kind":"inspect","sequence":2}])
        second=record("tool",active_tools=[{"key":"0"*63+"2","kind":"inspect","sequence":2}])
        a=terminal.render(first,100,32,mode="focus",reduced_motion=True)
        b=terminal.render(second,100,32,mode="focus",reduced_motion=True)
        self.assertNotEqual(body(a),body(b))

    def test_colour_has_distinct_layers_and_same_visible_bounds(self):
        self.assertIn("colour",__import__("inspect").signature(terminal.render).parameters)
        plain=terminal.render(record(),100,32,mode="focus",reduced_motion=True)
        styled=terminal.render(record(),100,32,mode="focus",reduced_motion=True,colour=True,truecolour=True)
        self.assertEqual(re.sub(r"\x1b\[[0-9;]*m","",styled),plain)
        self.assertGreaterEqual(len(set(re.findall(r"\x1b\[38;2;[0-9;]+m",styled))),3)
        self.assertTrue(styled.endswith("\x1b[0m"))

    def test_approval_and_fold_change_body_without_motion(self):
        live=body(terminal.render(record("tool"),100,32,mode="focus",reduced_motion=True))
        waiting=body(terminal.render(record("waiting"),100,32,mode="focus",reduced_motion=True))
        folded=body(terminal.render(record("compacting"),100,32,mode="focus",reduced_motion=True))
        self.assertNotEqual(live,waiting)
        self.assertNotEqual(live,folded)


if __name__ == "__main__":
    unittest.main()
