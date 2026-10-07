# -*- coding: utf-8 -*-
"""实时传感器采集：CPU / GPU / 内存。

温度策略（多级回退）：
  1. LibreHardwareMonitor（pythonnet，需 lib/ 下有 DLL）——最准确
  2. WMI MSAcpi_ThermalZoneTemperature——部分机器可用（需管理员）
  3. 都失败返回 None，UI 显示 "--"
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Optional

import psutil

try:
    import pynvml  # type: ignore
    _NVML_OK = True
except Exception:  # pragma: no cover
    pynvml = None  # type: ignore
    _NVML_OK = False


@dataclass
class CpuSample:
    temp: Optional[float] = None       # °C
    percent: float = 0.0               # 占用率 %
    freq_mhz: float = 0.0              # 当前频率


@dataclass
class GpuSample:
    temp: Optional[float] = None
    percent: float = 0.0
    mem_used: float = 0.0              # GB
    mem_total: float = 0.0             # GB


@dataclass
class MemSample:
    percent: float = 0.0
    used: float = 0.0                  # GB
    total: float = 0.0                 # GB


@dataclass
class SystemSample:
    cpu: CpuSample = field(default_factory=CpuSample)
    gpu: GpuSample = field(default_factory=GpuSample)
    mem: MemSample = field(default_factory=MemSample)
    has_gpu: bool = False


# ---------------------------------------------------------------------------
# CPU 温度（LHM 优先，WMI 兜底）
# ---------------------------------------------------------------------------
class CpuTemperatureSource:
    """温度源抽象：惰性初始化，失败自动降级。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._lhm = None          # LHM 桥接实例
        self._lhm_tried = False
        self._wmi_failed = False  # 仅标记"读取失败"，成功读取不会停用

    def read(self) -> Optional[float]:
        v = self._read_lhm()
        if v is not None:
            return v
        return self._read_wmi()

    # ---- LHM ----
    def _read_lhm(self) -> Optional[float]:
        if self._lhm_tried:
            return self._lhm.read() if self._lhm else None
        self._lhm_tried = True
        try:
            from core import lhm_sensor  # noqa: F401
            bridge = lhm_sensor.LhmBridge()
            if bridge.available:
                self._lhm = bridge
                return bridge.read()
        except Exception:
            self._lhm = None
        return None

    # ---- WMI ACPI ----
    def _read_wmi(self) -> Optional[float]:
        """每次采样都尝试读取；只有读取失败（异常或无数据）才标记不可用。

        注意：不能把"成功读取过"当作跳过条件，否则温度只会显示一帧。
        """
        if self._wmi_failed:
            return None
        try:
            import wmi  # type: ignore
            conn = wmi.WMI(namespace="root\\WMI")
            temps = []
            for tz in conn.MSAcpi_ThermalZoneTemperature():
                v = getattr(tz, "CurrentTemperature", None)
                if v:
                    # 单位 0.1K，换算 °C
                    celsius = (int(v) / 10.0) - 273.15
                    if 0 <= celsius <= 120:
                        temps.append(celsius)
            if temps:
                return max(temps)  # 取最高温度区
        except Exception:
            pass
        self._wmi_failed = True  # 失败才停用，成功时持续读取
        return None


# ---------------------------------------------------------------------------
# 主采集器
# ---------------------------------------------------------------------------
class SensorCollector:
    def __init__(self) -> None:
        self._cpu_temp = CpuTemperatureSource()
        self._nvml_init_done = False
        self._nvml_error: Optional[str] = None
        self._cpu_percent_called = False
        self._lock = threading.Lock()

    # ---- GPU（pynvml） ----
    def _ensure_nvml(self) -> bool:
        if not _NVML_OK:
            return False
        if self._nvml_init_done:
            return self._nvml_error is None
        self._nvml_init_done = True
        try:
            pynvml.nvmlInit()
            return True
        except Exception as e:
            self._nvml_error = str(e)
            return False

    def collect(self) -> SystemSample:
        s = SystemSample()

        # CPU 占用率（首次调用返回 0，预热一次）
        if not self._cpu_percent_called:
            psutil.cpu_percent(interval=None)
            self._cpu_percent_called = True
        s.cpu.percent = psutil.cpu_percent(interval=None)
        try:
            f = psutil.cpu_freq()
            s.cpu.freq_mhz = float(f.current) if f and f.current else 0.0
        except Exception:
            pass
        s.cpu.temp = self._cpu_temp.read()

        # 内存
        vm = psutil.virtual_memory()
        s.mem.percent = float(vm.percent)
        s.mem.used = vm.used / 1024 ** 3
        s.mem.total = vm.total / 1024 ** 3

        # GPU
        if self._ensure_nvml():
            try:
                s.has_gpu = True
                count = pynvml.nvmlDeviceGetCount()
                if count > 0:
                    h = pynvml.nvmlDeviceGetHandleByIndex(0)
                    try:
                        t = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
                        s.gpu.temp = float(t)
                    except Exception:
                        pass
                    try:
                        u = pynvml.nvmlDeviceGetUtilizationRates(h)
                        s.gpu.percent = float(u.gpu)
                    except Exception:
                        pass
                    try:
                        m = pynvml.nvmlDeviceGetMemoryInfo(h)
                        s.gpu.mem_used = m.used / 1024 ** 3
                        s.gpu.mem_total = m.total / 1024 ** 3
                    except Exception:
                        pass
            except Exception:
                s.has_gpu = False
        return s
