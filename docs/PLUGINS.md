# Plugin host

The host follows MacTools' separation between navigation metadata, plugin runtime state, actions and panel views. This is a Python implementation, not a binary-compatible port of MacTools plugins.

## Reference surfaces

- `SettingsView.swift`: grouped app, customization and plugin navigation.
- `SettingsSidebarPreferencesStore.swift`: persisted section expansion and plugin order.
- `PluginManagementSettingsView.swift`: searchable catalog, categories and install state.
- `PanelComponentLibrary.swift`: component selection, preview and panel placement.
- `PluginInterfaces.swift` and `PluginPanelItems.swift`: lifecycle and host-owned presentation.

WinTools uses neutral charcoal surfaces, colored plugin icons, compact grouped cards and a pink selection accent based on the reference screenshots. The host renders navigation and plugin headers; individual plugins render only their controls or data.

## Runtime contract

1. Add a `Manifest` to `wintools/catalog.py` with a stable ID, title, category, icon, version and access description.
2. Implement `Plugin` from `wintools/plugins/base.py`. Register its factory in `FACTORIES`.
3. `activate()` enables behavior; `deactivate()` must release resources before returning. It must raise if release fails, allowing the host to keep registration intact.
4. `actions()` returns local action IDs, titles, callbacks and optional confirmation text. The host namespaces IDs as `plugin-id:action-id` and rejects actions from disabled or removed plugins.
5. `create_view(compact)` creates a new widget for each placement. All views read the same runtime instance and subscribe to its `changed` signal. Do not store a single widget on the plugin.
6. Collection stays off the UI thread. The host passes enabled IDs to the monitor and routes snapshots to active plugins. Queued results from disabled plugins are ignored.

The screenshot plugin has a cancellable timer; disabling cancels pending capture. The clipboard plugin installs a Qt listener only after the user explicitly enables recording. It disconnects and clears memory on deactivation. The power plugin acquires and releases its thread-bound execution-state request on the UI thread.

## Catalog and panels

All current plugin code ships with the app. Adding creates and activates a runtime instance; removing deactivates it, removes its action registrations and deletes references from every panel. It does not delete source code. There is no external package loader or online download endpoint.

Panel membership, ordering, names, installed plugins, disabled state, sidebar order and collapsed groups are persisted in schema version 2. Version 1 settings migrate without losing the existing disabled-plugin or tray preferences. Turning a plugin off keeps its panel slots; removing it clears those slots. Clipboard content and active power requests are never persisted.

## Verification

Run `uv run --locked python -m unittest discover -s tests -v` for persistence, lifecycle, action authorization and Qt interaction checks. Tests use temporary preference files and fake clipboard/screen/system services. Run the documented smoke command for real read-only monitor data and screenshots of the host surfaces.

Hardware-specific capture behavior, protected-screen content, tray behavior and prolonged power-policy behavior still need device-level acceptance checks.
