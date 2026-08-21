"""Hold this package's constants and its checksum rule to what Nintendo specified.

A figure quoted in a docstring rots and cannot fail. This file is what turns
hardware.json from a record of a reading into a gate.

The checksum cases are the four worked examples the specification prints, driven
through this package's own function rather than through a copy of the arithmetic.
They are the cases that were wrong until the specification was read: this package
summed every byte once, and roughly a quarter of the retail library is not a
power of two.
"""

import json
import sys
import unittest
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from romimage import rewrite

HELD = json.loads((Path(__file__).resolve().parent / "hardware.json").read_text())

DIVERGENCES = json.loads((Path(__file__).resolve().parent / "divergences.json").read_text())

FACTS = HELD["facts"]

FIELDS = FACTS["fields"]


def offset(name: str) -> int:
    """Where the specification puts one field, relative to the base this package uses."""
    value: int = FIELDS[name]["offset"]
    return value


class DocumentTest(unittest.TestCase):
    def test_the_header_is_backed_by_a_named_document(self) -> None:
        self.assertEqual(HELD["document"]["publisher"], "Nintendo of America Inc.")

    def test_it_carries_a_digest_so_the_reading_can_be_repeated(self) -> None:
        self.assertRegex(HELD["document"]["sha256"], r"^[0-9a-f]{64}$")

    def test_every_field_names_the_page_it_was_read_from(self) -> None:
        missing = [
            name for name, field in FIELDS.items() if name != "note" and "manualPage" not in field
        ]

        self.assertEqual(missing, [])


class FieldOffsetTest(unittest.TestCase):
    """Each constant against the address the specification prints beside its name."""

    def test_the_map_mode_byte_sits_where_the_specification_puts_it(self) -> None:
        self.assertEqual(rewrite.MAP_MODE, offset("mapMode"))

    def test_and_the_cartridge_type_byte(self) -> None:
        self.assertEqual(rewrite.CHIPSET, offset("cartridgeType"))

    def test_and_the_rom_size_byte(self) -> None:
        self.assertEqual(rewrite.ROM_SIZE, offset("romSize"))

    def test_and_the_ram_size_byte(self) -> None:
        self.assertEqual(rewrite.SRAM_SIZE, offset("ramSize"))

    def test_and_the_complement(self) -> None:
        self.assertEqual(rewrite.CHECKSUM_COMPLEMENT, offset("complementCheck"))

    def test_and_the_checksum(self) -> None:
        self.assertEqual(rewrite.CHECKSUM, offset("checkSum"))

    def test_the_complement_sits_two_bytes_before_the_checksum(self) -> None:
        self.assertEqual(offset("checkSum") - offset("complementCheck"), 2)

    def test_the_two_together_are_the_four_bytes_neutralised_before_the_sum(self) -> None:
        self.assertEqual(rewrite.CHECKSUM_FIELD_BYTES, 4)

    def test_every_offset_falls_inside_the_registration_area(self) -> None:
        outside = [
            name
            for name, field in FIELDS.items()
            if name != "note" and not 0 <= field["offset"] < FACTS["registrationArea"]["value"]
        ]

        self.assertEqual(outside, [])


class NeutralBytesTest(unittest.TestCase):
    def test_the_four_bytes_count_as_the_values_the_specification_names(self) -> None:
        self.assertEqual(rewrite.CHECKSUM_FIELD_NEUTRAL, bytes.fromhex("ffff0000"))

    def test_and_the_specification_names_those_values(self) -> None:
        self.assertEqual(FACTS["checksumNeutralBytes"]["value"], "ff ff 00 00")

    def test_they_total_the_constant_this_package_used_to_add(self) -> None:
        self.assertEqual(sum(rewrite.CHECKSUM_FIELD_NEUTRAL), rewrite.CHECKSUM_FIELD_SUM)

    def test_the_checksum_ignores_whatever_those_bytes_held(self) -> None:
        image = bytearray(0x10000)
        image[0x7FC0 : 0x7FC0 + 21] = b"A CARTRIDGE          "
        places = [0x7FC0]
        before = rewrite.checksum(bytes(image), places)
        image[0x7FC0 + rewrite.CHECKSUM_COMPLEMENT : 0x7FC0 + rewrite.CHECKSUM_COMPLEMENT + 4] = (
            b"\x12\x34\x56\x78"
        )

        self.assertEqual(rewrite.checksum(bytes(image), places), before)


