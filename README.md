# WinTools

Python 实现的 Windows 常驻工具箱，参考 MacTools 的模块化组织方式。当前是 **0.1 可运行首版**，并非 MacTools 全量移植。界面使用 PySide6，系统采样使用 psutil，系统操作使用 Windows API。

## 已实现

- 深色中文桌面界面、系统托盘、关闭到托盘与退出。
- CPU、内存、系统盘占用、网络上下行速率、电池百分比与运行时间。
- 进程内存列表及名称 / PID 搜索、网卡 IP 与链路状态。
- 防止系统自动休眠，可选择保持屏幕常亮；停用模块或退出时释放请求。
- 显示、声音、网络、启动应用、存储、应用、电源和更新设置入口，任务管理器与锁屏。
- 5 个内置模块的启停、配置持久化、Ctrl+K 应用内命令搜索。

启动项、应用卸载、存储清理目前由 Windows 设置完成。没有直接删除文件、结束进程、采集剪贴板或安装第三方插件的功能。

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

配置路径由 Qt 的 AppLocalDataLocation 决定，具体位置显示在「偏好设置」页面。防休眠状态不会跨重启自动恢复。不需要管理员权限；受系统保护的数据可能不可见。

## 验证

```powershell
uv run --locked python -m unittest discover -s tests -v
uv run --locked python -m wintools --smoke-test --screenshot artifacts\dashboard.png
```

冒烟检查会打开窗口、获取真实系统数据、切换全部页面、截图并在约 5 秒后退出，不执行锁屏或更改系统设置。测试配置与正式配置隔离。

## 项目结构

- `wintools/app.py`：Qt 宿主、托盘、面板和操作搜索。
- `wintools/core.py`：内置模块目录、原子配置保存。
- `wintools/monitor.py`：后台系统采样线程。
- `wintools/windows.py`：Windows 电源与系统入口适配。
- `docs/MIGRATION.md`：MacTools 阅读结果、功能映射和后续路线。

当前模块目录属于内置功能开关，不是动态 Python 插件加载器。尚未提供安装包、自动更新、在线市场、拖拽面板或工作流。
