"""Qt desktop host, tray, built-in panels and searchable actions."""
import argparse
import os
from pathlib import Path
import platform
import sys

from PySide6.QtCore import Qt, QTimer, QStandardPaths
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QMainWindow, QMenu,
    QMessageBox, QPushButton, QProgressBar, QStackedWidget, QSystemTrayIcon,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .core import PLUGINS, Preferences, format_bytes
from .monitor import Monitor
from .windows import WindowsSystem


ACTIONS = (
    ("display", "显示设置", "分辨率 · 缩放 · 多显示器"),
    ("sound", "声音设置", "输出设备 · 麦克风 · 音量"),
    ("network", "网络设置", "Wi-Fi · 以太网 · 代理"),
    ("startup", "启动应用", "管理开机启动项目"),
    ("storage", "存储管理", "磁盘空间 · 临时文件"),
    ("apps", "应用管理", "查看和卸载已安装应用"),
    ("power", "电源设置", "屏幕关闭 · 睡眠时间"),
    ("update", "Windows 更新", "查看更新与系统版本"),
    ("taskmgr", "任务管理器", "进程 · 性能 · 服务"),
    ("lock", "锁定电脑", "立即返回 Windows 锁屏"),
)

STYLE = """
QWidget { font-family: 'Segoe UI', 'Microsoft YaHei UI'; font-size: 14px; color: #dce4f2; }
QMainWindow, QDialog { background: #10151e; }
QWidget#sidebar { background: #151c28; border-right: 1px solid #293345; }
QLabel#brand { font-size: 25px; font-weight: 700; color: #f4f7ff; }
QLabel#title { font-size: 28px; font-weight: 700; }
QLabel#muted { color: #92a1b7; }
QLabel#metric { font-size: 30px; font-weight: 600; color: #f2f6ff; }
QFrame#card { background: #1b2432; border: 1px solid #2b374a; border-radius: 12px; }
QPushButton { background: #243249; border: 1px solid #34445e; border-radius: 7px; padding: 10px 14px; text-align: left; }
QPushButton:hover { background: #304360; border-color: #6d9df7; }
QPushButton:checked { background: #29456d; color: #afceff; border-color: #5287d4; }
QPushButton:disabled { color: #647083; background: #1a2130; }
QLineEdit { background: #192230; border: 1px solid #34445e; border-radius: 7px; padding: 11px; }
QLineEdit:focus { border-color: #74a8ff; }
QProgressBar { background: #303e52; border: none; border-radius: 3px; max-height: 6px; }
QProgressBar::chunk { background: #75a5ff; border-radius: 3px; }
QTableWidget, QListWidget { background: #18212e; alternate-background-color: #1c2736; border: 1px solid #2b374a; border-radius: 6px; gridline-color: #293447; }
QHeaderView::section { background: #223047; padding: 10px; border: none; text-align: left; }
QTableWidget::item, QListWidget::item { padding: 8px; }
QListWidget::item:selected { background: #345581; }
QCheckBox { spacing: 10px; padding: 8px 0; }
QCheckBox::indicator { width: 18px; height: 18px; }
QMenu { background: #1b2432; border: 1px solid #34445e; }
QMenu::item { padding: 8px 24px; }
QMenu::item:selected { background: #345581; }
QStatusBar { color: #92a1b7; background: #151c28; }
"""


def label(text, role=None):
    item = QLabel(text)
    if role:
        item.setObjectName(role)
    item.setWordWrap(True)
    return item


def icon():
    image = QPixmap(64, 64)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#649bff"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, 60, 60, 15, 15)
    painter.setPen(QColor("#10151e"))
    font = painter.font()
    font.setPixelSize(36)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, "W")
    painter.end()
    return QIcon(image)


