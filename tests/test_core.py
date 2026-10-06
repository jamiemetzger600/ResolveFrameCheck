import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from framecheck import core  # noqa: E402


def C(path, frames, fps=24.0, tc="01:00:00:00", b=""):
    return core.Clip(os.path.basename(path), path, frames, fps, tc, b)


class T(unittest.TestCase):
    def status(self, raws, tcs):
        return [(r.status, r.stem, r.delta) for r in core.compare(raws, tcs)]

    def test_ok(self):
        self.assertEqual(self.status([C("/r/A001_C001.braw", 100)], [C("/t/A001_C001.mov", 100)]),
                         [(core.OK, "a001_c001", 0)])

    def test_mismatch_delta(self):
        r = core.compare([C("/r/A1.braw", 100)], [C("/t/A1.mov", 98)])[0]
        self.assertEqual((r.status, r.delta), (core.MISMATCH, -2))

    def test_missing_and_orphan(self):
        s = [x.status for x in core.compare([C("/r/A1.braw", 10)], [C("/t/Z9.mov", 10)])]
        self.assertEqual(sorted(s), sorted([core.MISSING, core.ORPHAN]))

    def test_suffix_and_case(self):
        r = core.compare([C("/r/A1.braw", 10)], [C("/t/a1_PROXY.mov", 10)])[0]
        self.assertEqual(r.status, core.OK)

    def test_ambiguous(self):
        r = core.compare([C("/r/A1.braw", 10)], [C("/t/A1.mov", 10), C("/u/A1.mp4", 10)])[0]
        self.assertEqual(r.status, core.AMBIGUOUS)

    def test_fps_warning(self):
        r = core.compare([C("/r/A1.braw", 10, 24)], [C("/t/A1.mov", 10, 25)])[0]
        self.assertEqual(r.status, core.OK)
        self.assertTrue(any("FPS" in w for w in r.warnings))

    def test_frames_fallback(self):
        c = core.clip_from_props({"Clip Name": "x", "File Path": "/x.mov", "Frames": "", "FPS": "24",
                                  "Start TC": "01:00:00:00", "End TC": "01:00:01:00"})
        self.assertEqual(c.frames, 24)

    def test_unavailable_frames(self):
        r = core.compare([C("/r/A1.braw", None)], [C("/t/A1.mov", 10)])[0]
        self.assertEqual(r.status, core.MISMATCH)


if __name__ == "__main__":
    unittest.main()
