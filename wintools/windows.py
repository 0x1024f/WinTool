"""Small explicit Windows API boundary; no shell command interpolation."""
import ctypes
from ctypes import wintypes
import os
import subprocess
import sys


class WindowsSystem:
    def __init__(self):
        self.awake = False
        self.display = False
        self.kernel = None
        if sys.platform == "win32":
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.SetThreadExecutionState.argtypes = [wintypes.DWORD]
            self.kernel.SetThreadExecutionState.restype = wintypes.DWORD

    def keep_awake(self, enabled: bool, display: bool = False):
        # Must be called on the same UI thread for acquisition and release.
        if self.kernel is None:
            raise OSError("此操作仅支持 Windows")
        flags = 0x80000000 | (0x1 if enabled else 0) | (0x2 if enabled and display else 0)
        if not self.kernel.SetThreadExecutionState(flags):
            raise ctypes.WinError(ctypes.get_last_error())
        self.awake, self.display = enabled, enabled and display

    def release(self):
        if self.awake:
            self.keep_awake(False)

    def open_action(self, action: str):
        if sys.platform != "win32":
            raise OSError("此操作仅支持 Windows")
        uris = {
            "display": "ms-settings:display", "sound": "ms-settings:sound",
            "network": "ms-settings:network-status", "startup": "ms-settings:startupapps",
            "storage": "ms-settings:storagesense", "apps": "ms-settings:appsfeatures",
            "power": "ms-settings:powersleep", "update": "ms-settings:windowsupdate",
        }
        if action in uris:
            os.startfile(uris[action])
        elif action == "taskmgr":
            subprocess.Popen([os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                                          "System32", "Taskmgr.exe")])
        elif action == "lock":
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.LockWorkStation.argtypes = []
            user.LockWorkStation.restype = wintypes.BOOL
            if not user.LockWorkStation():
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            raise ValueError("未知操作")
