import random
import tempfile
import unittest
import zlib
from pathlib import Path

from romimage import dump


def _image(banks=2, seed=1):
    generator = random.Random(seed)
    return bytes(generator.randrange(256) for _ in range(banks * 0x10000))


class CopierStubTest(unittest.TestCase):
    def test_a_whole_number_of_half_banks_carries_no_stub(self):
        self.assertFalse(dump.has_copier_stub(_image()))

    def test_the_same_image_with_five_hundred_and_twelve_more_bytes_does(self):
        self.assertTrue(dump.has_copier_stub(bytes(dump.COPIER_BYTES) + _image()))

    def test_a_file_no_longer_than_the_stub_cannot_be_one(self):
        self.assertFalse(dump.has_copier_stub(bytes(dump.COPIER_BYTES)))

    def test_a_length_of_no_recognised_shape_is_left_alone(self):
        self.assertFalse(dump.has_copier_stub(bytes(1234)))

    def test_the_test_is_the_one_the_header_reader_already_uses(self):
        import mapper

        for length in (0x20000, 0x20000 + 0x200, 0x200, 1234, 0x8000 + 0x200):
            self.assertEqual(
                dump.has_copier_stub(bytes(length)),
                mapper.has_copier_stub(bytes(length)),
            )

    def test_stripping_removes_exactly_the_stub(self):
        image = _image()

        self.assertEqual(dump.strip_copier_stub(bytes(dump.COPIER_BYTES) + image), image)

    def test_stripping_an_image_that_never_had_one_changes_nothing(self):
        image = _image()

        self.assertEqual(dump.strip_copier_stub(image), image)


class SplitSetTest(unittest.TestCase):
    def _set(self, folder, names, parts):
        for name, part in zip(names, parts, strict=True):
            (Path(folder) / name).write_bytes(part)

    def test_the_parts_join_in_name_order_with_one_stub_removed(self):
        first, second = _image(banks=1, seed=2), _image(banks=1, seed=3)

        with tempfile.TemporaryDirectory() as folder:
            self._set(
                folder,
                ["SF6A.078", "SF6B.078"],
                [bytes(dump.COPIER_BYTES) + first, second],
            )

            self.assertEqual(dump.read(folder), first + second)

    def test_the_order_ignores_case(self):
        first, second = _image(banks=1, seed=4), _image(banks=1, seed=5)

        with tempfile.TemporaryDirectory() as folder:
            self._set(folder, ["sf6a.078", "SF6B.078"], [first, second])

            self.assertEqual(dump.read(folder), first + second)

    def test_a_numbered_suffix_of_any_width_counts_as_a_part(self):
        first, second = _image(banks=1, seed=6), _image(banks=1, seed=7)

        with tempfile.TemporaryDirectory() as folder:
            self._set(folder, ["game.1", "game.2"], [first, second])

            self.assertEqual(dump.read(folder), first + second)

    def test_a_file_that_is_not_a_part_is_left_out(self):
        only = _image(banks=1, seed=8)

        with tempfile.TemporaryDirectory() as folder:
            self._set(folder, ["game.078", "notes.txt"], [only, b"nothing here"])

            self.assertEqual(dump.read(folder), only)

    def test_parts_are_found_below_the_folder_as_well_as_in_it(self):
        part = _image(banks=1, seed=9)

        with tempfile.TemporaryDirectory() as folder:
            nested = Path(folder) / "set"
            nested.mkdir()
            (nested / "game.078").write_bytes(part)

            self.assertEqual(dump.read(folder), part)

    def test_a_folder_with_no_parts_is_refused_rather_than_read_as_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "notes.txt").write_bytes(b"nothing here")

            with self.assertRaises(dump.NoParts):
                dump.read(folder)

    def test_joining_nothing_gives_nothing(self):
        self.assertEqual(dump.join([]), b"")


class LengthTest(unittest.TestCase):
    def test_it_agrees_with_the_test_that_reads_the_bytes(self):
        for size in (0, 0x200, 0x8000, 0x8200, 0x20000, 0x20200, 1234):
            self.assertEqual(dump.stub_by_length(size), dump.has_copier_stub(bytes(size)), size)


class FormTest(unittest.TestCase):
    def test_a_bare_file_says_so(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "game.sfc"
            path.write_bytes(_image())

            self.assertEqual(dump.form(path), dump.BARE)

    def test_a_file_with_a_stub_says_so(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "game.smc"
            path.write_bytes(bytes(dump.COPIER_BYTES) + _image())

            self.assertEqual(dump.form(path), dump.COPIER)

    def test_a_folder_says_how_many_parts_it_holds(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("game.1", "game.2", "game.3"):
                (Path(folder) / name).write_bytes(_image(banks=1))

            self.assertEqual(dump.form(folder), "3 part set")


class ReadTest(unittest.TestCase):
    def test_a_dump_comes_back_as_the_console_would_have_seen_it(self):
        image = _image()

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "game.smc"
            path.write_bytes(bytes(dump.COPIER_BYTES) + image)

            self.assertEqual(dump.read(path), image)


class RatioTest(unittest.TestCase):
    def test_an_empty_block_has_no_ratio_rather_than_a_division(self):
        self.assertEqual(dump.deflate_ratio(b""), 0.0)

    def test_a_block_of_one_repeated_byte_compresses_far_below_one(self):
        self.assertLess(dump.deflate_ratio(bytes(0x10000)), 0.1)

    def test_a_block_of_random_bytes_does_not(self):
        self.assertGreater(dump.deflate_ratio(_image(banks=1)), 0.9)

    def test_the_ratio_is_the_compressed_size_over_the_original(self):
        block = _image(banks=1, seed=10)

        self.assertEqual(
            dump.deflate_ratio(block),
            len(zlib.compress(block, dump.DEFLATE_LEVEL)) / len(block),
        )

    def test_one_ratio_per_whole_block_and_none_for_the_remainder(self):
        self.assertEqual(len(dump.block_ratios(bytes(0x10000 * 3 + 5), block=0x10000)), 3)

    def test_an_image_shorter_than_one_block_gives_no_ratios(self):
        self.assertEqual(dump.block_ratios(bytes(0x100), block=0x10000), [])


class ReuseTest(unittest.TestCase):
    def test_a_chunk_is_indexed_at_the_first_place_it_appears(self):
        index = dump.chunk_index(b"AB" * 8, chunk=4, stride=2)

        self.assertEqual(index[b"ABAB"], 0)

    def test_an_image_shorter_than_the_chunk_indexes_nothing(self):
        self.assertEqual(dump.chunk_index(b"AB", chunk=4, stride=2), {})

    def test_an_image_compared_with_itself_reuses_everything(self):
        image = _image(banks=1, seed=11)

        found, total = dump.measure_reuse(image, image)

        self.assertEqual(found, total)
        self.assertGreater(total, 0)

    def test_two_unrelated_images_reuse_nothing(self):
        found, _ = dump.measure_reuse(_image(banks=1, seed=12), _image(banks=1, seed=13))

        self.assertEqual(found, 0)

    def test_a_run_that_moved_by_less_than_a_chunk_is_still_found(self):
        run = _image(banks=1, seed=14)[:4096]

        found, _ = dump.measure_reuse(run + bytes(4096), bytes(dump.CHUNK_STRIDE) + run)

        self.assertGreater(found, 0)


if __name__ == "__main__":
    unittest.main()
