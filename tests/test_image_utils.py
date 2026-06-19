from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from hackerrank_orchestrator.image_utils import (
    build_openai_compatible_image_content,
    image_id_from_path,
    image_ids_from_raw,
    split_image_paths,
)


class ImageUtilsTests(unittest.TestCase):
    def test_split_image_paths(self) -> None:
        raw = "images/test/case_001/img_1.jpg; images/test/case_001/img_2.png"
        self.assertEqual(
            split_image_paths(raw),
            ["images/test/case_001/img_1.jpg", "images/test/case_001/img_2.png"],
        )

    def test_image_id_helpers(self) -> None:
        self.assertEqual(image_id_from_path("images/test/case_001/img_1.jpg"), "img_1")
        self.assertEqual(
            image_ids_from_raw("a/img_1.jpg;b/img_2.png"), ["img_1", "img_2"]
        )

    def test_openai_compatible_image_content(self) -> None:
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.jpg"
            image_path.write_bytes(b"fake-image-bytes")
            content = build_openai_compatible_image_content("check this", [image_path])
            self.assertEqual(content[0]["type"], "text")
            self.assertEqual(content[1]["type"], "image_url")
            self.assertIn("data:image/jpeg;base64,", content[1]["image_url"]["url"])


if __name__ == "__main__":
    unittest.main()
