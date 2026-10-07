# -*- coding: utf-8 -*-
"""趋势图组件：基于 pyqtgraph，绘制最近 N 秒的 CPU / GPU 温度曲线。"""
from __future__ import annotations

from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QVBoxLayout, QWidget

pg.setConfigOptions(antialias=True, background="white", foreground="#333333")

CPU_COLOR = "#3498DB"
GPU_COLOR = "#E67E22"


class TrendChart(QWidget):
    """轻量趋势图：环形缓冲，时间轴为"距今 -N 秒"，自动滚动。"""

    def __init__(self, window_seconds: int = 60, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("left", "温度", units="°C")
        self._plot.setLabel("bottom", "时间（秒）")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.addLegend(offset=(10, 6))
        self._cpu_curve = self._plot.plot(pen=pg.mkPen(CPU_COLOR, width=2), name="CPU 温度")
        self._gpu_curve = self._plot.plot(pen=pg.mkPen(GPU_COLOR, width=2), name="GPU 温度")

        # 中文标签字体
        tick_font = QFont("Microsoft YaHei", 9)
        for axis in ("left", "bottom"):
            self._plot.getAxis(axis).setTickFont(tick_font)

        self._window = max(10, window_seconds)
        self._cpu: deque[float] = deque(maxlen=self._window)
        self._gpu: deque[float] = deque(maxlen=self._window)
        lay.addWidget(self._plot)

    def set_window(self, seconds: int) -> None:
        self._window = max(10, seconds)
        self._cpu = deque(self._cpu, maxlen=self._window)
        self._gpu = deque(self._gpu, maxlen=self._window)

    def append(self, cpu_temp: float | None, gpu_temp: float | None) -> None:
        self._cpu.append(float("nan") if cpu_temp is None else float(cpu_temp))
        self._gpu.append(float("nan") if gpu_temp is None else float(gpu_temp))

    def clear(self) -> None:
        self._cpu.clear()
        self._gpu.clear()

    def refresh(self) -> None:
        """用 setData 增量更新（数据不足 2 点时清空曲线）。"""
        n = len(self._cpu)
        if n < 2:
            self._cpu_curve.setData([], [])
            self._gpu_curve.setData([], [])
            return
        x = np.arange(-n + 1, 1, dtype=float)  # 距今 -n+1 .. 0 秒
        cpu_y = np.array(self._cpu, dtype=float)
        gpu_y = np.array(self._gpu, dtype=float)
        self._cpu_curve.setData(x, cpu_y)  # nan 自动断线
        self._gpu_curve.setData(x, gpu_y)
        self._plot.enableAutoRange(axis="y", enable=True)
