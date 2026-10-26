# WinTools

Python 实现的 Windows 常驻工具箱，参考 MacTools 的分组侧栏、插件宿主、组件库与面板组合方式。当前版本 **0.2**，并非 MacTools 全量移植。界面使用 PySide6，系统采样使用 psutil，系统操作使用 Windows API。

## 已实现

- 分组侧栏：WinTools、自定义、插件设置。支持搜索、折叠、右键调整插件顺序。
- 插件库：名称与简介搜索、分类与状态筛选、详情、添加、启停、移除。
- 自定义面板：新建、重命名、删除、组件库预览、添加与移除组件、拖动或按钮排序。
- 插件生命周期：启停同时影响侧栏状态、采样、监听、操作搜索与托盘操作。
- 8 个插件：系统状态、进程查看、IP 概览、防止休眠、系统快捷操作、截图、剪贴板历史、锁定屏幕。
- CPU、内存、系统盘占用、网络上下行速率、电池百分比与运行时间。
- 进程内存列表及名称 / PID 搜索、网卡 IP 与链路状态。
- 防止系统自动休眠，可选择保持屏幕常亮；停用模块或退出时释放请求。
- 显示、声音、网络、启动应用、存储、应用、电源和更新设置入口，任务管理器与锁屏。
- 截图：选择显示器，隐藏主窗口后截图，保存 PNG 或复制到系统剪贴板。
- 剪贴板历史：添加后手动开启记录，最近 30 条文本仅保存在内存，可搜索、复制、清空；停用或退出自动清空。
- 配置持久化、旧版配置迁移、Ctrl+K 应用内命令搜索。

插件库使用随应用提供的本地目录，“添加 / 移除”管理宿主中的插件实例，并不下载或删除 Python 包。启动项、应用卸载和存储清理目前由 Windows 设置完成。尚未支持外部插件包、在线市场、自动更新、工作流或全局快捷键。

## 使用方式

1. 从「插件库」查看工具、添加需要的插件。
2. 左侧「插件设置」会自动出现新插件，进入后配置或使用功能。
3. 在「我的面板」选择或新建面板，通过「添加组件」预览并添加插件。
4. 通过「调整顺序」拖动组件；关闭插件会暂停组件，移除插件会清理所有面板引用。
5. 用 Ctrl+K 或托盘的「插件操作」执行已启用插件提供的操作。

剪贴板插件默认未添加，添加后也不会自动记录。启用记录后可能保存敏感文本，请按需开启；不提供磁盘历史或加密持久化。

## 运行

需要 Windows 10/11 和 uv。项目使用 uv 管理虚拟环境与依赖，默认 Python 3.12（由 `.python-version` 指定）。在项目目录运行：

```powershell
uv sync --locked
uv run --locked python -m wintools
```

uv 会自动创建或复用 `.venv`，按 `uv.lock` 安装依赖；没有合适的 Python 时会自动下载。无需手动激活环境。下载缓存位于项目的 `.uv-cache`。

添加或更新依赖：

```powershell
uv add <包名>
uv lock --upgrade
uv sync --locked
```

也可双击 `run.cmd`：脚本先通过 uv 同步锁定的依赖，成功后使用环境中的 Python 启动无控制台窗口的应用。首次同步需要联网。`pyproject.toml`、`.python-version` 和 `uv.lock` 应一同提交，`.venv` 与缓存不提交。

关闭窗口默认保留托盘图标，通过托盘菜单「退出」完全关闭。Ctrl+K 只在应用内生效，不是全局快捷键。

配置路径由 Qt 的 AppLocalDataLocation 决定，具体位置显示在「通用」页面。防休眠与剪贴板记录状态不会跨重启自动恢复。不需要管理员权限；受系统保护的数据可能不可见。

## 验证

```powershell
uv run --locked python -m unittest discover -s tests -v
uv run --locked python -m wintools --smoke-test --screenshot artifacts\plugin-library.png
```

冒烟检查会打开窗口、获取真实系统数据、切换全部页面、检查插件启停和侧栏同步并截图后退出。它不执行锁屏、读取剪贴板文本或更改系统设置。测试配置与正式配置隔离。截图包括插件库、我的面板和插件设置。

## 项目结构

- `wintools/app.py`：分组侧栏、插件库、组件库、面板编辑、托盘和操作搜索。
- `wintools/host.py`：插件注册、生命周期、动作路由与面板成员管理。
- `wintools/catalog.py`：独立于界面的插件元数据目录。
- `wintools/plugins/base.py`：插件与操作协议。
- `wintools/plugins/builtin.py`：独立插件实例与功能实现。
- `wintools/plugins/views.py`：插件视图工厂；同一插件可以出现在多个面板。
- `wintools/core.py`：配置校验、版本迁移与原子保存。
- `wintools/ui.py`：共享主题、图标、开关和卡片。
- `wintools/monitor.py`：后台系统采样线程。
- `wintools/windows.py`：Windows 电源与系统入口适配。
- `docs/MIGRATION.md`：MacTools 阅读结果、功能映射和后续路线。

扩展约定见 `docs/PLUGINS.md`。当前工厂注册是静态的，插件实例按添加与移除动态创建和销毁。
