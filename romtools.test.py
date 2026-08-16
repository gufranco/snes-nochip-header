import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


romtools = load_module("romtools")


class CopierHeaderTest(unittest.TestCase):
    def test_a_bare_image_has_no_copier_header(self):
        self.assertFalse(romtools.has_copier_header(bytes(0x8000)))

    def test_an_image_with_512_extra_bytes_has_one(self):
        self.assertTrue(romtools.has_copier_header(bytes(0x8000 + 512)))

    def test_a_file_shorter_than_the_header_has_none(self):
        self.assertFalse(romtools.has_copier_header(bytes(200)))

    def test_stripping_removes_exactly_512_bytes(self):
        data = bytes(0x8000 + 512)

        self.assertEqual(len(romtools.strip_header(data)) + 512, len(data))

    def test_stripping_leaves_a_bare_image_alone(self):
        data = bytes(0x8000)

        self.assertEqual(romtools.strip_header(data), data)

    def test_the_stripped_bytes_are_the_ones_after_the_header(self):
        data = bytes(512) + b"ROM" + bytes(0x8000 - 3)

        self.assertEqual(romtools.strip_header(data)[:3], b"ROM")


class JoinTest(unittest.TestCase):
    def test_no_parts_joins_to_nothing(self):
        self.assertEqual(romtools.join_parts([]), b"")

    def test_the_first_part_loses_its_copier_header(self):
        first = bytes(512) + b"A" * 0x8000
        second = b"B" * 0x8000

        joined = romtools.join_parts([first, second])

        self.assertEqual(joined, b"A" * 0x8000 + b"B" * 0x8000)

    def test_later_parts_are_taken_whole(self):
        first = bytes(512) + b"A" * 0x8000
        second = b"B" * 0x8000
        third = b"C" * 0x8000

        joined = romtools.join_parts([first, second, third])

        self.assertEqual(len(joined), 0x18000)

    def test_a_first_part_without_a_header_is_taken_whole(self):
        joined = romtools.join_parts([b"A" * 0x8000, b"B" * 0x8000])

        self.assertEqual(len(joined), 0x10000)


class SourceTest(unittest.TestCase):
    def test_a_plain_file_is_read_as_itself(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "image.sfc"
            source.write_bytes(b"A" * 0x8000)

            self.assertEqual(romtools.read_source(source), b"A" * 0x8000)

    def test_a_plain_file_loses_its_copier_header(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "image.sfc"
            source.write_bytes(bytes(512) + b"A" * 0x8000)

            self.assertEqual(romtools.read_source(source), b"A" * 0x8000)

    def test_a_folder_of_numbered_parts_is_joined_in_name_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "SF96SOEB.078").write_bytes(b"B" * 0x8000)
            (root / "SF96SOEA.078").write_bytes(bytes(512) + b"A" * 0x8000)

            self.assertEqual(romtools.read_source(root), b"A" * 0x8000 + b"B" * 0x8000)

    def test_a_folder_with_parts_in_subfolders_is_joined_too(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Disk 01").mkdir()
            (root / "Disk 02").mkdir()
            (root / "Disk 01" / "SETA.078").write_bytes(bytes(512) + b"A" * 0x8000)
            (root / "Disk 02" / "SETB.078").write_bytes(b"B" * 0x8000)

            self.assertEqual(romtools.read_source(root), b"A" * 0x8000 + b"B" * 0x8000)

    def test_a_folder_with_nothing_recognisable_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "notes.txt").write_text("nothing here")

            with self.assertRaises(ValueError):
                romtools.read_source(Path(folder))

    def test_the_parts_of_a_folder_are_listed_in_name_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("SETC.078", "SETA.078", "SETB.078"):
                (root / name).write_bytes(b"x")

            self.assertEqual(
                [p.name for p in romtools.parts_in(root)], ["SETA.078", "SETB.078", "SETC.078"]
            )

    def test_a_file_extension_that_is_not_three_digits_is_not_a_part(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "readme.txt").write_text("x")
            (root / "image.sfc").write_bytes(b"x")

            self.assertEqual(romtools.parts_in(root), [])


class FormTest(unittest.TestCase):
    def test_a_bare_file_reports_bare(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "image.sfc"
            source.write_bytes(b"A" * 0x8000)

            self.assertEqual(romtools.source_form(source), "bare")

    def test_a_headered_file_reports_the_copier_header(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "image.sfc"
            source.write_bytes(bytes(512) + b"A" * 0x8000)

            self.assertEqual(romtools.source_form(source), "copier header")

    def test_a_folder_reports_how_many_parts_it_joined(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("SETA.078", "SETB.078", "SETC.078"):
                (root / name).write_bytes(b"x" * 0x8000)

            self.assertEqual(romtools.source_form(root), "3 part set")


class IdentityTest(unittest.TestCase):
    def test_the_identity_of_known_bytes(self):
        found = romtools.identity(b"snes")

        self.assertEqual(found["size"], 4)
        self.assertEqual(found["crc32"], "CB018920")
        self.assertEqual(
            found["sha256"], "4f30ca9821db8cfd3b23bf1efd6d707eca448e2e151eff918e9523ff507990ab"
        )

    def test_the_digest_is_sixty_four_hex_characters(self):
        found = romtools.identity(b"")

        self.assertEqual(len(found["sha256"]), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in found["sha256"]))

    def test_the_crc_is_eight_upper_case_hex_characters(self):
        found = romtools.identity(b"")

        self.assertEqual(len(found["crc32"]), 8)
        self.assertTrue(all(c in "0123456789ABCDEF" for c in found["crc32"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
