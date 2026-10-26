"""Built-in plugins own their behavior and stop it on deactivation."""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog
from .base import Action, Plugin


class SystemPlugin(Plugin):
    def create_view(self, compact=False):
        from .views import SystemView
        return SystemView(self, compact)


class ProcessesPlugin(Plugin):
    def actions(self):
        return [Action("taskmgr", "打开任务管理器", lambda: self.services.system.open_action("taskmgr"))]

    def create_view(self, compact=False):
        from .views import DataView
        return DataView(self, compact, "processes")


class NetworkPlugin(Plugin):
    def actions(self):
        return [Action("settings", "打开网络设置", lambda: self.services.system.open_action("network"))]

    def create_view(self, compact=False):
        from .views import DataView
        return DataView(self, compact, "network")


class AwakePlugin(Plugin):
    def set_state(self, enabled, display=False):
        if not self.active:
            raise ValueError("插件未启用")
        self.services.system.keep_awake(enabled, display)
        self.changed.emit()

    def deactivate(self):
        self.services.system.release()
        super().deactivate()

    def actions(self):
        return [Action("toggle", "切换防止休眠", lambda: self.set_state(not self.services.system.awake))]

    def create_view(self, compact=False):
        from .views import AwakeView
        return AwakeView(self, compact)


SETTINGS_ACTIONS = (
    ("display", "显示设置"), ("sound", "声音设置"), ("network", "网络设置"),
    ("startup", "启动应用"), ("storage", "存储管理"), ("apps", "应用管理"),
    ("power", "电源设置"), ("update", "Windows 更新"),
)


class ShortcutsPlugin(Plugin):
    def actions(self):
        return [Action(key, title, lambda k=key: self.services.system.open_action(k)) for key, title in SETTINGS_ACTIONS]

    def create_view(self, compact=False):
        from .views import ActionsView
        return ActionsView(self, compact)


class LockPlugin(Plugin):
    def actions(self):
        return [Action("lock", "锁定电脑", lambda: self.services.system.open_action("lock"), "现在锁定 Windows？")]

    def create_view(self, compact=False):
        from .views import ActionsView
        return ActionsView(self, compact)


class ScreenshotPlugin(Plugin):
    def __init__(self, manifest, services):
        super().__init__(manifest, services)
        self.busy = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._capture)
        self.was_visible = False
        self.screen_name = ""
        self.to_clipboard = False

    def capture(self, screen_name="", to_clipboard=False):
        if not self.active or self.busy:
            return
        self.busy = True
        self.screen_name, self.to_clipboard = screen_name, to_clipboard
        self.was_visible = self.services.window.isVisible()
        self.services.window.hide()
        self.changed.emit()
        self.timer.start(450)

    def _restore(self):
        if self.was_visible:
            self.services.window.show_window()
        self.busy = False
        self.changed.emit()

    def _capture(self):
        try:
            if not self.active:
                return
            screens = QApplication.screens()
            screen = next((s for s in screens if s.name() == self.screen_name), None) if self.screen_name else QApplication.primaryScreen()
            if screen is None:
                raise OSError("所选显示器已断开，请重新选择。")
            pixmap = screen.grabWindow(0)
            if pixmap.isNull():
                raise OSError("无法获取屏幕图像。")
            self._restore()
            if self.to_clipboard:
                QApplication.clipboard().setPixmap(pixmap)
                self.services.notify("截图已复制到剪贴板")
            else:
                path, _ = QFileDialog.getSaveFileName(self.services.window, "保存截图", "截图.png", "PNG 图像 (*.png)")
                if path:
                    if not path.lower().endswith(".png"):
                        path += ".png"
                    if not pixmap.save(path, "PNG"):
                        raise OSError("截图保存失败，请检查文件路径。")
                    self.services.notify("截图已保存")
        except (OSError, RuntimeError) as exc:
            self.services.error(str(exc))
        finally:
            if self.busy:
                self._restore()

    def deactivate(self):
        self.timer.stop()
        if self.busy:
            self._restore()
        super().deactivate()

    def actions(self):
        return [Action("save", "截图并保存", self.capture),
                Action("copy", "截图到剪贴板", lambda: self.capture(to_clipboard=True))]

    def create_view(self, compact=False):
        from .views import ScreenshotView
        return ScreenshotView(self, compact)


class ClipboardPlugin(Plugin):
    def __init__(self, manifest, services):
        super().__init__(manifest, services)
        self.recording = False
        self.history = []

    def set_recording(self, enabled):
        if enabled == self.recording:
            return
        if enabled:
            if not self.active:
                raise ValueError("插件未启用")
            QApplication.clipboard().dataChanged.connect(self.record)
        else:
            QApplication.clipboard().dataChanged.disconnect(self.record)
        self.recording = enabled
        self.changed.emit()

    def record(self):
        if not self.active or not self.recording:
            return
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime is None or not mime.hasText():
            return
        if any("ExcludeClipboardContentFromMonitorProcessing" in fmt for fmt in mime.formats()):
            return
        text = clipboard.text()
        if not text.strip() or len(text) > 20000:
            return
        self.history = [text] + [item for item in self.history if item != text]
        del self.history[30:]
        self.changed.emit()

    def clear(self):
        self.history.clear()
        self.changed.emit()

    def deactivate(self):
        self.set_recording(False)
        self.clear()
        super().deactivate()

    def actions(self):
        return [Action("clear", "清空剪贴板历史", self.clear, "清空 WinTools 内存中的文本历史？系统剪贴板不会改变。")]

    def create_view(self, compact=False):
        from .views import ClipboardView
        return ClipboardView(self, compact)


FACTORIES = {
    "system": SystemPlugin, "processes": ProcessesPlugin, "network": NetworkPlugin,
    "awake": AwakePlugin, "shortcuts": ShortcutsPlugin, "screenshot": ScreenshotPlugin,
    "clipboard": ClipboardPlugin, "lock": LockPlugin,
}
