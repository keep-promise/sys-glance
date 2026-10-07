# -*- coding: utf-8 -*-
"""菜单二：实时监控——CPU / GPU / 内存三张指标卡片 + 温度趋势图 + 控制栏。"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.config import load_config, save_config
from core.sensors import SystemSample
from ui.widgets.metric_card import (
    GRAY,
    MEM_TH,
    PERCENT_TH,
    TEMP_TH,
    MetricCard,
    color_for,
)
from ui.widgets.trend_chart import TrendChart

INTERVALS = {  # 显示文本 → 毫秒
    "1 秒": 1000,
    "2 秒": 2000,
    "3 秒": 3000,
    "5 秒": 5000,
}


class SettingsDialog(QDialog):
    """监控设置：采样间隔 + 趋势窗口。"""

    def __init__(self, interval_ms: int, trend_seconds: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("监控设置")
        self.setModal(True)

        form = QFormLayout(self)
        self._interval = QSpinBox()
        self._interval.setRange(200, 60000)
        self._interval.setSingleStep(100)
        self._interval.setSuffix(" 毫秒")
        self._interval.setValue(interval_ms)
        form.addRow("采样间隔", self._interval)

        self._trend = QSpinBox()
        self._trend.setRange(10, 600)
        self._trend.setSingleStep(10)
        self._trend.setSuffix(" 秒")
        self._trend.setValue(trend_seconds)
        form.addRow("趋势窗口", self._trend)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def values(self) -> tuple[int, int]:
        return self._interval.value(), self._trend.value()


class MonitorTab(QWidget):
    """实时监控：三卡片并排 + 趋势图 + 控制栏。"""

    interval_changed = pyqtSignal(int)   # 毫秒
    trend_window_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = load_config()
        self._interval_ms = int(self._config.get("sampling_interval_ms", 1000))
        self._trend_seconds = int(self._config.get("trend_seconds", 60))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        # ---- 三张指标卡片 ----
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self._cpu_card = MetricCard("CPU", "🔥")
        self._gpu_card = MetricCard("GPU", "🎮")
        self._mem_card = MetricCard("内存", "🧠")
        for c in (self._cpu_card, self._gpu_card, self._mem_card):
            cards.addWidget(c)
        lay.addLayout(cards)

        # ---- 趋势图 ----
        trend_title = QLabel("趋势图（最近 60 秒）")
        trend_title.setStyleSheet("color:#555F6E; font-size:12px; font-weight:bold;")
        lay.addWidget(trend_title)
        self._chart = TrendChart(window_seconds=self._trend_seconds)
        lay.addWidget(self._chart, 1)

        # ---- 控制栏 ----
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)
        ctrl.addWidget(QLabel("采样间隔:"))
        self._interval_box = QComboBox()
        for label in INTERVALS:
            self._interval_box.addItem(label)
        self._interval_box.setCurrentText(self._label_for_ms(self._interval_ms))
        self._interval_box.currentTextChanged.connect(self._on_interval_changed)
        ctrl.addWidget(self._interval_box)

        self._pause_btn = QPushButton("⏸ 暂停")
        self._pause_btn.clicked.connect(self._on_pause_clicked)
        ctrl.addWidget(self._pause_btn)

        self._settings_btn = QPushButton("⚙ 设置")
        self._settings_btn.clicked.connect(self._on_settings_clicked)
        ctrl.addWidget(self._settings_btn)
        ctrl.addStretch(1)
        lay.addLayout(ctrl)

        self._paused = False
        self._last_warned_admin = False

    # ---- 控制 ----
    def _label_for_ms(self, ms: int) -> str:
        for label, v in INTERVALS.items():
            if v == ms:
                return label
        return "1 秒"

    def _on_interval_changed(self, label: str) -> None:
        ms = INTERVALS.get(label, 1000)
        self._interval_ms = ms
        self._config["sampling_interval_ms"] = ms
        save_config(self._config)
        self.interval_changed.emit(ms)

    def _on_pause_clicked(self) -> None:
        self._paused = not self._paused
        self._pause_btn.setText("▶ 继续" if self._paused else "⏸ 暂停")

    @property
    def paused(self) -> bool:
        return self._paused

    def _on_settings_clicked(self) -> None:
        dlg = SettingsDialog(self._interval_ms, self._trend_seconds, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            ms, trend = dlg.values()
            self._interval_ms = ms
            self._trend_seconds = trend
            self._config["sampling_interval_ms"] = ms
            self._config["trend_seconds"] = trend
            save_config(self._config)
            self._interval_box.setCurrentText(self._label_for_ms(ms))
            self.interval_changed.emit(ms)
            self.trend_window_changed.emit(trend)

    def on_trend_window_changed(self, seconds: int) -> None:
        self._chart.set_window(seconds)
        self._chart.clear()

    # ---- 数据更新 ----
    def update_sample(self, sample: SystemSample) -> None:
        if self._paused:
            return

        # CPU
        ct = sample.cpu.temp
        ccolor = color_for(ct, TEMP_TH)
        self._cpu_card.update_metrics(
            big_text=(f"{ct:.0f}°C" if ct is not None else "温度 --"),
            big_color=ccolor if ct is not None else GRAY,
            percent=sample.cpu.percent,
            percent_thresholds=PERCENT_TH,
            sub_text=f"{sample.cpu.percent:.0f}%  ·  {sample.cpu.freq_mhz / 1000:.2f} GHz"
            if sample.cpu.freq_mhz else f"{sample.cpu.percent:.0f}%",
        )

        # GPU
        gt = sample.gpu.temp
        gcolor = color_for(gt, TEMP_TH)
        if sample.has_gpu:
            gsub = f"{sample.gpu.percent:.0f}%  ·  显存 {sample.gpu.mem_used:.1f}/{sample.gpu.mem_total:.0f}G"
            self._gpu_card.update_metrics(
                big_text=(f"{gt:.0f}°C" if gt is not None else "温度 --"),
                big_color=gcolor if gt is not None else GRAY,
                percent=sample.gpu.percent if sample.gpu.percent > 0 else None,
                percent_thresholds=PERCENT_TH,
                sub_text=gsub,
            )
        else:
            self._gpu_card.update_metrics("--", GRAY, None, PERCENT_TH, "未检测到 NVIDIA GPU")

        # 内存
        mp = sample.mem.percent
        self._mem_card.update_metrics(
            big_text=f"{mp:.0f}%",
            big_color=color_for(mp, MEM_TH),
            percent=mp,
            percent_thresholds=MEM_TH,
            sub_text=f"{sample.mem.used:.1f} / {sample.mem.total:.0f} GB",
        )

        # 趋势图
        self._chart.append(ct, gt if sample.has_gpu else None)
        self._chart.refresh()

    def reset_chart(self) -> None:
        self._chart.clear()
        self._chart.refresh()
