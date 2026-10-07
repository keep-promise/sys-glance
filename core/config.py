# -*- coding: utf-8 -*-
"""配置读写：config.json 保存采样间隔、显示项、窗口位置等。"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

APP_NAME = "SysGlance"
DEFAULT_CONFIG: dict[str, Any] = {
    "sampling_interval_ms": 1000,   # 实时监控采样间隔（毫秒）
    "trend_seconds": 60,            # 趋势图时间窗口（秒）
    "window": {"x": None, "y": None, "width": 980, "height": 640},
    "start_with_windows": False,    # 开机自启
    "last_tab": 0,                  # 上次退出时的 Tab 索引
}


def config_dir() -> str:
    """配置目录：优先用户目录下 .sysglance，便于打包后使用。"""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.path.expanduser("~")
    d = os.path.join(base, ".sysglance")
    os.makedirs(d, exist_ok=True)
    return d


def config_path() -> str:
    return os.path.join(config_dir(), "config.json")


def load_config() -> dict[str, Any]:
    """读取配置；文件不存在或损坏时回退默认值。"""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # 深拷贝
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k, v in data.items():
                cfg[k] = v
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    """原子写入配置（先写临时文件再替换，避免写坏）。"""
    path = config_path()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
