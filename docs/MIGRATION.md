# MacTools → WinTools

## 阅读结论

本地参考项目：`D:\core\MacTools`。检查了 README、AGENTS、68 个插件目录，以及 PluginInterfaces、PluginPanelItems、ActionRegistry 和 KeepAwakeSession 等代表性实现。

MacTools 使用 Swift 6、SwiftUI、AppKit，目标系统为 macOS 14+。它是插件化的常驻工具宿主，核心划分如下：

| 原项目层次 | 作用 | Windows 对应设计 |
| --- | --- | --- |
| Sources/App | 菜单栏、面板、设置、窗口路由 | Qt 主窗口、系统托盘、页面路由 |
| Sources/MacToolsPluginKit | 插件元数据、声明式面板、操作协议 | Python 元数据目录；后续扩展生命周期协议与声明式控件 |
| Sources/Core/Plugins | 插件加载、安装、目录与显示偏好 | 首版内置模块启停；后续增加可信插件加载 |
| Sources/Core/Actions | 稳定操作标识、可用性、执行入口 | 首版固定操作 ID 与统一 Windows 适配入口 |
| Sources/Core/Shortcuts | 全局快捷键 | 首版应用内 Ctrl+K；后续 RegisterHotKey |
| Plugins | 独立功能与资源 | 首版 system/processes/network/awake/shortcuts |

可迁移的是产品结构和交互理念。AppKit、IOKit、EventKit、AppleScript、SMC 等实现需要用 Windows API 或 Windows 专用服务重写。

## 功能映射

| MacTools 功能组 / 代表插件 | Windows 方案 | 当前状态 |
| --- | --- | --- |
| SystemStatus / SystemData / PowerStatus | psutil、Windows 电源 API | 基础指标已实现，温度、功耗、电池健康未实现 |
| IPOverview | psutil 网卡与地址信息 | 本机地址与链路信息已实现；公网 IP / 测速未实现 |
| KeepAwake | SetThreadExecutionState | 已实现系统与屏幕防休眠；不覆盖合盖策略 |
| QuitApps | 进程查看、任务管理器 | 已实现查看和系统入口；不直接结束进程 |
| LaunchControl / Homebrew | 启动应用设置、winget | 已提供启动应用入口；winget 管理待实现 |
| DiskClean / StorageExplorer / EmptyTrash / XcodeClean | 存储设置、磁盘扫描、回收站 API | 已提供存储入口；扫描与清理待实现，Xcode 专项不适用 |
| DisplayBrightness / DisplayResolution / NightShift | WMI / DDC-CI、显示设置 | 已提供显示入口；亮度、模式切换待实现 |
| SystemMute / MicrophoneMute / AppVolume / DisplayVolume | Windows Core Audio | 已提供声音入口；直接音量控制待实现 |
| LockScreen / SystemPower | LockWorkStation、电源 API | 锁屏带确认；电源设置入口已实现 |
| ClipboardHistory / ClipboardClear | Qt Clipboard + DPAPI | 待实现；默认不采集，需过期和隐私控制 |
| Screenshot | Qt 屏幕捕获 / Windows Graphics Capture | 待实现，含 DPI、多屏、标注和区域录制 |
| WindowLayouts / WindowSwitcher / StageManager | EnumWindows / SetWindowPos / DWM | 待实现；需处理权限级别、DPI 与恢复布局 |
| InputRemapping / AppHotkey / MouseEnhancer / KeyStats | RegisterHotKey、低级输入钩子 | 待实现；需避免密码输入记录与快捷键冲突 |
| ActivityBar / DeviceBattery / Calendar | 前台窗口事件、设备 API、日历来源 | 待实现；日历来源待确定 |
| SavedScripts / AppleShortcuts / ActionGrid | 操作注册表、工作流执行器、PowerShell | 待实现；脚本需明确执行边界、取消与超时 |
| Appearance / MacSettings / RightClick / ZshConfig | Windows 设置、资源管理器、PowerShell 配置 | 后续按 Windows 习惯重新设计 |
| Translator / AIAssistant / AIUsage / CloudflareR2 | 独立网络服务适配、凭据存储 | 待实现；服务选择与密钥来源待确定 |
| FanControl / BatteryChargeLimit | 厂商 SDK 或受支持驱动 | 依设备决定，不作为通用基础功能 |
| Sidecar / HideNotch / Siri / Dock / Finder / True Tone 专属功能 | 无通用的一对一 Windows 等价实现 | 不直接移植；按具体需求寻找替代方案 |

## 分阶段实现

1. **基础宿主（当前）**：可运行桌面窗口、托盘、后台采样、内置模块开关、配置与命令搜索。
2. **高频操作**：Core Audio 音量、全局快捷键、窗口布局、截图；先确定键位和多屏行为。
3. **管理能力**：启动项备份恢复、winget 包管理、磁盘分析。清理必须先预览，执行前重新验证路径，优先回收站。
4. **个人效率**：可选剪贴板历史、工作流、定时与事件触发、操作取消和运行记录。
5. **发行与扩展**：插件生命周期、版本与兼容性、签名与信任策略、打包安装、更新与卸载。

首版只加载项目内代码，不从网络下载并执行 Python 插件。配置使用同目录临时文件和原子替换；采样在后台线程；防休眠获取和释放位于同一 UI 线程。

## 当前限制与验证范围

- 界面为固定深色主题，不是 Windows 原生 WinUI，也没有浅色主题与完整无障碍验收。
- 没有跨进程单实例控制，重复启动会出现多个托盘实例。
- 自动检查覆盖配置失败边界、电源状态失败边界和实际采样 / 页面渲染。锁屏、设置跳转、长时间防休眠、托盘交互仍需交互式验收。
- 网络速率是所有网卡计数合计，VPN 或虚拟网卡可能重复计数。
- 原项目声明 GPL-3.0-only。本首版没有复制 Swift 实现或素材；后续若直接移植原代码或素材，应保留对应许可和署名。
