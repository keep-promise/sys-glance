# -*- coding: utf-8 -*-
"""菜单一：系统总览（鲁大师风格）——左侧分类导航 + 右侧参数表格。"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core import hardware_info
from ui.widgets.info_card import InfoTable

# 分类 → 图标 + 说明
_CATEGORY_META = [
    ("主板", "🖥️"),
    ("处理器", "🔲"),
    ("内存", "🧠"),
    ("显卡", "🎮"),
    ("硬盘", "💾"),
    ("操作系统", "🪟"),
]


class OverviewTab(QWidget):
    """系统总览：点击左侧分类，右侧显示对应硬件详情。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        hint = QLabel("点击左侧分类，查看对应硬件参数")
        hint.setStyleSheet("color:#8A94A6; font-size:12px;")
        lay.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        # ---- 左侧导航 ----
        nav = QListWidget()
        nav.setObjectName("navList")
        nav.setFixedWidth(150)
        nav.setStyleSheet(
            "#navList { background:#F5F7FA; border:1px solid #E2E6ED; border-radius:8px;"
            " font-size:13px; outline:0; }"
            "#navList::item { padding:10px 12px; border:none; border-radius:6px; margin:2px 4px; }"
            "#navList::item:selected { background:#3B82F6; color:white; }"
            "#navList::item:hover:!selected { background:#E8EEF7; }"
        )
        for name, icon in _CATEGORY_META:
            item = QListWidgetItem(f"{icon}  {name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            nav.addItem(item)
        nav.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        nav.currentRowChanged.connect(self._on_row_changed)
        self._nav = nav
        splitter.addWidget(nav)

        # ---- 右侧详情 ----
        self._detail = InfoTable(self)
        self._detail.show_loading(_CATEGORY_META[0][1] + " 主板")
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        lay.addWidget(splitter, 1)

        self._data: dict[str, list[tuple[str, str]]] = {}
        self._icon_map = {name: icon for name, icon in _CATEGORY_META}

    # ---- 数据入口 ----
    def set_data(self, data: dict[str, list[tuple[str, str]]]) -> None:
        """由 StaticInfoThread.ready 信号传入。"""
        self._data = data or {}
        cur = self._nav.currentRow() if hasattr(self, "_nav") else 0
        if cur < 0:
            cur = 0
        self._show_category(cur)

    def _on_row_changed(self, row: int) -> None:
        self._show_category(row)

    def _show_category(self, row: int) -> None:
        name = _CATEGORY_META[row][0]
        icon = _CATEGORY_META[row][1]
        rows = self._data.get(name)
        if rows is None:
            self._detail.show_loading(f"{icon} {name}")
        elif not rows:
            self._detail.set_content(f"{icon} {name}", [("信息", "--")])
        else:
            self._detail.set_content(f"{icon} {name}", rows)
