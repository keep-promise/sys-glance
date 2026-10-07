# -*- coding: utf-8 -*-
"""指标卡片组件：实时监控 Tab 中 CPU / GPU / 内存 的紧凑卡片。

布局（按需求 3.1）：标题、主指标大字（温度或占用率）、进度条 + 副指标。
颜色规则（需求 3.3）：
  温度   <70 绿 | 70–85 黄 | >85 红
  占用率 <60 绿 | 60–85 黄 | >85 红
  内存   <70 绿 | 70–90 黄 | >90 红
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPainter
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget

GREEN = "#27AE60"
YELLOW = "#F39C12"
RED = "#E74C3C"
GRAY = "#9AA4B2"

TEMP_TH = (70.0, 85.0)      # 正常/警告/危险
PERCENT_TH = (60.0, 85.0)   # CPU/GPU 占用
MEM_TH = (70.0, 90.0)       # 内存占用


def color_for(value: Optional[float], thresholds: tuple[float, float], default: str = GRAY) -> str:
    if value is None:
        return default
    if value < thresholds[0]:
        return GREEN
    if value < thresholds[1]:
        return YELLOW
    return RED


class _RoundBar(QProgressBar):
    """圆角进度条，可动态改颜色。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTextVisible(False)
        self.setFixedHeight(16)
        self.setStyleSheet(self._css(GREEN))

    def _css(self, color: str) -> str:
        return (
            "QProgressBar { background:#EDF0F5; border:none; border-radius:8px; }"
            f"QProgressBar::chunk {{ background:{color}; border-radius:8px; }}"
        )

    def paintEvent(self, event: QPainter | None = None) -> None:  # noqa: D102
        super().paintEvent(event)

    def set_value(self, value: Optional[float], thresholds: tuple[float, float]) -> None:
        if value is None:
            self.setValue(0)
            self.setStyleSheet(self._css(GRAY))
            return
        self.setValue(int(min(100.0, max(0.0, value))))
        self.setStyleSheet(self._css(color_for(value, thresholds)))


class MetricCard(QFrame):
    """单个监控指标卡片。"""

    def __init__(self, title: str, icon: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setStyleSheet(
            "#metricCard { background:white; border:1px solid #E2E6ED; border-radius:10px; }"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        # 标题行：图标 + 名称
        head = QHBoxLayout()
        head.setSpacing(6)
        self._icon = QLabel(icon)
        self._icon.setStyleSheet("font-size:16px;")
        self._name = QLabel(title)
        nf = QFont(self._name.font())
        nf.setPointSize(11)
        nf.setBold(True)
        self._name.setFont(nf)
        head.addWidget(self._icon)
        head.addWidget(self._name)
        head.addStretch(1)
        lay.addLayout(head)

        # 主指标大字
        self._big = QLabel("--")
        bf = QFont(self._big.font())
        bf.setPointSize(26)
        bf.setBold(True)
        self._big.setFont(bf)
        self._big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._big)

        # 进度条 + 副指标
        self._bar = _RoundBar(self)
        lay.addWidget(self._bar)
        self._sub = QLabel("")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sf = QFont(self._sub.font())
        sf.setPointSize(9)
        self._sub.setFont(sf)
        self._sub.setStyleSheet(f"color:{GRAY};")
        lay.addWidget(self._sub)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # ---- 更新入口 ----
    def update_metrics(
        self,
        big_text: str,
        big_color: str,
        percent: Optional[float],
        percent_thresholds: tuple[float, float],
        sub_text: str,
    ) -> None:
        """通用更新：大字 + 进度条 + 副文本。"""
        self._big.setText(big_text)
        self._big.setStyleSheet(f"color:{big_color};")
        self._bar.set_value(percent, percent_thresholds)
        self._sub.setText(sub_text)

    def set_big_color(self, color: str) -> None:
        self._big.setStyleSheet(f"color:{color};")
