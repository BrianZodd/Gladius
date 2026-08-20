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


if __name__ == "__main__":
    unittest.main()
