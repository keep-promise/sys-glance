# -*- coding: utf-8 -*-
"""系统托盘：显示/隐藏窗口、切换 Tab、开机自启、退出。"""
from __future__ import annotations

import sys

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.config import APP_NAME

# Windows 开机自启注册表位置
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE = "SysGlance"


def make_tray_icon(size: int = 64) -> QIcon:
    """自绘托盘图标：蓝底圆角方块 + 白色仪表折线。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    margin = int(size * 0.06)
    body = QRect(margin, margin, size - 2 * margin, size - 2 * margin)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#3B82F6"))
    p.drawRoundedRect(body, int(size * 0.18), int(size * 0.18))
    # 折线（温度曲线）
    pen = QPen(QColor("white"), max(2, int(size * 0.06)), Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    w, h = body.width(), body.height()
    pts = [
        QPoint(body.x() + int(w * 0.12), body.y() + int(h * 0.72)),
        QPoint(body.x() + int(w * 0.30), body.y() + int(h * 0.52)),
        QPoint(body.x() + int(w * 0.48), body.y() + int(h * 0.64)),
        QPoint(body.x() + int(w * 0.66), body.y() + int(h * 0.38)),
        QPoint(body.x() + int(w * 0.88), body.y() + int(h * 0.22)),
    ]
    for i in range(len(pts) - 1):
        p.drawLine(pts[i], pts[i + 1])
    # 端点圆点
    p.setBrush(QColor("white"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(pts[-1], int(size * 0.06), int(size * 0.06))
    p.end()
    return QIcon(pm)


def autostart_enabled() -> bool:
    """当前是否已设置开机自启。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.QueryValueEx(k, _RUN_VALUE)
            return True
    except OSError:
        return False


def _entry_command() -> str:
    """开机自启命令：打包后指向 exe，否则 python + main.py。"""
    import os
    if getattr(sys, "frozen", False):  # PyInstaller 打包后
        return f'"{sys.executable}"'
    here = os.path.dirname(os.path.abspath(__file__))
    main_py = os.path.join(os.path.dirname(here), "main.py")
    if not os.path.exists(main_py):
        main_py = sys.argv[0]
    return f'"{sys.executable}" "{main_py}"'


def set_autostart(enabled: bool) -> bool:
    """设置/取消开机自启（HKCU Run，无需管理员）。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, _RUN_VALUE, 0, winreg.REG_SZ, _entry_command())
            else:
                try:
                    winreg.DeleteValue(k, _RUN_VALUE)
                except OSError:
                    pass
        return True
    except Exception:
        return False


class TrayIcon(QSystemTrayIcon):
    """托盘图标 + 右键菜单。"""

    show_hide_requested = pyqtSignal()
    tab_requested = pyqtSignal(int)   # 0 总览 / 1 监控
    quit_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(make_tray_icon(), parent)
        self.setToolTip(APP_NAME)

        self._menu = QMenu()
        self._toggle_action = QAction("显示 / 隐藏窗口", self._menu)
        self._toggle_action.triggered.connect(self.show_hide_requested.emit)
        self._menu.addAction(self._toggle_action)

        self._menu.addSeparator()
        self._switch_overview = QAction("切换到系统总览", self._menu)
        self._switch_overview.triggered.connect(lambda: self.tab_requested.emit(0))
        self._switch_monitor = QAction("切换到实时监控", self._menu)
        self._switch_monitor.triggered.connect(lambda: self.tab_requested.emit(1))
        self._menu.addAction(self._switch_overview)
        self._menu.addAction(self._switch_monitor)

        self._menu.addSeparator()
        self._autostart_action = QAction("开机自启", self._menu)
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(autostart_enabled())
        self._autostart_action.toggled.connect(set_autostart)
        self._menu.addAction(self._autostart_action)

        self._menu.addSeparator()
        self._quit_action = QAction("退出", self._menu)
        self._quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(self._quit_action)

        self.setContextMenu(self._menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # 左键单击
            self.show_hide_requested.emit()

    def refresh_autostart(self) -> None:
        self._autostart_action.setChecked(autostart_enabled())
