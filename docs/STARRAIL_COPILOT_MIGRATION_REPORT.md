# StarRailCopilot 设备控制与截图方案迁移报告

## 迁移目标

将 StarRailCopilot 项目中成熟的安卓设备控制与画面获取方案迁移到 **IstinaEndfieldAssistant_Sight** 项目中，提升设备兼容性、截图性能和触控可靠性。

**核心要求：**
- 保持 Sight 分支纯本地特性（不引入云端依赖）
- 兼容现有框架结构和日志系统
- 支持多种截图方式（scrcpy优先，多路回退）
- 支持多种触控方式（MaaTouch优先，Pipeline任务执行）
- 自动设备检测和智能降级

---

## 一、StarRailCopilot 架构分析

### 1.1 核心架构

StarRailCopilot 采用 **多重继承 + Mixin** 的模块化设计：

```
Device (device.py)
├── Screenshot (screenshot.py)    # 截图能力
│   ├── Adb                        # ADB 截图
│   ├── WSA                        # Windows Subsystem for Android
│   ├── DroidCast                  # DroidCast 视频流
│   ├── AScreenCap                 # aScreenCap
│   ├── Scrcpy                     # scrcpy 视频流
│   ├── NemuIpc                    # MuMu IPC
│   └── LDOpenGL                   # LDPlayer OpenGL
├── Control (control.py)          # 触控能力
│   ├── Hermit                     # Hermit 触控
│   ├── Minitouch                  # Minitouch
│   ├── Scrcpy                     # scrcpy 触控
│   ├── MaaTouch                   # MaaTouch（推荐）
│   └── NemuIpc                    # MuMu IPC
└── AppControl (app_control.py)   # 应用控制能力
    ├── Adb                        # ADB 应用管理
    ├── WSA                        # WSA 应用管理
    └── Uiautomator2               # uiautomator2 界面分析
```

### 1.2 截图方案对比

| 方法 | 实现文件 | 性能 | 兼容性 | 依赖 |
|------|---------|------|--------|------|
| **scrcpy** | `method/scrcpy.py` | ⭐⭐⭐⭐⭐ 视频流 | 通用 | scrcpy-server |
| **nemu_ipc** | `method/nemu_ipc.py` | ⭐⭐⭐⭐⭐ 共享内存 | MuMu 12+ | MuMu IPC |
| **ldopengl** | `method/ldopengl.py` | ⭐⭐⭐⭐ | LDPlayer | LDPlayer OpenGL |
| **DroidCast** | `method/droidcast.py` | ⭐⭐⭐ | 通用 | DroidCast |
| **aScreenCap** | `method/ascreencap.py` | ⭐⭐⭐ | 通用 | aScreenCap APK |
| **ADB** | `method/adb.py` | ⭐⭐ | 所有设备 | 无 |
| **uiautomator2** | `method/uiautomator2.py` | ⭐⭐ | 通用 | minicap |

**关键发现：**
- scrcpy 视频流性能最佳（无压缩、低延迟）
- nemu_ipc 仅适用于 MuMu 12+（共享内存零拷贝）
- ADB 截图最稳定但性能最差
- 支持 **自动降级**：优先尝试高性能方法，失败后自动切换

### 1.3 触控方案对比

| 方法 | 实现文件 | 性能 | 兼容性 | 依赖 |
|------|---------|------|--------|------|
| **MaaTouch** | `method/maatouch.py` | ⭐⭐⭐⭐⭐ | 通用 | MaaTouch APK |
| **scrcpy** | `method/scrcpy.py` | ⭐⭐⭐⭐ | 通用 | scrcpy-server |
| **minitouch** | `method/minitouch.py` | ⭐⭐⭐⭐ | 通用 | minitouch |
| **nemu_ipc** | `method/nemu_ipc.py` | ⭐⭐⭐⭐⭐ | MuMu 12+ | MuMu IPC |
| **Hermit** | `method/hermit.py` | ⭐⭐⭐ | VMOS | Hermit |
| **ADB** | `method/adb.py` | ⭐⭐ | 所有设备 | 无 |

**关键发现：**
- MaaTouch 性能最佳（与 scrcpy 相当），兼容性好
- nemu_ipc 性能最好但仅限 MuMu
- ADB 触控最稳定但延迟高
- **Pipeline 执行**：MaaFramework 支持任务编排，可批量执行操作

### 1.4 设备管理与自动检测

**Connection 类** (`connection.py`) 提供：
- **设备发现**：`get_devices()`、`detect_device()`
- **设备属性检测**：
  - `is_mumu_family`、`is_ldplayer_bluestacks_family`
  - `is_waydroid`、`is_avd`、`is_bluestacks_air`
  - `nemud_app_keep_alive`、`nemud_player_version`
- **智能配置**：根据设备类型自动选择最佳截图/触控方式
- **端口转发/反向**：支持网络设备通信

**配置系统**：
- `Config` 装饰器：运行时配置切换（`@Config.when(DEVICE_OVER_HTTP=False)`）
- 配置项：`Emulator_ScreenshotMethod`、`Emulator_ControlMethod`、`Emulator_Serial`
- 自动降级：不支持的方案自动回退到 `auto`

### 1.5 错误处理与重试

