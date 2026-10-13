"""Real frames: decoration may wait; public facts, ownership and geometry may not."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'))
import terminal


class Pacing(unittest.TestCase):
    def setUp(self):
        self.record = {'state':'working', 'sequence':1, 'active_tools':[], 'active_subagents':[]}
        self.options = dict(colour=False, now=10)

    def test_decoration_holds_one_body_then_draws_at_the_deadline(self):
        cache = terminal.PacedRenderCache()
        with patch.object(terminal.time, 'monotonic', return_value=1):
            first = cache.frame(self.record, 80, 24, **self.options)
        with patch.object(terminal.time, 'monotonic', return_value=1.1):
            held = cache.frame(self.record, 80, 24, colour=False, now=11)
            self.assertEqual(held, first)
        with patch.object(terminal.time, 'monotonic', return_value=1.21):
            drawn = cache.frame(self.record, 80, 24, colour=False, now=11)
        self.assertEqual(drawn, terminal.render(self.record, 80, 24, colour=False, now=11))
        self.assertNotEqual(drawn, first)

    def test_polling_wakes_for_the_drawing_deadline_without_a_busy_wait(self):
        cache = terminal.PacedRenderCache()
        self.assertTrue(callable(getattr(cache, 'wait_timeout', None)),
                        'drawing is still quantized to the old polling loop')
        with patch.object(terminal.time, 'monotonic', return_value=1):
            cache.frame(self.record, 80, 24, **self.options)
        with patch.object(terminal.time, 'monotonic', return_value=1.18):
            self.assertAlmostEqual(cache.wait_timeout(.09), .02)
        with patch.object(terminal.time, 'monotonic', return_value=1.25):
            self.assertEqual(cache.wait_timeout(.09), 0)

    def test_public_changes_and_attachment_generations_bypass_the_limit(self):
        for change in [dict(state='interrupted', sequence=2), dict(state='ended', sequence=2),
                       dict(state='unknown', sequence=2), dict(state='waiting', sequence=2)]:
            cache = terminal.PacedRenderCache()
            record = dict(self.record, **change)
            with patch.object(terminal.time, 'monotonic', return_value=1):
                cache.frame(self.record, 80, 24, **self.options)
                frame = cache.frame(record, 80, 24, colour=False, now=11)
            self.assertEqual(frame, terminal.render(record, 80, 24, colour=False, now=11))
        cache = terminal.PacedRenderCache()
        with patch.object(terminal.time, 'monotonic', return_value=1):
            cache.frame(self.record, 80, 24, attachment_identity=('owner', 1), **self.options)
            frame = cache.frame(self.record, 80, 24, attachment_identity=('owner', 2), colour=False, now=11)
        self.assertEqual(frame, terminal.render(self.record, 80, 24, colour=False, now=11))

    def test_resize_stale_blink_and_motion_preferences_are_immediate(self):
        for width, height, settings in [(40, 12, {}), (80, 24, {'stale':True}),
                                       (80, 24, {'blink':True}), (80, 24, {'calm':True}),
                                       (80, 24, {'reduced_motion':True})]:
            cache = terminal.PacedRenderCache()
            with patch.object(terminal.time, 'monotonic', return_value=1):
                cache.frame(self.record, 80, 24, **self.options)
                frame = cache.frame(self.record, width, height, colour=False, now=11, **settings)
            self.assertEqual(frame, terminal.render(self.record, width, height, colour=False, now=11, **settings))

    def test_nested_in_place_tool_changes_invalidate_the_held_body(self):
        cache = terminal.PacedRenderCache()
        record = dict(self.record, active_tools=[{'key':'1'*64, 'kind':'execute', 'sequence':1}])
        with patch.object(terminal.time, 'monotonic', return_value=1), \
                patch.object(terminal, 'render', wraps=terminal.render) as draw:
            cache.frame(record, 80, 24, **self.options)
            record['active_tools'][0]['kind'] = 'read'
            changed = cache.frame(record, 80, 24, colour=False, now=11)
            self.assertEqual(draw.call_count, 2)
        self.assertEqual(changed, terminal.render(record, 80, 24, colour=False, now=11))

    def test_static_frames_do_not_add_decorative_wakeups(self):
        cache = terminal.PacedRenderCache()
        self.assertTrue(callable(getattr(cache, 'wait_timeout', None)))
        with patch.object(terminal.time, 'monotonic', return_value=1):
            cache.frame('unknown', 80, 24, **self.options)
        with patch.object(terminal.time, 'monotonic', return_value=1.18):
            self.assertEqual(cache.wait_timeout(.25), .25)

    def test_slower_native_rhythms_are_not_accelerated(self):
        cache = terminal.PacedRenderCache()
        with patch.object(terminal.time, 'monotonic', return_value=1):
            cache.frame('idle', 80, 24, **self.options)
        with patch.object(terminal.time, 'monotonic', return_value=1.18):
            self.assertEqual(cache.wait_timeout(.25), .25)


if __name__ == '__main__':
    unittest.main()
