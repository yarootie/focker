import sys
import json
import os
import time
import base64
import subprocess
import ctypes
from ctypes import wintypes
from pathlib import Path

# Импорты реестра для автозагрузки (только Windows)
if os.name == 'nt':
    import winreg

from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsView,
                             QGraphicsScene, QGraphicsItem, QMenu,
                             QSystemTrayIcon, QInputDialog, QFileIconProvider,
                             QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QWidget, QFormLayout, 
                             QLineEdit, QCheckBox, QComboBox, QToolButton,
                             QFileDialog, QColorDialog, QListWidget, QListWidgetItem,
                             QFrame, QAbstractItemView, QSplitter, QKeySequenceEdit,
                             QStyleOption, QStyle, QTextBrowser, QStyleOptionGraphicsItem)
from PyQt6.QtCore import (Qt, QRectF, QPointF, pyqtSignal, QFileInfo,
                          QUrl, QSettings, QMimeData, QPoint, QRect, 
                          QPropertyAnimation, QEasingCurve, QThread, QSize, 
                          QParallelAnimationGroup, QSequentialAnimationGroup)
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont, QIcon,
                          QPainterPath, QWheelEvent, QDesktopServices, QPixmap,
                          QImage, QCursor, QAction, QDrag, QClipboard, 
                          QFontDatabase, QKeySequence, QShortcut, QTransform)
from PyQt6.QtSvg import QSvgRenderer

# ==========================================
# КОНФИГУРАЦИЯ
# ==========================================
APP_NAME = "Focker"
APP_VERSION = "1"
AUTHOR_INFO = {
    "name": "yarootie",
    "github": "https://github.com/yarootie",
    "telegram": "https://t.me/yarootie_channel"
}
DEFAULT_SETTINGS = {
    "theme": "dark",
    "accent_color": "#00bcd4",
    "minimize_to_tray": True,
    "root_folder": str(Path("data").absolute()),
    "autostart": False,
    "hotkey": "Alt+V",
    "first_run": True
}

THEMES = {
    "dark": {
        "background": "#18181D",
        "surface": "#25252A",
        "grid": "#33333A",
        "item_bg": "#2C2C32",
        "item_border": "#45454E",
        "text": "#E0E0E0",
        "text_secondary": "#A0A0A9",
        "note_bg": "#4D401D",
        "note_text": "#E0E0E0",
        "area_bg": "rgba(60, 60, 70, 0.3)",
        "area_text": "rgba(255, 255, 255, 0.4)",
        "area_border": "rgba(255, 255, 255, 0.2)",
        "shadow": "rgba(0, 0, 0, 0.7)",
        "win_controls": "#FFFFFF",
        "title_bg": "#25252A" 
    }
}

# ==========================================
# HELPER: RESOURCE PATH
# ==========================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class SettingsManager:
    def __init__(self):
        self.store = QSettings("FockerApp", "Config")
    def get(self, key):
        val = self.store.value(key, DEFAULT_SETTINGS.get(key))
        if isinstance(DEFAULT_SETTINGS.get(key), bool):
            return str(val).lower() == 'true'
        return val
    def set(self, key, value):
        self.store.setValue(key, value)
    def get_theme_colors(self):
        mode = self.get("theme")
        colors = THEMES.get(mode, THEMES["dark"])
        colors["accent"] = self.get("accent_color")
        return colors
config = SettingsManager()

# ==========================================
# GLOBAL HOTKEY MANAGER
# ==========================================
class GlobalHotkeyManager(QThread):
    activated = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.running = True
        self.hotkey_id = 1
        self.current_seq = config.get("hotkey")

    def parse_hotkey(self, seq_str):
        mods = 0
        vk = 0
        seq = seq_str.upper()
        if "CTRL" in seq: mods |= 0x0002
        if "ALT" in seq: mods |= 0x0001
        if "SHIFT" in seq: mods |= 0x0004
        if "META" in seq or "WIN" in seq: mods |= 0x0008
        parts = seq.split('+')
        key_char = parts[-1]
        if len(key_char) == 1 and key_char.isalnum():
            vk = ord(key_char)
        elif key_char.startswith("F") and key_char[1:].isdigit():
            f_num = int(key_char[1:])
            vk = 0x70 + (f_num - 1)
        return mods, vk

    def run(self):
        if os.name != 'nt': return
        mods, vk = self.parse_hotkey(self.current_seq)
        if vk == 0: mods, vk = 0x0002, 0x4D # Fallback Ctrl+M
        try:
            ctypes.windll.user32.RegisterHotKey(None, self.hotkey_id, mods, vk)
        except: pass
        
        msg = wintypes.MSG()
        while self.running:
            if ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == 0x0312 and msg.wParam == self.hotkey_id:
                    self.activated.emit()
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
    
    def stop(self):
        self.running = False
        if os.name == 'nt':
            ctypes.windll.user32.UnregisterHotKey(None, self.hotkey_id)
            ctypes.windll.user32.PostQuitMessage(0)

# ==========================================
# AUTOSTART MANAGER
# ==========================================
class AutostartManager:
    KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_KEY = "FockerApp"

    @staticmethod
    def set_state(enable: bool):
        if os.name != 'nt': return
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AutostartManager.KEY_PATH, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                exe_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
                if getattr(sys, 'frozen', False): exe_path = f'"{sys.executable}"'
                winreg.SetValueEx(key, AutostartManager.APP_KEY, 0, winreg.REG_SZ, exe_path)
            else:
                try: winreg.DeleteValue(key, AutostartManager.APP_KEY)
                except FileNotFoundError: pass
            winreg.CloseKey(key)
        except Exception as e: print(f"Autostart Error: {e}")

