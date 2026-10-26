"""Shared compact, neutral settings styling and host rendering primitives."""
from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPalette
from PySide6.QtWidgets import QLabel, QPushButton, QFrame, QVBoxLayout, QHBoxLayout, QSizePolicy, QLayout, QCheckBox

STYLE = """
QWidget { font-family: 'Segoe UI', 'Microsoft YaHei UI'; font-size: 13px; color: #e6e6e8; }
QMainWindow, QDialog, QWidget#content { background: #1e1e20; }
QWidget#sidebar { background: #262628; border-right: 1px solid #3a3a3d; }
QLabel { background: transparent; }
QLabel#brand { font-size: 22px; font-weight: 700; }
QLabel#title { font-size: 25px; font-weight: 650; }
QLabel#section { font-size: 15px; font-weight: 600; }
QLabel#muted { color: #a2a2aa; }
QLabel#metric { font-size: 23px; font-weight: 650; }
QLabel#badge { background: #3b3039; color: #f5a8ce; border-radius: 5px; padding: 4px 8px; }
QFrame#card { background: #2a2a2d; border: 1px solid #36363a; border-radius: 10px; }
QFrame#inset { background: #242426; border: 1px solid #38383b; border-radius: 8px; }
QPushButton { background: #39393c; border: 1px solid #444449; border-radius: 6px; padding: 7px 12px; }
QPushButton:hover { background: #48484e; border-color: #64646b; }
QPushButton:pressed { background: #525259; }
QPushButton:checked, QPushButton#primary { background: #d83989; color: white; border: 1px solid #e34b98; }
QPushButton:disabled { color: #75757e; background: #303033; border-color: #3b3b40; }
QLineEdit, QComboBox { background: #29292c; border: 1px solid #444448; border-radius: 7px; padding: 8px 10px; }
QLineEdit:focus, QComboBox:focus { border-color: #db589c; }
QComboBox QAbstractItemView { background: #303034; selection-background-color: #70405b; }
QScrollArea { border: none; background: transparent; }
QTreeWidget { background: transparent; border: none; outline: none; }
QTreeWidget::item { height: 32px; padding: 2px 7px; border-radius: 6px; }
QTreeWidget::item:selected { background: #494246; color: white; }
QTreeWidget::item:hover { background: #363638; }
QTreeWidget::branch { background: #262628; }
QTreeWidget::branch:selected { background: #262628; }
QListWidget, QTableWidget { background: #262629; border: 1px solid #3b3b40; border-radius: 7px; alternate-background-color: #2c2c30; gridline-color: #37373b; outline: none; }
QListWidget::item { padding: 10px; border-radius: 5px; }
QListWidget::item:selected { background: #54434d; }
QHeaderView::section { background: #333337; border: none; padding: 8px; color: #bcbcc4; }
QProgressBar { background: #414147; border: none; border-radius: 3px; max-height: 5px; }
QProgressBar::chunk { background: #52b9c6; border-radius: 3px; }
QCheckBox { spacing: 10px; padding: 7px 0; }
QCheckBox::indicator { width: 30px; height: 17px; border-radius: 8px; background: #53535a; border: 1px solid #64646c; }
QCheckBox::indicator:checked { background: #d83989; border: 1px solid #e876af; }
QCheckBox::indicator:disabled { background: #37373b; }
QMenu { background: #2a2a2d; border: 1px solid #4a4a50; }
QMenu::item { padding: 8px 22px; }
QMenu::item:selected { background: #594451; }
QStatusBar { background: #242426; color: #a2a2aa; font-size: 12px; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: #55555c; border-radius: 3px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


def label(text, role=None):
    item = QLabel(text)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setWordWrap(True)
    if role:
        item.setObjectName(role)
    return item


def button(text, callback, primary=False):
    item = QPushButton(text)
    if primary:
        item.setObjectName("primary")
    item.clicked.connect(lambda checked=False: callback())
    return item


def card(inset=False):
    frame = QFrame()
    frame.setObjectName("inset" if inset else "card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(12)
    layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    return frame, layout


def dark_palette():
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, "#1e1e20"),
                        (QPalette.ColorRole.Base, "#262628"),
                        (QPalette.ColorRole.AlternateBase, "#2c2c30"),
                        (QPalette.ColorRole.Text, "#e6e6e8"),
                        (QPalette.ColorRole.WindowText, "#e6e6e8"),
                        (QPalette.ColorRole.Button, "#39393c"),
                        (QPalette.ColorRole.ButtonText, "#e6e6e8"),
                        (QPalette.ColorRole.Highlight, "#594451"),
                        (QPalette.ColorRole.HighlightedText, "#ffffff")):
        palette.setColor(role, QColor(color))
    return palette


class Toggle(QCheckBox):
    """Keyboard-accessible checkbox with a switch indicator."""
    def sizeHint(self):
        return QSize(48 + self.fontMetrics().horizontalAdvance(self.text()), 32)

    def minimumSizeHint(self):
        return self.sizeHint()

    def hitButton(self, point):
        return self.rect().contains(point)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1 if self.isEnabled() else 0.45)
        y = (self.height() - 19) / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#d83989" if self.isChecked() else "#55555c"))
        painter.drawRoundedRect(QRectF(1, y, 33, 19), 9.5, 9.5)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(17 if self.isChecked() else 4, y + 3, 13, 13))
        painter.setPen(QColor("#e6e6e8"))
        painter.drawText(self.rect().adjusted(44, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, self.text())
        if self.hasFocus():
            painter.setPen(QColor("#ef8abc"))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 4, 4)


def icon(symbol="W", color="#e2569e"):
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    fill = QColor(color)
    fill.setAlpha(35)
    painter.setBrush(fill)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(1, 1, 62, 62, 14, 14)
    painter.setPen(QColor(color))
    font = painter.font()
    font.setFamily("Segoe UI Symbol")
    font.setPixelSize(34)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, symbol)
    painter.end()
    return QIcon(pixmap)


def plugin_heading(manifest, subtitle=True):
    row = QHBoxLayout()
    image = QLabel()
    image.setPixmap(icon(manifest.symbol, manifest.color).pixmap(44, 44))
    image.setFixedSize(44, 44)
    row.addWidget(image)
    text = QVBoxLayout()
    text.setSpacing(3)
    text.addWidget(label(manifest.title, "section"))
    if subtitle:
        text.addWidget(label(f"{manifest.category} · {manifest.kind} · {manifest.version}", "muted"))
    row.addLayout(text, 1)
    return row


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())
