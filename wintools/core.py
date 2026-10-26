"""Shared plugin catalog and validated, atomic preferences."""
from dataclasses import dataclass
import json
from pathlib import Path
import os
import tempfile


@dataclass(frozen=True)
class Plugin:
    id: str
    title: str
    description: str
    category: str


PLUGINS = (
    Plugin("system", "系统状态", "实时 CPU、内存、系统盘和网络速率", "监控"),
    Plugin("processes", "进程查看", "查看进程内存占用与 PID", "监控"),
    Plugin("network", "网络信息", "网卡状态、本机 IP 与连接速率", "监控"),
    Plugin("awake", "防止休眠", "保持系统唤醒，可同时保持屏幕常亮", "电源"),
    Plugin("shortcuts", "快捷操作", "快速打开 Windows 设置和系统管理工具", "系统"),
)


class Preferences:
    def __init__(self, path: Path):
        self.path = path
        self.warning = ""
        self.disabled: set[str] = set()
        self.close_to_tray = True
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            disabled = data.get("disabled", [])
            if not isinstance(disabled, list) or not all(isinstance(x, str) for x in disabled):
                raise ValueError("Invalid plugin list")
            if not isinstance(data.get("close_to_tray", True), bool):
                raise ValueError("Invalid tray preference")
            self.disabled = set(disabled) & {p.id for p in PLUGINS}
            self.close_to_tray = data.get("close_to_tray", True)
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, AttributeError):
            self.warning = "配置无法读取，已使用默认设置；原文件未修改。"

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"version": 1, "disabled": sorted(self.disabled),
                           "close_to_tray": self.close_to_tray}, stream, ensure_ascii=False, indent=2)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def format_bytes(value: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return "0 B"
