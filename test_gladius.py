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


class ConfigRobustnessTests(ConfigTests):
    """A hand-edited config must never crash a hotkey-launched app."""

    def test_wrong_types_fall_back_to_defaults(self):
        self.cfg_path.write_text(json.dumps({
            "number_of_pictures": "seven",     # not a number
            "dim_opacity": "very",             # not a number
            "cache_batch_size": None,          # not a number
            "fit_mode": "diagonal",            # not a known mode
            "border_color": "not-a-color",     # not a color
            "on_select_command": 42,           # not a string
        }))
        cfg = gladius.Config.load()
        self.assertEqual(cfg.number_of_pictures, 7)
        self.assertEqual(cfg.dim_opacity, 0.7)
        self.assertEqual(cfg.cache_batch_size, 8)
        self.assertEqual(cfg.fit_mode, "fill")
        self.assertEqual(cfg.border_color, "#C27B63")
        self.assertIsNone(cfg.on_select_command)

    def test_numeric_strings_are_accepted(self):
        self.cfg_path.write_text(json.dumps({"number_of_pictures": "9",
                                             "dim_opacity": "0.4"}))
        cfg = gladius.Config.load()
        self.assertEqual(cfg.number_of_pictures, 9)
        self.assertAlmostEqual(cfg.dim_opacity, 0.4)

    def test_bool_like_values(self):
        self.cfg_path.write_text(json.dumps({"shear": "off", "recursive": "yes"}))
        cfg = gladius.Config.load()
        self.assertIs(cfg.shear, False)
        self.assertIs(cfg.recursive, True)

    def test_named_and_short_hex_colors_are_kept(self):
        """Anything Qt can parse survives — not just the #RRGGBB the pane cycles."""
        for value in ("steelblue", "#fff"):
            self.cfg_path.write_text(json.dumps({"border_color": value}))
            self.assertEqual(gladius.Config.load().border_color, value)

    def test_cache_batch_size_clamped(self):
        self.cfg_path.write_text(json.dumps({"cache_batch_size": 9999}))
        self.assertLessEqual(gladius.Config.load().cache_batch_size, 64)
        self.cfg_path.write_text(json.dumps({"cache_batch_size": 0}))
        self.assertGreaterEqual(gladius.Config.load().cache_batch_size, 1)


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

    def test_key_varies_with_thumb_height(self):
        """A bigger display gets its own cache entries instead of upscaling."""
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "w.jpg"
            f.write_bytes(b"one")
            self.assertNotEqual(gladius.thumb_key(f, 500), gladius.thumb_key(f, 1000))

    def test_missing_file_does_not_raise(self):
        """A file deleted between scan and cache build must not kill startup."""
        key = gladius.thumb_key(Path(r"C:\gone\missing.jpg"))
        self.assertTrue(key.endswith(".jpg"))


class EnvFallbackTests(unittest.TestCase):
    def test_app_dir_falls_back_when_env_missing(self):
        self.assertEqual(gladius._app_dir("GLADIUS_NO_SUCH_VAR", "Roaming"),
                         Path.home() / "AppData" / "Roaming")

    def test_app_dir_uses_env_when_present(self):
        with mock.patch.dict("os.environ", {"GLADIUS_TEST_VAR": r"D:\somewhere"}):
            self.assertEqual(gladius._app_dir("GLADIUS_TEST_VAR", "Roaming"),
                             Path(r"D:\somewhere"))


class SetterLogicTests(unittest.TestCase):
    def test_fit_mode_pairs(self):
        self.assertEqual(gladius.FIT_MODES["fill"], ("10", "0"))
        self.assertEqual(gladius.FIT_MODES["tile"], ("0", "1"))
        self.assertEqual(len(gladius.FIT_MODES), 6)

    def test_build_select_command(self):
        cmd = gladius.build_select_command(
            'wal -i "{path}"', Path(r"C:\pics\a b.jpg"))
        self.assertEqual(cmd, f'wal -i "{Path(r"C:/pics/a b.jpg").resolve()}"')

    def test_direct_exts_exclude_webp(self):
        self.assertNotIn(".webp", gladius.DIRECT_EXTS)
        self.assertIn(".jfif", gladius.DIRECT_EXTS)

    def test_spi_set_resolves_the_path(self):
        """Explorer reads the file from outside this process, so the path handed
        to Windows must be the real one even under MSIX redirection."""
        sent = []
        fake = mock.Mock(return_value=1)
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "current.png"
            target.write_bytes(b"x")
            with mock.patch.object(gladius.ctypes, "windll") as windll:
                windll.user32.SystemParametersInfoW = \
                    lambda *a: sent.append(a[2]) or 1
                gladius._spi_set(target)
        self.assertEqual(sent, [str(target.resolve())])
        del fake

    def test_set_wallpaper_transcodes_non_direct(self):
        calls = []
        with mock.patch.object(gladius, "_apply_fit_mode"), \
             mock.patch.object(gladius, "_spi_set",
                               side_effect=lambda p: calls.append(p) or True), \
             mock.patch.object(gladius, "_transcode_to_png",
                               return_value=Path("C:/fake/current.png")) as tr:
            ok = gladius.set_wallpaper(Path("C:/pics/x.webp"), "fill")
        self.assertTrue(ok)
        tr.assert_called_once()
        self.assertEqual(calls, [Path("C:/fake/current.png")])


