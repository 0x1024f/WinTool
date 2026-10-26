"""Background collection; emit immutable-by-convention snapshots to the UI."""
import os
import socket
import time

import psutil
from PySide6.QtCore import QThread, Signal


class Monitor(QThread):
    snapshot = Signal(dict)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = frozenset({"system", "processes", "network"})

    def run(self):
        previous = psutil.net_io_counters()
        stamp = time.monotonic()
        psutil.cpu_percent()
        while not self.isInterruptionRequested():
            try:
                enabled = self.enabled
                data = {}
                if "system" in enabled:
                    now = time.monotonic()
                    net = psutil.net_io_counters()
                    elapsed = max(now - stamp, 0.01)
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
                    battery = psutil.sensors_battery()
                    data["system"] = {
                        "cpu": psutil.cpu_percent(), "memory": memory.percent,
                        "memory_used": memory.used, "memory_total": memory.total,
                        "disk": disk.percent, "disk_free": disk.free,
                        "down": max(0, net.bytes_recv - previous.bytes_recv) / elapsed,
                        "up": max(0, net.bytes_sent - previous.bytes_sent) / elapsed,
                        "uptime": max(0, time.time() - psutil.boot_time()),
                        "battery": None if battery is None else battery.percent,
                    }
                    previous, stamp = net, now
                if "processes" in enabled:
                    rows = []
                    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
                        if self.isInterruptionRequested():
                            return
                        try:
                            info = proc.info
                            if info["memory_info"] is not None:
                                rows.append((info["pid"], info["name"] or "系统进程", info["memory_info"].rss))
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    data["processes"] = sorted(rows, key=lambda row: row[2], reverse=True)
                if "network" in enabled:
                    stats = psutil.net_if_stats()
                    data["network"] = [
                        (name, "已连接" if stats.get(name) and stats[name].isup else "未连接",
                         ", ".join(a.address for a in addresses if a.family in (socket.AF_INET, socket.AF_INET6)),
                         str(stats[name].speed) if name in stats and stats[name].speed > 0 else "—")
                        for name, addresses in psutil.net_if_addrs().items()
                    ]
                self.snapshot.emit(data)
            except (OSError, psutil.Error) as exc:
                self.failed.emit(str(exc))
            for _ in range(20):
                if self.isInterruptionRequested():
                    return
                self.msleep(100)
