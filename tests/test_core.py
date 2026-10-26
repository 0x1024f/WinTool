import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from wintools.core import Preferences
from wintools.windows import WindowsSystem


class PreferencesTests(unittest.TestCase):
    def test_round_trip_and_unknown_plugins(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            prefs = Preferences(path)
            prefs.disabled = {"system", "unknown"}
            prefs.close_to_tray = False
            prefs.save()
            restored = Preferences(path)
            self.assertEqual(restored.disabled, {"system"})
            self.assertFalse(restored.close_to_tray)

    def test_invalid_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            for text in ('{"disabled": "system"}', '[]', '{broken'):
                path.write_text(text)
                prefs = Preferences(path)
                self.assertTrue(prefs.warning)
                self.assertEqual(path.read_text(), text)

    def test_failed_replace_preserves_previous_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            prefs = Preferences(path)
            prefs.save()
            original = path.read_bytes()
            prefs.disabled = {"system"}
            with patch("wintools.core.os.replace", side_effect=PermissionError):
                with self.assertRaises(PermissionError):
                    prefs.save()
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])


class PowerTests(unittest.TestCase):
    def test_release_clears_awake_request(self):
        system = WindowsSystem()
        system.kernel = Mock()
        system.kernel.SetThreadExecutionState.return_value = 1
        system.keep_awake(True, True)
        self.assertTrue(system.awake)
        system.release()
        self.assertFalse(system.awake)
        self.assertFalse(system.display)
        system.kernel.SetThreadExecutionState.assert_called_with(0x80000000)

    def test_failure_does_not_claim_state_changed(self):
        system = WindowsSystem()
        system.kernel = Mock()
        system.kernel.SetThreadExecutionState.return_value = 0
        with self.assertRaises(OSError):
            system.keep_awake(True)
        self.assertFalse(system.awake)

    def test_unknown_action_is_rejected(self):
        with self.assertRaises(ValueError):
            WindowsSystem().open_action("arbitrary command")


if __name__ == "__main__":
    unittest.main()
