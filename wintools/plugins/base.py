"""Runtime contract: lifecycle, actions, snapshots and panel view factories."""
from dataclasses import dataclass
from typing import Callable
from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class Action:
    id: str
    title: str
    callback: Callable
    confirmation: str = ""


class Plugin(QObject):
    changed = Signal()

    def __init__(self, manifest, services):
        super().__init__()
        self.manifest = manifest
        self.services = services
        self.active = False
        self.snapshot = None

    def activate(self):
        self.active = True

    def deactivate(self):
        self.active = False
        self.snapshot = None
        self.changed.emit()

    def update(self, snapshot):
        if self.active:
            self.snapshot = snapshot
            self.changed.emit()

    def actions(self):
        return []

    def create_view(self, compact=False):
        raise NotImplementedError
