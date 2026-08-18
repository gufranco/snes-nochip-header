import json
import random
import tempfile
import unittest
from pathlib import Path

from romimage import identity, manifest, rewrite


def _blank(banks=2, seed=1):
    generator = random.Random(seed)
    return bytearray(generator.randrange(256) for _ in range(banks * 0x10000))


def _cartridge(banks=2, seed=1, at=0x007FC0, chipset=0x43):
    image = _blank(banks, seed)
    image[at : at + 21] = b"A CARTRIDGE          "
    image[at + rewrite.MAP_MODE] = 0x20
    image[at + rewrite.CHIPSET] = chipset
    image[at + rewrite.ROM_SIZE] = 0x09
    image[at + rewrite.SRAM_SIZE] = 0x00
    image[at + rewrite.CHECKSUM_COMPLEMENT : at + rewrite.CHECKSUM_COMPLEMENT + 4] = bytes(4)
    return bytes(image)


GOOD = _cartridge()
DONE = rewrite.declare_rom_only(GOOD)
OTHER = _cartridge(seed=2)
CORRUPT = _cartridge(seed=3)


def _document():
    return {
        "canonical": {"form": "one file, no copier stub"},
        "artifacts": [
            {
                "name": "A Cartridge, Japanese",
                "filename": "a-cartridge-jp.sfc",
                "accepted": [identity.measure(GOOD)],
                "rewritten": identity.measure(DONE),
                "bad": [dict(identity.measure(CORRUPT), why="overdump")],
            }
        ],
    }


class LoadTest(unittest.TestCase):
    def test_a_document_is_taken_as_given(self):
        self.assertEqual(len(manifest.Manifest(_document()).artifacts), 1)

    def test_a_path_is_read_from_disk(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "artifacts.manifest.json"
            path.write_text(json.dumps(_document()))

            self.assertEqual(len(manifest.Manifest.from_path(path).artifacts), 1)

    def test_a_document_with_no_artifacts_is_refused(self):
        with self.assertRaises(manifest.Malformed):
            manifest.Manifest({"canonical": {}})

    def test_an_artifact_with_no_accepted_form_is_refused(self):
        with self.assertRaises(manifest.Malformed):
            manifest.Manifest({"artifacts": [{"name": "x", "accepted": []}]})

    def test_an_accepted_form_with_no_deciding_value_is_refused(self):
        with self.assertRaises(manifest.Malformed):
            manifest.Manifest({"artifacts": [{"name": "x", "accepted": [{"crc32": "0"}]}]})


class MatchTest(unittest.TestCase):
    def setUp(self):
        self.manifest = manifest.Manifest(_document())

    def test_the_file_it_expects_is_recognised(self):
        self.assertEqual(self.manifest.diagnose(GOOD)["state"], manifest.KNOWN)

    def test_an_already_rewritten_file_is_recognised_as_that(self):
        self.assertEqual(self.manifest.diagnose(DONE)["state"], manifest.REWRITTEN)

    def test_a_dump_it_knows_to_be_damaged_is_named_as_damaged(self):
        found = self.manifest.diagnose(CORRUPT)

        self.assertEqual(found["state"], manifest.BAD_DUMP)
        self.assertEqual(found["why"], "overdump")

    def test_a_file_of_the_right_size_and_wrong_content_says_so(self):
        self.assertEqual(self.manifest.diagnose(OTHER)["state"], manifest.SAME_SIZE)

    def test_a_file_of_no_recognised_size_is_simply_unknown(self):
        self.assertEqual(self.manifest.diagnose(bytes(0x1000))["state"], manifest.UNKNOWN)

    def test_a_copier_stub_comes_off_before_the_comparison(self):
        found = self.manifest.diagnose(bytes(0x200) + GOOD)

        self.assertEqual(found["state"], manifest.KNOWN)
        self.assertEqual(found["form"], "copier header")

    def test_the_form_is_reported_as_given_when_one_is_supplied(self):
        self.assertEqual(self.manifest.diagnose(GOOD, form="4 part set")["form"], "4 part set")

    def test_what_it_computed_is_reported_whether_or_not_it_matched(self):
        found = self.manifest.diagnose(OTHER)

        self.assertEqual(found["identity"]["sha256"], identity.measure(OTHER)["sha256"])

    def test_a_recognised_file_names_the_artifact_it_is(self):
        self.assertEqual(self.manifest.diagnose(GOOD)["artifact"]["name"], "A Cartridge, Japanese")

    def test_an_unrecognised_file_names_no_artifact(self):
        self.assertIsNone(self.manifest.diagnose(bytes(0x1000))["artifact"])

    def test_the_headers_it_found_come_back_with_the_verdict(self):
        found = self.manifest.diagnose(GOOD)

        self.assertEqual(found["headers"][0]["coprocessor"], "S-DD1")

    def test_a_manifest_that_lists_no_damaged_dumps_still_answers(self):
        document = _document()
        del document["artifacts"][0]["bad"]

        self.assertEqual(manifest.Manifest(document).diagnose(CORRUPT)["state"], manifest.SAME_SIZE)

    def test_a_manifest_that_lists_no_rewritten_form_still_answers(self):
        document = _document()
        del document["artifacts"][0]["rewritten"]

        self.assertEqual(manifest.Manifest(document).diagnose(DONE)["state"], manifest.SAME_SIZE)


class ExplainTest(unittest.TestCase):
    def setUp(self):
        self.manifest = manifest.Manifest(_document())

    def test_it_always_prints_what_it_computed(self):
        said = self.manifest.explain(self.manifest.diagnose(OTHER))

        self.assertIn(identity.measure(OTHER)["sha256"], said)

    def test_a_recognised_file_is_named(self):
        self.assertIn("A Cartridge, Japanese", self.manifest.explain(self.manifest.diagnose(GOOD)))

    def test_an_already_rewritten_file_says_so_rather_than_reading_as_wrong(self):
        self.assertIn("already", self.manifest.explain(self.manifest.diagnose(DONE)))

    def test_a_damaged_dump_says_damaged_rather_than_wrong(self):
        self.assertIn("overdump", self.manifest.explain(self.manifest.diagnose(CORRUPT)))

    def test_a_same_size_miss_says_what_to_suspect(self):
        said = self.manifest.explain(self.manifest.diagnose(OTHER))

        self.assertIn("contents do not", said)

    def test_an_unknown_file_says_the_manifest_does_not_know_it(self):
        self.assertIn("not a file", self.manifest.explain(self.manifest.diagnose(bytes(0x1000))))

    def test_every_header_it_found_is_printed(self):
        said = self.manifest.explain(self.manifest.diagnose(GOOD))

        self.assertIn("S-DD1", said)


if __name__ == "__main__":
    unittest.main()
