# -*- coding: utf-8 -*-
"""LibreHardwareMonitor 桥接（pythonnet）。

前置条件（可选）：
  - pip install pythonnet
  - lib/LibreHardwareMonitorLib.dll 及其依赖（HidSharp.dll 等）位于：
      1) 环境变量 LIBREHARDWAREMONITOR_PATH 指向的目录
      2) 项目根目录 lib/ 目录

未满足时 available=False，上层自动回退到 WMI 温度或显示 "--"。
"""
from __future__ import annotations

import glob
import os
import sys
from typing import Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _candidate_dirs() -> list[str]:
    dirs = []
    env = os.environ.get("LIBREHARDWAREMONITOR_PATH")
    if env:
        dirs.append(env)
    dirs.append(os.path.join(_PROJECT_ROOT, "lib"))
    return dirs


def find_lhm_dll() -> Optional[str]:
    for d in _candidate_dirs():
        if not d or not os.path.isdir(d):
            continue
        hits = glob.glob(os.path.join(d, "LibreHardwareMonitorLib.dll"))
        if hits:
            return hits[0]
    return None


class LhmBridge:
    """对 LibreHardwareMonitor 的最小封装：读取 CPU / GPU 温度。"""

    def __init__(self) -> None:
        self.available = False
        self._computer = None
        self._cpu_hw = None
        self._gpu_hw = None
        self._try_init()

    def _try_init(self) -> None:
        dll = find_lhm_dll()
        if not dll:
            return
        try:
            import clr  # pythonnet

            clr.AddReference(os.path.splitext(dll)[0])
            from LibreHardwareMonitor.Hardware import Computer, SensorType  # type: ignore

            computer = Computer()
            computer.IsCpuEnabled = True
            computer.IsGpuEnabled = True
            computer.Open()
            cpus, gpus = [], []
            for hw in computer.Hardware:
                hw.Update()
                t = str(hw.HardwareType)
                if "Cpu" in t:
                    cpus.append(hw)
                elif "Gpu" in t:
                    gpus.append(hw)
            self._computer = computer
            self._cpu_hw = cpus[0] if cpus else None
            self._gpu_hw = gpus[0] if gpus else None
            self.available = True
        except Exception:
            self.available = False
            if self._computer is not None:
                try:
                    self._computer.Close()
                except Exception:
                    pass
            self._computer = None

    def _read_temp(self, hw, kind: str) -> Optional[float]:
        if hw is None:
            return None
        try:
            hw.Update()
            for s in hw.Sensors:
                if str(s.SensorType) == kind:
                    v = s.Value
                    if v is not None and 0 < float(v) < 150:
                        return float(v)
        except Exception:
            pass
        return None

    def cpu_temp(self) -> Optional[float]:
        return self._read_temp(self._cpu_hw, "Temperature")

    def gpu_temp(self) -> Optional[float]:
        return self._read_temp(self._gpu_hw, "Temperature")

    def close(self) -> None:
        if self._computer is not None:
            try:
                self._computer.Close()
            except Exception:
                pass

    def __del__(self) -> None:  # pragma: no cover
        try:
            self.close()
        except Exception:
            pass
