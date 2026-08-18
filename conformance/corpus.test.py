import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from conformance import corpus
from romimage import rewrite


def _case(**changes):
    base = {
        "size": 0x100000,
        "map": 0x20,
        "chipset": 0x43,
        "rom_size": 0x0A,
        "sram_size": 0x00,
        "needs_rewrite": True,
        "size_byte": 10,
        "cartridges": 1,
    }
    return {**base, **changes}


def _document(cases):
    return {
        "measured_across": sum(case["cartridges"] for case in cases),
        "refused": 0,
        "properties_held": dict.fromkeys(("complement", "recompute", "confined", "settled"), 1),
        "cases": cases,
    }


class ShippedTest(unittest.TestCase):
    def test_the_shipped_corpus_is_there_and_parses(self):
        self.assertGreater(len(corpus.load()["cases"]), 0)

    def test_it_was_measured_across_a_real_library(self):
        self.assertGreater(corpus.load()["measured_across"], 1000)

    def test_every_shipped_case_agrees_with_the_model(self):
        wrong = corpus.check(corpus.load())

        self.assertEqual(wrong, [])

    def test_no_shipped_case_carries_anything_but_measurements(self):
        allowed = {
            "size",
            "map",
            "chipset",
            "rom_size",
            "sram_size",
            "needs_rewrite",
            "size_byte",
            "cartridges",
        }

        for case in corpus.load()["cases"]:
            self.assertEqual(set(case) - allowed, set())


class CheckTest(unittest.TestCase):
    def test_a_case_that_agrees_is_not_reported(self):
        self.assertEqual(corpus.check(_document([_case()])), [])

    def test_a_wrong_exponent_is_reported(self):
        wrong = corpus.check(_document([_case(size_byte=3)]))

        self.assertEqual(wrong[0]["why"], "size_byte")

    def test_a_declared_coprocessor_that_claims_no_rewrite_is_reported(self):
        wrong = corpus.check(_document([_case(chipset=0x43, needs_rewrite=False)]))

        self.assertEqual(wrong[0]["why"], "needs_rewrite")

    def test_a_wrong_size_byte_in_the_header_that_claims_no_rewrite_is_reported(self):
        wrong = corpus.check(_document([_case(chipset=0x00, rom_size=0x01, needs_rewrite=False)]))

        self.assertEqual(wrong[0]["why"], "needs_rewrite")

    def test_a_cartridge_already_declaring_rom_only_may_say_it_needs_nothing(self):
        clean = _case(chipset=0x00, rom_size=10, needs_rewrite=False)

        self.assertEqual(corpus.check(_document([clean])), [])

    def test_the_report_names_the_case_that_failed(self):
        wrong = corpus.check(_document([_case(size_byte=3)]))

        self.assertEqual(wrong[0]["case"]["chipset"], 0x43)


class LoadTest(unittest.TestCase):
    def test_a_path_is_read_from_disk(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "corpus.json"
            path.write_text(json.dumps(_document([_case()])))

            self.assertEqual(len(corpus.load(path)["cases"]), 1)


class ReportTest(unittest.TestCase):
    def _said(self, document, wrong):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            corpus.report(document, wrong)
        return buffer.getvalue()

    def test_it_says_how_many_cases_and_how_many_cartridges(self):
        said = self._said(_document([_case()]), [])

        self.assertIn("1 declarations", said)
        self.assertIn("1 cartridges", said)

    def test_it_says_how_many_agreed(self):
        self.assertIn("1 agreed, 0 did not", self._said(_document([_case()]), []))

    def test_a_disagreement_is_printed(self):
        document = _document([_case(size_byte=3)])

        self.assertIn("size_byte", self._said(document, corpus.check(document)))


class MainTest(unittest.TestCase):
    def test_the_shipped_corpus_replays_clean(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(corpus.main(["corpus.py"]), 0)

    def test_a_corpus_that_disagrees_exits_non_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "corpus.json"
            path.write_text(json.dumps(_document([_case(size_byte=3)])))

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(corpus.main(["corpus.py", str(path)]), 1)

    def test_it_refuses_more_arguments_than_it_takes(self):
        self.assertEqual(corpus.main(["corpus.py", "a", "b"]), 2)


class ModelTest(unittest.TestCase):
    def test_the_exponent_the_corpus_expects_is_the_one_the_model_computes(self):
        for case in corpus.load()["cases"][:50]:
            self.assertEqual(rewrite.size_byte(case["size"]), case["size_byte"])


if __name__ == "__main__":
    unittest.main()
