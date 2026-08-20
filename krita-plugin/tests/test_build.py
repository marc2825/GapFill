import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


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
            self.assertIn("actions/gapfill_krita.action", names)
            self.assertIn("gapfill_krita/__init__.py", names)
            self.assertIn("gapfill_krita/resources/models/unet32.onnx", names)
            self.assertNotIn(
                "gapfill_krita/_native/"
                "gapfill_krita_native_5_3_3.cp313-win_amd64.pyd",
                names,
            )
            self.assertFalse(any("__pycache__" in name for name in names))

    def test_distribution_validates_and_stages_exact_native_helper(self):
        import sys

        scripts = Path(__file__).resolve().parents[1] / "scripts"
        sys.path.insert(0, str(scripts))
        try:
            import build_plugin
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper = root / build_plugin.NATIVE_HELPER_FILENAME
            helper.write_bytes(b"deterministic native test payload")
            first = root / "first.zip"
            second = root / "second.zip"

            with mock.patch.object(
                build_plugin,
                "NATIVE_HELPER_SHA256",
                hashlib.sha256(helper.read_bytes()).hexdigest(),
            ):
                build_plugin.build(first, native_helper=helper)
                build_plugin.build(second, native_helper=helper)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(
                    archive.read(
                        "gapfill_krita/_native/"
                        "gapfill_krita_native_5_3_3.cp313-win_amd64.pyd"
                    ),
                    helper.read_bytes(),
                )

    def test_distribution_rejects_native_helper_with_wrong_hash(self):
        import sys

        scripts = Path(__file__).resolve().parents[1] / "scripts"
        sys.path.insert(0, str(scripts))
        try:
            import build_plugin
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper = root / build_plugin.NATIVE_HELPER_FILENAME
            helper.write_bytes(b"wrong helper")
            output = root / "rejected.zip"
            with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                build_plugin.build(output, native_helper=helper)


if __name__ == "__main__":
    unittest.main()