# ==========================================
# SVG ICONS
# ==========================================
SVG_LOGO_F = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M5 3h14v4h-9v3h9v4h-9v7h-5z"/></svg>"""
SVG_GEAR = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M19.14,12.94a7.14,7.14 0 0 0 0-1.88l2.03-1.58a0.5,0.5 0 0 0 .12-0.63l-1.92-3.32a0.5,0.5 0 0 0-0.6-0.22l-2.39,0.96a6.9,6.9 0 0 0-1.6-0.94l-0.36-2.54a0.5,0.5 0 0 0-0.5-0.42H9.97a0.5,0.5 0 0 0-0.5,0.42L9.11,6.3a6.9,6.9 0 0 0-1.6,0.94L5.12,6.28a0.5,0.5 0 0 0-0.6,0.22L2.6,9.82a0.5,0.5 0 0 0 .12,0.63L4.75,12a7.14,7.14 0 0 0 0,1.88L2.72,15.46a0.5,0.5 0 0 0-.12,0.63l1.92,3.32a0.5,0.5 0 0 0 .6,0.22l2.39-0.96c0.5,0.36,1.04,0.66,1.6,0.94l0.36,2.54a0.5,0.5 0 0 0 .5,0.42h4.41a0.5,0.5 0 0 0 .5-0.42l0.36-2.54c0.56-0.28,1.1-0.58,1.6-0.94l2.39,0.96a0.5,0.5 0 0 0 .6-0.22l1.92-3.32a0.5,0.5 0 0 0-.12-0.63ZM12,15.5A3.5,3.5 0 1 1 15.5,12 3.5,3.5 0 0 1 12,15.5Z"/></svg>"""
SVG_PLUS = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M19 11H13V5a1 1 0 0 0-2 0v6H5a1 1 0 0 0 0 2h6v6a1 1 0 0 0 2 0v-6h6a1 1 0 0 0 0-2z"/></svg>"""
SVG_MIN = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect x="4" y="11" width="16" height="2" fill="currentColor"/></svg>"""
SVG_MAX = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect x="4" y="4" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"/></svg>"""
SVG_CLOSE = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M18.3 5.71L12 12l6.3 6.29-1.41 1.42L10.59 13.41 4.29 19.71 2.88 18.29 9.18 12 2.88 5.71 4.29 4.29 10.59 10.59 16.88 4.29z"/></svg>"""
SVG_FOLDER = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M10 4l2 2h8v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h6z"/></svg>"""
SVG_NOTE = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M14 2H6a2 2 0 0 0-2 2v16l4-2h10a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"/></svg>"""
SVG_PASTE = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M19 3H14.82C14.4 1.84 13.3 1 12 1s-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v13a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2zM12 3c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1z"/></svg>"""
SVG_OPEN = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zM7 7v2h14V7H7z"/></svg>"""
SVG_TRASH = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>"""
SVG_BACKDROP = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M20,4H4C2.9,4,2,4.9,2,6v12c0,1.1,0.9,2,2,2h16c1.1,0,2-0.9,2-2V6C22,4.9,21.1,4,20,4z M20,18H4V6h16V18z"/><circle fill="currentColor" cx="16" cy="10" r="2.5"/><polygon fill="currentColor" points="11,12 8,16 18,16 18,14 "/></svg>"""
SVG_INFO = """<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>"""

def svg_icon_from_string(svg_str: str, size: int = 24, color: str = None) -> QIcon:
    if color: svg_str = svg_str.replace('currentColor', color)
    renderer = QSvgRenderer(bytearray(svg_str, encoding='utf-8'))
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return QIcon(pix)

def load_custom_font():
    font_path = resource_path("font.ttf")
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families: return families[0]
    return "Segoe UI"
APP_FONT_FAMILY = "Segoe UI"