- **统一重试装饰器**：`@retry`（5次重试）
- **异常分类**：
  - `RequestHumanTakeover`：需要人工干预
  - `EmulatorNotRunningError`：模拟器未运行
  - `GameNotRunningError`：游戏崩溃
  - `GameStuckError`：卡死检测
  - `GameTooManyClickError`：连点保护
- **连点保护**：记录最近30次点击，检测异常频率
- **卡死检测**：`stuck_timer` 60秒超时，自动截图记录

### 1.6 日志系统

- **自定义 logger**：`module.logger.logger`
- **日志级别**：DEBUG、INFO、WARNING、EXCEPTION、CRITICAL
- **分类**：MAIN、ADB、COMMUNICATION、EXECUTION、AUTHENTICATION、GUI、EXCEPTION、PERFORMANCE
- **性能监控**：`log_performance()` 记录操作耗时
- **截图队列**：`screenshot_deque` 保存最近N张截图用于错误分析

---

## 二、IstinaEndfieldAssistant_Sight 现有架构分析

### 2.1 核心模块结构

```
src/core/
├── capability/
│   ├── device/
│   │   ├── adb_manager.py      # ADB设备管理器（基于adbutils）
│   │   └── touch/
│   │       ├── touch_manager.py    # 统一触控管理器
│   │       └── maafw_touch_adapter.py  # MaaFramework适配器
│   ├── screenshot/
│   │   └── __init__.py         # 导出 ScreenCapture
│   └── input/
│       └── screenshot/
│           └── screen_capture.py   # 屏幕捕获器（scrcpy优先）
├── foundation/
│   ├── logger.py               # 客户端日志系统（JSON格式）
│   └── paths.py                # 统一路径管理
└── ...
```

### 2.2 现有设备管理方案

**ADBDeviceManager** (`adb_manager.py`)：
- 基于 `adbutils.AdbClient` + `subprocess`
- 功能：设备发现、连接、分辨率查询、文件传输、shell命令
- 提供 `create_connection()` 用于 scrcpy 的 socket 连接
- **未实现**：截图、触控、应用控制

**ScreenCapture** (`screen_capture.py`)：
- **优先级策略**：scrcpy → MAA → ADB（配置可调）
- **scrcpy 实现**：依赖 `scrcpy_core.py`（未分析，需确认）
- **MAA 回退**：通过 `TouchManager.screencap()` 获取 numpy 图像
- **ADB 回退**：`exec-out screencap -p` 获取 PNG
- **图像处理**：Base64编码、可选缩放（已删除，保持原始分辨率）
- **间隔控制**：`min_interval` 限制截图频率
- **性能监控**：集成 `logger.log_performance()`

**TouchManager** (`touch_manager.py`)：
- **设备类型**：仅支持 Android（`TouchDeviceType.ANDROID`）
- **连接方式**：`connect_android()` → `MaaFwTouchExecutor`
- **执行策略**：Pipeline 优先，单次控制备用
- **Pipeline 任务**：`run_pipeline_task()`、`run_pipeline_sequence()`
- **单次控制**：`safe_press()`、`safe_swipe()`、`safe_long_press()`
- **工具入口**：`execute_tool_call()` 统一执行

**MaaFwTouchExecutor** (`maafw_touch_adapter.py`)：
- **MaaFramework 集成**：通过 `maa` 包导入（pip install MaaFw）
- **核心组件**：`Resource`、`AdbController`、`Tasker`
- **连接流程**：
  1. `_load_library()`：加载 MaaFramework 动态库（自动初始化）
  2. `Toolkit.find_adb_devices()`：自动发现设备配置
  3. `AdbController()`：创建控制器（支持 screencap/input 方法配置）
  4. `Tasker.bind()`：绑定资源与控制器
- **坐标转换**：`_convert_to_maa_coords()` 处理原始分辨率 → MaaFw 空间
- **分辨率获取**：先截图获取，回退到 ADB `wm size` 查询
- **Pipeline 支持**：`load_pipeline()`、`run_pipeline_task()`、`override_pipeline()`
- **OCR 支持**：`post_ocr_model()`、`ocr()`（MaaFw 5.11.1+）

### 2.3 日志与配置

**日志系统** (`foundation/logger.py`)：
- **ClientLogger**：单例模式，多处理器（文件、控制台、GUI）
- **LogCategory**：ADB、MAIN、COMMUNICATION 等分类
- **性能监控**：`log_performance()`、`get_performance_statistics()`
- **日志轮转**：按大小轮转（默认 50MB，保留 5 份）
- **自动清理**：定期清理旧日志（默认保留 3 天）

**路径管理** (`foundation/paths.py`)：
- **固定参考点**：基于 `paths.py` 自身位置计算项目根目录
- **统一接口**：`get_project_root()`、`get_src_dir()`、`get_config_dir()` 等
- **sys.path 管理**：`ensure_src_path()`、`ensure_project_path()`

### 2.4 现有架构优势

1. **模块化清晰**：截图、触控、设备管理分离
2. **Pipeline 优先**：支持任务编排，效率高
3. **智能降级**：scrcpy → MAA → ADB，配置灵活
4. **坐标归一化**：保持原始分辨率，支持任意屏幕
5. **日志完善**：分类、性能、轮转、清理一应俱全
6. **路径统一**：避免 `sys.path` 问题

