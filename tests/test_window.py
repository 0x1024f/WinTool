"""Exercise the plugin-to-sidebar-to-panel flow through Qt controls."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton, QLineEdit, QDialog, QListWidget
from PySide6.QtTest import QTest

from wintools.app import Window
from wintools.core import Preferences
from wintools.ui import STYLE, dark_palette


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setPalette(dark_palette())
        cls.app.setStyleSheet(STYLE)

    def test_add_component_and_remove_plugin_from_ui(self):
        with tempfile.TemporaryDirectory() as directory:
            window = Window(Preferences(Path(directory) / "prefs.json"), smoke=True)
            window.show()
            try:
                QTest.qWait(30)
                window.market_search.setText("剪贴板")
                row = window.market_rows["clipboard"]
                next(b for b in row.findChildren(QPushButton) if b.text() == "添加").click()
                self.assertIn("plugin:clipboard", window.nav_items)
                window.selected_panel = "controls"
                window.navigate("panels")
                errors = []

                def add_from_library():
                    dialog = QApplication.activeModalWidget()
                    try:
                        self.assertIsInstance(dialog, QDialog)
                        dialog.findChild(QLineEdit).setText("剪贴板")
                        self.app.processEvents()
                        next(b for b in dialog.findChildren(QPushButton) if b.text().startswith("添加到") and not b.isHidden()).click()
                    except Exception as exc:
                        errors.append(exc)
                        if dialog:
                            dialog.reject()

                QTimer.singleShot(100, add_from_library)
                window.component_library()
                if errors:
                    raise errors[0]
                self.assertIn("clipboard", window.host.panel("controls")["items"])

                def reorder():
                    dialog = QApplication.activeModalWidget()
                    try:
                        items = dialog.findChild(QListWidget)
                        item = items.takeItem(items.count() - 1)
                        items.insertItem(0, item)
                        next(b for b in dialog.findChildren(QPushButton) if b.text() == "保存顺序").click()
                    except Exception as exc:
                        errors.append(exc)
                        dialog.reject()

                QTimer.singleShot(100, reorder)
                window.edit_order()
                if errors:
                    raise errors[0]
                restored = Preferences(window.prefs.path)
                self.assertEqual(restored.panels[1]["items"][0], "clipboard")
                window.navigate("plugin:clipboard")
                with patch.object(window.services, "confirm", return_value=True):
                    next(b for b in window.scroll.widget().findChildren(QPushButton) if b.text() == "移除").click()
                self.assertEqual(window.destination, "marketplace")
                self.assertNotIn("plugin:clipboard", window.nav_items)
                self.assertNotIn("clipboard", window.host.panel("controls")["items"])
            finally:
                window.quit_app()
                self.app.processEvents()
