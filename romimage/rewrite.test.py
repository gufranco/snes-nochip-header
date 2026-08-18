import itertools
import random
import unittest

from romimage import rewrite


def _blank(banks=2, seed=1):
    generator = random.Random(seed)
    return bytearray(generator.randrange(256) for _ in range(banks * 0x10000))


def _stamp(image, at, title=b"A CARTRIDGE          ", chipset=0x43, mapping=0x20):
    """Write a whole header, because a real mirror is byte-identical to the first."""
    block = bytearray(rewrite.HEADER_BYTES)
    block[: len(title)] = title
    block[rewrite.MAP_MODE] = mapping
    block[rewrite.CHIPSET] = chipset
    block[rewrite.ROM_SIZE] = 0x09
    block[rewrite.SRAM_SIZE] = 0x00
    block[0x19] = 0x01
    block[0x1A] = 0x02
    block[0x1B] = 0x03
    image[at : at + rewrite.HEADER_BYTES] = block


def _cartridge(banks=2, seed=1, at=(0x007FC0,), chipset=0x43):
    image = _blank(banks, seed)
    for place in at:
        _stamp(image, place, chipset=chipset)
    return bytes(image)


class SizeByteTest(unittest.TestCase):
    def test_a_one_megabyte_image_is_declared_as_ten(self):
        self.assertEqual(rewrite.size_byte(0x100000), 10)

    def test_the_next_byte_past_a_power_takes_the_next_exponent(self):
        self.assertEqual(rewrite.size_byte(0x100001), 11)

    def test_a_single_byte_image_is_still_declared_as_one_kilobyte(self):
        self.assertEqual(rewrite.size_byte(1), 0)

    def test_an_empty_image_does_not_loop_forever(self):
        self.assertEqual(rewrite.size_byte(0), 0)


class MirrorTest(unittest.TestCase):
    def test_a_single_header_is_found_where_it_sits(self):
        self.assertEqual(rewrite.mirrors(_cartridge()), [0x007FC0])

    def test_every_repeat_of_the_same_header_is_found(self):
        self.assertEqual(
            rewrite.mirrors(_cartridge(at=(0x007FC0, 0x017FC0))),
            [0x007FC0, 0x017FC0],
        )

    def test_an_image_with_no_readable_title_has_no_mirrors(self):
        self.assertEqual(rewrite.mirrors(bytes(0x20000)), [])

    def test_a_repeat_declaring_a_different_mapping_is_not_a_mirror(self):
        image = bytearray(_cartridge(at=(0x007FC0, 0x017FC0)))
        image[0x017FC0 + rewrite.MAP_MODE] = 0x21

        self.assertEqual(rewrite.mirrors(bytes(image)), [0x007FC0])

    def test_an_image_the_map_cannot_place_has_no_anchor(self):
        self.assertIsNone(rewrite.anchor_of(bytes(0x20000)))

    def test_the_anchor_is_the_one_the_map_reports(self):
        image = _cartridge()

        self.assertEqual(rewrite.anchor_of(image), rewrite.mirrors(image)[0])

    def test_a_repeat_that_differs_by_one_byte_is_not_a_mirror(self):
        image = bytearray(_cartridge(at=(0x007FC0, 0x017FC0)))
        image[0x017FC0 + 0x19] ^= 0xFF

        self.assertEqual(rewrite.mirrors(bytes(image)), [0x007FC0])

    def test_a_high_layout_header_anchors_as_well_as_a_low_one(self):
        self.assertEqual(rewrite.mirrors(_cartridge(at=(0x00FFC0,))), [0x00FFC0])

    def test_a_header_of_spaces_identifies_nothing(self):
        self.assertFalse(rewrite.identifies(b" " * rewrite.HEADER_BYTES))

    def test_a_header_of_zeroes_identifies_nothing_either(self):
        self.assertFalse(rewrite.identifies(bytes(rewrite.HEADER_BYTES)))

    def test_a_header_of_all_ones_identifies_nothing_either(self):
        self.assertFalse(rewrite.identifies(b"\xff" * rewrite.HEADER_BYTES))

    def test_one_byte_that_is_not_padding_is_enough_to_identify(self):
        self.assertTrue(rewrite.identifies(b" " * 31 + b"A"))

    def test_a_header_of_padding_is_placed_but_never_searched_for(self):
        image = bytearray(_blank(banks=2, seed=21))
        image[0x007FC0 : 0x007FC0 + rewrite.HEADER_BYTES] = b" " * rewrite.HEADER_BYTES
        image[0x010000 : 0x010000 + 0x1000] = b" " * 0x1000

        self.assertEqual(rewrite.mirrors(bytes(image)), [0x007FC0])

    def test_no_two_mirrors_overlap(self):
        image = bytearray(_blank(banks=2, seed=12))
        _stamp(image, 0x007FC0)
        block = bytes(image[0x007FC0 : 0x007FC0 + rewrite.HEADER_BYTES])
        image[0x010000 : 0x010000 + len(block) * 3] = block * 3

        found = rewrite.mirrors(bytes(image))

        self.assertEqual(len(found), len(set(found)))
        self.assertTrue(
            all(
                second - first >= rewrite.HEADER_BYTES
                for first, second in itertools.pairwise(found)
            )
        )

    def test_a_title_that_appears_in_the_data_is_not_a_mirror(self):
        image = bytearray(_blank(banks=2, seed=13))
        _stamp(image, 0x007FC0)
        image[0x010000 : 0x010000 + 21] = b"A CARTRIDGE          "

        self.assertEqual(rewrite.mirrors(bytes(image)), [0x007FC0])


