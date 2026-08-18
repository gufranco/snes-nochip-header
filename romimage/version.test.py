import unittest
from pathlib import Path

import romimage
from romimage import version

ROOT = Path(__file__).resolve().parent.parent


class VersionTest(unittest.TestCase):
    def test_the_version_is_three_numbers(self):
        parts = version.VERSION.split(".")

        self.assertEqual(len(parts), 3)
        self.assertTrue(all(part.isdigit() for part in parts))

    def test_the_package_reports_the_same_version(self):
        self.assertEqual(romimage.__version__, version.VERSION)


class SurfaceTest(unittest.TestCase):
    def test_everything_it_declares_is_reachable(self):
        missing = [name for name in romimage.__all__ if not hasattr(romimage, name)]

        self.assertEqual(missing, [])

    def test_the_release_job_rewrites_the_file_the_package_reads(self):
        assets = (ROOT / ".releaserc.json").read_text()

        self.assertIn("romimage/version.py", assets)

    def test_the_script_that_rewrites_it_points_at_the_same_file(self):
        script = (ROOT / "scripts" / "set-version.sh").read_text()

        self.assertIn("romimage/version.py", script)


if __name__ == "__main__":
    unittest.main()
