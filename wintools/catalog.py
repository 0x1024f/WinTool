"""Built-in plugin manifests, independent of the UI and runtime instances."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Manifest:
    id: str
    title: str
    description: str
    category: str
    symbol: str
    color: str
    kind: str = "功能行"
    version: str = "1.0.0"
    permission: str = "无需额外权限"


PLUGINS = (
    Manifest("system", "系统状态", "CPU、内存、磁盘与网络速率，组合成紧凑的实时组件。", "监控", "◉", "#37c4cf", "实时组件"),
    Manifest("processes", "进程查看", "搜索正在运行的进程，按内存用量查看并打开任务管理器。", "监控", "▤", "#5cacf8", "列表组件"),
    Manifest("network", "IP 概览", "查看网卡、连接状态、本机 IP 地址及链路速率。", "监控", "◎", "#5cacf8", "列表组件"),
    Manifest("awake", "防止休眠", "让系统保持唤醒，也可以让屏幕常亮；退出后自动释放。", "系统", "☕", "#e9b95d"),
    Manifest("shortcuts", "系统快捷操作", "集中打开显示、声音、启动应用、存储等 Windows 设置。", "系统", "▦", "#a28af9", "操作网格"),
    Manifest("screenshot", "截图", "选择显示器，隐藏工具窗口后截图，保存 PNG 或复制图像。", "效率", "▣", "#be8af5", permission="仅在执行截图时读取所选屏幕"),
    Manifest("clipboard", "剪贴板历史", "临时保存最近 30 条文本，搜索与重新复制；历史仅保存在内存。", "效率", "▥", "#64c987", "列表组件", permission="手动开始记录后读取剪贴板文本；可能包含敏感信息"),
    Manifest("lock", "锁定屏幕", "从面板、托盘或操作搜索锁定 Windows，执行前确认。", "系统", "▢", "#e784a8"),
)
CATALOG = {plugin.id: plugin for plugin in PLUGINS}
DEFAULT_INSTALLED = {"system", "processes", "network", "awake", "shortcuts", "screenshot", "lock"}
DEFAULT_PANELS = [
    {"id": "dashboard", "title": "系统状态", "items": ["system", "processes", "network"]},
    {"id": "controls", "title": "快捷控制", "items": ["awake", "screenshot", "lock", "shortcuts"]},
]