class Window(QMainWindow):
    def __init__(self, prefs, smoke=False):
        super().__init__()
        self.prefs = prefs
        self.system = WindowsSystem()
        self.smoke = smoke
        self.exiting = False
        self.has_snapshot = False
        self.processes = []
        self.pages = {}
        self.nav_buttons = {}
        self.setWindowTitle("WinTools · Windows 工具箱")
        self.setWindowIcon(icon())
        self.resize(1120, 760)
        self.setMinimumSize(920, 650)
        host = QWidget()
        self.setCentralWidget(host)
        root = QHBoxLayout(host)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(212)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(20, 28, 20, 22)
        nav.setSpacing(12)
        nav.addWidget(label("WinTools", "brand"))
        nav.addWidget(label("你的 Windows 工具箱", "muted"))
        nav.addSpacing(28)
        self.stack = QStackedWidget()
        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)
        for key, title in [(p.id, p.title) for p in PLUGINS] + [("plugins", "插件管理"), ("settings", "偏好设置")]:
            button = QPushButton(title)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, k=key: self.navigate(k))
            nav.addWidget(button)
            self.nav_buttons[key] = button
        nav.addStretch()
        search = QPushButton("搜索操作    Ctrl+K")
        search.clicked.connect(self.command_palette)
        nav.addWidget(search)
        nav.addWidget(label("LOCAL FIRST  /  v0.1", "muted"))
        self.build_dashboard()
        self.build_processes()
        self.build_network()
        self.build_awake()
        self.build_actions()
        self.build_plugins()
        self.build_settings()
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("WinTools · Windows 工具箱")
        menu = QMenu(self)
        menu.addAction("打开 WinTools", self.show_window)
        menu.addAction("搜索操作", self.command_palette)
        menu.addSeparator()
        menu.addAction("退出", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        if not smoke and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.shortcut.activated.connect(self.command_palette)
        self.monitor = Monitor(self)
        self.monitor.snapshot.connect(self.update_snapshot)
        self.monitor.failed.connect(lambda error: self.statusBar().showMessage(f"采样失败：{error}"))
        self.apply_plugins()
        self.navigate("system" if "system" not in prefs.disabled else "plugins")
        self.monitor.start()
        self.statusBar().showMessage(prefs.warning or "本地运行 · 每 2 秒刷新 · Ctrl+K 搜索操作")

    def page(self, key, title, description):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(18)
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(description, "muted"))
        self.pages[key] = widget
        self.stack.addWidget(widget)
        return layout

    def build_dashboard(self):
        layout = self.page("system", "系统概览", f"{platform.node()}  /  Windows {platform.release()}  ·  实时设备状态")
        grid = QGridLayout()
        grid.setSpacing(18)
        self.metrics = {}
        for index, (key, title) in enumerate((("cpu", "CPU 使用率"), ("memory", "内存使用率"), ("disk", "系统盘使用率"), ("network", "网络下载速率"))):
            card = QFrame()
            card.setObjectName("card")
            box = QVBoxLayout(card)
            box.setContentsMargins(22, 22, 22, 22)
            box.setSpacing(16)
            box.addWidget(label(title, "muted"))
            value, detail = label("—", "metric"), label("正在获取数据…", "muted")
            bar = QProgressBar()
            bar.setTextVisible(False)
            box.addWidget(value)
            box.addWidget(bar)
            box.addWidget(detail)
            if key == "network":
                bar.hide()
            grid.addWidget(card, index // 2, index % 2)
            self.metrics[key] = (value, detail, bar)
        layout.addLayout(grid)
        self.device_info = label("正在读取运行时间…", "muted")
        layout.addWidget(self.device_info)
        layout.addStretch()
        layout.addWidget(label("工作更专注，常用工具触手可及。", "muted"))

    def table(self, columns):
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().hide()
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        return table

    def build_processes(self):
        layout = self.page("processes", "进程查看", "按内存占用排序。系统保护进程可能无法读取。")
        self.process_filter = QLineEdit()
        self.process_filter.setPlaceholderText("搜索进程名称或 PID…")
        self.process_filter.textChanged.connect(self.render_processes)
        layout.addWidget(self.process_filter)
        self.process_table = self.table(["进程名称", "PID", "内存占用"])
        layout.addWidget(self.process_table)
        button = QPushButton("在任务管理器中管理进程 ↗")
        button.clicked.connect(lambda: self.run_action("taskmgr"))
        layout.addWidget(button)

    def build_network(self):
        layout = self.page("network", "网络信息", "本机网卡地址与链路状态；链路速率不代表互联网测速。")
        self.network_table = self.table(["网卡", "状态", "IP 地址", "链路 Mbps"])
        layout.addWidget(self.network_table)

    def build_awake(self):
        layout = self.page("awake", "防止休眠", "适合下载、演示和长时间任务。退出 WinTools 后恢复系统休眠策略。")
        self.awake_check = QCheckBox("保持系统唤醒")
        self.display_check = QCheckBox("同时保持屏幕常亮")
        self.display_check.setEnabled(False)
        self.awake_check.toggled.connect(self.change_awake)
        self.display_check.toggled.connect(self.change_awake)
        layout.addWidget(self.awake_check)
        layout.addWidget(self.display_check)
        self.awake_status = label("当前使用 Windows 默认休眠策略", "muted")
        layout.addWidget(self.awake_status)
        layout.addWidget(label("不会阻止手动睡眠、关机或合盖策略；不修改电源计划。", "muted"))
        layout.addStretch()

    def build_actions(self):
        layout = self.page("shortcuts", "快捷操作", "直达 Windows 系统设置，常用操作集中管理。")
        grid = QGridLayout()
        for index, (key, title, description) in enumerate(ACTIONS):
            button = QPushButton(f"{title}  ↗\n{description}")
            button.setMinimumHeight(76)
            button.clicked.connect(lambda checked=False, k=key: self.run_action(k))
            grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(grid)
        layout.addStretch()

    def build_plugins(self):
        layout = self.page("plugins", "插件管理", "第一版提供 5 个内置模块。关闭模块会停止其数据采样或释放其状态。")
        self.plugin_checks = {}
        for plugin in PLUGINS:
            card = QFrame()
            card.setObjectName("card")
            row = QHBoxLayout(card)
            text = QVBoxLayout()
            text.addWidget(label(f"{plugin.title}  /  {plugin.category}"))
            text.addWidget(label(plugin.description, "muted"))
            row.addLayout(text, 1)
            check = QCheckBox("启用")
            check.setChecked(plugin.id not in self.prefs.disabled)
            check.toggled.connect(lambda checked, key=plugin.id: self.toggle_plugin(key, checked))
            self.plugin_checks[plugin.id] = check
            row.addWidget(check)
            layout.addWidget(card)
        layout.addStretch()

    def build_settings(self):
        layout = self.page("settings", "偏好设置", "配置保存在当前 Windows 用户的本地应用数据目录。")
        check = QCheckBox("关闭窗口时最小化到系统托盘")
        check.setChecked(self.prefs.close_to_tray)
        check.toggled.connect(self.change_close_behavior)
        layout.addWidget(check)
        layout.addWidget(label("托盘不可用时，关闭窗口会正常退出。通过托盘菜单可完全退出。", "muted"))
        layout.addWidget(label(str(self.prefs.path), "muted"))
        layout.addSpacing(20)
        layout.addWidget(label("关于 WinTools"))
        layout.addWidget(label("Python + Qt · 参考 MacTools 的模块化工具箱设计\n当前为 0.1 首版，不包含在线插件市场与自动更新。", "muted"))
        layout.addStretch()

    def change_close_behavior(self, checked):
        self.prefs.close_to_tray = checked
        self.save_preferences()

    def save_preferences(self):
        try:
            self.prefs.save()
        except OSError as exc:
            QMessageBox.warning(self, "配置未保存", f"本次设置已生效，但无法保存：{exc}")

    def toggle_plugin(self, key, checked):
        if not checked and key == "awake":
            try:
                self.system.release()
            except OSError as exc:
                self.plugin_checks[key].blockSignals(True)
                self.plugin_checks[key].setChecked(True)
                self.plugin_checks[key].blockSignals(False)
                QMessageBox.warning(self, "无法停用", str(exc))
                return
            self.awake_check.setChecked(False)
        if checked:
            self.prefs.disabled.discard(key)
        else:
            self.prefs.disabled.add(key)
        self.apply_plugins()
        self.save_preferences()

    def apply_plugins(self):
        self.monitor.enabled = frozenset(p.id for p in PLUGINS if p.id not in self.prefs.disabled)
        for plugin in PLUGINS:
            self.nav_buttons[plugin.id].setEnabled(plugin.id not in self.prefs.disabled)

    def navigate(self, key):
        if key in self.prefs.disabled:
            return
        self.stack.setCurrentWidget(self.pages[key])
        for name, button in self.nav_buttons.items():
            button.setChecked(name == key)

    def change_awake(self, *_):
        try:
            self.system.keep_awake(self.awake_check.isChecked(), self.display_check.isChecked())
        except OSError as exc:
            self.awake_check.blockSignals(True)
            self.display_check.blockSignals(True)
            self.awake_check.setChecked(self.system.awake)
            self.display_check.setChecked(self.system.display)
            self.awake_check.blockSignals(False)
            self.display_check.blockSignals(False)
            QMessageBox.warning(self, "操作失败", str(exc))
        self.display_check.setEnabled(self.system.awake)
        self.awake_status.setText("防休眠已启用" if self.system.awake else "当前使用 Windows 默认休眠策略")

    def run_action(self, key):
        if key == "lock" and QMessageBox.question(self, "锁定电脑", "现在锁定 Windows？") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.system.open_action(key)
            self.statusBar().showMessage("操作已发送给 Windows", 5000)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "操作失败", str(exc))

    def command_palette(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("搜索操作 · Ctrl+K")
        dialog.resize(560, 430)
        layout = QVBoxLayout(dialog)
        field = QLineEdit()
        field.setPlaceholderText("搜索功能、Windows 设置…")
        results = QListWidget()
        layout.addWidget(field)
        layout.addWidget(results)
        entries = [(title, lambda k=key: self.run_action(k)) for key, title, _ in ACTIONS] if "shortcuts" not in self.prefs.disabled else []
        entries += [(p.title, lambda k=p.id: self.navigate(k)) for p in PLUGINS if p.id not in self.prefs.disabled]
        entries += [("插件管理", lambda: self.navigate("plugins")), ("偏好设置", lambda: self.navigate("settings"))]
        filtered = []

        def refresh(query):
            filtered[:] = [(title, callback) for title, callback in entries if query.casefold() in title.casefold()]
            results.clear()
            results.addItems([title for title, _ in filtered])
            if filtered:
                results.setCurrentRow(0)

        def execute(*_):
            index = results.currentRow()
            if index >= 0:
                dialog.accept()
                filtered[index][1]()

        field.textChanged.connect(refresh)
        field.returnPressed.connect(execute)
        results.itemActivated.connect(execute)
        refresh("")
        field.setFocus()
        dialog.exec()

    def fill_table(self, table, rows):
        scroll = table.verticalScrollBar().value()
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                table.setItem(i, j, item)
        table.verticalScrollBar().setValue(scroll)

    def render_processes(self, *_):
        query = self.process_filter.text().casefold()
        rows = [(name, pid, format_bytes(memory)) for pid, name, memory in self.processes
                if query in name.casefold() or query in str(pid)]
        self.fill_table(self.process_table, rows)

    def update_snapshot(self, data):
        self.has_snapshot = True
        if "system" in data and "system" not in self.prefs.disabled:
            info = data["system"]
            for key in ("cpu", "memory", "disk"):
                value, detail, bar = self.metrics[key]
                value.setText(f"{info[key]:.1f}%")
                bar.setValue(round(info[key]))
            self.metrics["cpu"][1].setText(f"{os.cpu_count()} 个逻辑处理器")
            self.metrics["memory"][1].setText(f"{format_bytes(info['memory_used'])} / {format_bytes(info['memory_total'])}")
            self.metrics["disk"][1].setText(f"剩余 {format_bytes(info['disk_free'])}")
            self.metrics["network"][0].setText(f"{format_bytes(info['down'])}/s")
            self.metrics["network"][1].setText(f"上传 {format_bytes(info['up'])}/s · 所有网卡合计")
            hours = int(info["uptime"] // 3600)
            battery = "无电池 / 台式设备" if info["battery"] is None else f"电池 {info['battery']:.0f}%"
            self.device_info.setText(f"已运行 {hours // 24} 天 {hours % 24} 小时  ·  {battery}")
        if "processes" in data and "processes" not in self.prefs.disabled:
            self.processes = data["processes"]
            self.render_processes()
        if "network" in data and "network" not in self.prefs.disabled:
            self.fill_table(self.network_table, data["network"])

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if not self.exiting and self.prefs.close_to_tray and self.tray.isVisible():
            self.hide()
            event.ignore()
        else:
            self.shutdown()
            event.accept()

    def shutdown(self):
        self.monitor.requestInterruption()
        self.monitor.wait()
        try:
            self.system.release()
        finally:
            self.tray.hide()

    def quit_app(self):
        self.exiting = True
        self.close()


def main():
    parser = argparse.ArgumentParser(description="WinTools Windows utility dashboard")
    parser.add_argument("--smoke-test", action="store_true", help="Collect data, render panels and exit")
    parser.add_argument("--screenshot", type=Path, help="Screenshot output for smoke test")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("WinTools currently supports Windows only")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("WinTools")
    app.setOrganizationName("WinTools")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    config = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "settings.json"
    if args.smoke_test:
        config = Path("artifacts/smoke-settings.json")
    window = Window(Preferences(config), smoke=args.smoke_test)
    window.show()
    outcome = [0]
    if args.smoke_test:
        def finish():
            try:
                assert window.has_snapshot, "No monitoring snapshot received"
                assert window.process_table.rowCount() > 0, "Process list is empty"
                assert window.network_table.rowCount() > 0, "Network list is empty"
                for key in window.pages:
                    window.navigate(key)
                    app.processEvents()
                window.navigate("system")
                app.processEvents()
                if args.screenshot:
                    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                    assert window.grab().save(str(args.screenshot)), "Screenshot save failed"
                print("PASS: live metrics, processes, network and all seven panels")
            except Exception as exc:
                print(f"FAIL: {exc}", file=sys.stderr)
                outcome[0] = 1
            finally:
                window.quit_app()
        QTimer.singleShot(5000, finish)
    result = app.exec()
    return outcome[0] or result
