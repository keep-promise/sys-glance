# -*- coding: utf-8 -*-
"""SysGlance 入口。

用法：
    python main.py            # 正常启动
    python main.py --smoke-test  # 启动 3 秒后自动退出并打印诊断，用于验证
"""
from __future__ import annotations

import os
import sys

# Windows 控制台中文输出兼容
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 保证以源码目录运行时可导入 core/ui
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run(smoke: bool = False) -> int:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("SysGlance")
    app.setQuitOnLastWindowClosed(False)  # 关窗隐藏到托盘

    from ui.main_window import MainWindow

    win = MainWindow()
    win.show()

    if smoke:
        from core import hardware_info
        from core.config import config_path

        def report() -> None:
            print("=== SysGlance smoke test ===")
            print(f"admin: {hardware_info.is_admin()}")
            print(f"config: {config_path()}")
            print("tabs:", win._tabs.count(), "| overview:", win._overview is not None,
                  "| monitor:", win._monitor is not None)
            print("collector running:", win._collector.isRunning())
            print("tray visible:", win._tray.isVisible())
            win.quit_application()  # 安全退出：先停线程

        QTimer.singleShot(5000, report)

    return app.exec()


if __name__ == "__main__":
    smoke = "--smoke-test" in sys.argv
    raise SystemExit(run(smoke=smoke))