class DescribeTest(unittest.TestCase):
    def test_each_mirror_is_reported_once(self):
        found = rewrite.describe(_cartridge(at=(0x007FC0, 0x017FC0)))

        self.assertEqual([entry["at"] for entry in found], [0x007FC0, 0x017FC0])

    def test_a_known_chipset_byte_is_named(self):
        found = rewrite.describe(_cartridge(chipset=0x43))

        self.assertEqual(found[0]["coprocessor"], "S-DD1")

    def test_a_chipset_byte_nobody_documents_is_left_unnamed(self):
        found = rewrite.describe(_cartridge(chipset=0x77))

        self.assertIsNone(found[0]["coprocessor"])

    def test_the_title_comes_back_without_its_padding(self):
        found = rewrite.describe(_cartridge())

        self.assertEqual(found[0]["title"], "A CARTRIDGE")

    def test_an_image_with_no_header_describes_nothing(self):
        self.assertEqual(rewrite.describe(bytes(0x20000)), [])


class ChecksumTest(unittest.TestCase):
    def test_it_ignores_whatever_the_checksum_fields_held(self):
        image = bytearray(_cartridge())
        before = rewrite.checksum(bytes(image))
        image[0x007FC0 + rewrite.CHECKSUM] = 0xAB
        image[0x007FC0 + rewrite.CHECKSUM + 1] = 0xCD

        self.assertEqual(rewrite.checksum(bytes(image)), before)

    def test_it_is_sixteen_bits(self):
        self.assertLess(rewrite.checksum(_cartridge(banks=4)), 0x10000)

    def test_changing_one_byte_of_content_changes_it(self):
        image = bytearray(_cartridge())
        before = rewrite.checksum(bytes(image))
        image[0x000100] ^= 0xFF

        self.assertNotEqual(rewrite.checksum(bytes(image)), before)


class SmallCartridgeTest(unittest.TestCase):
    """A cartridge too small for the map's plausible-size band.

    The map awards a point for a declared size between eight and fourteen, which
    is two hundred and fifty six kilobytes and up. A thirty two kilobyte cartridge
    declares five and never earns it, so it survives on the other three signals.
    Correcting its size byte mid-rewrite therefore costs nothing it had, but
    clearing the checksum agreement costs a point it did have, and for the moment
    before the new checksum is written the header is no longer placeable.
    """

    def _small(self):
        image = _blank(banks=1, seed=31)
        _stamp(image, 0x007FC0)
        return bytes(image[:0x8000])

    def test_the_checksum_uses_the_mirrors_it_was_given(self):
        image = self._small()
        places = rewrite.mirrors(image)

        self.assertEqual(rewrite.checksum(image, places), rewrite.checksum(image))

    def test_supplying_no_mirrors_leaves_out_the_convention(self):
        image = self._small()
        places = rewrite.mirrors(image)

        difference = rewrite.checksum(image, places) - rewrite.checksum(image, [])

        self.assertEqual(difference, rewrite.CHECKSUM_FIELD_SUM * len(places))

    def test_a_small_cartridge_still_recomputes_to_what_was_written(self):
        image = self._small()

        written = rewrite.declare_rom_only(image)
        at = rewrite.mirrors(image)[0]
        value = written[at + rewrite.CHECKSUM] | (written[at + rewrite.CHECKSUM + 1] << 8)

        self.assertEqual(value, rewrite.checksum(written))

    def test_and_settles_on_a_second_pass(self):
        once = rewrite.declare_rom_only(self._small())

        self.assertEqual(rewrite.declare_rom_only(once), once)


