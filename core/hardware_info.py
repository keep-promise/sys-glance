# -*- coding: utf-8 -*-
"""静态硬件信息采集：WMI + psutil，带缓存。

所有函数都是防御式的：单点失败不影响整体，失败的字段返回 "--"。
"""
from __future__ import annotations

import ctypes
import platform
import re
import sys
import time
from typing import Any, Callable, Optional

import psutil

try:  # wmi 依赖 pywin32；未安装或导入失败时降级
    import wmi  # type: ignore
    _WMI_OK = True
except Exception:  # pragma: no cover
    wmi = None  # type: ignore
    _WMI_OK = False

try:  # NVIDIA 专属
    import pynvml  # type: ignore
    _NVML_OK = True
except Exception:  # pragma: no cover
    pynvml = None  # type: ignore
    _NVML_OK = False

UNKNOWN = "--"

#: 各分类显示顺序（与左侧导航一致）
CATEGORIES = ["主板", "处理器", "内存", "显卡", "硬盘", "操作系统"]

#: 常见 CPU 制程对照（仅当型号可识别时使用，标注"约"）
_CPU_PROCESS_MAP = [
    (re.compile(r"Ryzen\s*\d+\s*9\s*9\d{2,3}X", re.I), "5nm（约）"),
    (re.compile(r"Ryzen\s*\d+\s*[578]\d{3}X", re.I), "5nm（约）"),
    (re.compile(r"Ryzen\s*\d+\s*7\d{3}", re.I), "5nm（约）"),
    (re.compile(r"Ryzen\s*\d+\s*5\d{3}", re.I), "5nm（约）"),
    (re.compile(r"Core\s*i[3579][- ]1[345]", re.I), "Intel 7（约）"),
    (re.compile(r"Core\s*i[3579][- ]14\d{3}", re.I), "Intel 7（约）"),
    (re.compile(r"Core\s*i[3579][- ]12\d{3}", re.I), "Intel 7（约）"),
    (re.compile(r"Core\s*i[3579][- ]11\d{3}", re.I), "10nm（约）"),
    (re.compile(r"Core\s*i[3579][- ]10\d{3}", re.I), "14nm（约）"),
]

#: SMBIOS 内存类型编号 → 名称
_MEM_TYPE_MAP = {
    20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5", 27: "LPDDR",
    28: "LPDDR2", 29: "LPDDR3", 30: "LPDDR4", 35: "LPDDR5", 0: "未知",
}


class _Cache:
    """一次性缓存，避免重复查询慢速 WMI。"""

    def __init__(self) -> None:
        self.data: Optional[dict[str, list[tuple[str, str]]]] = None
        self.time: float = 0.0
        self.lock = __import__("threading").Lock()

    def get(self, force: bool = False) -> dict[str, list[tuple[str, str]]]:
        with self.lock:
            if self.data is None or force:
                self.data = _collect_all()
                self.time = time.time()
            return self.data


_cache = _Cache()


def get_hardware_info(force: bool = False) -> dict[str, list[tuple[str, str]]]:
    """返回 {分类: [(字段, 值), ...]}，带缓存。"""
    return _cache.get(force)


