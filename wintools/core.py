"""Versioned preferences with validation, migration and atomic persistence."""
from copy import deepcopy
import json
from pathlib import Path
import os
import tempfile

from .catalog import CATALOG, PLUGINS, DEFAULT_INSTALLED, DEFAULT_PANELS


def string_list(value):
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("Expected a list of strings")
    return list(dict.fromkeys(value))


class Preferences:
    def __init__(self, path: Path):
        self.path = path
        self.warning = ""
        self.installed = set(DEFAULT_INSTALLED)
        self.disabled = set()
        self.close_to_tray = True
        self.panels = deepcopy(DEFAULT_PANELS)
        self.sidebar_order = list(CATALOG)
        self.collapsed = set()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version", 1) not in (1, 2):
                raise ValueError("Unsupported preferences")
            installed = set(string_list(data.get("installed", list(DEFAULT_INSTALLED)))) & CATALOG.keys()
            disabled = set(string_list(data.get("disabled", []))) & installed
            close = data.get("close_to_tray", True)
            if not isinstance(close, bool):
                raise ValueError("Invalid tray preference")
            panels = data.get("panels", deepcopy(DEFAULT_PANELS))
            if not isinstance(panels, list) or not 1 <= len(panels) <= 20:
                raise ValueError("Invalid panels")
            normalized = []
            seen = set()
            for panel in panels:
                if not isinstance(panel, dict):
                    raise ValueError("Invalid panel")
                key, title = panel.get("id"), panel.get("title")
                if not isinstance(key, str) or not key or key in seen or not isinstance(title, str) or not title.strip():
                    raise ValueError("Invalid panel identity")
                seen.add(key)
                normalized.append({"id": key, "title": title[:40],
                                   "items": [p for p in string_list(panel.get("items", [])) if p in installed]})
            order = [p for p in string_list(data.get("sidebar_order", list(CATALOG))) if p in CATALOG]
            collapsed = set(string_list(data.get("collapsed", []))) & {"app", "custom", "plugins"}
            self.installed, self.disabled, self.close_to_tray = installed, disabled, close
            self.panels = normalized
            self.sidebar_order = order + [p for p in CATALOG if p not in order]
            self.collapsed = collapsed
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, AttributeError):
            self.warning = "配置无法读取，已使用默认设置；原文件未修改。"

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"version": 2, "installed": sorted(self.installed),
                           "disabled": sorted(self.disabled), "close_to_tray": self.close_to_tray,
                           "panels": self.panels, "sidebar_order": self.sidebar_order,
                           "collapsed": sorted(self.collapsed)}, stream, ensure_ascii=False, indent=2)
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