class DeclareTest(unittest.TestCase):
    def test_the_chipset_becomes_rom_only(self):
        declared = rewrite.declare_rom_only(_cartridge())

        self.assertEqual(declared[0x007FC0 + rewrite.CHIPSET], rewrite.CHIPSET_ROM_ONLY)

    def test_the_size_byte_matches_the_image_it_describes(self):
        declared = rewrite.declare_rom_only(_cartridge(banks=2))

        self.assertEqual(declared[0x007FC0 + rewrite.ROM_SIZE], rewrite.size_byte(0x20000))

    def test_every_mirror_is_updated_rather_than_only_the_first(self):
        declared = rewrite.declare_rom_only(_cartridge(at=(0x007FC0, 0x017FC0)))

        for at in (0x007FC0, 0x017FC0):
            self.assertEqual(declared[at + rewrite.CHIPSET], rewrite.CHIPSET_ROM_ONLY)

    def test_the_pair_it_writes_is_a_complement_of_itself(self):
        declared = rewrite.declare_rom_only(_cartridge())
        at = 0x007FC0

        value = declared[at + rewrite.CHECKSUM] | (declared[at + rewrite.CHECKSUM + 1] << 8)
        complement = declared[at + rewrite.CHECKSUM_COMPLEMENT] | (
            declared[at + rewrite.CHECKSUM_COMPLEMENT + 1] << 8
        )

        self.assertEqual(value ^ complement, 0xFFFF)

    def test_the_value_it_writes_is_the_one_recomputed_from_the_result(self):
        declared = rewrite.declare_rom_only(_cartridge())
        at = 0x007FC0

        written = declared[at + rewrite.CHECKSUM] | (declared[at + rewrite.CHECKSUM + 1] << 8)

        self.assertEqual(written, rewrite.checksum(declared))

    def test_declaring_twice_changes_nothing_the_second_time(self):
        once = rewrite.declare_rom_only(_cartridge())

        self.assertEqual(rewrite.declare_rom_only(once), once)

    def test_the_original_image_is_left_alone(self):
        image = _cartridge()

        rewrite.declare_rom_only(image)

        self.assertNotEqual(image[0x007FC0 + rewrite.CHIPSET], rewrite.CHIPSET_ROM_ONLY)

    def test_nothing_outside_a_header_is_touched(self):
        image = _cartridge()

        declared = rewrite.declare_rom_only(image)

        outside = [
            at
            for at in rewrite.changes(image, declared)
            if not any(
                place <= at < place + rewrite.HEADER_BYTES for place in rewrite.mirrors(image)
            )
        ]
        self.assertEqual(outside, [])

    def test_an_image_with_no_header_is_refused_rather_than_stamped(self):
        with self.assertRaises(rewrite.NoHeader):
            rewrite.declare_rom_only(bytes(0x20000))


class NeedsTest(unittest.TestCase):
    def test_a_cartridge_declaring_a_coprocessor_needs_rewriting(self):
        self.assertTrue(rewrite.needs_rewrite(_cartridge()))

    def test_one_already_declared_does_not(self):
        self.assertFalse(rewrite.needs_rewrite(rewrite.declare_rom_only(_cartridge())))

    def test_a_wrong_size_byte_alone_is_enough(self):
        image = bytearray(rewrite.declare_rom_only(_cartridge()))
        image[0x007FC0 + rewrite.ROM_SIZE] = 0x01

        self.assertTrue(rewrite.needs_rewrite(bytes(image)))

    def test_an_image_with_no_header_is_refused_rather_than_answered(self):
        with self.assertRaises(rewrite.NoHeader):
            rewrite.needs_rewrite(bytes(0x20000))


class ChangeTest(unittest.TestCase):
    def test_identical_images_differ_nowhere(self):
        self.assertEqual(rewrite.changes(b"abc", b"abc"), [])

    def test_each_differing_position_is_reported_once(self):
        self.assertEqual(rewrite.changes(b"abc", b"aXc"), [1])

    def test_a_difference_in_a_later_block_is_still_found(self):
        before = bytes(0x3000)
        after = bytearray(before)
        after[0x2ABC] = 0xFF

        self.assertEqual(rewrite.changes(before, bytes(after), block=0x1000), [0x2ABC])

    def test_two_differences_in_one_block_are_both_found(self):
        before = bytes(0x2000)
        after = bytearray(before)
        after[0x100] = after[0x200] = 0xFF

        self.assertEqual(rewrite.changes(before, bytes(after), block=0x1000), [0x100, 0x200])

    def test_a_block_that_runs_past_the_end_is_not_walked_past_it(self):
        before = bytes(0x1800)
        after = bytearray(before)
        after[0x17FF] = 0xFF

        self.assertEqual(rewrite.changes(before, bytes(after), block=0x1000), [0x17FF])

    def test_the_block_size_does_not_change_the_answer(self):
        before = bytes(0x4000)
        after = bytearray(before)
        after[0x0001] = after[0x1FFF] = after[0x3ABC] = 0xFF

        wanted = [0x0001, 0x1FFF, 0x3ABC]
        for block in (0x10, 0x1000, 0x10000):
            self.assertEqual(rewrite.changes(before, bytes(after), block=block), wanted)


if __name__ == "__main__":
    unittest.main()
