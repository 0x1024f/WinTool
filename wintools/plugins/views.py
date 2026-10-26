"""Plugin-owned views. All action execution still passes through the host."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QProgressBar,
    QCheckBox, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QListWidget, QListWidgetItem, QLayout, QSizePolicy,
)
from ..core import format_bytes
from ..ui import label, button, card, Toggle


class PluginView(QWidget):
    def __init__(self, plugin, compact):
        super().__init__()
        self.plugin, self.compact = plugin, compact
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(12)
        self.box.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    def execute(self, action):
        self.plugin.services.run(f"{self.plugin.manifest.id}:{action}")


class SystemView(PluginView):
    def __init__(self, plugin, compact):
        super().__init__(plugin, compact)
        grid = QGridLayout()
        grid.setSpacing(9)
        self.metrics = {}
        for index, (key, title, color) in enumerate([
            ("cpu", "CPU", "#64cd87"), ("memory", "内存", "#e4c45a"),
            ("disk", "系统盘", "#63acfa"), ("down", "网络下载", "#38cad6"),
        ]):
            frame, layout = card(True)
            layout.addWidget(label(title, "muted"))
            value = label("—", "metric")
            layout.addWidget(value)
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; }}")
            layout.addWidget(bar)
            detail = label("等待采样", "muted")
            layout.addWidget(detail)
            grid.addWidget(frame, index // 2, index % 2)
            self.metrics[key] = value, detail, bar
        self.box.addLayout(grid)
        self.footer = label("每 2 秒刷新", "muted")
        self.box.addWidget(self.footer)
        plugin.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        data = self.plugin.snapshot
        if not data:
            return
        for key in ("cpu", "memory", "disk"):
            self.metrics[key][0].setText(f"{data[key]:.1f}%")
            self.metrics[key][2].setValue(round(data[key]))
        self.metrics["cpu"][1].setText("当前处理器使用率")
        self.metrics["memory"][1].setText(f"{format_bytes(data['memory_used'])} / {format_bytes(data['memory_total'])}")
        self.metrics["disk"][1].setText(f"可用 {format_bytes(data['disk_free'])}")
        self.metrics["down"][0].setText(f"{format_bytes(data['down'])}/s")
        self.metrics["down"][1].setText(f"↑ {format_bytes(data['up'])}/s")
        self.metrics["down"][2].hide()
        hours = int(data["uptime"] // 3600)
        battery = "无电池" if data["battery"] is None else f"电量 {data['battery']:.0f}%"
        self.footer.setText(f"运行 {hours // 24} 天 {hours % 24} 小时 · {battery}")


class DataView(PluginView):
    def __init__(self, plugin, compact, kind):
        super().__init__(plugin, compact)
        self.kind = kind
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索进程 / PID" if kind == "processes" else "搜索网卡 / IP")
        self.search.textChanged.connect(self.refresh)
        self.box.addWidget(self.search)
        columns = ["进程", "PID", "内存"] if kind == "processes" else ["网卡", "状态", "IP 地址", "Mbps"]
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(190 if compact else 360)
        if compact:
            self.table.setMaximumHeight(240)
        self.box.addWidget(self.table)
        for action in plugin.actions():
            self.box.addWidget(button(action.title + " ↗", lambda k=action.id: self.execute(k)))
        plugin.changed.connect(self.refresh)
        self.refresh()

    def refresh(self, *_):
        rows = self.plugin.snapshot or []
        if self.kind == "processes":
            rows = [(name, str(pid), format_bytes(memory)) for pid, name, memory in rows]
        query = self.search.text().casefold()
        rows = [row for row in rows if query in " ".join(map(str, row)).casefold()]
        if self.compact:
            rows = rows[:5]
        scroll = self.table.verticalScrollBar().value()
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                self.table.setItem(i, j, item)
        self.table.verticalScrollBar().setValue(scroll)


class AwakeView(PluginView):
    def __init__(self, plugin, compact):
        super().__init__(plugin, compact)
        self.enabled = Toggle("保持系统唤醒")
        self.display = Toggle("同时保持屏幕常亮")
        self.box.addWidget(self.enabled)
        self.box.addWidget(self.display)
        self.status = label("", "muted")
        self.box.addWidget(self.status)
        self.enabled.toggled.connect(self.apply)
        self.display.toggled.connect(self.apply)
        plugin.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        system = self.plugin.services.system
        for widget, value in ((self.enabled, system.awake), (self.display, system.display)):
            widget.blockSignals(True)
            widget.setChecked(value)
            widget.blockSignals(False)
        self.display.setEnabled(system.awake)
        self.status.setText("正在防止自动休眠" if system.awake else "跟随 Windows 电源策略")

    def apply(self, *_):
        try:
            self.plugin.set_state(self.enabled.isChecked(), self.display.isChecked())
        except (OSError, ValueError) as exc:
            self.plugin.services.error(str(exc))
            self.refresh()


class ActionsView(PluginView):
    def __init__(self, plugin, compact):
        super().__init__(plugin, compact)
        grid = QGridLayout()
        for index, action in enumerate(plugin.actions()):
            grid.addWidget(button(action.title, lambda key=action.id: self.execute(key)), index // 2, index % 2)
        self.box.addLayout(grid)
        if plugin.manifest.id == "shortcuts":
            self.box.addWidget(label("打开 Windows 官方设置页面", "muted"))


class ScreenshotView(PluginView):
    def __init__(self, plugin, compact):
        super().__init__(plugin, compact)
        self.screens = QComboBox()
        for screen in QApplication.screens():
            size = screen.size()
            self.screens.addItem(f"{screen.name()} · {size.width()} × {size.height()}", screen.name())
        self.box.addWidget(self.screens)
        row = QHBoxLayout()
        self.save = button("截图并保存", lambda: plugin.capture(self.screens.currentData()), True)
        self.copy = button("复制截图", lambda: plugin.capture(self.screens.currentData(), True))
        row.addWidget(self.save)
        row.addWidget(self.copy)
        self.box.addLayout(row)
        self.box.addWidget(label("自动隐藏 WinTools 后捕获所选显示器。", "muted"))
        plugin.changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.save.setEnabled(not self.plugin.busy)
        self.copy.setEnabled(not self.plugin.busy)


class ClipboardView(PluginView):
    def __init__(self, plugin, compact):
        super().__init__(plugin, compact)
        self.recording = Toggle("开始记录复制的文本")
        self.recording.toggled.connect(plugin.set_recording)
        self.box.addWidget(self.recording)
        self.box.addWidget(label("可能包含密码等敏感文本。仅保留最近 30 条，不写入磁盘；停用或退出即清空。", "muted"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索历史文本…")
        self.search.textChanged.connect(self.refresh)
        self.box.addWidget(self.search)
        self.items = QListWidget()
        self.items.setMinimumHeight(150 if compact else 250)
        self.items.itemActivated.connect(self.copy_item)
        self.box.addWidget(self.items)
        row = QHBoxLayout()
        row.addWidget(button("复制所选", self.copy_item))
        row.addWidget(button("清空历史", lambda: self.execute("clear")))
        self.box.addLayout(row)
        plugin.changed.connect(self.refresh)
        self.refresh()

    def refresh(self, *_):
        self.recording.blockSignals(True)
        self.recording.setChecked(self.plugin.recording)
        self.recording.blockSignals(False)
        self.items.clear()
        query = self.search.text().casefold()
        for text in self.plugin.history:
            if query in text.casefold():
                item = QListWidgetItem(text.replace("\n", " ")[:120])
                item.setData(Qt.ItemDataRole.UserRole, text)
                self.items.addItem(item)

    def copy_item(self, *_):
        item = self.items.currentItem()
        if item:
            text = item.data(Qt.ItemDataRole.UserRole)
            QApplication.clipboard().setText(text)
            self.plugin.services.notify("文本已复制")
