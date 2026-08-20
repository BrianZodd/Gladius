"""Unit tests for the pure logic of gladius.py (stdlib unittest, no Qt app needed).

Run: python -m unittest test_gladius -v
No test touches the real %APPDATA%, the real registry, or the real wallpaper.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import gladius


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg_path = Path(self.tmp.name) / "config.json"
        self.p1 = mock.patch.object(gladius, "CONFIG_DIR", Path(self.tmp.name))
        self.p2 = mock.patch.object(gladius, "CONFIG_PATH", self.cfg_path)
        self.p1.start(); self.p2.start()
        self.addCleanup(self.p1.stop)
        self.addCleanup(self.p2.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_first_run_creates_defaults(self):
        cfg = gladius.Config.load()
        self.assertTrue(self.cfg_path.exists())
        self.assertEqual(cfg.number_of_pictures, 7)
        self.assertTrue(cfg.wallpaper_path.endswith("Wallpapers"))

    def test_partial_file_merges_defaults(self):
        self.cfg_path.write_text(json.dumps({"number_of_pictures": 5, "junk_key": 1}))
        cfg = gladius.Config.load()
        self.assertEqual(cfg.number_of_pictures, 5)
        self.assertEqual(cfg.fit_mode, "fill")
        self.assertFalse(hasattr(cfg, "junk_key"))

    def test_corrupt_file_falls_back(self):
        self.cfg_path.write_text("{not json")
        cfg = gladius.Config.load()
        self.assertEqual(cfg.border_color, "#C27B63")

    def test_clamps(self):
        self.cfg_path.write_text(json.dumps({"number_of_pictures": 99,
                                             "dim_opacity": 7, "backdrop": "vanta"}))
        cfg = gladius.Config.load()
        self.assertEqual(cfg.number_of_pictures, 15)
        self.assertEqual(cfg.dim_opacity, 1.0)
        self.assertEqual(cfg.backdrop, "dim")


class ScanTests(unittest.TestCase):
    def test_recursive_scan_filters_and_sorts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "sub").mkdir()
            (root / "b.jpg").write_bytes(b"x")
            (root / "sub" / "a.PNG").write_bytes(b"x")
            (root / "notes.txt").write_bytes(b"x")
            cfg = gladius.Config(wallpaper_path=d, recursive=True)
            names = [p.name for p in gladius.scan_wallpapers(cfg)]
            self.assertEqual(names, ["b.jpg", "a.PNG"])  # sorted by full lowered path
            cfg2 = gladius.Config(wallpaper_path=d, recursive=False)
            self.assertEqual([p.name for p in gladius.scan_wallpapers(cfg2)], ["b.jpg"])

    def test_missing_dir_returns_empty(self):
        cfg = gladius.Config(wallpaper_path=r"C:\definitely\not\here")
        self.assertEqual(gladius.scan_wallpapers(cfg), [])


class ThumbKeyTests(unittest.TestCase):
    def test_key_changes_with_content(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "w.jpg"
            f.write_bytes(b"one")
            k1 = gladius.thumb_key(f)
            f.write_bytes(b"three!")      # different size ⇒ different key even if mtime ties
            k2 = gladius.thumb_key(f)
            self.assertNotEqual(k1, k2)
            self.assertTrue(k1.endswith(".jpg"))


if __name__ == "__main__":
    unittest.main()
