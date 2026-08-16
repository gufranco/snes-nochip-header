import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


identify = load_module("identify")

KNOWN = identify.MANIFEST["artifacts"][0]
DIGEST = KNOWN["accepted"][0]["sha256"]
REPAIRED = KNOWN["repaired"]["sha256"]


class ManifestTest(unittest.TestCase):
    def test_the_manifest_declares_a_canonical_form(self):
        self.assertIn("form", identify.MANIFEST["canonical"])

    def test_every_artifact_carries_a_sha256_for_every_accepted_form(self):
        for artifact in identify.MANIFEST["artifacts"]:
            for accepted in artifact["accepted"]:
                self.assertEqual(len(accepted["sha256"]), 64)

    def test_every_artifact_carries_the_digest_it_repairs_to(self):
        for artifact in identify.MANIFEST["artifacts"]:
            self.assertEqual(len(artifact["repaired"]["sha256"]), 64)

    def test_no_repaired_digest_equals_the_one_it_came_from(self):
        for artifact in identify.MANIFEST["artifacts"]:
            for accepted in artifact["accepted"]:
                self.assertNotEqual(accepted["sha256"], artifact["repaired"]["sha256"])

    def test_every_artifact_records_where_its_numbers_came_from(self):
        for artifact in identify.MANIFEST["artifacts"]:
            self.assertTrue(artifact["provenance"])


class MatchTest(unittest.TestCase):
    def test_a_known_digest_is_recognised(self):
        found = identify.match_digest(DIGEST)

        self.assertEqual(found["state"], "known")
        self.assertEqual(found["artifact"]["language"], KNOWN["language"])

    def test_an_already_repaired_digest_is_recognised_as_such(self):
        found = identify.match_digest(REPAIRED)

        self.assertEqual(found["state"], "repaired")

    def test_an_unknown_digest_is_unknown(self):
        found = identify.match_digest("0" * 64)

        self.assertEqual(found["state"], "unknown")


class DiagnoseTest(unittest.TestCase):
    def test_a_file_carrying_a_copier_header_is_named_as_such(self):
        found = identify.diagnose(bytes(0x8000 + 512))

        self.assertEqual(found["form"], "copier header")

    def test_a_file_of_the_canonical_size_is_named_as_such(self):
        found = identify.diagnose(bytes(12582912))

        self.assertEqual(found["form"], "bare")

    def test_the_diagnosis_reports_the_digest_it_computed(self):
        found = identify.diagnose(b"snes" * 4)

        self.assertEqual(len(found["identity"]["sha256"]), 64)

    def test_a_short_file_is_reported_as_too_small(self):
        found = identify.diagnose(b"snes")

        self.assertEqual(found["state"], "unknown")
        self.assertEqual(found["size"], 4)

    def test_a_known_image_is_diagnosed_as_known_after_stripping(self):
        found = identify.diagnose(bytes(512) + bytes(0x8000))

        self.assertEqual(found["form"], "copier header")
        self.assertEqual(found["size"], 0x8000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
