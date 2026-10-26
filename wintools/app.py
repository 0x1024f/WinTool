"""Plugin-first settings shell, component library and customizable panels."""
import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from PySide6.QtCore import Qt, QSize, QTimer, QStandardPaths
from PySide6.QtGui import QKeySequence, QShortcut, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QScrollArea, QComboBox, QCheckBox,
    QDialog, QListWidget, QListWidgetItem, QAbstractItemView, QMessageBox,
    QInputDialog, QMenu, QSystemTrayIcon, QSplitter, QLayout,
)
from .catalog import CATALOG, PLUGINS
from .core import Preferences
from .host import PluginHost
from .monitor import Monitor
from .windows import WindowsSystem
from .ui import STYLE, label, button, card, icon, plugin_heading, clear_layout, Toggle, dark_palette


class Services:
    def __init__(self, window):
        self.window = window
        self.system = WindowsSystem()

    def notify(self, message):
        self.window.statusBar().showMessage(message, 6000)

    def error(self, message):
        QMessageBox.warning(self.window, "操作未完成", message)

    def confirm(self, title, message):
        return QMessageBox.question(self.window, title, message) == QMessageBox.StandardButton.Yes

    def run(self, action_id):
        self.window.attempt(lambda: self.window.host.execute(action_id))


class Window(QMainWindow):
    def __init__(self, prefs, smoke=False):
        super().__init__()
        self.prefs, self.smoke = prefs, smoke
        self.exiting = False
        self.closed = False
        self.destination = "marketplace"
        self.selected_panel = prefs.panels[0]["id"]
        self.market_query = ""
        self.market_category = "全部"
        self.market_state = "全部状态"
        self.has_snapshot = False
        self.services = Services(self)
        self.host = PluginHost(prefs, self.services)
        self.setWindowTitle("WinTools")
        self.setWindowIcon(icon())
        self.resize(1180, 820)
        self.setMinimumSize(980, 660)
        splitter = QSplitter()
        self.setCentralWidget(splitter)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(330)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 22, 14, 14)
        side.setSpacing(12)
        side.addWidget(label("WinTools", "brand"))
        self.nav_search = QLineEdit()
        self.nav_search.setPlaceholderText("搜索设置与插件")
        self.nav_search.textChanged.connect(self.filter_sidebar)
        side.addWidget(self.nav_search)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(12)
        self.tree.setRootIsDecorated(False)
        self.tree.setIconSize(QSize(23, 23))
        self.tree.currentItemChanged.connect(self.sidebar_selected)
        self.tree.itemClicked.connect(self.sidebar_clicked)
        self.tree.itemCollapsed.connect(self.remember_groups)
        self.tree.itemExpanded.connect(self.remember_groups)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.sidebar_menu)
        side.addWidget(self.tree, 1)
        side.addWidget(button("搜索操作                 Ctrl+K", self.command_palette))
        self.sidebar_status = label("", "muted")
        side.addWidget(self.sidebar_status)
        splitter.addWidget(sidebar)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        splitter.addWidget(self.scroll)
        splitter.setSizes([248, 932])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("WinTools")
        self.tray.activated.connect(self.tray_activated)
        self.tray_menu = QMenu(self)
        self.tray.setContextMenu(self.tray_menu)
        if not smoke and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.shortcut.activated.connect(self.command_palette)
        self.monitor = Monitor(self)
        self.monitor.snapshot.connect(self.update_snapshot)
        self.monitor.failed.connect(lambda message: self.services.notify("采样失败：" + message))
        self.host.changed.connect(self.host_changed)
        self.host_changed()
        self.monitor.start()
        self.statusBar().showMessage(prefs.warning or "本地插件库 · 按需添加工具，自由组合面板")

    def attempt(self, callback):
        try:
            return callback()
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            self.services.error(str(exc))

    def host_changed(self):
        self.monitor.enabled = self.host.active_ids & {"system", "processes", "network"}
        if self.destination.startswith("plugin:") and self.destination[7:] not in self.host.instances:
            self.destination = "marketplace"
        if not any(p["id"] == self.selected_panel for p in self.prefs.panels):
            self.selected_panel = self.prefs.panels[0]["id"]
        self.build_sidebar()
        self.build_tray()
        self.render()

    def build_sidebar(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        self.nav_items = {}
        groups = [
            ("app", "WinTools", [("general", "通用", "⚙", "#a5a5ae"), ("permissions", "权限与隐私", "◇", "#66b6e8"), ("about", "关于", "ⓘ", "#a5a5ae")]),
            ("custom", "自定义", [("panels", "我的面板", "▦", "#a998f2"), ("marketplace", "插件库", "◈", "#ef66aa"), ("actions", "操作与快捷键", "⌘", "#dfac62")]),
            ("plugins", "插件设置", [("plugin:" + key, CATALOG[key].title + (" · 已停用" if key in self.prefs.disabled else ""), CATALOG[key].symbol, CATALOG[key].color)
                                       for key in self.prefs.sidebar_order if key in self.prefs.installed]),
        ]
        for group_id, title, entries in groups:
            parent = QTreeWidgetItem([("▸  " if group_id in self.prefs.collapsed else "▾  ") + title])
            parent.setData(0, Qt.ItemDataRole.UserRole + 2, title)
            parent.setData(0, Qt.ItemDataRole.UserRole + 1, group_id)
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            parent.setForeground(0, QColor("#99999f"))
            self.tree.addTopLevelItem(parent)
            for key, title, symbol, color in entries:
                item = QTreeWidgetItem([title])
                item.setIcon(0, icon(symbol, color))
                item.setData(0, Qt.ItemDataRole.UserRole, key)
                parent.addChild(item)
                self.nav_items[key] = item
                if key == self.destination:
                    self.tree.setCurrentItem(item)
            parent.setExpanded(group_id not in self.prefs.collapsed)
        self.tree.blockSignals(False)
        self.filter_sidebar(self.nav_search.text())
        self.sidebar_status.setText(f"{len(self.prefs.installed)} 个已添加 · {len(self.host.active_ids)} 个已启用")

    def filter_sidebar(self, query):
        query = query.strip().casefold()
        self.tree.blockSignals(True)
        for index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(index)
            visible = False
            for i in range(group.childCount()):
                item = group.child(i)
                match = query in item.text(0).casefold()
                item.setHidden(not match)
                visible |= match
            group.setHidden(not visible and bool(query))
            group_id = group.data(0, Qt.ItemDataRole.UserRole + 1)
            group.setExpanded(True if query else group_id not in self.prefs.collapsed)
        self.tree.blockSignals(False)

    def remember_groups(self, *_):
        if self.nav_search.text():
            return
        self.prefs.collapsed = {self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole + 1)
                                for i in range(self.tree.topLevelItemCount()) if not self.tree.topLevelItem(i).isExpanded()}
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            group.setText(0, ("▾  " if group.isExpanded() else "▸  ") + group.data(0, Qt.ItemDataRole.UserRole + 2))
        self.save_preferences()

    def sidebar_clicked(self, item, column):
        if item.data(0, Qt.ItemDataRole.UserRole + 1):
            item.setExpanded(not item.isExpanded())

    def sidebar_selected(self, item, previous):
        if item:
            key = item.data(0, Qt.ItemDataRole.UserRole)
            if key:
                self.navigate(key)

    def sidebar_menu(self, position):
        item = self.tree.itemAt(position)
        key = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if not key or not key.startswith("plugin:"):
            return
        plugin_id = key[7:]
        menu = QMenu(self)
        menu.addAction("上移", lambda: self.move_sidebar(plugin_id, -1))
        menu.addAction("下移", lambda: self.move_sidebar(plugin_id, 1))
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def move_sidebar(self, key, direction):
        visible = [p for p in self.prefs.sidebar_order if p in self.prefs.installed]
        index = visible.index(key)
        target = index + direction
        if 0 <= target < len(visible):
            other = visible[target]
            order = self.prefs.sidebar_order
            a, b = order.index(key), order.index(other)
            order[a], order[b] = order[b], order[a]
            self.host.persist()

    def navigate(self, destination):
        self.destination = destination
        item = self.nav_items.get(destination)
        if item:
            self.tree.blockSignals(True)
            self.tree.setCurrentItem(item)
            item.parent().setExpanded(True)
            self.tree.blockSignals(False)
        self.render()

    def page(self, title, description):
        old = self.scroll.takeWidget()
        if old:
            old.hide()
            old.deleteLater()
        widget = QWidget()
        widget.setObjectName("content")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 28, 30, 26)
        layout.setSpacing(18)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(description, "muted"))
        self.scroll.setWidget(widget)
        return layout

    def render(self):
        if self.destination.startswith("plugin:"):
            self.render_plugin(self.destination[7:])
        else:
            getattr(self, "render_" + self.destination)()

    def render_marketplace(self):
        box = self.page("插件库", "按需添加工具，在插件设置中配置，再将组件放入你的面板。")
        summary = QHBoxLayout()
        summary.addWidget(label(f"内置目录  {len(PLUGINS)}", "badge"))
        summary.addWidget(label("所有插件随应用提供，无需下载", "muted"), 1)
        box.addLayout(summary)
        self.market_search = QLineEdit()
        self.market_search.setPlaceholderText("搜索插件名称或简介")
        self.market_search.setText(self.market_query)
        self.market_search.textChanged.connect(self.filter_market)
        box.addWidget(self.market_search)
        filters = QHBoxLayout()
        self.category_buttons = {}
        for category in ("全部", "系统", "效率", "监控"):
            count = len(PLUGINS) if category == "全部" else sum(p.category == category for p in PLUGINS)
            item = button(f"{category}  {count}", lambda c=category: self.choose_category(c))
            item.setCheckable(True)
            item.setChecked(category == self.market_category)
            self.category_buttons[category] = item
            filters.addWidget(item)
        filters.addStretch()
        state = QComboBox()
        state.addItems(["全部状态", "已添加", "未添加", "已停用"])
        state.setCurrentText(self.market_state)
        state.currentTextChanged.connect(self.choose_market_state)
        filters.addWidget(state)
        box.addLayout(filters)
        self.market_rows = {}
        for manifest in sorted(PLUGINS, key=lambda p: p.id not in self.prefs.installed):
            frame, layout = card()
            row = plugin_heading(manifest)
            installed = manifest.id in self.prefs.installed
            if installed:
                row.addWidget(label("已启用" if manifest.id in self.host.active_ids else "已停用", "muted"))
                row.addWidget(button("设置", lambda k=manifest.id: self.navigate("plugin:" + k)))
            else:
                row.addWidget(button("添加", lambda k=manifest.id: self.attempt(lambda: self.host.install(k)), True))
            row.addWidget(button("详情", lambda k=manifest.id: self.plugin_details(k)))
            layout.addLayout(row)
            layout.addWidget(label(manifest.description, "muted"))
            box.addWidget(frame)
            self.market_rows[manifest.id] = frame
        self.market_empty = label("没有匹配的插件，请调整搜索词或分类。", "muted")
        box.addWidget(self.market_empty)
        box.addStretch()
        self.filter_market(self.market_query)

    def choose_category(self, category):
        self.market_category = category
        for key, widget in self.category_buttons.items():
            widget.setChecked(key == category)
        self.filter_market(self.market_query)

    def choose_market_state(self, state):
        self.market_state = state
        self.filter_market(self.market_query)

    def filter_market(self, query):
        self.market_query = query
        count = 0
        for manifest in PLUGINS:
            match = query.casefold() in (manifest.title + manifest.description).casefold()
            match &= self.market_category in ("全部", manifest.category)
            if self.market_state == "已添加":
                match &= manifest.id in self.prefs.installed
            elif self.market_state == "未添加":
                match &= manifest.id not in self.prefs.installed
            elif self.market_state == "已停用":
                match &= manifest.id in self.prefs.disabled
            self.market_rows[manifest.id].setVisible(match)
            count += int(match)
        self.market_empty.setVisible(count == 0)

    def plugin_details(self, key):
        manifest = CATALOG[key]
        dialog = QDialog(self)
        dialog.setWindowTitle(manifest.title)
        dialog.resize(500, 310)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)
        layout.addLayout(plugin_heading(manifest))
        layout.addWidget(label(manifest.description))
        layout.addWidget(label("权限与数据\n" + manifest.permission, "muted"))
        layout.addWidget(label("来源：WinTools 内置插件 · 与应用一起更新", "muted"))
        def open_plugin():
            dialog.accept()
            if key not in self.host.instances:
                self.attempt(lambda: self.host.install(key))
            if key in self.host.instances:
                self.navigate("plugin:" + key)
        layout.addWidget(button("打开设置" if key in self.host.instances else "添加插件", open_plugin, True))
        dialog.exec()
        dialog.deleteLater()

    def render_plugin(self, key):
        plugin = self.host.instances[key]
        manifest = plugin.manifest
        box = self.page(manifest.title, manifest.description)
        frame, layout = card()
        row = plugin_heading(manifest)
        toggle = Toggle("启用")
        toggle.setChecked(plugin.active)
        toggle.toggled.connect(lambda checked: self.set_plugin_enabled(key, checked))
        row.addWidget(toggle)
        row.addWidget(button("移除", lambda: self.uninstall(key)))
        layout.addLayout(row)
        layout.addWidget(label(manifest.permission, "muted"))
        box.addWidget(frame)
        if plugin.active:
            control, content = card()
            content.addWidget(label("功能与设置", "section"))
            content.addWidget(plugin.create_view())
            box.addWidget(control)
            add = QHBoxLayout()
            add.addWidget(label("添加到面板", "muted"))
            target = QComboBox()
            for panel in self.prefs.panels:
                target.addItem(panel["title"], panel["id"])
            add.addWidget(target, 1)
            add.addWidget(button("添加组件", lambda: self.attempt(lambda: self.host.add_item(target.currentData(), key))))
            box.addLayout(add)
        else:
            box.addWidget(label("插件已停用。相关操作与组件暂停，重新启用后恢复。", "muted"))
        box.addStretch()

    def uninstall(self, key):
        if self.services.confirm("移除插件", f"移除“{CATALOG[key].title}”？它会从侧栏和所有面板移除，可随时从插件库重新添加。"):
            self.attempt(lambda: self.host.uninstall(key))

    def set_plugin_enabled(self, key, enabled):
        try:
            self.host.set_enabled(key, enabled)
        except (OSError, ValueError) as exc:
            self.services.error(str(exc))
            self.render()

    def render_panels(self):
        box = self.page("我的面板", "把实时组件、功能行和操作网格组合在一起。面板布局会自动保存。")
        row = QHBoxLayout()
        self.panel_picker = QComboBox()
        for panel in self.prefs.panels:
            self.panel_picker.addItem(panel["title"], panel["id"])
        self.panel_picker.setCurrentIndex(self.panel_picker.findData(self.selected_panel))
        self.panel_picker.currentIndexChanged.connect(self.select_panel)
        row.addWidget(self.panel_picker, 1)
        row.addWidget(button("新建", self.new_panel))
        row.addWidget(button("重命名", self.rename_panel))
        row.addWidget(button("删除", self.delete_panel))
        box.addLayout(row)
        toolbar = QHBoxLayout()
        panel = self.host.panel(self.selected_panel)
        toolbar.addWidget(label(f"{len(panel['items'])} 个组件", "muted"))
        toolbar.addStretch()
        toolbar.addWidget(button("调整顺序", self.edit_order))
        toolbar.addWidget(button("＋ 添加组件", self.component_library, True))
        box.addLayout(toolbar)
        columns = QHBoxLayout()
        left, right = QVBoxLayout(), QVBoxLayout()
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)
        columns.setSpacing(16)
        for index, key in enumerate(panel["items"]):
            plugin = self.host.instances.get(key)
            if not plugin:
                continue
            frame, layout = card()
            header = plugin_heading(plugin.manifest, False)
            header.addWidget(button("设置", lambda k=key: self.navigate("plugin:" + k)))
            remove = button("×", lambda k=key: self.host.remove_item(self.selected_panel, k))
            remove.setToolTip("从此面板移除组件")
            header.addWidget(remove)
            layout.addLayout(header)
            if plugin.active:
                layout.addWidget(plugin.create_view(compact=True))
            else:
                layout.addWidget(label("插件已停用", "muted"))
                layout.addWidget(button("启用插件", lambda k=key: self.attempt(lambda: self.host.set_enabled(k, True))))
            (left if index % 2 == 0 else right).addWidget(frame)
        left.addStretch()
        right.addStretch()
        box.addLayout(columns)
        if not panel["items"]:
            box.addWidget(label("这个面板还没有组件。点击“添加组件”选择你的工具。", "muted"))
        box.addStretch()

    def select_panel(self, index):
        self.selected_panel = self.panel_picker.itemData(index)
        self.render()

    def new_panel(self):
        name, ok = QInputDialog.getText(self, "新建面板", "面板名称")
        if ok and name.strip():
            key = self.attempt(lambda: self.host.add_panel(name))
            if key:
                self.selected_panel = key
                self.render()

    def rename_panel(self):
        panel = self.host.panel(self.selected_panel)
        name, ok = QInputDialog.getText(self, "重命名面板", "面板名称", text=panel["title"])
        if ok and name.strip():
            panel["title"] = name.strip()[:40]
            self.host.persist()

    def delete_panel(self):
        if len(self.prefs.panels) == 1:
            self.services.notify("至少保留一个面板")
            return
        if self.services.confirm("删除面板", "删除此面板布局？已添加的插件会保留。"):
            self.prefs.panels = [p for p in self.prefs.panels if p["id"] != self.selected_panel]
            self.host.persist()

    def edit_order(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("调整组件顺序")
        dialog.resize(420, 420)
        box = QVBoxLayout(dialog)
        box.addWidget(label("拖动排序，或使用下方按钮。面板按从左到右排列。", "muted"))
        items = QListWidget()
        items.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        for key in self.host.panel(self.selected_panel)["items"]:
            item = QListWidgetItem(CATALOG[key].title)
            item.setData(Qt.ItemDataRole.UserRole, key)
            items.addItem(item)
        box.addWidget(items)
        def move(offset):
            index = items.currentRow()
            if 0 <= index + offset < items.count() and index >= 0:
                item = items.takeItem(index)
                items.insertItem(index + offset, item)
                items.setCurrentRow(index + offset)
        controls = QHBoxLayout()
        controls.addWidget(button("上移", lambda: move(-1)))
        controls.addWidget(button("下移", lambda: move(1)))
        controls.addWidget(button("保存顺序", dialog.accept, True))
        box.addLayout(controls)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.host.set_panel_order(self.selected_panel, [items.item(i).data(Qt.ItemDataRole.UserRole) for i in range(items.count())])
        dialog.deleteLater()

    def component_library(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("组件库")
        dialog.resize(880, 650)
        root = QHBoxLayout(dialog)
        sidebar = QVBoxLayout()
        search = QLineEdit()
        search.setPlaceholderText("搜索组件")
        items = QListWidget()
        items.setFixedWidth(220)
        sidebar.addWidget(search)
        sidebar.addWidget(items)
        root.addLayout(sidebar)
        preview = QVBoxLayout()
        root.addLayout(preview, 1)
        def show_preview():
            clear_layout(preview)
            item = items.currentItem()
            if not item:
                preview.addWidget(label("没有可用组件，请先在插件库添加并启用插件。", "muted"))
                return
            key = item.data(Qt.ItemDataRole.UserRole)
            plugin = self.host.instances[key]
            preview.addWidget(label(plugin.manifest.title, "title"))
            preview.addWidget(label(plugin.manifest.description, "muted"))
            frame, content = card()
            view = plugin.create_view(compact=True)
            view.setEnabled(False)
            content.addWidget(view)
            preview.addWidget(frame)
            preview.addStretch()
            existing = key in self.host.panel(self.selected_panel)["items"]
            def add():
                self.host.add_item(self.selected_panel, key)
                dialog.accept()
            add_button = button("已添加到此面板" if existing else "添加到“" + self.host.panel(self.selected_panel)["title"] + "”", add, True)
            add_button.setEnabled(not existing)
            preview.addWidget(add_button)
        def filter_items(query):
            items.blockSignals(True)
            items.clear()
            for key in self.prefs.sidebar_order:
                if key in self.host.active_ids and query.casefold() in CATALOG[key].title.casefold():
                    item = QListWidgetItem(icon(CATALOG[key].symbol, CATALOG[key].color), CATALOG[key].title)
                    item.setData(Qt.ItemDataRole.UserRole, key)
                    items.addItem(item)
            items.setCurrentRow(0)
            items.blockSignals(False)
            show_preview()
        search.textChanged.connect(filter_items)
        items.currentItemChanged.connect(lambda *_: show_preview())
        filter_items("")
        dialog.exec()
        dialog.deleteLater()

    def render_actions(self):
        box = self.page("操作与快捷键", "操作由已启用插件提供。Ctrl+K 在应用内打开统一搜索。")
        search = QLineEdit()
        search.setPlaceholderText("搜索操作或插件")
        box.addWidget(search)
        rows = []
        for key, manifest, action in self.host.actions():
            frame, layout = card()
            row = QHBoxLayout()
            row.addWidget(label(action.title), 1)
            row.addWidget(label(manifest.title, "muted"))
            row.addWidget(button("执行", lambda k=key: self.services.run(k)))
            layout.addLayout(row)
            box.addWidget(frame)
            rows.append((action.title + manifest.title, frame))
        search.textChanged.connect(lambda query: [frame.setVisible(query.casefold() in title.casefold()) for title, frame in rows])
        box.addWidget(label("当前快捷键仅在 WinTools 内生效。", "muted"))
        box.addStretch()

    def render_general(self):
        box = self.page("通用", "设置常驻行为与导航。工具功能由插件提供。")
        frame, content = card()
        content.addWidget(label("窗口与托盘", "section"))
        check = Toggle("关闭窗口时保留在系统托盘")
        check.setChecked(self.prefs.close_to_tray)
        check.toggled.connect(self.set_close_behavior)
        content.addWidget(check)
        content.addWidget(label("托盘菜单可打开面板、执行插件操作或完全退出。", "muted"))
        box.addWidget(frame)
        frame, content = card()
        content.addWidget(label("侧栏与面板", "section"))
        content.addWidget(label("点击分组标题旁的箭头折叠分组。右键插件可上移或下移，顺序自动保存。", "muted"))
        content.addWidget(button("编辑我的面板", lambda: self.navigate("panels")))
        box.addWidget(frame)
        box.addWidget(label("配置文件\n" + str(self.prefs.path), "muted"))
        box.addStretch()

    def set_close_behavior(self, value):
        self.prefs.close_to_tray = value
        self.save_preferences()

    def save_preferences(self):
        try:
            self.prefs.save()
        except OSError as exc:
            self.services.error("配置保存失败：" + str(exc))

    def render_permissions(self):
        box = self.page("权限与隐私", "查看已添加插件的数据访问方式。")
        for key in self.prefs.sidebar_order:
            if key not in self.prefs.installed:
                continue
            manifest = CATALOG[key]
            frame, content = card()
            content.addLayout(plugin_heading(manifest, False))
            content.addWidget(label(manifest.permission, "muted"))
            box.addWidget(frame)
        box.addStretch()

    def render_about(self):
        box = self.page("关于 WinTools", "把常用 Windows 工具放到同一个地方。")
        frame, content = card()
        content.addWidget(label("WinTools 0.2", "brand"))
        content.addWidget(label("借鉴 MacTools 的分组侧栏、插件宿主、组件库和面板组合方式，使用 Python 与 Qt 实现 Windows 功能。"))
        content.addWidget(label("当前提供 8 个内置插件。插件库是本地目录，暂不支持在线市场、外部插件包、工作流和全局快捷键。", "muted"))
        box.addWidget(frame)
        box.addStretch()

    def command_palette(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("搜索操作")
        dialog.resize(580, 450)
        box = QVBoxLayout(dialog)
        search = QLineEdit()
        search.setPlaceholderText("搜索操作、插件或页面…")
        results = QListWidget()
        box.addWidget(search)
        box.addWidget(results)
        entries = [(action.title + "  ·  " + manifest.title, lambda k=key: self.services.run(k)) for key, manifest, action in self.host.actions()]
        entries += [(manifest.title + "  ·  插件设置", lambda k=key: self.navigate("plugin:" + k))
                    for key, manifest in CATALOG.items() if key in self.host.instances]
        entries += [(title, lambda k=key: self.navigate(k)) for key, title in [("panels", "我的面板"), ("marketplace", "插件库"), ("general", "通用")]]
        filtered = []
        def refresh(query):
            filtered[:] = [(title, callback) for title, callback in entries if query.casefold() in title.casefold()]
            results.clear()
            results.addItems([title for title, _ in filtered])
            results.setCurrentRow(0)
        def execute(*_):
            index = results.currentRow()
            if index >= 0:
                callback = filtered[index][1]
                dialog.accept()
                # Close the search dialog before screenshot actions hide the host.
                QTimer.singleShot(0, callback)
        search.textChanged.connect(refresh)
        search.returnPressed.connect(execute)
        results.itemActivated.connect(execute)
        refresh("")
        search.setFocus()
        dialog.exec()
        dialog.deleteLater()

    def build_tray(self):
        self.tray_menu.clear()
        self.tray_menu.addAction("打开 WinTools", self.show_window)
        panels = self.tray_menu.addMenu("我的面板")
        for panel in self.prefs.panels:
            panels.addAction(panel["title"], lambda k=panel["id"]: self.show_panel(k))
        actions = self.tray_menu.addMenu("插件操作")
        for key, manifest, action in self.host.actions():
            actions.addAction(manifest.title + " · " + action.title, lambda k=key: self.services.run(k))
        self.tray_menu.addSeparator()
        self.tray_menu.addAction("退出", self.quit_app)

    def show_panel(self, key):
        self.selected_panel = key
        self.navigate("panels")
        self.show_window()

    def update_snapshot(self, data):
        self.has_snapshot = True
        self.host.update(data)

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
            return
        self.shutdown()
        event.accept()

    def shutdown(self):
        if self.closed:
            return
        self.closed = True
        self.monitor.requestInterruption()
        self.monitor.wait()
        for message in self.host.shutdown():
            print(message, file=sys.stderr)
        self.tray.hide()

    def quit_app(self):
        self.exiting = True
        self.close()


def main():
    parser = argparse.ArgumentParser(description="WinTools plugin host")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("WinTools currently supports Windows only")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("WinTools")
    app.setOrganizationName("WinTools")
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setStyleSheet(STYLE)
    temp = TemporaryDirectory() if args.smoke_test else None
    path = Path(temp.name) / "settings.json" if temp else Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "settings.json"
    window = Window(Preferences(path), smoke=args.smoke_test)
    window.show()
    outcome = [0]
    if args.smoke_test:
        def finish():
            try:
                assert window.has_snapshot
                assert window.host.instances["processes"].snapshot
                assert window.host.instances["network"].snapshot
                for key in ("general", "permissions", "about", "actions", "panels"):
                    window.navigate(key)
                    app.processEvents()
                for key in list(window.host.instances):
                    window.navigate("plugin:" + key)
                    app.processEvents()
                window.host.install("clipboard")
                window.navigate("plugin:clipboard")
                app.processEvents()
                window.host.set_enabled("clipboard", False)
                assert "clipboard:clear" not in [entry[0] for entry in window.host.actions()]
                window.host.uninstall("clipboard")
                assert "plugin:clipboard" not in window.nav_items
                if args.screenshot:
                    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                    for destination, name in [("marketplace", args.screenshot.name), ("panels", "panels.png"), ("plugin:awake", "plugin-settings.png")]:
                        window.navigate(destination)
                        app.processEvents()
                        assert window.grab().save(str(args.screenshot.parent / name))
                    window.selected_panel = "controls"
                    window.navigate("panels")
                    app.processEvents()
                    assert window.grab().save(str(args.screenshot.parent / "controls.png"))
                    captures = []
                    def capture_library():
                        dialog = app.activeModalWidget()
                        if dialog:
                            captures.append(dialog.grab().save(str(args.screenshot.parent / "components.png")))
                            dialog.reject()
                    QTimer.singleShot(250, capture_library)
                    window.component_library()
                    assert captures == [True], "Component library screenshot failed"
                print("PASS: live data, all plugin views, lifecycle, sidebar and panel rendering")
            except Exception as exc:
                import traceback
                traceback.print_exc()
                outcome[0] = 1
            finally:
                window.quit_app()
        QTimer.singleShot(4500, finish)
    result = app.exec()
    if temp:
        temp.cleanup()
    return outcome[0] or result