# ==========================================
# Стили
# ==========================================
def get_stylesheet():
    c = config.get_theme_colors()
    accent = c['accent']
    return f"""
    QMainWindow, QDialog, QWidget {{
        background-color: {c['background']};
        color: {c['text']};
        font-family: '{APP_FONT_FAMILY}', Roboto, sans-serif;
    }}
    QPushButton.title-btn {{
        background: transparent;
        border: none;
        color: {c['text_secondary']};
        padding: 6px;
        border-radius: 4px;
    }}
    QPushButton.title-btn:hover {{
        background-color: {c['item_border']};
        color: {c['text']};
    }}
    QPushButton.close-btn:hover {{
        background-color: #e81123;
        color: white;
    }}
    QLineEdit, QComboBox, QListWidget, QKeySequenceEdit {{
        background-color: {c['item_bg']};
        color: {c['text']};
        border: 1px solid {c['item_border']};
        padding: 8px;
        border-radius: 8px;
        selection-background-color: {accent};
        selection-color: {c['background']};
    }}
    QLineEdit:focus, QComboBox:focus, QListWidget:focus, QKeySequenceEdit:focus {{
        border: 2px solid {accent};
    }}
    QPushButton.main-btn {{
        background-color: {accent};
        color: {c['background']};
        border: none;
        padding: 8px 16px;
        border-radius: 12px;
        font-weight: 700;
    }}
    QCheckBox {{ spacing: 8px; color: {c['text']}; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid {c['item_border']}; background: {c['item_bg']}; }}
    QCheckBox::indicator:checked {{ background-color: {accent}; border: 1px solid {accent}; image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0iIzE4MTgxRCIgZD0iTTkgMTYuMTdMNC44MyAxMmwtMS40MiAxLjQxTDkgMTkgMjEgN2wtMS40MS0xLjQxeiIvPjwvc3ZnPg=="); }}
    QMenu {{ background-color: {c['surface']}; color: {c['text']}; border: 1px solid {c['item_border']}; border-radius: 10px; padding: 6px; }}
    QMenu::item {{ padding: 8px 18px; border-radius: 6px; min-width: 160px; color: {c['text']}; }}
    QMenu::item:selected {{ background-color: {accent}; color: {c['surface']}; font-weight: bold; }}
    QLabel#Link {{ color: {accent}; text-decoration: none; }}
    QTextBrowser {{ background-color: {c['item_bg']}; border: 1px solid {c['item_border']}; border-radius: 8px; padding: 10px; }}
    """

# ==========================================
# STORAGE
# ==========================================
class EncryptedStorage:
    KEY = 55
    @staticmethod
    def save(data_dict, path):
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        try:
            json_str = json.dumps(data_dict, ensure_ascii=False)
            chars = [chr(ord(c) ^ EncryptedStorage.KEY) for c in json_str]
            b64_bytes = base64.b64encode("".join(chars).encode('utf-8'))
            with open(path, 'wb') as f: f.write(b64_bytes)
        except Exception as e: print(f"Save failed: {e}")
    @staticmethod
    def load(path):
        if not os.path.exists(path): return None
        try:
            with open(path, 'rb') as f: b64_bytes = f.read()
            xor_str = base64.b64decode(b64_bytes).decode('utf-8')
            json_str = "".join([chr(ord(c) ^ EncryptedStorage.KEY) for c in xor_str])
            return json.loads(json_str)
        except: return None

