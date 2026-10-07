# -*- coding: utf-8 -*-
"""主窗口：顶部标签页整合两个菜单 + 共享采集线程 + 系统托盘。"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QWidget,
)

from core import hardware_info
from core.collector import CollectorThread, StaticInfoThread
from core.config import load_config, save_config
from ui.monitor_tab import MonitorTab
from ui.overview_tab import OverviewTab
from ui.tray import TrayIcon

TAB_NAMES = ["📋 系统总览", "📊 实时监控"]


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = load_config()
        self.setWindowTitle("SysGlance — 系统总览与实时监控")
        self.setMinimumSize(820, 560)

        # ---- 顶部标签页 ----
        self._tabs = QTabWidget(self)
        self._tabs.setDocumentMode(True)
        self._tabs.tabBar().setExpanding(False)
        self._tabs.setStyleSheet(
            "QTabBar::tab { padding:8px 26px; font-size:13px; font-weight:bold;"
            " color:#6B7280; border:1px solid #E2E6ED; border-bottom:none;"
            " border-top-left-radius:6px; border-top-right-radius:6px; background:#F5F7FA; }"
            "QTabBar::tab:selected { color:#3B82F6; background:white; }"
        )
        self._overview = OverviewTab(self)
        self._monitor = MonitorTab(self)
        self._tabs.addTab(self._overview, TAB_NAMES[0])
        self._tabs.addTab(self._monitor, TAB_NAMES[1])
        self.setCentralWidget(self._tabs)

        # ---- 状态栏 ----
        sb = QStatusBar(self)
        self._status_label = QLabel("初始化…")
        sb.addWidget(self._status_label)
        self.setStatusBar(sb)

        # ---- 窗口位置恢复 ----
        self._restore_window_state()

        # ---- 托盘 ----
        self._tray = TrayIcon(self)
        self._tray.show_hide_requested.connect(self.toggle_visible)
        self._tray.tab_requested.connect(self.switch_tab)
        self._tray.quit_requested.connect(self.quit_application)
        self._tray.show()

        # ---- 权限检测 ----
        self._admin = hardware_info.is_admin()
        if not self._admin:
            self._status_label.setText(
                "⚠ 当前非管理员权限：温度将显示 --（温度需要 LibreHardwareMonitor 或管理员权限）"
            )

        # ---- 采集线程 ----
        interval = int(self._config.get("sampling_interval_ms", 1000))
        self._collector = CollectorThread(interval_ms=interval, parent=self)
        self._collector.sample_ready.connect(self._monitor.update_sample)
        self._monitor.interval_changed.connect(self._on_interval_changed)
        self._monitor.trend_window_changed.connect(self._monitor.on_trend_window_changed)
        self._collector.start()

        # ---- 静态信息后台加载 ----
        self._static_loader = StaticInfoThread(force=False, parent=self)
        self._static_loader.ready.connect(self._on_static_ready)
        self._static_loader.start()

        # ---- 恢复上次 Tab ----
        last_tab = int(self._config.get("last_tab", 0))
        if last_tab in (0, 1):
            self._tabs.setCurrentIndex(last_tab)

    # ------------------------------------------------------------------
    # 窗口状态
    # ------------------------------------------------------------------
    def _restore_window_state(self) -> None:
        w = self._config.get("window", {})
        x, y = w.get("x"), w.get("y")
        width = int(w.get("width", 980))
        height = int(w.get("height", 640))
        self.resize(width, height)
        if x is not None and y is not None:
            self.move(int(x), int(y))

    def _save_window_state(self) -> None:
        self._config["window"] = {
            "x": self.x(), "y": self.y(),
            "width": self.width(), "height": self.height(),
        }
        self._config["last_tab"] = self._tabs.currentIndex()
        save_config(self._config)

    # ------------------------------------------------------------------
    # 槽
    # ------------------------------------------------------------------
    def _on_static_ready(self, data: dict) -> None:
        self._overview.set_data(data)
        self._status_label.setText("就绪" if self._admin else self._status_label.text())

    def _on_interval_changed(self, ms: int) -> None:
        self._collector.set_interval(ms)
        if self._collector.isRunning() and not self._collector.isPaused():
            pass

    def switch_tab(self, index: int) -> None:
        if index in (0, 1):
            self._tabs.setCurrentIndex(index)

    def toggle_visible(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def quit_application(self) -> None:
        """停止线程、保存状态并退出（安全路径，供托盘/关闭/退出信号调用）。"""
        self._save_window_state()
        self._stop_threads()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _stop_threads(self) -> None:
        self._collector.stop()
        self._collector.wait(8000)
        if self._static_loader.isRunning():
            self._static_loader.wait(8000)

    # ------------------------------------------------------------------
    # 关闭行为：最小化到托盘
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        if self._tray.isVisible():
            self._save_window_state()
            self.hide()
            self._tray.showMessage(
                "SysGlance", "仍在后台运行，可从托盘恢复。右键托盘图标可退出。",
                TrayIcon.MessageIcon.Information, 2000,
            )
            event.ignore()
        else:
            self._stop_threads()
            event.accept()