class RandomPickTests(unittest.TestCase):
    def test_avoids_current_when_possible(self):
        a, b = Path(r"C:\w\a.jpg"), Path(r"C:\w\b.jpg")
        for _ in range(20):
            self.assertEqual(gladius.pick_random([a, b], str(a.resolve())), b)

    def test_single_file_still_returned(self):
        a = Path(r"C:\w\a.jpg")
        self.assertEqual(gladius.pick_random([a], str(a.resolve())), a)

    def test_empty_returns_none(self):
        self.assertIsNone(gladius.pick_random([], ""))


class VersionTests(unittest.TestCase):
    def test_parses_with_and_without_v_prefix(self):
        self.assertEqual(gladius.parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(gladius.parse_version("1.2.3"), (1, 2, 3))

    def test_short_and_long_forms(self):
        self.assertEqual(gladius.parse_version("2.0"), (2, 0))
        self.assertEqual(gladius.parse_version("1.2.3.4"), (1, 2, 3, 4))

    def test_garbage_parses_to_empty(self):
        """A tag we can't read must never be treated as a version."""
        for junk in ("", "latest", "v", "nightly-build", None):
            self.assertEqual(gladius.parse_version(junk), ())

    def test_is_newer_compares_numerically(self):
        self.assertTrue(gladius.is_newer("1.0.10", "1.0.9"))    # not string order
        self.assertTrue(gladius.is_newer("v1.1.0", "1.0.0"))
        self.assertFalse(gladius.is_newer("1.0.0", "1.0.0"))
        self.assertFalse(gladius.is_newer("0.9.0", "1.0.0"))

    def test_unequal_lengths(self):
        self.assertTrue(gladius.is_newer("1.1", "1.0.9"))
        self.assertFalse(gladius.is_newer("1.0", "1.0.0"))

    def test_unreadable_version_is_never_newer(self):
        """Fail closed: a garbage tag must not nag the user to 'upgrade'."""
        self.assertFalse(gladius.is_newer("garbage", "1.0.0"))
        self.assertFalse(gladius.is_newer("1.0.1", "garbage"))


class UpdateCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "update.json"
        p = mock.patch.object(gladius, "UPDATE_CACHE", self.path)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_missing_cache_reads_as_empty(self):
        self.assertEqual(gladius.read_update_cache(), {})

    def test_corrupt_cache_reads_as_empty(self):
        self.path.write_text("{not json")
        self.assertEqual(gladius.read_update_cache(), {})

    def test_round_trip(self):
        gladius.write_update_cache({"latest": "1.2.0", "checked_at": 100.0})
        self.assertEqual(gladius.read_update_cache()["latest"], "1.2.0")

    def test_unwritable_cache_does_not_raise(self):
        """The cache is a nicety; losing it must never break a launch."""
        with mock.patch.object(Path, "write_text", side_effect=OSError):
            gladius.write_update_cache({"latest": "1.2.0"})

    def test_should_check_when_never_checked(self):
        self.assertTrue(gladius.should_check({}, now=1000.0))

    def test_should_not_check_inside_the_interval(self):
        cache = {"checked_at": 1000.0}
        self.assertFalse(gladius.should_check(cache, now=1000.0 + 60))

    def test_should_check_after_the_interval(self):
        cache = {"checked_at": 1000.0}
        self.assertTrue(
            gladius.should_check(cache, now=1000.0 + gladius.UPDATE_INTERVAL + 1))

    def test_clock_moved_backwards_still_checks(self):
        """A stale future timestamp must not wedge the check off forever."""
        self.assertTrue(gladius.should_check({"checked_at": 9e12}, now=1000.0))

    def test_pending_update_only_when_newer(self):
        gladius.write_update_cache({"latest": "0.1.0", "checked_at": 1.0})
        self.assertIsNone(gladius.pending_update(current="1.0.0"))
        gladius.write_update_cache({"latest": "9.9.9", "checked_at": 1.0})
        self.assertEqual(gladius.pending_update(current="1.0.0"), "9.9.9")


class UpgradeCommandTests(unittest.TestCase):
    def test_scoop_install_gets_scoop_command(self):
        p = r"C:\Users\x\scoop\apps\gladius\current\gladius.exe"
        self.assertIn("scoop update", gladius.upgrade_command(p))

    def test_winget_install_gets_winget_command(self):
        p = r"C:\Users\x\AppData\Local\Microsoft\WinGet\Packages\BrianZodd.Gladius_x\gladius.exe"
        self.assertIn("winget upgrade", gladius.upgrade_command(p))

    def test_unknown_location_points_at_releases(self):
        self.assertIn("github.com", gladius.upgrade_command(r"D:\tools\gladius.exe"))

    def test_detection_is_case_insensitive(self):
        p = r"C:\Users\x\SCOOP\Apps\Gladius\current\gladius.exe"
        self.assertIn("scoop update", gladius.upgrade_command(p))


if __name__ == "__main__":
    unittest.main()
