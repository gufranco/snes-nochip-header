import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


header = load_module("header")

TITLE = b"Star Ocean           "


def image_with_header(at=0x007FC0, size=0x010000, chipset=0x45, map_mode=0x32):
    data = bytearray(size)
    data[at : at + len(TITLE)] = TITLE
    data[at + header.MAP_MODE] = map_mode
    data[at + header.CHIPSET] = chipset
    data[at + header.ROM_SIZE] = 0x0D
    data[at + header.SRAM_SIZE] = 0x03
    return bytes(data)


class SizeByteTest(unittest.TestCase):
    def test_one_megabyte_is_ten(self):
        self.assertEqual(header.size_byte(1024 * 1024), 10)

    def test_twelve_megabytes_rounds_up_to_sixteen(self):
        self.assertEqual(header.size_byte(12 * 1024 * 1024), 14)

    def test_four_megabytes_is_twelve(self):
        self.assertEqual(header.size_byte(4 * 1024 * 1024), 12)

    def test_a_single_byte_still_reports_one_kilobyte(self):
        self.assertEqual(header.size_byte(1), 0)


class PositionTest(unittest.TestCase):
    def test_a_header_at_the_hirom_position_is_found(self):
        found = header.header_positions(image_with_header())

        self.assertEqual(found, [0x007FC0])

    def test_an_image_with_no_header_finds_nothing(self):
        self.assertEqual(header.header_positions(bytes(0x10000)), [])

    def test_every_mirror_of_the_title_is_found(self):
        data = bytearray(image_with_header(size=0x100000))
        data[0x087FC0 : 0x087FC0 + 0x20] = data[0x007FC0:0x007FE0]

        found = header.header_positions(bytes(data))

        self.assertEqual(found, [0x007FC0, 0x087FC0])

    def test_a_title_without_a_plausible_map_mode_is_not_a_header(self):
        found = header.header_positions(image_with_header(map_mode=0x7F))

        self.assertEqual(found, [])


class DeclareTest(unittest.TestCase):
    def test_the_chipset_byte_becomes_rom_only(self):
        declared = header.declare_no_coprocessor(image_with_header())

        self.assertEqual(declared[0x007FC0 + header.CHIPSET], 0x00)

    def test_the_size_byte_matches_the_image(self):
        declared = header.declare_no_coprocessor(image_with_header(size=0x100000))

        self.assertEqual(declared[0x007FC0 + header.ROM_SIZE], 10)

    def test_the_checksum_and_its_complement_are_a_pair(self):
        declared = header.declare_no_coprocessor(image_with_header())
        at = 0x007FC0
        complement = declared[at + header.CHECKSUM_COMPLEMENT] | (
            declared[at + header.CHECKSUM_COMPLEMENT + 1] << 8
        )
        value = declared[at + header.CHECKSUM] | (declared[at + header.CHECKSUM + 1] << 8)

        self.assertEqual(complement ^ value, 0xFFFF)

    def test_the_recorded_checksum_is_the_one_the_image_sums_to(self):
        declared = header.declare_no_coprocessor(image_with_header())
        at = 0x007FC0
        value = declared[at + header.CHECKSUM] | (declared[at + header.CHECKSUM + 1] << 8)

        self.assertEqual(value, header.checksum(declared, at))

    def test_declaring_twice_changes_nothing_further(self):
        once = header.declare_no_coprocessor(image_with_header())

        self.assertEqual(header.declare_no_coprocessor(once), once)

    def test_the_source_image_is_not_modified(self):
        data = image_with_header()

        header.declare_no_coprocessor(data)

        self.assertEqual(data[0x007FC0 + header.CHIPSET], 0x45)

    def test_an_image_with_no_header_is_refused(self):
        with self.assertRaises(ValueError):
            header.declare_no_coprocessor(bytes(0x10000))

    def test_every_mirror_is_declared_not_just_the_first(self):
        data = bytearray(image_with_header(size=0x100000))
        data[0x087FC0 : 0x087FC0 + 0x20] = data[0x007FC0:0x007FE0]

        declared = header.declare_no_coprocessor(bytes(data))

        self.assertEqual(declared[0x087FC0 + header.CHIPSET], 0x00)


class ReadTest(unittest.TestCase):
    def test_reading_reports_the_declared_coprocessor(self):
        found = header.read(image_with_header())

        self.assertEqual(found[0]["chipset"], 0x45)
        self.assertEqual(found[0]["title"], "Star Ocean")

    def test_an_image_declaring_rom_only_reports_zero(self):
        found = header.read(image_with_header(chipset=0x00))

        self.assertEqual(found[0]["chipset"], 0x00)

    def test_reading_an_image_with_no_header_reports_nothing(self):
        self.assertEqual(header.read(bytes(0x10000)), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