def is_admin() -> bool:
    """当前进程是否管理员权限。"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _wmi_conn() -> Optional[Any]:
    if not _WMI_OK:
        return None
    try:
        return wmi.WMI()
    except Exception:
        return None


def _gb(n: int) -> str:
    """字节数 → 可读 GB。"""
    if not n or n <= 0:
        return UNKNOWN
    v = n / (1024 ** 3)
    return f"{v:.1f} GB" if v >= 10 else f"{v:.2f} GB"


def _safe(fn: Callable[[], str], fallback: str = UNKNOWN) -> str:
    try:
        v = fn()
        return v if v not in (None, "") else fallback
    except Exception:
        return fallback


# ---------------------------------------------------------------------------
# 主板
# ---------------------------------------------------------------------------
def collect_mainboard() -> list[tuple[str, str]]:
    conn = _wmi_conn()
    rows: list[tuple[str, str]] = []
    if conn is None:
        return [("厂商", UNKNOWN), ("型号", UNKNOWN), ("芯片组", UNKNOWN),
                ("BIOS 版本", UNKNOWN), ("BIOS 日期", UNKNOWN)]
    try:
        board = conn.Win32_BaseBoard()
        if board:
            b = board[0]
            rows.append(("厂商", _safe(lambda: b.Manufacturer.strip())))
            rows.append(("型号", _safe(lambda: b.Product.strip())))
        else:
            rows += [("厂商", UNKNOWN), ("型号", UNKNOWN)]
        bios = conn.Win32_BIOS()
        if bios:
            bi = bios[0]
            ver = _safe(lambda: bi.SMBIOSBIOSVersion.strip())
            date = UNKNOWN
            try:
                raw = str(getattr(bi, "ReleaseDate", "") or "")
                digits = "".join(ch for ch in raw.split(".")[0] if ch.isdigit())
                if len(digits) >= 8:
                    date = f"{digits[0:4]}/{digits[4:6]}/{digits[6:8]}"
            except Exception:
                pass
            rows.append(("BIOS 版本", ver))
            rows.append(("BIOS 日期", date))
        else:
            rows += [("BIOS 版本", UNKNOWN), ("BIOS 日期", UNKNOWN)]
    except Exception:
        rows += [("BIOS 版本", UNKNOWN), ("BIOS 日期", UNKNOWN)]
    # 芯片组：从主板型号推断常见芯片组（WMI 无直接字段）
    chipset = UNKNOWN
    try:
        model = ""
        for k, v in rows:
            if k == "型号":
                model = v
        if "B650" in model.upper():
            chipset = "AMD B650"
        elif "X670" in model.upper():
            chipset = "AMD X670"
        elif "B660" in model.upper() or "B760" in model.upper():
            chipset = "Intel B660/B760"
        elif "Z690" in model.upper() or "Z790" in model.upper():
            chipset = "Intel Z690/Z790"
        elif "X570" in model.upper() or "B550" in model.upper():
            chipset = "AMD X570/B550"
        elif "H610" in model.upper():
            chipset = "Intel H610"
    except Exception:
        pass
    # 芯片组插到"型号"之后
    out: list[tuple[str, str]] = []
    for k, v in rows:
        out.append((k, v))
        if k == "型号":
            out.append(("芯片组", chipset))
    return out


# ---------------------------------------------------------------------------
# 处理器
# ---------------------------------------------------------------------------
def collect_cpu() -> list[tuple[str, str]]:
    conn = _wmi_conn()
    name = core = thread = base = max_freq = cache = socket = process = UNKNOWN
    if conn is not None:
        try:
            cpus = conn.Win32_Processor()
            if cpus:
                c = cpus[0]
                name = _safe(lambda: c.Name.strip())
                core = _safe(lambda: str(c.NumberOfCores))
                thread = _safe(lambda: str(c.NumberOfLogicalProcessors))
                base = _freq_str(_safe(lambda: str(c.MaxClockSpeed), ""))
                socket = _safe(lambda: c.SocketDesignation.strip())
                cache = _safe(lambda: c.L3CacheSize and f"{int(c.L3CacheSize) // 1024} MB")
                if cache == UNKNOWN:
                    cache = _safe(lambda: c.L2CacheSize and f"{int(c.L2CacheSize) // 1024} MB")
        except Exception:
            pass
    if name == UNKNOWN:
        try:
            name = platform.processor() or UNKNOWN
        except Exception:
            pass
    if core == UNKNOWN:
        core = _safe(lambda: str(psutil.cpu_count(logical=False) or 0))
    if thread == UNKNOWN:
        thread = _safe(lambda: str(psutil.cpu_count(logical=True) or 0))
    if base == UNKNOWN:
        try:
            f = psutil.cpu_freq()
            if f and f.max:
                base = _freq_str(str(int(f.max)))
        except Exception:
            pass
    # 最大频率：WMI MaxClockSpeed 是 MHz；psutil.cpu_freq().max 同为 MHz
    max_freq = UNKNOWN
    try:
        f = psutil.cpu_freq()
        if f and f.max:
            max_freq = _freq_str(str(int(f.max)))
    except Exception:
        pass
    process = _guess_process(name)
    return [
        ("型号", name),
        ("核心数/线程数", f"{core} 核 / {thread} 线程" if core != UNKNOWN and thread != UNKNOWN else UNKNOWN),
        ("基准频率", base),
        ("最大频率", max_freq),
        ("缓存", cache),
        ("插槽", socket),
        ("制程", process),
    ]


def _freq_str(mhz: str) -> str:
    try:
        v = int(float(mhz))
        if v <= 0:
            return UNKNOWN
        return f"{v / 1000:.2f} GHz"
    except Exception:
        return UNKNOWN


def _guess_process(name: str) -> str:
    if name in (UNKNOWN, ""):
        return UNKNOWN
    for pat, label in _CPU_PROCESS_MAP:
        if pat.search(name):
            return label
    return UNKNOWN


# ---------------------------------------------------------------------------
# 内存
# ---------------------------------------------------------------------------
def collect_memory() -> list[tuple[str, str]]:
    vm = psutil.virtual_memory()
    total = _gb(vm.total)
    used = _gb(vm.used)
    avail = _gb(vm.available)
    rows: list[tuple[str, str]] = [
        ("总容量", total),
        ("已用 / 可用", f"{used} / {avail}"),
    ]
    freq = type_ = slots = UNKNOWN
    conn = _wmi_conn()
    if conn is not None:
        try:
            sticks = conn.Win32_PhysicalMemory()
            sticks = [s for s in sticks if getattr(s, "Capacity", 0)]
            if sticks:
                speeds = {int(getattr(s, "Speed", 0) or 0) for s in sticks}
                speeds.discard(0)
                if speeds:
                    freq = f"{max(speeds)} MHz"
                mtypes = {int(getattr(s, "SMBIOSMemoryType", 0) or 0) for s in sticks}
                mtypes.discard(0)
                if mtypes:
                    names = {_MEM_TYPE_MAP.get(t, f"类型{t}") for t in mtypes}
                    type_ = "/".join(sorted(names))
                total_slots = UNKNOWN
                try:
                    arr = conn.Win32_PhysicalMemoryArray()
                    if arr and getattr(arr[0], "MemoryDevices", None):
                        total_slots = str(int(arr[0].MemoryDevices))
                except Exception:
                    pass
                slots = f"{len(sticks)} / {total_slots}"
        except Exception:
            pass
    rows.append(("频率", freq))
    rows.append(("类型", type_))
    rows.append(("插槽使用", slots))
    return rows


# ---------------------------------------------------------------------------
# 显卡
# ---------------------------------------------------------------------------
def collect_gpu() -> list[tuple[str, str]]:
    """优先 NVIDIA（pynvml 提供核心/显存频率），否则 WMI 兜底。"""
    rows: list[tuple[str, str]] = []
    if _NVML_OK:
        try:
            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            for i in range(count):
                h = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(h)
                if isinstance(name, bytes):
                    name = name.decode(errors="replace")
                name = str(name).strip()
                mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                vram = f"{mem.total / 1024 ** 3:.0f} GB"
                try:
                    core_clk = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_GRAPHICS)
                except Exception:
                    core_clk = 0
                try:
                    mem_clk = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_MEM)
                except Exception:
                    mem_clk = 0
                try:
                    drv = pynvml.nvmlSystemGetDriverVersion()
                    drv = drv.decode(errors="replace") if isinstance(drv, bytes) else str(drv)
                except Exception:
                    drv = UNKNOWN
                rows.append(("型号", name))
                rows.append(("显存", vram))
                rows.append(("驱动版本", drv))
                rows.append(("核心频率", _freq_str(str(core_clk))))
                rows.append(("显存频率", f"{mem_clk} MHz" if mem_clk else UNKNOWN))
                rows.append(("适配器", f"GPU {i}"))
            pynvml.nvmlShutdown()
            if rows:
                return rows
        except Exception:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
    # WMI 兜底
    conn = _wmi_conn()
    if conn is not None:
        try:
            for vc in conn.Win32_VideoController():
                rows.append(("型号", _safe(lambda: vc.Name.strip())))
                vram = _safe(lambda: f"{int(vc.AdapterRAM) / 1024 ** 3:.0f} GB" if int(vc.AdapterRAM or 0) > 0 else "")
                rows.append(("显存", vram))
                rows.append(("驱动版本", _safe(lambda: vc.DriverVersion.strip())))
        except Exception:
            pass
    if not rows:
        rows = [("型号", UNKNOWN), ("显存", UNKNOWN), ("驱动版本", UNKNOWN)]
    return rows


# ---------------------------------------------------------------------------
# 硬盘
# ---------------------------------------------------------------------------
def _disk_kind(model: str, media: str, iface: str) -> str:
    """判断 SSD/HDD：优先 MSFT_PhysicalDisk 的 MediaType，否则启发式。"""
    m = (media or "").upper()
    if "SSD" in m or "SOLID" in m:
        return "SSD"
    # MSFT_PhysicalDisk（root\Microsoft\Windows\Storage）：4=SSD, 3=HDD
    try:
        conn = wmi.WMI(namespace="root\\Microsoft\\Windows\\Storage")
        for p in conn.MSFT_PhysicalDisk():
            pm = str(getattr(p, "Model", "") or "").upper()
            if pm and (pm in model.upper() or model.upper() in pm):
                mt = int(getattr(p, "MediaType", 0) or 0)
                if mt == 4:
                    return "SSD"
                if mt == 3:
                    return "HDD"
    except Exception:
        pass
    if "HDD" in m or "FIXED" in m:
        return "HDD"
    if iface.upper() == "NVME":
        return "SSD"
    return iface if iface else "SSD"


def collect_disks() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    conn = _wmi_conn()
    phys: list[tuple[str, str, str]] = []  # (型号, 容量, 类型)
    if conn is not None:
        try:
            for d in conn.Win32_DiskDrive():
                model = _safe(lambda: d.Model.strip())
                size = _gb(int(getattr(d, "Size", 0) or 0))
                iface = _safe(lambda: d.InterfaceType.strip())
                media = _safe(lambda: d.MediaType.strip())
                kind = _disk_kind(model, media, iface)
                phys.append((model, size, kind))
        except Exception:
            pass
    if not phys:
        try:
            for part in psutil.disk_partitions(all=False):
                try:
                    u = psutil.disk_usage(part.mountpoint)
                    rows.append((f"分区 {part.mountpoint}", f"{_gb(u.total)}（已用 {_gb(u.used)} / 可用 {_gb(u.free)}）"))
                    rows.append(("类型", part.fstype or UNKNOWN))
                except Exception:
                    pass
        except Exception:
            pass
        if not rows:
            rows = [("型号", UNKNOWN), ("容量", UNKNOWN)]
        return rows
    for model, size, kind in phys:
        if len(phys) == 1:
            rows.append(("型号", model))
            rows.append(("容量", size))
            rows.append(("类型", kind))
            # 汇总分区用量
            try:
                total_u = total_f = 0
                for part in psutil.disk_partitions(all=False):
                    try:
                        u = psutil.disk_usage(part.mountpoint)
                        total_u += u.used
                        total_f += u.free
                    except Exception:
                        pass
                if total_u + total_f > 0:
                    rows.append(("已用 / 可用", f"{_gb(total_u)} / {_gb(total_f)}"))
            except Exception:
                pass
        else:
            rows.append((f"型号（{size}）", model))
            rows.append(("类型", kind))
    # 温度（可选）：仅管理员 + 支持 SMART 的盘可读，失败显示 "--"
    rows.append(("温度", collect_disk_temperature()))
    return rows


def collect_disk_temperature() -> str:
    """尝试通过 WMI SMART 读取第一块盘的温度（需管理员，非所有盘支持）。"""
    if not is_admin() or not _WMI_OK:
        return UNKNOWN
    try:
        conn = wmi.WMI(namespace="root\\WMI")
        for attr in conn.MSStorageDriver_ATAPISmartData():
            data = getattr(attr, "VendorSpecific", None)
            if not data:
                continue
            for i in range(len(data) - 1):
                if data[i] == 0x01 and i + 1 < len(data):  # Temperature attribute
                    t = data[i + 1]
                    if 0 < t < 120:
                        return f"{t} °C"
    except Exception:
        pass
    return UNKNOWN


# ---------------------------------------------------------------------------
# 操作系统
# ---------------------------------------------------------------------------
def collect_os() -> list[tuple[str, str]]:
    conn = _wmi_conn()
    version = build = arch = install = UNKNOWN
    if conn is not None:
        try:
            oses = conn.Win32_OperatingSystem()
            if oses:
                o = oses[0]
                version = _safe(lambda: o.Caption.strip())
                build = _safe(lambda: f"{o.BuildNumber}.{o.UBR}")
                arch = _safe(lambda: o.OSArchitecture.strip())
                raw = _safe(lambda: str(o.InstallDate))
                if raw != UNKNOWN:
                    # InstallDate 形如 20220121130954.000000+480 → 2022-01-21
                    digits = "".join(ch for ch in raw.split(".")[0] if ch.isdigit())
                    if len(digits) >= 8:
                        install = f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
        except Exception:
            pass
    if version == UNKNOWN:
        try:
            version = platform.platform()
        except Exception:
            pass
    if arch == UNKNOWN:
        arch = platform.machine() or UNKNOWN
    computer = platform.node() or UNKNOWN
    user = UNKNOWN
    try:
        import getpass
        user = getpass.getuser() or UNKNOWN
    except Exception:
        pass
    return [
        ("版本", version),
        ("Build 号", build),
        ("架构", arch),
        ("安装日期", install),
        ("计算机名", computer),
        ("当前用户", user),
    ]


def _collect_all() -> dict[str, list[tuple[str, str]]]:
    return {
        "主板": collect_mainboard(),
        "处理器": collect_cpu(),
        "内存": collect_memory(),
        "显卡": collect_gpu(),
        "硬盘": collect_disks(),
        "操作系统": collect_os(),
    }