### 2.5 现有架构不足

1. **截图方式单一**：
   - 缺少 nemu_ipc、ldopengl 等高性能方案
   - scrcpy 依赖未明确（`scrcpy_core.py` 是否存在？）
   - 无自动基准测试选择最佳方法

2. **触控方式有限**：
   - 仅支持 MaaFramework（需 pip install MaaFw）
   - 缺少 minitouch、scrcpy 触控、ADB 触控的直接实现
   - 无自动降级机制（MaaFw 失败后无法回退）

3. **设备检测薄弱**：
   - 无设备类型识别（无法区分 MuMu、LDPlayer、BlueStacks）
   - 无自动配置推荐（需手动设置截图/触控方式）
   - 缺少设备属性（`is_mumu_family`、`is_ldplayer` 等）

4. **错误处理简化**：
   - 无统一重试机制（MaaFw 有，但 ScreenCapture 无）
   - 缺少连点、卡死检测
   - 异常分类不细（仅 `LogCategory`）

5. **配置系统不完整**：
   - 无 `Config` 装饰器，运行时切换困难
   - 配置项分散，无统一管理

---

## 三、迁移方案设计

### 3.1 架构整合策略

**核心原则：**
- **增量迁移**：不重写现有代码，逐步增强
- **向后兼容**：保持现有 API 不变，内部优化
- **配置驱动**：通过 `client_config.json` 控制行为
- **智能降级**：优先 StarRailCopilot 的高性能方案，失败回退到现有方案

**整合架构图：**

