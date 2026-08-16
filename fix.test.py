import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fix = load_module("fix")
header = load_module("header")
identify = load_module("identify")
romtools = load_module("romtools")

TITLE = b"Star Ocean           "


def image(size=0x100000, chipset=0x45):
    data = bytearray(size)
    at = 0x007FC0
    data[at : at + len(TITLE)] = TITLE
    data[at + header.MAP_MODE] = 0x32
    data[at + header.CHIPSET] = chipset
    data[at + header.ROM_SIZE] = 0x0D
    return bytes(data)


class RepairTest(unittest.TestCase):
    def test_repairing_clears_the_coprocessor(self):
        repaired = fix.repair(image())

        self.assertEqual(header.read(repaired)[0]["chipset"], 0x00)

    def test_repairing_an_image_that_declares_nothing_changes_no_bytes(self):
        already = fix.repair(image(chipset=0x00))

        self.assertEqual(fix.repair(already), already)

    def test_repairing_reports_what_it_changed(self):
        changed = fix.changes(image(), fix.repair(image()))

        self.assertIn(0x007FC0 + header.CHIPSET, changed)

    def test_nothing_outside_the_headers_is_touched(self):
        before = image()
        after = fix.repair(before)
        positions = header.header_positions(before)

        for at in fix.changes(before, after):
            self.assertTrue(
                any(place <= at < place + header.HEADER_LENGTH for place in positions),
                f"{at:#08x} is outside every header",
            )


class NeedsRepairTest(unittest.TestCase):
    def test_an_image_declaring_a_coprocessor_needs_repair(self):
        self.assertTrue(fix.needs_repair(image()))

    def test_an_image_declaring_nothing_still_needs_a_correct_size(self):
        self.assertTrue(fix.needs_repair(image(chipset=0x00)))

    def test_a_repaired_image_needs_nothing(self):
        self.assertFalse(fix.needs_repair(fix.repair(image())))

    def test_an_image_with_no_header_cannot_be_judged(self):
        with self.assertRaises(ValueError):
            fix.needs_repair(bytes(0x10000))


class RunTest(unittest.TestCase):
    def test_writing_the_output_produces_a_repaired_file(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "in.sfc"
            target = Path(folder) / "out.sfc"
            source.write_bytes(image())

            self.assertEqual(fix.main(["fix.py", str(source), str(target)]), 0)
            self.assertEqual(header.read(target.read_bytes())[0]["chipset"], 0x00)

    def test_reporting_without_an_output_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "in.sfc"
            source.write_bytes(image())

            self.assertEqual(fix.main(["fix.py", str(source)]), 0)
            self.assertEqual(list(Path(folder).iterdir()), [source])

    def test_a_missing_argument_is_refused(self):
        self.assertEqual(fix.main(["fix.py"]), 2)

    def test_an_image_with_no_header_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "in.sfc"
            target = Path(folder) / "out.sfc"
            source.write_bytes(bytes(0x10000))

            self.assertEqual(fix.main(["fix.py", str(source), str(target)]), 1)
            self.assertFalse(target.exists())


SUPPLIED = os.environ.get("NOCHIP_IMAGE")


@unittest.skipUnless(SUPPLIED, "set NOCHIP_IMAGE to a local chip-free image to run this")
class SuppliedImageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = romtools.load(Path(SUPPLIED))

    def test_the_manifest_recognises_it(self):
        found = identify.diagnose(self.data)

        self.assertIn(found["state"], ("known", "repaired"))

    def test_repairing_it_reaches_the_digest_the_manifest_records(self):
        found = identify.diagnose(self.data)
        if found["state"] == "repaired":
            self.skipTest("this image is already repaired")

        repaired = fix.repair(self.data)

        self.assertEqual(
            romtools.identity(repaired)["sha256"], found["artifact"]["repaired"]["sha256"]
        )

    def test_repairing_it_touches_only_header_bytes(self):
        repaired = fix.repair(self.data)
        positions = header.header_positions(self.data)

        for at in fix.changes(self.data, repaired):
            self.assertTrue(any(place <= at < place + header.HEADER_LENGTH for place in positions))


if __name__ == "__main__":
    unittest.main(verbosity=2)
