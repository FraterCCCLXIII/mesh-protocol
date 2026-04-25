"""Tests for mesh_views (§9) home_timeline validation."""
import unittest

from mesh_views import (
    ViewRejectionError,
    validate_and_estimate_home_timeline,
    HOME_TIMELINE_VIEW,
)


class TestHomeTimelineView(unittest.TestCase):
    def test_sane_params(self):
        lim, off, cost = validate_and_estimate_home_timeline(100, 50, 0, False)
        self.assertEqual(lim, 50)
        self.assertEqual(off, 0)
        self.assertEqual(cost.view, HOME_TIMELINE_VIEW)
        self.assertGreater(cost.estimated_events_scanned, 0)

    def test_reject_limit_too_high(self):
        with self.assertRaises(ViewRejectionError) as c:
            validate_and_estimate_home_timeline(10, 500, 0, False)
        self.assertEqual(c.exception.status_code, 400)

    def test_reject_offset_too_high(self):
        with self.assertRaises(ViewRejectionError) as c:
            validate_and_estimate_home_timeline(10, 20, 50_000, False)
        self.assertIn("pathological", c.exception.detail)

    def test_reject_too_many_follows(self):
        with self.assertRaises(ViewRejectionError) as c:
            validate_and_estimate_home_timeline(20_000, 20, 0, False)
        self.assertEqual(c.exception.status_code, 413)


if __name__ == "__main__":
    unittest.main()
