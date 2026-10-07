# -*- coding: utf-8 -*-
"""信息卡片组件：总览 Tab 右侧的详情表格（QTableWidget 封装）。

样式遵循"鲁大师风格"：字段名灰色小字、值黑色大字、对齐整齐、只读。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class InfoTable(QWidget):
    """以 字段名|值 两列展示一组硬件参数。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._title = QLabel("")
        f = self._title.font()
        f.setPointSize(13)
        f.setBold(True)
        self._title.setFont(f)
        lay.addWidget(self._title)

        self._table = QTableWidget(0, 2)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setStyleSheet(
            "QTableWidget { background: white; border: 1px solid #E2E6ED; border-radius: 8px; }"
            "QTableWidget::item { padding: 8px 14px; border: none; }"
            "QTableWidget::item:selected { background: transparent; }"
        )
        lay.addWidget(self._table, 1)

    def set_content(self, title: str, rows: list[tuple[str, str]]) -> None:
        """title 为分类名，rows 为 [(字段名, 值), ...]。"""
        self._title.setText(title)
        self._table.setRowCount(len(rows))
        for r, (k, v) in enumerate(rows):
            key_item = QTableWidgetItem(str(k))
            key_item.setForeground(Qt.GlobalColor.gray)
            kf = QFont(key_item.font())
            kf.setPointSize(9)
            key_item.setFont(kf)
            self._table.setItem(r, 0, key_item)

            val_item = QTableWidgetItem(str(v) if v not in (None, "") else "--")
            val_item.setForeground(Qt.GlobalColor.black)
            vf = QFont(val_item.font())
            vf.setPointSize(11)
            vf.setBold(True)
            val_item.setFont(vf)
            self._table.setItem(r, 1, val_item)
        self._table.resizeRowsToContents()

    def show_loading(self, title: str) -> None:
        self.set_content(title, [("状态", "正在加载…")])