```
┌─────────────────────────────────────────────────────────────┐
│                    TouchManager (现有)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  connect_android() → MaaFwTouchExecutor              │  │
│  │    ├─ MaaFramework (Pipeline优先)                    │  │
│  │    ├─ 失败降级：ADB触控（新增）                       │  │
│  │    └─ 失败降级：minitouch/scrcpy（未来）             │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 ScreenCapture (现有)                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  capture_screen()                                    │  │
│  │    ├─ scrcpy (现有)                                  │  │
│  │    ├─ MAA回退 (现有)                                 │  │
│  │    ├─ ADB回退 (现有)                                 │  │
│  │    └─ 新增：nemu_ipc / ldopengl / DroidCast         │  │
│  └──────────────────────────────────────────────────────┘  │
│         ▲                                                 │
│         │                                                 │
│  ┌──────┴──────────────────────────────────────────────┐  │
│  │  StarRailCopilot 截图 Mixin（新增集成层）            │  │
│  │  - Adb (增强：retry、错误处理)                       │  │
│  │  - Scrcpy (增强：自动重启、分辨率检测)               │  │
│  │  - NemuIpc (新增)                                    │  │
│  │  - LDOpenGL (新增)                                   │  │
│  │  - DroidCast (增强)                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               ADBDeviceManager (现有)                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  - 设备发现、连接、shell命令                         │  │
│  │  - adbutils AdbClient（socket连接）                  │  │
│  │  - 新增：设备属性检测（is_mumu_family等）            │  │
│  │  - 新增：智能配置推荐（根据设备类型）                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 分阶段实施计划

#### 阶段 1：增强 ADBDeviceManager（1-2天）

**目标：** 添加设备属性检测和智能推荐

**新增文件：**
- `src/core/capability/device/device_detector.py` - 设备检测器

**修改文件：**
- `src/core/capability/device/adb_manager.py` - 集成设备检测

**实现内容：**

1. **DeviceDetector 类**：
   ```python
   class DeviceDetector:
       """设备类型检测器"""

       def __init__(self, adb_manager: ADBDeviceManager):
           self.adb_manager = adb_manager
           self.logger = get_logger()

       def detect_device_type(self, serial: str) -> DeviceType:
           """检测设备类型（MuMu、LDPlayer、BlueStacks、WSA、普通设备）"""
           # 通过 getprop 查询特征属性
           # 通过端口号判断（MuMu: 16384-17408）
           # 通过 ro.product.brand 判断（waydroid、bluestacks）

       def get_recommended_config(self, device_type: DeviceType) -> dict:
           """根据设备类型返回推荐的截图/触控配置"""
           # MuMu → nemu_ipc + MaaTouch
           # LDPlayer → ldopengl + MaaTouch
           # BlueStacks → scrcpy + MaaTouch
           # WSA → scrcpy + ADB触控
   ```

2. **ADBDeviceManager 集成**：
   ```python
   class ADBDeviceManager:
       def __init__(self, ...):
           ...
           self._detector = DeviceDetector(self)

       def get_device_info(self, serial: str) -> DeviceInfo:
           """获取完整设备信息（含类型、推荐配置）"""
           device_type = self._detector.detect_device_type(serial)
           recommended = self._detector.get_recommended_config(device_type)
           return DeviceInfo(serial, device_type, recommended, ...)
   ```

**验收标准：**
- 能正确识别 MuMu、LDPlayer、BlueStacks、WSA、普通设备
- 返回推荐的截图/触控方案
- 不影响现有功能

#### 阶段 2：集成 StarRailCopilot 截图方案（2-3天）

**目标：** 将 7 种截图方式集成到 ScreenCapture

**新增文件：**
- `src/core/capability/screenshot/starrail_methods.py` - StarRail 截图方法集

**修改文件：**
- `src/core/capability/input/screenshot/screen_capture.py` - 扩展方法选择

**实现内容：**

1. **创建 StarRailScreenshotMixin**：
   - 从 `module.device.screenshot.Screenshot` 复制 7 个截图方法
   - 移除对 `module.base`、`module.exception` 等内部依赖
   - 替换 `self.config` 为 `self.config.get('screen', {})`
   - 替换 `self.adb` 为 `self.adb_manager.adb`（adbutils 客户端）
   - 替换 `self.logger` 为 `self.logger`（现有 logger）
   - 保留 `@retry` 装饰器（需移植 `retry.py`）

2. **移植 retry 装饰器**：
   ```python
   # src/core/capability/screenshot/retry.py
   def retry(func):
       """重试装饰器（移植自 StarRailCopilot）"""
       @wraps(func)
       def retry_wrapper(self, *args, **kwargs):
           init = None
           for _ in range(RETRY_TRIES):  # 5次
               try:
                   if callable(init):
                       time.sleep(retry_sleep(_))
                       init()
                   return func(self, *args, **kwargs)
               except (AdbError, ImageTruncated, ...):
                   # 根据异常类型决定是否重试
                   ...
           raise RequestHumanTakeover
       return retry_wrapper
   ```

3. **ScreenCapture 扩展**：
   ```python
   class ScreenCapture:
       def __init__(self, ...):
           ...
           # 初始化 StarRail 混合类
           self._starrail = StarRailScreenshotMixin(self)
           self._screenshot_methods.update({
               'nemu_ipc': self._starrail.screenshot_nemu_ipc,
               'ldopengl': self._starrail.screenshot_ldopengl,
               'droidcast': self._starrail.screenshot_droidcast,
               'droidcast_raw': self._starrail.screenshot_droidcast_raw,
               'ascreencap': self._starrail.screenshot_ascreencap,
               'ascreencap_nc': self._starrail.screenshot_ascreencap_nc,
           })

       def _determine_scrcpy_enabled(self):
           # 扩展：询问 DeviceDetector 推荐方案
           device_info = self.adb_manager.get_device_info(self.device_serial)
           if device_info.recommended_screenshot == 'nemu_ipc':
               return 'nemu_ipc'
           ...
   ```

4. **配置项扩展** (`client_config.example.json`)：
   ```json
   {
     "screen": {
       "method": "auto",
       "scrcpy": {
         "frame_rate": 10,
         "max_resolution": 1280,
         "bitrate": 20000000,
         "auto_restart": true
       },
       "nemu_ipc": {
         "enabled": true
       },
       "ldopengl": {
         "enabled": true
       },
       "droidcast": {
         "enabled": true
       },
       "adb": {
         "use_nc": false
       }
     }
   }
   ```

**验收标准：**
- 支持 7 种截图方式（至少 5 种可工作）
- 自动选择推荐方案（根据设备类型）
- 失败降级机制正常（nemu_ipc → scrcpy → ADB）
- 性能监控正常（`log_performance`）

#### 阶段 3：集成 StarRailCopilot 触控方案（2-3天）

**目标：** 扩展 TouchManager 支持多种触控方式

**新增文件：**
- `src/core/capability/device/touch/starrail_control.py` - StarRail 触控方法集

**修改文件：**
- `src/core/capability/device/touch/touch_manager.py` - 扩展执行器

**实现内容：**

1. **创建 StarRailControlMixin**：
   - 从 `module.device.control.Control` 复制触控方法
   - 依赖 `module.device.method.*`，需移植这些文件：
     - `method/minitouch.py`
     - `method/scrcpy.py`
     - `method/hermit.py`
     - `method/nemu_ipc.py`
   - 移除对 `module.base` 依赖，替换为本地工具函数

2. **移植 minitouch 相关**：
   - `src/core/capability/device/touch/minitouch_commands.py` - CommandBuilder
   - `src/core/capability/device/touch/minitouch.py` - Minitouch 执行器
   - `src/core/capability/device/touch/insert_swipe.py` - 滑动插值算法

3. **移植 scrcpy 触控**：
   - `src/core/capability/device/touch/scrcpy_control.py` - scrcpy 触控实现
   - 依赖 `scrcpy` 库（pip install scrcpy-client）

4. **TouchManager 扩展**：
   ```python
   class TouchManager:
       def __init__(self):
           ...
           self._control_methods = {
               'MaaTouch': self._maa_executor,
               'minitouch': None,      # 延迟初始化
               'scrcpy': None,         # 延迟初始化
               'nemu_ipc': None,       # 延迟初始化
               'hermit': None,         # 延迟初始化
               'ADB': self._adb_control  # 始终可用
           }

       def connect_android(self, ..., control_method: str = 'auto'):
           # auto 时询问 DeviceDetector 推荐
           if control_method == 'auto':
               device_info = self.adb_manager.get_device_info(address)
               control_method = device_info.recommended_control

           if control_method == 'MaaTouch':
               self._android_executor = MaaFwTouchExecutor(...)
           elif control_method == 'minitouch':
               self._android_executor = MinitouchExecutor(...)
           elif control_method == 'scrcpy':
               self._android_executor = ScrcpyControlExecutor(...)
           ...
   ```

5. **ADB 触控实现**（`_adb_control`）：
   ```python
   class ADBControl:
       def __init__(self, adb_manager: ADBDeviceManager, serial: str):
           self.adb_manager = adb_manager
           self.serial = serial

       def click(self, x, y):
           self.adb_manager.shell_command(self.serial, f"input tap {x} {y}")

       def swipe(self, x1, y1, x2, y2, duration):
           self.adb_manager.shell_command(self.serial,
               f"input swipe {x1} {y1} {x2} {y2} {duration}")
   ```

**配置项扩展：**
```json
{
  "touch": {
    "method": "auto",
    "maa_touch": {
      "enabled": true,
      "press_duration_ms": 50,
      "press_jitter_px": 2
    },
    "minitouch": {
      "enabled": true
    },
    "scrcpy": {
      "enabled": true
    },
    "nemu_ipc": {
      "enabled": true
    },
    "hermit": {
      "enabled": true
    },
    "adb": {
      "enabled": true
    }
  }
}
```

**验收标准：**
- 支持 5 种触控方式（MaaTouch、minitouch、scrcpy、nemu_ipc、ADB）
- 自动选择推荐方案
- 失败降级（MaaTouch → minitouch → scrcpy → ADB）
- Pipeline 任务正常执行

#### 阶段 4：错误处理与性能优化（1天）

**目标：** 移植 StarRailCopilot 的错误处理机制

**新增文件：**
- `src/core/capability/device/error_handler.py` - 错误处理器
- `src/core/capability/device/stuck_detector.py` - 卡死/连点检测

**实现内容：**

1. **StuckDetector**（移植自 `device.py`）：
   ```python
   class StuckDetector:
       def __init__(self, timeout=60, max_clicks=30):
           self.stuck_timer = Timer(timeout, count=timeout)
           self.click_record = deque(maxlen=max_clicks)
           self.detect_record = set()

       def record_click(self, button: str):
           self.click_record.append(button)

       def check_stuck(self) -> bool:
           if self.stuck_timer.reached():
               # 触发卡死异常
               return True
           # 检查连点
           first15 = islice(self.click_record, 0, 15)
           count = Counter(first15).most_common(2)
           if count[0][1] >= 12:  # 15次中12次相同
               return True
           return False
   ```

2. **RetryHandler**（增强现有 retry）：
   - 支持 `RequestHumanTakeover` 不重试
   - 支持 `AdbError` 根据错误码决定重试
   - 支持 `ImageTruncated` 自动重试截图

3. **集成到 ScreenCapture 和 TouchManager**：
   ```python
   class ScreenCapture:
       def __init__(self):
           self._stuck_detector = StuckDetector()
           self._error_handler = ErrorHandler(self.logger)

       def capture_screen(self, device_serial):
           try:
               self._stuck_detector.record_operation('screenshot')
               ...
           except AdbError as e:
               if self._error_handler.should_retry(e):
                   self.adb_manager.adb_reconnect()
                   # 重试
               else:
                   raise
   ```

**验收标准：**
- 卡死检测正常（60秒无操作触发）
- 连点检测正常（15次点击12次相同触发）
- 重试机制正常（5次重试，指数退避）
- 异常分类清晰（`AdbError`、`ImageTruncated`、`RequestHumanTakeover`）

#### 阶段 5：配置系统集成（1天）

**目标：** 统一配置管理，支持动态切换

**修改文件：**
- `src/core/foundation/config.py`（如不存在则新建）
- `config/client_config.example.json`

**实现内容：**

1. **Config 系统**（移植 `module.base.decorator.Config`）：
   ```python
   # src/core/foundation/config.py
   class Config:
       """配置装饰器，支持运行时条件切换"""

       @staticmethod
       def when(condition: str):
           def decorator(func):
               @wraps(func)
               def wrapper(self, *args, **kwargs):
                   if self._check_condition(condition):
                       return func(self, *args, **kwargs)
                   else:
                       # 调用下一个匹配的或默认实现
                       ...
               return wrapper
           return decorator
   ```

2. **配置项定义**：
   ```python
   # config/client_config.json
   {
     "device": {
       "emulator": {
         "screenshot_method": "auto",  # auto/scrcpy/nemu_ipc/ldopengl/adb
         "control_method": "auto",     # auto/MaaTouch/minitouch/scrcpy/nemu_ipc/ADB
         "serial": "auto"
       }
     },
     "screen": {
       "min_interval": 0.1,
       "save_interval": 1.0,
       "save_folder": "cache/screenshots"
     },
     "touch": {
       "press_duration_ms": 50,
       "swipe_duration_ms": 300,
       "long_press_duration_ms": 1000
     },
     "error": {
       "save_screenshots": true,
       "screenshot_length": 30,
       "stuck_timeout": 60
     }
   }
   ```

3. **ConfigManager 类**：
   ```python
   class ConfigManager:
       def __init__(self, config_path: str):
           self._config = self._load_config(config_path)
           self._listeners = []

       def get(self, key: str, default=None):
           return deep_get(self._config, key, default)

       def set(self, key: str, value):
           self._config = deep_set(self._config, key, value)
           self._notify_listeners(key, value)
   ```

**验收标准：**
- 支持 `Config.when(DEVICE_OVER_HTTP=False)` 风格的条件装饰器
- 配置可动态修改（`config.set('device.screenshot_method', 'scrcpy')`）
- 配置变更通知机制（用于 UI 实时更新）

#### 阶段 5.5：MaaFramework 降级方案（关键）

**问题：** MaaFw 可能未安装或版本不兼容

**解决方案：**

1. **MaaFw 可选依赖**：
   - 不强制要求 `pip install MaaFw`
   - 未安装时自动降级到 ADB 触控

2. **MaaFw 版本检测**：
   ```python
   try:
       from maa import Library
       # 检查版本号
       version = Library.version()
       if version < (5, 10, 0):
           logger.warning("MaaFw 版本过低，建议升级到 5.10.0+")
   except ImportError:
       MAAFW_AVAILABLE = False
   ```

3. **TouchManager 降级逻辑**：
   ```python
   def connect_android(self, ..., control_method='auto'):
       if control_method in ('auto', 'MaaTouch'):
           if MAAFW_AVAILABLE:
               self._android_executor = MaaFwTouchExecutor(...)
           else:
               logger.warning("MaaFramework 未安装，降级到 ADB 触控")
               self._android_executor = ADBControlExecutor(...)
       elif control_method == 'minitouch':
           # 检查 minitouch 是否可用
           ...
   ```

4. **ADBControlExecutor 实现**：
   - 直接调用 `adb_manager.shell_command()` 执行 `input tap/swipe`
   - 无 Pipeline 支持，仅单次控制
   - 性能较差但保证可用性

**验收标准：**
- MaaFw 未安装时，TouchManager 仍能连接并执行基本操作
- 控制方法可手动指定（`config.set('touch.method', 'ADB')`）
- 日志清晰提示降级原因

---

## 四、关键问题与解决方案

### 4.1 坐标系统与归一化

**问题：**
- StarRailCopilot：固定 1280x720 坐标空间
- IstinaEndfieldAssistant：使用原始分辨率，支持归一化
- MaaFw 内部可能缩放分辨率（`self._resolution` 与原始分辨率不同）

**解决方案：**
- 保持现有设计：**外部传入原始分辨率坐标**
- 在 `MaaFwTouchExecutor` 内部进行坐标转换（已有 `_convert_to_maa_coords`）
- 其他触控方式（minitouch、scrcpy）也需统一使用原始分辨率
- **关键修改**：确保所有触控实现都接受原始分辨率坐标，内部不做缩放

### 4.2 截图分辨率与性能

**问题：**
- scrcpy 视频流可能高分辨率（1080p、2k），网络带宽受限
- MaaFw 截图可能自动缩放到 1280x720

**解决方案：**
- **scrcpy**：配置 `max_resolution` 限制（`config.screen.scrcpy.max_resolution=1280`）
- **MaaFw**：保持 `use_normalized_coords=True`，让 MaaFw 内部处理缩放
- **ADB**：原始分辨率，后续可缩放
- **统一输出**：所有截图方法最终返回 `base64` 编码的 PNG 字节（保持现有接口）

### 4.3 依赖管理

**问题：**
- StarRailCopilot 依赖 `module.base`、`module.exception`、`module.logger` 等内部模块
- 直接复制代码会引入大量依赖

**解决方案：**
- **最小化移植**：仅复制核心逻辑，移除不必要的依赖
- **依赖替换表**：

| StarRailCopilot 依赖 | 替换为 |
|---------------------|--------|
| `module.base.decorator.cached_property` | `functools.cached_property` (Python 3.8+) |
| `module.base.decorator.Config` | 自建 `Config` 装饰器或直接读取 `self.config` |
| `module.base.timer.Timer` | 自建简单 `Timer` 类或 `time.time()` |
| `module.base.utils.*` | 复制所需函数到 `src/core/capability/shared/utils.py` |
| `module.exception.*` | 使用内置异常或自定义异常 |
| `module.logger.logger` | 使用 `get_logger()` |
| `module.device.connection.Connection` | 使用 `ADBDeviceManager` |
| `module.device.method.*` | 直接复制到 `touch/` 目录，移除 `Connection` 继承 |

### 4.4 线程安全与资源管理

**问题：**
- scrcpy 视频流在后台线程持续接收
- MaaFw 有初始化线程（`early_maatouch_init`）
- 多设备并发连接

**解决方案：**
- **ScreenCapture**：已实现 `_scrcpy_core` 单例，需确保线程安全
  - 添加锁：`self._lock = threading.Lock()`
  - `start_scrcpy()`、`stop_scrcpy()`、`get_latest_frame()` 加锁
- **MaaFwTouchExecutor**：已有 `_library_loaded` 锁，保持现状
- **多设备**：`ADBDeviceManager` 无状态，可共享；`ScreenCapture` 和 `TouchManager` 需按设备序列号隔离实例

### 4.5 错误恢复与用户提示

**问题：**
- 自动降级可能频繁发生，用户不知情
- 需要明确提示用户安装缺失组件

**解决方案：**
- **分级日志**：
  - INFO：自动降级（"scrcpy 不可用，切换到 ADB 截图"）
  - WARNING：建议安装（"建议安装 MaaFramework 以提升性能"）
  - ERROR：严重错误（"所有截图方式均失败"）
- **配置检查**：启动时验证配置有效性，输出建议
- **GUI 提示**：如运行 GUI，在状态栏显示当前使用的截图/触控方式

---

## 五、代码修改详细清单

### 5.1 新增文件清单

```
src/core/capability/device/
├── device_detector.py                    # 设备检测器（阶段1）
├── error_handler.py                      # 错误处理器（阶段4）
├── stuck_detector.py                     # 卡死/连点检测（阶段4）
└── touch/
    ├── starrail_control.py               # StarRail 触控方法集（阶段3）
    ├── minitouch_commands.py             # Minitouch 命令构建器
    ├── minitouch.py                      # Minitouch 执行器
    ├── scrcpy_control.py                 # scrcpy 触控
    ├── nemu_ipc_control.py               # MuMu IPC 触控
    ├── hermit_control.py                 # Hermit 触控
    └── adb_control.py                    # ADB 触控（简单实现）