class ShortImageTest(unittest.TestCase):
    """Nintendo's four worked examples, through this package's own function.

    Each names the megabit size the specification uses, and each is the arithmetic
    that specification prints for it.
    """

    def rule(self, size: str) -> str:
        for entry in FACTS["shortImageMirroring"]["workedExamples"]:
            if entry["size"] == size:
                return str(entry["rule"])
        raise AssertionError(f"the specification prints no worked example for {size}")

    def test_a_size_the_specification_does_not_work_through_is_refused(self) -> None:
        with self.assertRaises(AssertionError):
            self.rule("7 Mbit")

    def test_a_power_of_two_is_summed_once(self) -> None:
        data = bytes([3]) * 0x100000

        self.assertEqual(rewrite.mirrored_sum(data), 3 * 0x100000)

    def test_twelve_megabit(self) -> None:
        head = bytes([1]) * 0x100000
        tail = bytes([2]) * 0x80000

        self.assertEqual(
            (rewrite.mirrored_sum(head + tail), self.rule("12 Mbit")),
            (
                sum(head) + 2 * sum(tail),
                "(Total of first 8M bit) + [(Total of last 4M bit) x2] = Check Sum",
            ),
        )

    def test_ten_megabit(self) -> None:
        head = bytes([1]) * 0x100000
        tail = bytes([2]) * 0x40000

        self.assertEqual(
            (rewrite.mirrored_sum(head + tail), self.rule("10 Mbit")),
            (sum(head) + 4 * sum(tail), "(Total of first 8M bit) + [(Total of last 2M bit) x4]"),
        )

    def test_twenty_megabit(self) -> None:
        head = bytes([1]) * 0x200000
        tail = bytes([2]) * 0x80000

        self.assertEqual(
            (rewrite.mirrored_sum(head + tail), self.rule("20 Mbit")),
            (sum(head) + 4 * sum(tail), "(Total of first 16M bit) + [(Total of last 4M bit) x4]"),
        )

    def test_twenty_four_megabit(self) -> None:
        head = bytes([1]) * 0x200000
        tail = bytes([2]) * 0x100000

        self.assertEqual(
            (rewrite.mirrored_sum(head + tail), self.rule("24 Mbit")),
            (sum(head) + 2 * sum(tail), "(Total of first 16M bit) + [(Total of last 8M bit) x2]"),
        )

    def test_every_short_image_reaches_a_power_of_two(self) -> None:
        uneven = [0x180000, 0x140000, 0x280000, 0x300000, 0x500000, 0x600000, 0x160000]

        totals = [rewrite.mirrored_sum(bytes(size)) for size in uneven]
        reached = [rewrite.mirrored_sum(bytes([1]) * size) for size in uneven]

        self.assertEqual(
            (totals, [value & (value - 1) for value in reached]),
            ([0] * len(uneven), [0] * len(uneven)),
        )


class SizeByteTest(unittest.TestCase):
    """The declared size, against every row the specification prints."""

    def test_every_printed_row_is_reproduced(self) -> None:
        upper = {"0x09": 4, "0x0A": 8, "0x0B": 16, "0x0C": 32, "0x0D": 64}

        computed = {
            code: rewrite.size_byte(megabit * 1024 * 1024 // 8) for code, megabit in upper.items()
        }

        self.assertEqual(computed, {code: int(code, 16) for code in upper})

    def test_the_table_this_file_checks_is_the_one_in_the_document(self) -> None:
        self.assertEqual(set(FIELDS["romSize"]["table"]), {"0x09", "0x0A", "0x0B", "0x0C", "0x0D"})


class CartridgeTypeTest(unittest.TestCase):
    def test_rom_only_is_the_value_the_specification_gives_it(self) -> None:
        self.assertEqual(rewrite.CHIPSET_ROM_ONLY, FIELDS["cartridgeType"]["romOnly"])

    def test_and_the_specification_calls_that_value_rom_only(self) -> None:
        self.assertEqual(FIELDS["cartridgeType"]["withoutCoprocessor"]["0x00"], "ROM Only")

    def test_every_undocumented_coprocessor_nibble_is_written_down(self) -> None:
        documented = {int(key, 16) for key in FIELDS["cartridgeType"]["withCoprocessorUpperNibble"]}

        undocumented = sorted({value >> 4 for value in rewrite.COPROCESSORS} - documented)

        self.assertEqual(undocumented, [0x4, 0x5])

    def test_and_the_entry_that_writes_them_down_exists(self) -> None:
        named = {entry["id"] for entry in DIVERGENCES["divergences"]}

        self.assertIn("coprocessor-nibbles-outside-the-table", named)


class DivergenceTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.entries: list[dict[str, Any]] = DIVERGENCES["divergences"]

    def test_no_two_entries_share_an_id(self) -> None:
        names = [entry["id"] for entry in self.entries]

        self.assertEqual(len(names), len(set(names)))

    def test_every_entry_says_which_side_the_package_follows(self) -> None:
        missing = [entry["id"] for entry in self.entries if not entry.get("packageFollows")]

        self.assertEqual(missing, [])

    def test_every_open_entry_says_what_would_settle_it(self) -> None:
        missing = [
            entry["id"]
            for entry in self.entries
            if entry["status"] == "open" and not entry.get("wouldSettleIt")
        ]

        self.assertEqual(missing, [])

    def test_every_closed_entry_says_what_would_reopen_it(self) -> None:
        missing = [
            entry["id"]
            for entry in self.entries
            if entry["status"] == "closed" and not entry.get("wouldReopenIt")
        ]

        self.assertEqual(missing, [])

    def test_the_corrected_defect_records_what_was_measured_both_ways(self) -> None:
        found = next(entry for entry in self.entries if entry["id"] == "short-image-checksum")

        self.assertEqual(set(found["measured"]) >= {"before", "after", "subjects"}, True)

    def test_and_says_how_it_survived_the_checks_that_existed(self) -> None:
        found = next(entry for entry in self.entries if entry["id"] == "short-image-checksum")

        self.assertIn("howItSurvived", found)

    def test_the_cartridges_that_still_disagree_are_named_rather_than_averaged(self) -> None:
        found = next(
            entry for entry in self.entries if entry["id"] == "cartridges-that-still-disagree"
        )

        self.assertNotEqual(found["groups"], [])


if __name__ == "__main__":
    unittest.main()
