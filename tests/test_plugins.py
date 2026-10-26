"""Consequential lifecycle and persistence boundaries without system mutations."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from wintools.core import Preferences
from wintools.host import PluginHost


class FakeClipboard(QObject):
    dataChanged = Signal()

    def __init__(self):
        super().__init__()
        self.value = ""

    def text(self):
        return self.value

    def mimeData(self):
        result = Mock()
        result.hasText.return_value = True
        result.formats.return_value = ["text/plain"]
        return result

    def setText(self, value):
        self.value = value
        self.dataChanged.emit()


class PluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "settings.json"
        self.prefs = Preferences(self.path)
        self.services = Mock()
        self.services.confirm.return_value = True
        self.host = PluginHost(self.prefs, self.services)

    def tearDown(self):
        self.host.shutdown()
        self.temp.cleanup()

    def test_install_panel_order_disable_and_remove_survive_restart(self):
        self.host.install("clipboard")
        panel = self.host.add_panel("工作")
        self.host.add_item(panel, "clipboard")
        self.host.add_item(panel, "awake")
        self.host.set_panel_order(panel, ["awake", "clipboard"])
        self.host.set_enabled("clipboard", False)
        self.assertNotIn("clipboard:clear", [row[0] for row in self.host.actions()])
        self.assertEqual(self.host.panel(panel)["items"], ["awake", "clipboard"])
        restored = Preferences(self.path)
        self.assertIn("clipboard", restored.installed)
        self.assertIn("clipboard", restored.disabled)
        self.assertEqual(restored.panels[-1]["items"], ["awake", "clipboard"])
        self.host.uninstall("clipboard")
        self.assertNotIn("clipboard", Preferences(self.path).installed)
        self.assertEqual(self.host.panel(panel)["items"], ["awake"])

    def test_failed_power_release_keeps_plugin_registered_and_enabled(self):
        self.services.system.release.side_effect = OSError("denied")
        with self.assertRaises(OSError):
            self.host.uninstall("awake")
        self.assertIn("awake", self.host.active_ids)
        self.assertIn("awake", self.prefs.installed)
        self.services.system.release.side_effect = None

    def test_disabled_action_and_stale_snapshot_are_rejected(self):
        self.host.set_enabled("processes", False)
        with self.assertRaises(ValueError):
            self.host.execute("processes:taskmgr")
        self.host.update({"processes": [(1, "stale", 100)]})
        self.assertIsNone(self.host.instances["processes"].snapshot)
        self.services.system.open_action.assert_not_called()

    def test_lock_confirmation_routes_through_host(self):
        self.services.confirm.return_value = False
        self.host.execute("lock:lock")
        self.services.system.open_action.assert_not_called()
        self.services.confirm.return_value = True
        self.host.execute("lock:lock")
        self.services.system.open_action.assert_called_once_with("lock")

    def test_clipboard_is_opt_in_and_disconnects_on_disable(self):
        clipboard = FakeClipboard()
        with patch("wintools.plugins.builtin.QApplication.clipboard", return_value=clipboard):
            self.host.install("clipboard")
            plugin = self.host.instances["clipboard"]
            clipboard.setText("not recorded")
            self.assertEqual(plugin.history, [])
            plugin.set_recording(True)
            for i in range(35):
                clipboard.setText(f"text {i}")
            self.assertEqual(len(plugin.history), 30)
            clipboard.setText("text 33")
            self.assertEqual(plugin.history[0], "text 33")
            self.host.set_enabled("clipboard", False)
            clipboard.setText("after disable")
            self.assertFalse(plugin.recording)
            self.assertEqual(plugin.history, [])
            self.host.set_enabled("clipboard", True)
            self.assertFalse(plugin.recording)

    def test_screenshot_save_and_deactivate_cancel(self):
        plugin = self.host.instances["screenshot"]
        screen = Mock()
        pixmap = QPixmap(20, 20)
        pixmap.fill()
        screen.grabWindow.return_value = pixmap
        path = Path(self.temp.name) / "capture.png"
        with patch("wintools.plugins.builtin.QApplication.primaryScreen", return_value=screen), \
             patch("wintools.plugins.builtin.QFileDialog.getSaveFileName", return_value=(str(path), "")):
            plugin.capture()
            plugin.timer.stop()
            plugin._capture()
        self.assertTrue(path.read_bytes().startswith(b"\x89PNG"))
        self.assertFalse(plugin.busy)
        plugin.capture()
        self.host.set_enabled("screenshot", False)
        self.assertFalse(plugin.timer.isActive())
        self.assertFalse(plugin.busy)

    def test_version_one_migration_retains_existing_preferences(self):
        self.path.write_text(json.dumps({"version": 1, "disabled": ["system"], "close_to_tray": False}))
        restored = Preferences(self.path)
        self.assertIn("system", restored.disabled)
        self.assertFalse(restored.close_to_tray)
        self.assertEqual(restored.panels[0]["id"], "dashboard")
        restored.save()
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["version"], 2)

    def test_malformed_panel_does_not_partially_apply_preferences(self):
        self.path.write_text(json.dumps({"version": 2, "installed": [], "panels": [{"id": "x", "title": ""}]}))
        restored = Preferences(self.path)
        self.assertTrue(restored.warning)
        self.assertTrue(restored.installed)
        self.assertEqual(restored.panels[0]["id"], "dashboard")
