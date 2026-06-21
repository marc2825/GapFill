import tempfile
import unittest
import zipfile
from pathlib import Path


class BuildTests(unittest.TestCase):
    def test_distribution_contains_entrypoint_model_and_no_cache(self):
        import sys

        scripts = Path(__file__).resolve().parents[1] / "scripts"
        sys.path.insert(0, str(scripts))
        try:
            from build_plugin import build
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "gapfill-krita.zip"
            build(output)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
            self.assertIn("gapfill_krita.desktop", names)
            self.assertIn("gapfill_krita/__init__.py", names)
            self.assertIn("gapfill_krita/resources/models/unet32.onnx", names)
            self.assertFalse(any("__pycache__" in name for name in names))


if __name__ == "__main__":
    unittest.main()