src/core/capability/screenshot/
├── starrail_methods.py                   # StarRail 截图方法集（阶段2）
├── retry.py                              # 重试装饰器
├── utils.py                              # 工具函数（移植自 module.base.utils）
└── exceptions.py                        # 异常定义（移植自 module.exception）

src/core/foundation/
├── config.py                             # 配置系统（阶段5）
└── decorators.py                        # 装饰器集合（Config、cached_property 等）
```

### 5.2 修改文件清单

```
# 阶段1
src/core/capability/device/adb_manager.py
  - 添加 DeviceDetector 成员
  - 添加 get_device_info() 方法

# 阶段2
src/core/capability/input/screenshot/screen_capture.py
  - 集成 StarRailScreenshotMixin
  - 扩展 _screenshot_methods 字典
  - 修改 _determine_scrcpy_enabled() 加入设备检测
  - 添加配置项读取

# 阶段3
src/core/capability/device/touch/touch_manager.py
  - 扩展 _control_methods 字典
  - 修改 connect_android() 支持多种控制方式
  - 添加 _adb_control 成员
  - 集成 StarRailControlMixin

src/core/capability/device/touch/maafw_touch_adapter.py
  - 确保坐标转换正确（已实现）
  - 添加 `_original_resolution` 成员（从 ADB 查询）

