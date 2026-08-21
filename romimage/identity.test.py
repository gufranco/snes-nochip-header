import hashlib
import random
import unittest
import zlib

from romimage import identity


def _image(banks: int = 1, seed: int = 1) -> bytes:
    generator = random.Random(seed)
    return bytes(generator.randrange(256) for _ in range(banks * 0x10000))


class MeasureTest(unittest.TestCase):
    def test_the_size_is_the_length_in_bytes(self) -> None:
        self.assertEqual(identity.measure(_image(banks=2))["size"], 0x20000)

    def test_every_published_value_is_present(self) -> None:
        found = identity.measure(_image())

        self.assertEqual(set(found), {"size", "crc32", "md5", "sha1", "sha256"})

    def test_the_deciding_value_is_the_one_it_names(self) -> None:
        self.assertEqual(identity.AUTHORITATIVE, "sha256")

    def test_the_digests_are_of_the_bytes_given(self) -> None:
        image = _image(seed=2)
        found = identity.measure(image)

        self.assertEqual(found["crc32"], f"{zlib.crc32(image):08X}")
        self.assertEqual(found["sha256"], hashlib.sha256(image).hexdigest())
        self.assertEqual(found["sha1"], hashlib.sha1(image).hexdigest())
        self.assertEqual(found["md5"], hashlib.md5(image).hexdigest())

    def test_two_images_that_differ_by_one_byte_measure_differently(self) -> None:
        first = bytearray(_image(seed=3))
        second = bytearray(first)
        second[0] ^= 0xFF

        self.assertNotEqual(
            identity.measure(bytes(first))["sha256"],
            identity.measure(bytes(second))["sha256"],
        )

    def test_an_empty_image_measures_rather_than_failing(self) -> None:
        self.assertEqual(identity.measure(b"")["size"], 0)


class AgreementTest(unittest.TestCase):
    def test_a_measurement_agrees_with_itself(self) -> None:
        found = identity.measure(_image(seed=4))

        self.assertTrue(identity.agrees(found, found))

    def test_the_deciding_value_settles_it_even_when_another_disagrees(self) -> None:
        found = identity.measure(_image(seed=5))
        loose = dict(found, crc32="00000000")

        self.assertTrue(identity.agrees(found, loose))

    def test_a_different_deciding_value_is_a_different_file(self) -> None:
        first = identity.measure(_image(seed=6))
        second = identity.measure(_image(seed=7))

        self.assertFalse(identity.agrees(first, second))

    def test_an_expectation_with_no_deciding_value_is_refused(self) -> None:
        found = identity.measure(_image(seed=8))

        with self.assertRaises(identity.NoAuthority):
            identity.agrees(found, {"crc32": found["crc32"]})


if __name__ == "__main__":
    unittest.main()
