import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/cyclops-keeper/scripts"))
import terminal


def record(state="idle", event="SessionStart", **extra):
    return {"schema":"activity-face/v1", "state":state, "event":event,
            "updated_at":1000, "sequence":1, "active_tools":[],
            "active_subagents":[], "transitions":[], **extra}


def caption(frame):
    return re.sub(r"\x1b\[[0-9;]*m", "", frame).splitlines()[-2]


class TerminalCaptionTests(unittest.TestCase):
    def test_balanced_and_focus_reserve_an_event_caption_above_the_status(self):
        snapshot=record("tool", "PreToolUse", active_tools=[
            {"key":"a"*64,"kind":"execute","sequence":2},
            {"key":"b"*64,"kind":"inspect","sequence":3}])
        for mode in ("balanced", "focus"):
            frame=terminal.render(snapshot,80,24,mode=mode,reduced_motion=True)
            lines=frame.splitlines()
            self.assertEqual(len(lines),24)
            self.assertTrue(all(len(line)==80 for line in lines))
            self.assertIn("I send a work line outward.", lines[-2])
            self.assertIn("2 call threads still out", lines[-2])
            self.assertIn("KEEPER / TOOL ACTIVITY", lines[-1])

    def test_every_observed_host_event_has_a_neutral_caption(self):
        cases={
            "SessionStart":("idle", "I meet the session at its first signal."),
            "UserPromptSubmit":("working", "I turn toward the fresh line."),
            "PreToolUse":("tool", "I send a work line outward."),
            "PermissionRequest":("waiting", "I hold at the gate; permission has the next move."),
            "PostToolUse":("working", "The work line comes back to me."),
            "Stop":("stopped", "I let this turn come to rest."),
            "Interrupt":("interrupted", "I hold at the interrupted line."),
            "SessionEnd":("ended", "The session line closes here."),
            "PreCompact":("compacting", "I gather the weave inward for a fold."),
            "PostCompact":("idle", "The fold is through; I open the weave again."),
            "SubagentStart":("branching", "I let a side thread run beside mine."),
            "SubagentStop":("working", "That side thread closes; its tether falls quiet."),
        }
        for event,(state,phrase) in cases.items():
            with self.subTest(event=event):
                frame=terminal.render(record(state,event),80,18,mode="focus",reduced_motion=True)
                self.assertIn(phrase,caption(frame))

    def test_returns_do_not_claim_success_and_keep_other_live_relations_visible(self):
        snapshot=record("tool", "PostToolUse", active_tools=[
            {"key":"b"*64,"kind":"inspect","sequence":3}])
        text=caption(terminal.render(snapshot,80,18,reduced_motion=True))
        self.assertIn("The work line comes back to me.",text)
        self.assertIn("1 call thread still out",text)
        self.assertNotIn("success",text.casefold())
        self.assertNotIn("complete",text.casefold())

    def test_missing_and_stale_signals_do_not_reuse_event_copy(self):
        missing=caption(terminal.render(record("unknown","SessionStart"),80,18))
        stale=caption(terminal.render(record("working","UserPromptSubmit",stale=True),80,18))
        self.assertIn("No session signal yet",missing)
        self.assertIn("Signal stale",stale)
        self.assertNotIn("turn has started",stale)

    def test_caption_never_displays_private_payload_values(self):
        snapshot=record("tool", "PreToolUse", prompt="PRIVATE_PROMPT",
                        tool_name="PRIVATE_TOOL", tool_input={"command":"PRIVATE_ARGUMENT"},
                        tool_response="PRIVATE_RESULT", session_id="PRIVATE_SESSION",
                        active_tools=[{"key":"a"*64,"kind":"execute","sequence":2}])
        frame=terminal.render(snapshot,100,24)
        for secret in ("PRIVATE_PROMPT", "PRIVATE_TOOL", "PRIVATE_ARGUMENT",
                       "PRIVATE_RESULT", "PRIVATE_SESSION"):
            self.assertNotIn(secret,frame)

    def test_caption_wording_is_independent_of_calm_and_reduced_motion(self):
        snapshot=record("branching", "SubagentStart", active_subagents=[
            {"key":"a"*64,"sequence":2}])
        regular=caption(terminal.render(snapshot,80,18))
        quiet=caption(terminal.render(snapshot,80,18,calm=True,reduced_motion=True))
        self.assertEqual(regular,quiet)

    def test_narrow_captions_keep_the_event_copy_whole_and_skip_counts_that_do_not_fit(self):
        narrow=caption(terminal.render(record("compacting","PreCompact"),24,12,reduced_motion=True))
        self.assertIn("Gathering the weave.",narrow)
        self.assertNotIn("…",narrow)
        one_call=record("tool","PreToolUse",active_tools=[
            {"key":"a"*64,"kind":"execute","sequence":2}])
        medium=caption(terminal.render(one_call,64,12,reduced_motion=True))
        self.assertIn("I send a work line outward.",medium)
        self.assertIn("1 call thread still out",medium)
        tight=caption(terminal.render(one_call,24,12,reduced_motion=True))
        self.assertIn("Work line out.",tight)
        self.assertNotIn("1 call",tight)

    def test_caption_band_collapses_at_small_sizes_and_all_sizes_keep_exact_bounds(self):
        for width,height in ((80,24),(23,10),(6,1)):
            for unicode in (True,False):
                with self.subTest(width=width,height=height,unicode=unicode):
                    frame=terminal.render(record("tool","PreToolUse"),width,height,
                                          unicode=unicode,reduced_motion=True)
                    lines=frame.splitlines()
                    self.assertEqual(len(lines),height)
                    self.assertTrue(all(len(line)==width for line in lines))
                    if width < 24:
                        self.assertNotIn("Tool call started",frame)


if __name__ == "__main__":
    unittest.main()