# ==========================================
# UI COMPONENTS
# ==========================================
class CustomTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(48)
        self.parent = parent
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(8)

        self.icon_lbl = QLabel()
        icon_path = resource_path("icon.png")
        if os.path.exists(icon_path):
             self.icon_lbl.setPixmap(QPixmap(icon_path).scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
             self.icon_lbl.setPixmap(svg_icon_from_string(SVG_LOGO_F, 24, config.get_theme_colors()['accent']).pixmap(24,24))
        
        self.title_lbl = QLabel(f"{APP_NAME}")
        self.title_lbl.setObjectName("TitleLabel")

        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.title_lbl)
        layout.addStretch()

        self.btn_settings = QPushButton()
        self.btn_settings.setFixedSize(36, 36)
        self.btn_settings.setIcon(svg_icon_from_string(SVG_GEAR, 18, config.get_theme_colors()['text_secondary']))
        self.btn_settings.setProperty("class", "title-btn")
        self.btn_settings.clicked.connect(self.parent.open_settings_window)

        c = config.get_theme_colors()
        self.win_col = c['win_controls']

        self.btn_min = QPushButton()
        self.btn_min.setFixedSize(36, 36)
        self.btn_min.setIcon(svg_icon_from_string(SVG_MIN, 14, self.win_col))
        self.btn_min.clicked.connect(self.parent.showMinimized)
        self.btn_min.setProperty("class", "title-btn")

        self.btn_max = QPushButton()
        self.btn_max.setFixedSize(36, 36)
        self.btn_max.setIcon(svg_icon_from_string(SVG_MAX, 14, self.win_col))
        self.btn_max.clicked.connect(self.toggle_max)
        self.btn_max.setProperty("class", "title-btn")

        self.btn_close = QPushButton()
        self.btn_close.setFixedSize(36, 36)
        self.btn_close.setIcon(svg_icon_from_string(SVG_CLOSE, 14, self.win_col))
        self.btn_close.clicked.connect(self.parent.close)
        self.btn_close.setProperty("class", "close-btn")

        layout.addWidget(self.btn_settings)
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

        self.start_pos = None
        self.setMouseTracking(True)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        c = config.get_theme_colors()
        p.fillRect(self.rect(), QColor(c['title_bg']))
        p.setPen(QPen(QColor(c['item_border']), 1))
        p.drawLine(0, self.height()-1, self.width(), self.height()-1)

    def toggle_max(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.btn_max.setIcon(svg_icon_from_string(SVG_MAX, 14, self.win_col))
        else:
            self.parent.showMaximized()
            self.btn_max.setIcon(svg_icon_from_string(SVG_MAX, 14, self.win_col))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.start_pos and not self.parent.isMaximized():
            delta = event.globalPosition().toPoint() - self.start_pos
            self.parent.move(self.parent.x() + delta.x(), self.parent.y() + delta.y())
            self.start_pos = event.globalPosition().toPoint()
            event.accept()
    def mouseReleaseEvent(self, event): self.start_pos = None

class ResizeHandle(QGraphicsItem):
    def __init__(self, parent):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.size = 18
        self.setZValue(100)
    def boundingRect(self):
        p_w = self.parentItem().width
        p_h = self.parentItem().height
        return QRectF(p_w - self.size, p_h - self.size, self.size, self.size)
    def paint(self, painter, option, widget):
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        if lod < 0.5: return

        c = config.get_theme_colors()
        painter.setPen(QPen(QColor(c['text_secondary']), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p_w = self.parentItem().width
        p_h = self.parentItem().height
        s = self.size
        painter.drawLine(QPointF(p_w - s + 8, p_h - 4), QPointF(p_w - 4, p_h - s + 8))
        painter.drawLine(QPointF(p_w - s + 12, p_h - 4), QPointF(p_w - 4, p_h - s + 12))

# ==========================================
# CANVAS OBJECTS (OPTIMIZED)
# ==========================================
class BaseCanvasItem(QGraphicsItem):
    def __init__(self, x, y, width, height, data_model):
        super().__init__()
        self.setPos(x, y)
        self.width, self.height = max(width, 60), max(height, 60)
        self.data_model = data_model
        self.c = config.get_theme_colors()
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        self.setAcceptHoverEvents(True)
        self.resize_handle = ResizeHandle(self)
        self.is_resizing = False
        self.is_hovering = False
        self.resize_start_pos = None
        self.resize_start_dims = None

    def boundingRect(self): return QRectF(-6, -6, self.width + 12, self.height + 12)
    def hoverEnterEvent(self, e): self.is_hovering = True; self.update()
    def hoverLeaveEvent(self, e): self.is_hovering = False; self.update()

    def paint(self, painter, option, widget):
        self.c = config.get_theme_colors()
        lod = option.levelOfDetailFromTransform(painter.worldTransform())

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if lod > 0.4 and not self.isSelected() and self.data_model['type'] != 'area':
            shadow_color = QColor(self.c['shadow'])
            shadow_color.setAlpha(35)
            painter.setBrush(shadow_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(5, 5, self.width, self.height, 14, 14)
        
        bg_col = QColor(self.c['item_bg'])
        if self.data_model['type'] == 'note': bg_col = QColor(self.c['note_bg'])
        if self.data_model['type'] == 'area': bg_col = QColor(self.c['area_bg'])
        painter.setBrush(bg_col)

        pen = QPen()
        if self.isSelected():
            pen = QPen(QColor(self.c['accent']), 3)
        elif self.is_hovering and self.data_model['type'] != 'area':
            pen = QPen(QColor(self.c['accent']).lighter(140), 2)
        else:
            if self.data_model['type'] == 'area':
                pen = QPen(QColor(self.c['area_border']), 2, Qt.PenStyle.DashLine)
            else:
                pen = QPen(QColor(self.c['item_border']), 1)
        painter.setPen(pen)
        painter.drawRoundedRect(0, 0, self.width, self.height, 14, 14)
        
        self.resize_handle.setVisible(self.isSelected() and lod > 0.3)

    def mousePressEvent(self, event):
        if self.resize_handle.isVisible() and self.resize_handle.boundingRect().contains(event.pos()) and self.isSelected():
            self.is_resizing = True
            self.resize_start_pos = event.screenPos()
            self.resize_start_dims = (self.width, self.height)
            event.accept()
        else:
            self.setZValue(self.zValue() + 1)
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_resizing:
            delta = event.screenPos() - self.resize_start_pos
            self.prepareGeometryChange()
            self.width = max(60, self.resize_start_dims[0] + delta.x())
            self.height = max(60, self.resize_start_dims[1] + delta.y())
            self.update()
            self.resize_handle.update()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if self.is_resizing:
            self.is_resizing = False
            if self.scene(): self.scene().notify_change()
        super().mouseReleaseEvent(event)

    def show_context_menu(self, screen_pos):
        menu = QMenu()
        menu.setStyleSheet(get_stylesheet())
        sel = self.scene().selectedItems()
        if self not in sel: sel = [self]
        
        open_act = QAction(svg_icon_from_string(SVG_OPEN, 16), "Открыть", menu)
        loc_act = QAction(svg_icon_from_string(SVG_FOLDER, 16), "Открыть в папке", menu)
        menu.addAction(open_act)
        menu.addAction(loc_act)
        menu.addSeparator()
        
        ren_act = QAction(svg_icon_from_string(SVG_NOTE, 16), "Переименовать", menu) if len(sel) == 1 else None
        if ren_act: menu.addAction(ren_act)
        
        del_act = QAction(svg_icon_from_string(SVG_TRASH, 16), f"Удалить ({len(sel)})", menu)
        menu.addAction(del_act)
        
        action = menu.exec(screen_pos)
        
        if action == del_act:
            scene_ref = self.scene()
            for i in sel: i.setSelected(False)
            for i in sel: scene_ref.removeItem(i)
            scene_ref.notify_change()
        elif action == open_act:
            for i in sel:
                if isinstance(i, FileItem): QDesktopServices.openUrl(QUrl.fromLocalFile(i.file_path))
        elif action == loc_act:
            for i in sel:
                if isinstance(i, FileItem):
                    clean_path = i.file_path.replace("/", "\\")
                    subprocess.Popen(f'explorer /select,"{clean_path}"')
        elif action == ren_act:
            self.handle_rename()

    def handle_rename(self):
        curr = ""
        if isinstance(self, FileItem): curr = self.alias_name
        elif isinstance(self, NoteItem): curr = self.text
        elif isinstance(self, GroupAreaItem): curr = self.title
        res, ok = QInputDialog.getText(None, "Переименовать", "Имя:", text=curr)
        if ok and res:
            if isinstance(self, FileItem):
                self.alias_name = res
                self.data_model['alias'] = res
            elif isinstance(self, NoteItem): self.text = res; self.data_model['text'] = res
            elif isinstance(self, GroupAreaItem): self.title = res; self.data_model['title'] = res
            self.update(); self.scene().notify_change()

class FileItem(BaseCanvasItem):
    def __init__(self, x, y, path, alias=None):
        super().__init__(x, y, 160, 180, {"type": "file", "path": path, "alias": alias})
        self.file_path = path
        self.alias_name = alias if alias else os.path.basename(path)
        self.is_img = self.file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
        self.preview = None
        if self.is_img and os.path.exists(path):
            self.preview = QPixmap(path).scaled(500, 500, Qt.AspectRatioMode.KeepAspectRatio)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        cr = QRectF(10, 10, self.width - 20, self.height - 50)
        
        if lod < 0.2:
            painter.fillRect(cr, QColor(self.c['item_border']))
            return 

        if self.is_img and self.preview:
            path = QPainterPath()
            path.addRoundedRect(cr, 10, 10)
            painter.setClipPath(path)
            painter.drawPixmap(cr.toRect(), self.preview, self.preview.rect())
            painter.setClipping(False)
        else:
            QFileIconProvider().icon(QFileInfo(self.file_path)).paint(painter, int(cr.x()+cr.width()/2-32), int(cr.y()+cr.height()/2-32), 64, 64)
        
        if lod > 0.4:
            painter.setPen(QColor(self.c['text']))
            painter.setFont(QFont(APP_FONT_FAMILY, 10, QFont.Weight.Bold))
            tr = QRectF(5, self.height - 35, self.width - 10, 30)
            painter.drawText(tr, Qt.AlignmentFlag.AlignCenter, painter.fontMetrics().elidedText(self.alias_name, Qt.TextElideMode.ElideMiddle, int(tr.width())))

    def mouseDoubleClickEvent(self, e): QDesktopServices.openUrl(QUrl.fromLocalFile(self.file_path))

class NoteItem(BaseCanvasItem):
    def __init__(self, x, y, text="Note"):
        super().__init__(x, y, 250, 200, {"type": "note", "text": text})
        self.text = text
    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        
        if lod < 0.3:
            painter.setBrush(QColor(self.c['note_text']))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(20, 20, int(self.width-40), 4)
            painter.drawRect(20, 30, int(self.width-60), 4)
            return

        painter.setPen(QColor(self.c['note_text']))
        painter.setFont(QFont(APP_FONT_FAMILY, 12))
        painter.drawText(QRectF(15, 15, self.width - 30, self.height - 30), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, self.text)
    
    def mouseDoubleClickEvent(self, e): self.handle_rename()

class GroupAreaItem(BaseCanvasItem):
    def __init__(self, x, y, title="Group"):
        super().__init__(x, y, 400, 300, {"type": "area", "title": title})
        self.title = title
        self.setZValue(-999)
    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        if lod < 0.2: return

        painter.setPen(QColor(self.c['area_text']))
        painter.setFont(QFont(APP_FONT_FAMILY, 14, QFont.Weight.ExtraBold))
        painter.drawText(QRectF(15, 15, self.width - 30, 40), Qt.AlignmentFlag.AlignLeft, self.title)

# ==========================================
# WINDOWS: GUIDE & SETTINGS
# ==========================================
class GuideWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle("Гайд Focker")
        self.setFixedSize(500, 400)
        self.setStyleSheet(get_stylesheet())
        
        layout = QVBoxLayout(self)
        
        title = QLabel(f"Добро пожаловать в {APP_NAME}!")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont(APP_FONT_FAMILY, 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        text = QTextBrowser()
        text.setHtml(f"""
        <body style="font-family:'{APP_FONT_FAMILY}'; font-size:14px; color:{config.get_theme_colors()['text']};">
            <p>Здравствуйте, пользователи программы. Краткий гайд по проге.</p>
            <ul>
                <li><b>Вставить файл:</b> Перетаскивание (Drag & Drop), кнопка "+", правой кнопкой мыши по пустому месту или Ctrl+V.</li>
                <li><b>Работа с окном:</b> <span style="color:#e81123; font-weight:bold;">При нажатии на крестик ("X") программа не закрывается, а сворачивается в трей (к часам).</span></li>
                <li><b>Полный выход:</b> Чтобы выключить программу полностью, нажмите правой кнопкой на значок в трее и выберите "Выключить полностью".</li>
                <li><b>Оптимизация:</b> Текст и мелкие детали скрываются при отдалении (Zoom Out), чтобы программа работала быстрее.</li>
            </ul>
        </body>
        """)
        text.setOpenExternalLinks(True)
        layout.addWidget(text)
        
        btn = QPushButton("Понятно, погнали!")
        btn.setProperty("class", "main-btn")
        btn.clicked.connect(self.close)
        layout.addWidget(btn)

class SettingsWindow(QDialog):
    def __init__(self, parent=None, hotkey_mgr=None):
        super().__init__(parent)
        self.hotkey_mgr = hotkey_mgr
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle("Настройки Focker")
        self.resize(400, 500)
        self.setStyleSheet(get_stylesheet())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        lbl = QLabel("Настройки")
        lbl.setFont(QFont(APP_FONT_FAMILY, 18, QFont.Weight.Bold))
        layout.addWidget(lbl)
        
        form = QFormLayout()
        
        self.accent_ed = QLineEdit(config.get("accent_color"))
        btn_col = QPushButton("...")
        btn_col.clicked.connect(lambda: self.accent_ed.setText(QColorDialog.getColor(QColor(self.accent_ed.text())).name()))
        h_col = QHBoxLayout()
        h_col.addWidget(self.accent_ed); h_col.addWidget(btn_col)
        form.addRow("Цвет акцента:", h_col)
        
        self.key_seq = QKeySequenceEdit(QKeySequence(config.get("hotkey")))
        form.addRow("Хоткей мини-меню:", self.key_seq)

        self.root_ed = QLineEdit(config.get("root_folder"))
        btn_root = QPushButton("...")
        btn_root.clicked.connect(lambda: self.root_ed.setText(QFileDialog.getExistingDirectory(None, "Папка", self.root_ed.text())))
        h_root = QHBoxLayout()
        h_root.addWidget(self.root_ed); h_root.addWidget(btn_root)
        form.addRow("Папка данных:", h_root)
        
        self.auto_chk = QCheckBox("Запускать с Windows")
        self.auto_chk.setChecked(config.get("autostart"))
        form.addRow(self.auto_chk)
        
        layout.addLayout(form)

        # Кнопка вызова гайда
        btn_guide = QPushButton(" Открыть гайд снова")
        btn_guide.setIcon(svg_icon_from_string(SVG_INFO, 16, config.get_theme_colors()['text']))
        btn_guide.clicked.connect(lambda: GuideWindow(self).exec())
        layout.addWidget(btn_guide)
        
        layout.addStretch()
        
        save = QPushButton("Сохранить и Перезапустить")
        save.setProperty("class", "main-btn")
        save.setFixedHeight(40)
        save.clicked.connect(self.save)
        layout.addWidget(save)
        
        # Info
        dev_lbl = QLabel(f"Focker v{APP_VERSION} by {AUTHOR_INFO['name']}")
        dev_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dev_lbl.setStyleSheet(f"color: {config.get_theme_colors()['text_secondary']}; margin-top:10px;")
        layout.addWidget(dev_lbl)

    def save(self):
        config.set("accent_color", self.accent_ed.text())
        config.set("root_folder", self.root_ed.text())
        config.set("autostart", self.auto_chk.isChecked())
        seq_str = self.key_seq.keySequence().toString()
        if not seq_str: seq_str = "Ctrl+M"
        config.set("hotkey", seq_str)
        AutostartManager.set_state(self.auto_chk.isChecked())
        QApplication.quit()
        subprocess.Popen([sys.executable, sys.argv[0]])

# ==========================================
# MINI MODE
# ==========================================
class MiniFileList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setStyleSheet("border: none; background: transparent;")
    def startDrag(self, actions):
        item = self.currentItem()
        if not item: return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(item.data(Qt.ItemDataRole.UserRole))])
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

class MiniModeWindow(QWidget):
    def __init__(self, scene_ref):
        super().__init__()
        self.scene_ref = scene_ref
        
        icon_path = resource_path("icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            self.setWindowIcon(svg_icon_from_string(SVG_LOGO_F, 64, config.get_theme_colors()['accent']))
        
        self.setWindowTitle("Mini Focker")

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(300, 400)
        scr = QApplication.primaryScreen().geometry()
        self.move(scr.width() - 320, scr.height() - 450)
        c = config.get_theme_colors()
        self.setStyleSheet(f"""
            QWidget {{ background-color: {c['surface']}; border: 2px solid {c['accent']}; border-radius: 12px; }}
            QListWidget {{ background: {c['item_bg']}; border: none; margin: 5px; border-radius: 8px; }}
            QListWidget::item {{ color: {c['text']}; padding: 10px; border-bottom: 1px solid {c['grid']}; }}
            QListWidget::item:hover {{ background: {c['area_bg']}; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) 
        
        header_widget = QWidget()
        header_widget.setStyleSheet(f"background-color: {c['title_bg']}; border-top-left-radius: 10px; border-top-right-radius: 10px; border: none;")
        h_layout = QHBoxLayout(header_widget)
        h_layout.setContentsMargins(15, 8, 10, 8)
        
        title_lbl = QLabel("Mini Focker")
        title_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 16px; border: none; background: transparent;")
        h_layout.addWidget(title_lbl)
        
        h_layout.addStretch()
        
        cls = QPushButton()
        cls.setIcon(svg_icon_from_string(SVG_CLOSE, 14, "#FFFFFF"))
        cls.setFixedSize(24, 24)
        cls.setStyleSheet("background:transparent; border:none;")
        cls.setCursor(Qt.CursorShape.PointingHandCursor)
        cls.clicked.connect(self.hide)
        h_layout.addWidget(cls)
        
        layout.addWidget(header_widget)
        
        self.list = MiniFileList()
        layout.addWidget(self.list)
        self.old_pos = None

    def refresh_list(self):
        self.list.clear()
        for item in self.scene_ref.items():
            if isinstance(item, FileItem):
                li = QListWidgetItem(item.alias_name)
                li.setData(Qt.ItemDataRole.UserRole, item.file_path)
                li.setIcon(QFileIconProvider().icon(QFileInfo(item.file_path)))
                self.list.addItem(li)

    def show_animated(self):
        self.refresh_list()
        self.show()

    def hide_animated(self):
        self.hide()
    
    def mousePressEvent(self, e): self.old_pos = e.globalPosition().toPoint()
    def mouseMoveEvent(self, e):
        if self.old_pos:
            self.move(self.pos() + e.globalPosition().toPoint() - self.old_pos)
            self.old_pos = e.globalPosition().toPoint()
    def mouseReleaseEvent(self, e): self.old_pos = None

# ==========================================
# SCENE & VIEW
# ==========================================
class InfiniteScene(QGraphicsScene):
    change_occurred = pyqtSignal()
    def __init__(self):
        super().__init__()
        # Use BSP Tree Indexing for Viewport Culling
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)
        self.setSceneRect(-50000, -50000, 100000, 100000)
        self.setBackgroundBrush(QColor(config.get_theme_colors()['background']))
        self.parent_view = None
    
    def notify_change(self): self.change_occurred.emit()
    
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        c = config.get_theme_colors()
        painter.setPen(QPen(QColor(c['grid']), 1))
        # Оптимизация сетки: рисуем только в rect
        l, t = int(rect.left()) - int(rect.left())%50, int(rect.top()) - int(rect.top())%50
        for x in range(l, int(rect.right()), 50):
            for y in range(t, int(rect.bottom()), 50): painter.drawPoint(x, y)
    
    def add_file_item(self, x, y, p, alias=None): 
        i = FileItem(x, y, p, alias)
        self.addItem(i)
        return i
        
    def contextMenuEvent(self, e):
        item = self.itemAt(e.scenePos(), QTransform())
        while item and item.parentItem(): item = item.parentItem()
        
        if isinstance(item, BaseCanvasItem): 
            item.show_context_menu(e.screenPos())
        else:
            self.create_general_menu(e.scenePos(), e.screenPos())

    def create_general_menu(self, scene_pos, screen_pos):
        menu = QMenu()
        menu.setStyleSheet(get_stylesheet())
        act_f = menu.addAction(svg_icon_from_string(SVG_FOLDER, 16), "Файл")
        act_n = menu.addAction(svg_icon_from_string(SVG_NOTE, 16), "Заметка")
        act_a = menu.addAction(svg_icon_from_string(SVG_BACKDROP, 16), "Задний фон")
        menu.addSeparator()
        act_p = menu.addAction(svg_icon_from_string(SVG_PASTE, 16), "Вставить (Ctrl+V)")
        
        res = menu.exec(screen_pos)
        
        if res == act_f:
            p, _ = QFileDialog.getOpenFileName(None, "Файл")
            if p: self.add_file_item(scene_pos.x(), scene_pos.y(), p); self.notify_change()
        elif res == act_n: self.addItem(NoteItem(scene_pos.x(), scene_pos.y(), "Текст...")); self.notify_change()
        elif res == act_a: self.addItem(GroupAreaItem(scene_pos.x(), scene_pos.y(), "Фон")); self.notify_change()
        elif res == act_p: self.parent_view.paste_cb(scene_pos.x(), scene_pos.y())

class CanvasView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        scene.parent_view = self
        
        # ОПТИМИЗАЦИЯ Viewport
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        
        self.setOptimizationFlags(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing)
        
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)
        self.panning = False
        
        self.fab = QToolButton(self)
        self.fab.setIcon(svg_icon_from_string(SVG_PLUS, 28, config.get_theme_colors()['background']))
        self.fab.setFixedSize(64, 64)
        self.fab.setStyleSheet(f"background-color: {config.get_theme_colors()['accent']}; border-radius: 32px;")
        self.fab.clicked.connect(self.show_import_menu)
    
    def resizeEvent(self, e): super().resizeEvent(e); self.fab.move(self.width()-90, self.height()-90)
    
    def show_import_menu(self):
        center_scene_pos = self.mapToScene(self.viewport().rect().center())
        self.scene().create_general_menu(center_scene_pos, QCursor.pos())

    def paste_cb(self, x, y):
        md = QApplication.clipboard().mimeData()
        if md.hasUrls(): 
            for u in md.urls(): self.scene().add_file_item(x, y, u.toLocalFile())
        elif md.hasText(): self.scene().addItem(NoteItem(x, y, md.text()))
        elif md.hasImage() and not md.imageData().isNull():
             path = Path(config.get("root_folder"))/"clipboard_images"/f"paste_{int(time.time())}.png"
             path.parent.mkdir(parents=True, exist_ok=True)
             md.imageData().save(str(path))
             self.scene().add_file_item(x, y, str(path))
        self.scene().notify_change()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
        else: super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
        else: super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            pos = self.mapToScene(e.position().toPoint())
            for u in e.mimeData().urls():
                self.scene().add_file_item(pos.x(), pos.y(), u.toLocalFile())
            self.scene().notify_change()
            e.acceptProposedAction()
        else:
            super().dropEvent(e)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Paste):
            cursor_pos = self.mapFromGlobal(QCursor.pos())
            if not self.rect().contains(cursor_pos):
                scene_pos = self.mapToScene(self.viewport().rect().center())
            else:
                scene_pos = self.mapToScene(cursor_pos)
            self.paste_cb(scene_pos.x(), scene_pos.y())
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.MiddleButton:
            self.panning = True; self.start_pan = e.pos(); self.setCursor(Qt.CursorShape.ClosedHandCursor); e.accept()
        else: super().mousePressEvent(e)
    def mouseMoveEvent(self, e):
        if self.panning:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - (e.pos().x()-self.start_pan.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - (e.pos().y()-self.start_pan.y()))
            self.start_pan = e.pos(); e.accept()
        else: super().mouseMoveEvent(e)
    def mouseReleaseEvent(self, e):
        if self.panning: self.panning = False; self.setCursor(Qt.CursorShape.ArrowCursor)
        else: super().mouseReleaseEvent(e)
    def wheelEvent(self, e): self.scale(1.1, 1.1) if e.angleDelta().y() > 0 else self.scale(1/1.1, 1/1.1)

# ==========================================
# MAIN WINDOW
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(1000, 700)
        self.setWindowTitle(APP_NAME)
        
        # FIX: Загружаем иконку из файла
        icon_path = resource_path("icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            self.setWindowIcon(svg_icon_from_string(SVG_LOGO_F, 64, config.get_theme_colors()['accent']))
        
        main_w = QWidget()
        self.setCentralWidget(main_w)
        layout = QVBoxLayout(main_w)
        layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        
        self.title_bar = CustomTitleBar(self)
        layout.addWidget(self.title_bar)
        
        self.scene = InfiniteScene()
        self.view = CanvasView(self.scene)
        layout.addWidget(self.view)
        
        self.ghk = GlobalHotkeyManager()
        self.ghk.activated.connect(self.toggle_mini_mode)
        self.ghk.start()

        self.project_path = Path(config.get("root_folder")) / "focker.dat"
        self.load_data()
        self.scene.change_occurred.connect(self.save_data)
        
        self.mini = MiniModeWindow(self.scene)
        self.mini.hide()
        
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.windowIcon()) # Иконка трея берется из иконки окна
        self.tray.setToolTip(APP_NAME)
        
        tray_menu = QMenu()
        tray_menu.setStyleSheet(get_stylesheet())
        
        act_show = QAction("Открыть", self)
        act_show.triggered.connect(self.showNormal)
        
        act_quit = QAction("Выключить полностью", self)
        act_quit.triggered.connect(self.force_quit)
        
        tray_menu.addAction(act_show)
        tray_menu.addAction(act_quit)
        
        self.tray.setContextMenu(tray_menu)
        self.tray.show()
        
        self.tray.activated.connect(self.tray_icon_activated)

        if config.get("first_run"):
            QApplication.processEvents()
            GuideWindow(self).exec()
            config.set("first_run", False)

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()

    def open_settings_window(self):
        SettingsWindow(self, self.ghk).exec()

    def toggle_mini_mode(self):
        if self.mini.isVisible(): self.mini.hide_animated()
        else: self.mini.show_animated()

    def load_data(self):
        d = EncryptedStorage.load(str(self.project_path))
        if not d: return
        for i in d:
            if i['type'] == 'file': 
                alias = i.get('alias', None)
                item = self.scene.add_file_item(i['x'], i['y'], i['path'], alias)
                item.width = i['w']
                item.height = i.get('h', item.height)
            elif i['type'] == 'note':
                it = NoteItem(i['x'], i['y'], i['text']); self.scene.addItem(it); it.width, it.height = i['w'], i['h']
            elif i['type'] == 'area':
                it = GroupAreaItem(i['x'], i['y'], i['title']); self.scene.addItem(it); it.width, it.height = i['w'], i['h']

    def save_data(self):
        out = []
        for i in self.scene.items():
            if isinstance(i, BaseCanvasItem):
                d = {'type': i.data_model['type'], 'x': i.x(), 'y': i.y(), 'w': i.width, 'h': i.height}
                if isinstance(i, FileItem): 
                    d['path'] = i.file_path
                    d['alias'] = i.alias_name
                elif isinstance(i, NoteItem): d['text'] = i.text
                elif isinstance(i, GroupAreaItem): d['title'] = i.title
                out.append(d)
        EncryptedStorage.save(out, str(self.project_path))

    def closeEvent(self, e):
        if self.tray.isVisible():
            e.ignore()
            self.hide()
            self.save_data()
        else:
            self.force_quit()

    def force_quit(self):
        self.save_data()
        self.mini.close()
        self.ghk.stop()
        QApplication.quit()

if __name__ == '__main__':
    # --- ИСПРАВЛЕНИЕ ИКОНКИ В ПАНЕЛИ ЗАДАЧ ---
    if os.name == 'nt':
        try:
            # Уникальный ID: "Author.Product.SubProduct.Version"
            myappid = f'yarootie.focker.app.{APP_VERSION}'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except ImportError:
            pass
    # -----------------------------------------

    app = QApplication(sys.argv)
    
    # Устанавливаем иконку глобально для всего приложения
    icon_path = resource_path("icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        app.setWindowIcon(svg_icon_from_string(SVG_LOGO_F, 64, "#00bcd4"))

    APP_FONT_FAMILY = load_custom_font()
    app.setFont(QFont(APP_FONT_FAMILY, 9))
    
    win = MainWindow()
    win.show()
    sys.exit(app.exec())