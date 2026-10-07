# -*- coding: utf-8 -*-
"""采集调度器：独立 QThread 负责实时采样，静态信息后台加载。

两个线程互不阻塞 UI：
  - CollectorThread  每 interval_ms 采集一次实时数据，发 sample_ready 信号
  - StaticInfoThread 后台加载硬件静态信息，完成后发 ready 信号
"""
from __future__ import annotations

import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal

from core import hardware_info
from core.sensors import SensorCollector, SystemSample


class CollectorThread(QThread):
    """实时采样线程（CPU/GPU/内存）。"""

    sample_ready = pyqtSignal(object)  # SystemSample

    def __init__(self, interval_ms: int = 1000, parent=None) -> None:
        super().__init__(parent)
        self._interval = max(200, int(interval_ms)) / 1000.0
        self._collector = SensorCollector()
        self._go = threading.Event()
        self._running = True

    # ---- 控制 ----
    def set_interval(self, ms: int) -> None:
        self._interval = max(200, int(ms)) / 1000.0

    def pause(self) -> None:
        self._go.clear()

    def resume(self) -> None:
        self._go.set()

    def stop(self) -> None:
        self._running = False
        self._go.set()

    # ---- 主循环 ----
    def run(self) -> None:  # noqa: D102
        self._go.set()
        while self._running:
            self._go.wait()            # 暂停时在此阻塞
            if not self._running:
                break
            try:
                sample: SystemSample = self._collector.collect()
                self.sample_ready.emit(sample)
            except Exception:
                pass
            time.sleep(self._interval)


class StaticInfoThread(QThread):
    """后台加载静态硬件信息（WMI 较慢，避免卡 UI）。"""

    ready = pyqtSignal(dict)

    def __init__(self, force: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._force = force

    def run(self) -> None:  # noqa: D102
        try:
            data = hardware_info.get_hardware_info(force=self._force)
        except Exception:
            data = {c: [] for c in hardware_info.CATEGORIES}
        self.ready.emit(data)
