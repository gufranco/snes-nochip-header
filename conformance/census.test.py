import contextlib
import io
import json
import random
import tempfile
import unittest
import zipfile
from pathlib import Path

from conformance import census
from romimage import rewrite


def _cartridge(banks=2, seed=1, at=0x007FC0, chipset=0x43, mapping=0x20):
    generator = random.Random(seed)
    image = bytearray(generator.randrange(256) for _ in range(banks * 0x10000))
    image[at : at + 21] = b"A CARTRIDGE          "
    image[at + rewrite.MAP_MODE] = mapping
    image[at + rewrite.CHIPSET] = chipset
    image[at + rewrite.ROM_SIZE] = 0x09
    image[at + rewrite.SRAM_SIZE] = 0x00
    image[at + rewrite.CHECKSUM_COMPLEMENT : at + rewrite.CHECKSUM_COMPLEMENT + 4] = bytes(4)
    return bytes(image)


class ImagesTest(unittest.TestCase):
    def test_a_folder_yields_every_cartridge_in_a_fixed_order(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "b.sfc").write_bytes(_cartridge(seed=2))
            (Path(folder) / "a.sfc").write_bytes(_cartridge(seed=1))

            self.assertEqual([name for name, _ in census.images(folder)], ["a.sfc", "b.sfc"])

    def test_a_file_that_is_not_a_cartridge_is_left_out(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "a.sfc").write_bytes(_cartridge())
            (Path(folder) / "notes.txt").write_bytes(b"nothing")

            self.assertEqual([name for name, _ in census.images(folder)], ["a.sfc"])

    def test_a_limit_stops_the_walk_early(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("a.sfc", "b.sfc", "c.sfc"):
                (Path(folder) / name).write_bytes(_cartridge())

            self.assertEqual(len(list(census.images(folder, limit=2))), 2)

    def test_an_archive_is_read_member_by_member_rather_than_unpacked(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("set/b.sfc", _cartridge(seed=2))
            archive.writestr("set/a.sfc", _cartridge(seed=1))
            archive.writestr("set/readme.txt", "nothing")

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "library.zip"
            path.write_bytes(buffer.getvalue())

            self.assertEqual([name for name, _ in census.images(path)], ["a.sfc", "b.sfc"])

    def test_an_archive_honours_the_limit_too(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name in ("a.sfc", "b.sfc", "c.sfc"):
                archive.writestr(name, _cartridge())

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "library.zip"
            path.write_bytes(buffer.getvalue())

            self.assertEqual(len(list(census.images(path, limit=2))), 2)


class SurveyTest(unittest.TestCase):
    def _library(self, folder, images):
        for index, image in enumerate(images):
            (Path(folder) / f"{index:03d}.sfc").write_bytes(image)
        return folder

    def test_a_cartridge_with_a_header_is_read(self):
        with tempfile.TemporaryDirectory() as folder:
            found = census.survey(self._library(folder, [_cartridge()]))

            self.assertEqual(found["read"], 1)
            self.assertEqual(found["refused"], 0)

    def test_a_file_with_no_header_is_refused_rather_than_guessed_at(self):
        with tempfile.TemporaryDirectory() as folder:
            found = census.survey(self._library(folder, [bytes(0x20000)]))

            self.assertEqual(found["read"], 0)
            self.assertEqual(found["refused"], 1)

    def test_a_copier_stub_is_counted_as_a_form_and_then_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            found = census.survey(self._library(folder, [bytes(0x200) + _cartridge()]))

            self.assertEqual(found["forms"]["copier stub"], 1)
            self.assertEqual(found["read"], 1)

    def test_two_cartridges_declaring_the_same_thing_are_one_case(self):
        with tempfile.TemporaryDirectory() as folder:
            found = census.survey(self._library(folder, [_cartridge(seed=1), _cartridge(seed=2)]))

            self.assertEqual(len(found["cases"]), 1)
            self.assertEqual(sum(found["cases"].values()), 2)

    def test_a_different_chipset_is_a_different_case(self):
        with tempfile.TemporaryDirectory() as folder:
            found = census.survey(
                self._library(folder, [_cartridge(chipset=0x43), _cartridge(chipset=0x00)])
            )

            self.assertEqual(len(found["cases"]), 2)

    def test_a_coprocessor_it_can_name_is_counted_by_name(self):
        with tempfile.TemporaryDirectory() as folder:
            found = census.survey(self._library(folder, [_cartridge(chipset=0x43)]))

            self.assertEqual(found["coprocessor"]["S-DD1"], 1)

    def test_a_cartridge_declaring_no_coprocessor_counts_as_none(self):
        with tempfile.TemporaryDirectory() as folder:
            found = census.survey(self._library(folder, [_cartridge(chipset=0x00)]))

            self.assertEqual(found["coprocessor"]["none"], 1)

    def test_every_property_holds_on_a_real_shaped_cartridge(self):
        with tempfile.TemporaryDirectory() as folder:
            found = census.survey(self._library(folder, [_cartridge()]))

            for name in census.PROPERTIES:
                self.assertEqual(found["properties"][name], 1, name)
            self.assertEqual(found["failures"], [])

    def test_the_two_packages_agree_about_a_real_cartridge(self):
        with tempfile.TemporaryDirectory() as folder:
            found = census.survey(self._library(folder, [_cartridge()]))

            self.assertEqual(found["disagreed_with_the_map"], 0)

    def test_they_agree_about_a_file_that_is_not_one(self):
        with tempfile.TemporaryDirectory() as folder:
            found = census.survey(self._library(folder, [bytes(0x20000)]))

            self.assertEqual(found["disagreed_with_the_map"], 0)

    def test_a_disagreement_is_counted_rather_than_hidden(self):
        image = bytearray(_cartridge())
        image[0x007FC0 + rewrite.MAP_MODE] = 0x7F

        with tempfile.TemporaryDirectory() as folder:
            found = census.survey(self._library(folder, [bytes(image)]))

            self.assertEqual(found["disagreed_with_the_map"], found["refused"])

    def test_a_cartridge_that_needs_no_rewrite_is_not_counted_as_needing_one(self):
        with tempfile.TemporaryDirectory() as folder:
            found = census.survey(self._library(folder, [rewrite.declare_rom_only(_cartridge())]))

            self.assertEqual(found["needs_rewrite"], 0)


class FailedTest(unittest.TestCase):
    def test_a_cartridge_where_everything_held_reports_nothing(self):
        self.assertEqual(census.failed("a.sfc", dict.fromkeys(census.PROPERTIES, True)), [])

    def test_a_property_that_did_not_hold_is_named_with_its_cartridge(self):
        properties = dict.fromkeys(census.PROPERTIES, True)
        properties["settled"] = False

        self.assertEqual(
            census.failed("a.sfc", properties), [{"file": "a.sfc", "property": "settled"}]
        )

    def test_every_property_that_failed_is_reported(self):
        found = census.failed("a.sfc", dict.fromkeys(census.PROPERTIES, False))

        self.assertEqual(len(found), len(census.PROPERTIES))


class CorpusTest(unittest.TestCase):
    def _survey(self, images):
        with tempfile.TemporaryDirectory() as folder:
            for index, image in enumerate(images):
                (Path(folder) / f"{index:03d}.sfc").write_bytes(image)
            return census.survey(folder)

    def test_every_case_carries_the_exponent_it_must_produce(self):
        built = census.corpus(self._survey([_cartridge(banks=2)]))

        self.assertEqual(built["cases"][0]["size_byte"], rewrite.size_byte(0x20000))

    def test_every_case_carries_how_many_cartridges_it_accounts_for(self):
        built = census.corpus(self._survey([_cartridge(seed=1), _cartridge(seed=2)]))

        self.assertEqual(built["cases"][0]["cartridges"], 2)

    def test_it_records_how_many_cartridges_it_was_measured_across(self):
        built = census.corpus(self._survey([_cartridge()]))

        self.assertEqual(built["measured_across"], 1)

    def test_it_carries_nothing_that_could_rebuild_a_cartridge(self):
        built = census.corpus(self._survey([_cartridge()]))

        self.assertEqual(
            set(built["cases"][0]),
            {
                "size",
                "map",
                "chipset",
                "rom_size",
                "sram_size",
                "needs_rewrite",
                "size_byte",
                "cartridges",
            },
        )

    def test_what_it_writes_is_json(self):
        built = census.corpus(self._survey([_cartridge()]))

        self.assertEqual(json.loads(json.dumps(built)), built)


class MainTest(unittest.TestCase):
    def test_it_refuses_a_call_with_the_wrong_number_of_arguments(self):
        self.assertEqual(census.main(["census.py"]), 2)

    def test_it_writes_the_corpus_where_it_was_told_to(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "a.sfc").write_bytes(_cartridge())
            out = Path(folder) / "corpus.json"

            self.assertEqual(census.main(["census.py", folder, str(out), "1"]), 0)
            self.assertEqual(json.loads(out.read_text())["measured_across"], 1)

    def test_a_library_where_everything_held_exits_zero(self):
        self.assertEqual(census.verdict({"failures": []}), 0)

    def test_a_library_where_something_failed_exits_non_zero(self):
        self.assertEqual(
            census.verdict({"failures": [{"file": "a.sfc", "property": "settled"}]}), 1
        )


class ReportTest(unittest.TestCase):
    def _said(self, found):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            census.report(found)
        return buffer.getvalue()

    def _survey(self, images):
        with tempfile.TemporaryDirectory() as folder:
            for index, image in enumerate(images):
                (Path(folder) / f"{index:03d}.sfc").write_bytes(image)
            return census.survey(folder)

    def test_it_says_how_many_disagreed_with_the_map(self):
        said = self._said(self._survey([_cartridge()]))

        self.assertIn("disagreed with the map", said)

    def test_it_says_how_many_it_read_and_how_many_it_refused(self):
        said = self._said(self._survey([_cartridge(), bytes(0x20000)]))

        self.assertIn("1 cartridges read, 1 refused", said)

    def test_it_says_how_many_still_declare_a_coprocessor(self):
        self.assertIn("1 still declare", self._said(self._survey([_cartridge()])))

    def test_it_names_every_property_it_checked(self):
        said = self._said(self._survey([_cartridge()]))

        for name in census.PROPERTIES:
            self.assertIn(name, said)

    def test_a_failure_is_printed_rather_than_only_counted(self):
        found = self._survey([_cartridge()])
        found["failures"] = [{"file": "broken.sfc", "property": "settled"}]

        self.assertIn("broken.sfc", self._said(found))


if __name__ == "__main__":
    unittest.main()