# 阶段4
src/core/capability/device/adb_manager.py
  - 集成 StuckDetector（可选，用于 ADB 操作）
src/core/capability/input/screenshot/screen_capture.py
  - 集成 StuckDetector
  - 集成 ErrorHandler
```

### 5.3 配置项修改

`config/client_config.example.json` 新增：

```json
{
  "device": {
    "emulator": {
      "screenshot_method": "auto",
      "control_method": "auto",
      "serial": "auto",
      "auto_detect": true
    }
  },
  "screen": {
    "min_interval": 0.1,
    "methods": {
      "scrcpy": {
        "enabled": true,
        "frame_rate": 10,
        "max_resolution": 1280,
        "bitrate": 20000000,
        "auto_restart": true
      },
      "nemu_ipc": {
        "enabled": true
      },
      "ldopengl": {
        "enabled": true
      },
      "droidcast": {
        "enabled": true
      },
      "adb": {
        "enabled": true,
        "use_nc": false
      }
    }
  },
  "touch": {
    "method": "auto",
    "methods": {
      "MaaTouch": {
        "enabled": true,
        "press_duration_ms": 50,
        "press_jitter_px": 2,
        "use_normalized_coords": true
      },
      "minitouch": {
        "enabled": true
      },
      "scrcpy": {
        "enabled": true
      },
      "nemu_ipc": {
        "enabled": true
      },
      "ADB": {
        "enabled": true
      }
    }
  },
  "error": {
    "save_screenshots": true,
    "screenshot_length": 30,
    "stuck_timeout_seconds": 60,
    "click_record_length": 30,
    "max_clicks_per_15": 12
  }
}
```

---

## 六、风险评估与应对

### 6.1 技术风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| MaaFramework 版本冲突 | 触控功能失效 | 中 | 提供 ADB 降级方案；明确版本要求（5.10.0+） |
| scrcpy 性能不稳定 | 截图卡顿 | 低 | 自动重启机制；回退到其他方法 |
| nemu_ipc 仅限 MuMu | 设备兼容性 | 高 | 设备检测后仅对 MuMu 推荐 |
| 坐标转换错误 | 点击偏移 | 中 | 单元测试验证；截图对比 |
| 依赖移植不完整 | ImportError | 中 | 逐步测试每种方法；完整依赖映射表 |

### 6.2 兼容性风险

- **现有 API 变更**：TouchManager 和 ScreenCapture 保持 API 不变，内部增强 → **低风险**
- **配置项新增**：旧配置可继续使用，新功能默认关闭 → **低风险**
- **性能回归**：新增检测逻辑增加开销 → 基准测试验证（<1ms） → **中风险**

### 6.3 维护成本

- **代码量增加**：约 +3000 行（StarRail 移植 + 适配层）
- **测试覆盖**：需为每种截图/触控方式编写集成测试
- **文档更新**：需更新 `AGENTS.md`、`README.md`、配置模板

---

## 七、测试计划

### 7.1 单元测试

- `test_device_detector.py`：设备类型识别准确率
- `test_stuck_detector.py`：卡死/连点检测逻辑
- `test_coordinate_conversion.py`：坐标转换精度
- `test_config_system.py`：配置加载、动态修改

### 7.2 集成测试（需真实设备）

| 测试项 | 设备 | 截图方案 | 触控方案 | 预期结果 |
|--------|------|----------|----------|----------|
| 截图-ADB | 任意 | ADB | - | PNG 数据正确，耗时 <500ms |
| 截图-scrcpy | 任意 | scrcpy | - | 视频流稳定，延迟 <100ms |
| 截图-nemu_ipc | MuMu 12+ | nemu_ipc | - | 零拷贝，延迟 <50ms |
| 触控-MaaTouch | 任意 | - | MaaTouch | 点击准确，延迟 <100ms |
| 触控-minitouch | 任意 | - | minitouch | 点击准确，延迟 <150ms |
| 触控-ADB | 任意 | - | ADB | 点击准确，延迟 <300ms |
| 降级-scrcpy→ADB | 任意 | scrcpy 失败 | - | 自动切换，日志提示 |
| 降级-MaaTouch→ADB | 任意 | - | MaaTouch 失败 | 自动切换，日志提示 |
| Pipeline 任务 | 任意 | scrcpy | MaaTouch | 任务编排成功 |

### 7.3 性能基准

- **截图延迟**（平均）：
  - scrcpy: <100ms
  - nemu_ipc: <50ms
  - ADB: <500ms
- **触控延迟**（点击到响应）：
  - MaaTouch: <100ms
  - minitouch: <150ms
  - ADB: <300ms
- **内存占用**：<50MB（不含 scrcpy 视频流缓冲区）

---

## 八、交付物清单

1. **完整代码**：
   - 新增 15+ 文件（见 5.1）
   - 修改 5+ 文件（见 5.2）
   - 总计约 +3000 行

2. **配置模板更新**：
   - `config/client_config.example.json` 新增截图/触控配置段
   - `config/logging_config.json` 可选（保持现有）

3. **文档**：
   - `docs/DEVICE_CONTROL_MIGRATION.md`（本报告）
   - `docs/SCREENSHOT_METHODS.md` - 截图方法对比与使用指南
   - `docs/TOUCH_METHODS.md` - 触控方法对比与使用指南
   - `AGENTS.md` 更新 - 新增设备控制说明

4. **测试报告**：
   - `test_results/screenshot_benchmark.json`
   - `test_results/touch_benchmark.json`
   - `test_results/device_detection.json`

5. **迁移脚本**（可选）：
   - `scripts/migrate_device_control.py` - 自动复制 StarRail 代码并适配

---

## 九、后续优化方向

### 9.1 短期（迁移完成后1周）

- **性能调优**：根据实际设备测试结果，调整默认配置
- **异常监控**：增加 Sentry 或类似错误上报
- **用户反馈**：收集实际使用中的兼容性问题，更新设备检测规则

### 9.2 中期（1-3个月）

- **Pipeline 编辑器**：GUI 可视化编辑任务流程
- **AI 坐标预测**：基于 VLM 自动校准坐标偏移
- **多设备并行**：同时控制多个设备，负载均衡
- **云端同步**：设备配置云端备份（Sight 分支可能不需要）

### 9.3 长期（3-6个月）

- **自研触控协议**：基于 USB HID 的直接触控（绕过 ADB）
- **内核级截图**：使用 framebuffer 直接读取（root）
- **机器学习优化**：自适应选择最佳截图/触控组合

---

## 十、总结

本迁移方案基于 **StarRailCopilot** 成熟的设备控制架构，结合 **IstinaEndfieldAssistant_Sight** 现有的模块化设计，提出 **增量迁移、智能降级、配置驱动** 的整合策略。

**核心优势：**
1. **兼容性提升**：支持 7 种截图、5 种触控，覆盖所有主流模拟器
2. **性能提升**：scrcpy/nemu_ipc 视频流 + MaaTouch，延迟降低 50%+
3. **可靠性提升**：自动降级 + 重试 + 卡死检测，减少人工干预
4. **可维护性**：模块化设计，配置驱动，易于扩展新方法

**实施成本：** 约 5-7 人天（含测试）
**风险等级：** 中等（依赖移植复杂度，但可逐步验证）
**预期收益：** 显著提升设备兼容性和自动化稳定性

---

**附录：StarRailCopilot 关键文件索引**

| 文件 | 用途 | 迁移优先级 |
|------|------|-----------|
| `module/device/device.py` | 主设备类（整合） | 参考 |
| `module/device/screenshot.py` | 截图 Mixin | 高 |
| `module/device/control.py` | 触控 Mixin | 高 |
| `module/device/app_control.py` | 应用控制 | 中 |
| `module/device/connection.py` | 连接管理 | 高（部分） |
| `module/device/method/*.py` | 具体实现 | 高 |
| `module/base/decorator.py` | 装饰器（Config、cached_property） | 中 |
| `module/base/timer.py` | Timer 类 | 低（可简化） |
| `module/base/utils.py` | 工具函数 | 中 |
| `module/exception.py` | 异常定义 | 低（可简化） |
| `module/logger.py` | 日志（已有替代） | 无 |

---

**报告生成时间：** 2026-06-23
**分析基于：** StarRailCopilot_Published (最新版本)