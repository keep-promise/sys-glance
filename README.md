# SysGlance — 系统硬件总览与实时监控

PyQt6 双菜单 Windows 工具，参考鲁大师风格：

- **📋 系统总览**：左侧分类导航 + 右侧参数表格（主板 / 处理器 / 内存 / 显卡 / 硬盘 / 操作系统）
- **📊 实时监控**：CPU / GPU / 内存三张指标卡片 + 温度趋势图（最近 60 秒）+ 采样控制

## 运行

```bash
# 方式一：项目虚拟环境（推荐，基于系统 Python 3.11，依赖已装全）
.venv\Scripts\python main.py

# 方式二：先激活 venv 再运行
.venv\Scripts\activate
python main.py

# 方式三：直接用全局 Python（需自行装依赖）
pip install -r requirements.txt
python main.py
```

> `.venv` 是已创建好的虚拟环境（Python 3.11）。重装依赖：
> `.venv\Scripts\python -m pip install -r requirements.txt`

验证是否正常：`python main.py --smoke-test`（启动 5 秒后自动退出并打印诊断）。

## CPU 温度说明（重要）

CPU 温度按以下顺序获取，全部失败时显示 `--`：

1. **LibreHardwareMonitor（最准确，推荐）**：把 `LibreHardwareMonitorLib.dll` 及依赖
   （`HidSharp.dll` 等）放入项目 `lib/` 目录，或设置环境变量
   `LIBREHARDWAREMONITOR_PATH` 指向 DLL 所在目录。可从
   https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases 下载
   `LibreHardwareMonitor.zip` 解压获得。
2. **WMI ACPI**（`MSAcpi_ThermalZoneTemperature`）：需管理员权限，部分主板可用。
3. 均不可用时温度显示 `--`。

GPU 温度 / 占用 / 显存通过 `nvidia-ml-py`（NVIDIA）读取；非 NVIDIA 显卡时 GPU 卡片显示
静态信息，实时指标显示 `--`。

## 功能

- 顶部 Tab 切换总览 / 监控
- 系统托盘：显示/隐藏窗口、切换 Tab、开机自启（HKCU Run）、退出；关闭窗口最小化到托盘
- 设置：采样间隔（200ms–60s）、趋势窗口（10–600s），持久化到 `%APPDATA%\.sysglance\config.json`
- 颜色告警：温度 <70°C 绿 / 70–85 黄 / >85 红；CPU/GPU 占用 <60% 绿 / 60–85 黄 / >85 红；
  内存 <70% 绿 / 70–90 黄 / >90 红

## 打包

```bash
pip install pyinstaller
python -m PyInstaller build.spec
```

产物在 `dist/SysGlance.exe`。开机自启命令会自动适配打包后的 exe。

## 目录结构

```
main.py                 # 入口
ui/
  main_window.py        # 主窗口 + Tab 切换 + 托盘接线
  overview_tab.py       # 系统总览
  monitor_tab.py        # 实时监控
  widgets/              # info_card / metric_card / trend_chart
  tray.py               # 系统托盘 + 开机自启
core/
  collector.py          # 采集调度器（QThread + 静态加载线程）
  hardware_info.py      # 静态硬件信息（WMI + psutil，带缓存）
  sensors.py            # 实时采集（psutil / pynvml / 温度回退）
  lhm_sensor.py         # LibreHardwareMonitor 桥接（可选）
  config.py             # config.json 读写
```

## 已知限制

- 制程、芯片组等 WMI 无直接字段的值由型号推断，推断不出显示 `--`
- 硬盘温度依赖 SMART 与管理员权限，读不到显示 `--`
