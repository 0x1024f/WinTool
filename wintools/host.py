"""Plugin host: install state, lifecycle, action routing and panel membership."""
from uuid import uuid4
from PySide6.QtCore import QObject, Signal
from .catalog import CATALOG
from .plugins import FACTORIES


class PluginHost(QObject):
    changed = Signal()

    def __init__(self, prefs, services, factories=None):
        super().__init__()
        self.prefs, self.services = prefs, services
        self.factories = factories or FACTORIES
        self.instances = {}
        for key in prefs.sidebar_order:
            if key in prefs.installed:
                instance = self.factories[key](CATALOG[key], services)
                self.instances[key] = instance
                if key not in prefs.disabled:
                    instance.activate()

    @property
    def active_ids(self):
        return frozenset(key for key, plugin in self.instances.items() if plugin.active)

    def persist(self):
        try:
            self.prefs.save()
        except OSError as exc:
            self.services.error(f"设置已在本次会话生效，但保存失败：{exc}")
        self.changed.emit()

    def install(self, key):
        if key not in CATALOG:
            raise ValueError("未知插件")
        if key in self.instances:
            return
        plugin = self.factories[key](CATALOG[key], self.services)
        plugin.activate()
        self.instances[key] = plugin
        self.prefs.installed.add(key)
        self.prefs.disabled.discard(key)
        self.persist()

    def set_enabled(self, key, enabled):
        plugin = self.instances[key]
        if enabled == plugin.active:
            return
        if enabled:
            plugin.activate()
            self.prefs.disabled.discard(key)
        else:
            plugin.deactivate()
            self.prefs.disabled.add(key)
        self.persist()

    def uninstall(self, key):
        plugin = self.instances[key]
        plugin.deactivate()
        del self.instances[key]
        plugin.deleteLater()
        self.prefs.installed.discard(key)
        self.prefs.disabled.discard(key)
        for panel in self.prefs.panels:
            panel["items"] = [item for item in panel["items"] if item != key]
        self.persist()

    def actions(self):
        return [(f"{key}:{action.id}", plugin.manifest, action)
                for key, plugin in self.instances.items() if plugin.active
                for action in plugin.actions()]

    def execute(self, action_id):
        for key, manifest, action in self.actions():
            if key == action_id:
                if action.confirmation and not self.services.confirm(action.title, action.confirmation):
                    return
                action.callback()
                return
        raise ValueError("该操作当前不可用，插件可能已停用或移除。")

    def update(self, snapshots):
        for key, data in snapshots.items():
            if key in self.instances and self.instances[key].active:
                self.instances[key].update(data)

    def panel(self, key):
        return next(panel for panel in self.prefs.panels if panel["id"] == key)

    def add_panel(self, title):
        if not title.strip() or len(self.prefs.panels) >= 20:
            raise ValueError("面板名称不能为空，最多创建 20 个面板。")
        key = uuid4().hex
        self.prefs.panels.append({"id": key, "title": title.strip()[:40], "items": []})
        self.persist()
        return key

    def add_item(self, panel_id, key):
        if key not in self.active_ids:
            raise ValueError("请先添加并启用插件。")
        panel = self.panel(panel_id)
        if key not in panel["items"]:
            panel["items"].append(key)
            self.persist()

    def set_panel_order(self, panel_id, items):
        panel = self.panel(panel_id)
        if set(items) != set(panel["items"]) or len(items) != len(set(items)):
            raise ValueError("无效的组件顺序")
        panel["items"] = list(items)
        self.persist()

    def remove_item(self, panel_id, key):
        self.panel(panel_id)["items"].remove(key)
        self.persist()

    def shutdown(self):
        errors = []
        for plugin in self.instances.values():
            if plugin.active:
                try:
                    plugin.deactivate()
                except (OSError, RuntimeError) as exc:
                    errors.append(f"{plugin.manifest.title}: {exc}")
        return errors
