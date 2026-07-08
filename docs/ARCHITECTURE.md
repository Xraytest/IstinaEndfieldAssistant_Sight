# 项目架构总览

## 1. 核心语言与生态

| 维度 | IEA (IstinaEndfieldAssistant) | MaaEnd |
|------|------------------------------|--------|
| **主要语言** | Python 3.12+ | TypeScript/JavaScript + Go 1.25.6 + C++ |
| **GUI 框架** | PyQt6 | 无原生 GUI（仅 CLI/独立运行器） |
| **运行时** | CPython + venv | Node.js 22+ + Go 可执行文件 + C++ DLL |
| **包管理** | pip / requirements.txt | pnpm (Node.js) + Go modules + CMake |
| **AI/ML 栈** | torch, ultralytics, onnxruntime, llama-cpp | 无 Python AI 依赖（C++ ONNX Runtime 用于算法） |
| **LLM 位置** | `src/core/capability/llm/`（LlamaServerRuntime + LlamaClient） | Go service 中无 Python LLM 依赖 |
| **构建系统** | 无（纯 Python 解释执行） | CMake (C++) + pnpm (TS) + Go build + Python build_and_install.py |
| **代码格式化** | 基础 lint | Prettier (JSON/YAML/MD) + go fmt + maa-tools check |

## 2. 架构分层对比

### IEA — 分层 Python 架构

```
src/
├── core/
│   ├── capability/        # 能力层
│   │   ├── device/        # ADB/Android 设备交互 (ADBDeviceManager, TouchManager, AndroidRuntime + JSON-RPC daemon)
│   │   ├── element_recognition/  # 场景理解（Template/OCR/Color/YOLO 4 种识别后端 + Pipeline 图引擎）
│   │   ├── input/         # 输入控制（OCR 引擎归并在 element_recognition/backends/ 下）
│   │   └── llm/           # LLM 运行时（llama-server 桥接、VLM）
│   ├── foundation/        # 基础层（日志、路径、GPU 检查）
│   └── service/           # 服务层
│       ├── maa_end/       # MaaFramework Python 运行时桥接
│       ├── navigation/    # 导航服务（实体/坐标/VLM 行走）
│       └── runtime.py     # 统一运行时入口（IstinaRuntime）
├── gui/pyqt6/             # GUI 页面/组件（5 个页面 + CLIBridge）
└── cli/                   # CLI 命令路由（istina.py + handlers.py）
```

### MaaEnd — 四层 MaaFramework 原生架构

```
MaaEnd/
├── assets/
│   ├── interface.json              # 第 1 层：项目入口（控制器、资源、Agent、任务导入）
│   ├── tasks/                      # 第 2 层：任务定义（option、pipeline_override）
│   │   └── preset/                 #     预设（DailyFull、QuickDaily、RealtimeAssist）
│   └── resource/
│       └── pipeline/               # 第 3 层：低代码 FSM Pipeline 节点
├── agent/                          # 第 4 层：自定义逻辑扩展
│   ├── go-service/                 #     Go 编写的 30+ 业务包（Custom Action/Recognition）
│   └── cpp-algo/                   #     C++ 算法加速（MapLocator、MapNavigator 等）
├── tools/                          # Node.js 工具链（pipeline 生成器、i18n 同步）
└── tests/                          # MaaTools 测试套件
```

**执行路径**：`Task → Pipeline 节点 FSM → 识别/操作循环 → 必要时调用 Go/C++ 自定义逻辑`

## 3. 运行时模型差异

### IEA 作为"上层智能协调器"

IEA 不直接实现游戏自动化逻辑，而是作为 **Python 层的统一协调器**：

- `IstinaRuntime` 封装了设备层 (`AndroidRuntimeProxy`)、MaaEnd 运行时 (`MaaEndRuntime`)、LLM 运行时 (`LlamaServerRuntime`)、场景理解 (`SceneUnderstandingService`) 和导航 (`Navigator`)
- 通过 `MaaEndRuntime` 加载 MaaEnd 的 `interface.json` 和任务 JSON
- 将 IEA 的 JSON 配置转换为 MaaEnd 的 `pipeline_override`，驱动 MaaFramework 执行
- 额外提供 IEA 独有的能力：VLM 导航 (`nav3`)、多后端场景理解 (`scene.identify`)、LLM 对话 (`llm.chat`)

### MaaEnd 作为"原生执行引擎"

MaaEnd 是 MaaFramework 的 **原生扩展**，采用"Pipeline 管流程，Go/C++ 管难点"的设计原则：

- **第 1 层** `interface.json`：注册 4 种控制器（Win32-Front、ADB、PlayCover、Wlroots）、8 个任务组、2 个 Agent 进程（go-service + cpp-algo）
- **第 2 层** `assets/tasks/*.json`：声明式任务定义，包含 `option` 系统（switch/checkbox/select/input）和 `pipeline_override`
- **第 3 层** `assets/resource/pipeline/*.json`：低代码 FSM（有限状态机），定义识别→操作→跳转流程
- **第 4 层** `agent/`：Go/C++ 实现 Pipeline 难以表达的复杂逻辑（实时战斗、地图定位、基质扫描等）

## 4. 任务与预设系统

### IEA 的任务加载方式

```python
# src/core/service/maa_end/runtime.py
class MaaEndRuntime:
    def load_tasks(self):
        # 递归扫描 MaaEnd/assets/tasks/**/*.json
        # 提取 task 列表和全局 option 定义
        # 构建 self._tasks: Dict[name, task_def]

    def build_pipeline_override(self, task_name, options):
        # 根据 option 定义（switch/checkbox/select/input）
        # 动态生成 pipeline_override
        # 支持嵌套选项和 {token} 替换
```

IEA 在 Python 中**动态构建** pipeline override，这意味着：
- 可以在运行时灵活调整选项
- 支持 IEA 特有的导航参数（如 `nav.to_coords`）
- 不依赖 MaaEnd 的编译流程
- IEA 自身也有精简版 `assets/tasks/` 和 `assets/pipelines/`（约 12 个模块），但核心执行已迁移到 MaaEnd

### MaaEnd 的任务定义方式

```json
// assets/tasks/DailyRewards.json
{
    "task": [{
        "name": "DailyRewards",
        "entry": "DailyRewardStart",
        "option": ["DailyEmailRewards", "DailyTaskRewards", ...],
        "controller": ["Win32-Front", "ADB", "PlayCover", "Wlroots"],
        "group": ["other_menu"]
    }],
    "option": {
        "DailyEmailRewards": {
            "type": "switch",
            "cases": [{
                "name": "Yes",
                "pipeline_override": {"DailyEmailRewardSub": {"enabled": true}}
            }]
        }
    }
}
```

MaaEnd 的任务是**静态 JSON**，通过 MaaFramework 的 `Tasker.post_task()` 直接执行。option 系统支持：
- **switch**：布尔开关，启用/禁用 Pipeline 子节点
- **checkbox**：多选，激活多个 case
- **select**：单选，选择执行路径
- **input**：用户输入，支持 `{token}` 替换和正则校验

### 预设（Preset）系统

MaaEnd 的预设是任务序列：

```json
// assets/tasks/preset/DailyFull.json
{
  "preset": [
    {"name": "VisitFriends", "option": {...}},
    {"name": "DijiangRewards", "option": {...}},
    {"name": "CreditShoppingN2", "option": {...}},
    {"name": "DeliveryJobs", "option": {...}},
    {"name": "SellProduct"},
    {"name": "AutoStockpile"},
    {"name": "AutoStockStaple"},
    {"name": "AutoSell"},
    {"name": "EnvironmentMonitoring"},
    // ... 20+ tasks
  ]
}
```

MaaEnd 提供 3 个预设：`DailyFull`（全套日常）、`QuickDaily`（快速日常）、`RealtimeAssist`（实时开荒辅助）。

## 5. Pipeline 系统差异

### IEA — Python Pipeline 引擎

IEA 实现了自己的 Pipeline 执行引擎：

- **`PipelineNode`**：数据类表示识别/操作节点，支持 `DirectHit`、`TemplateMatch`、`OCR`、`ColorMatch`、`And`、`Or` 识别类型
- **`PipelineGraph`**：有向图，支持入口解析
- **`PipelineLoader`**：从 `assets/pipelines/` 和 MaaEnd 的 `resource/pipeline/nodes.json` 加载
- **`PipelineRunner`**：执行 Pipeline 图，支持限流、最大命中次数、前置/后置延迟、冻结等待
- **双路由模板匹配**：优先 MaaFramework 原生识别，失败则回退到 OpenCV

### MaaEnd — MaaFramework Pipeline FSM

MaaEnd 的 Pipeline 是 MaaFramework **Pipeline 协议**的扩展，核心是**有限状态机(FSM)**：

```json
{
    "NodeName": {
        "recognition": {"type": "TemplateMatch", "param": {...}},
        "action": {"type": "Click"},
        "next": ["NextNode", "[JumpBack]SceneManager"],
        "pre_delay": 0, "post_delay": 0
    }
}
```

**MaaEnd 编码规范（关键规则）**：
- **禁止硬延迟**：不用 `pre_delay`/`post_delay`，优先用中间识别节点
- **首轮命中**：扩充 `next` 列表，确保一次截图就命中
- **原子化操作**：每步操作都有独立识别节点
- **OCR 完整文本**：`expected` 必须写完整文本，禁止写片段

**万能场景跳转（SceneManager / [JumpBack]）**：
- `SceneAnyEnterWorld`：从任意界面进入任意大世界
- `SceneEnterMenuRegionalDevelopment`：从任意界面进入地区建设菜单
- `[JumpBack]` 语法：无法识别时回退到更基础场景
- 公开接口（`Interface/`）供任务使用，私有实现（`SceneManager/`）禁止直接引用

## 6. 导航系统差异

### IEA — 三层导航

| 层级 | 名称 | 技术 | 文件 |
|------|------|------|------|
| **Nav1** | MaaEnd 原生导航 | MaaEnd `MapTracker` 任务 | `MaaEndRuntime.run_task()` |
| **Nav2** | scrcpy 视觉导航 | 小地图识别 + navmesh | `navigation/minimap_locator.py`, `navigator.py`, `entity_db.py`, `map_data_loader.py` |
| **Nav3** | VLM 驱动行走 | llama-server 视觉推理 | `navigation/vlm_walk_navigator.py` |

IEA 的导航更偏向**研究与探索**（VLM 理解、实体查询、坐标导航）。

### MaaEnd — C++ 算法导航

MaaEnd 的导航主要由 C++ 实现：

| 组件 | 职责 |
|------|------|
| `cpp-algo/source/MapLocator/` | AI+CV 小地图定位（YOLO 预测器、运动追踪、匹配策略） |
| `cpp-algo/source/MapNavigator/` | 高精度自动导航（A* 寻路、动作执行器、采集扫描器） |
| `cpp-algo/source/EssenceGridScan/` | 基质网格识别与滚动扫描 |
| `cpp-algo/source/RecoGrid/` | 网格识别与滚动累计扫描引擎 |
| `cpp-algo/source/Navmesh/` | 导航网格 |

MaaEnd 的导航更偏向**游戏内自动化**（自动寻路、自动战斗、自动采集）。

## 7. 场景理解差异

### IEA — 混合识别引擎（4 后端）

```python
class EndfieldElementRecognizer:
    def __init__(self):
        self._backends = [
            TemplateBackend(),   # OpenCV SIFT + MaaFW 双路由
            OCRBackend(),        # MaaFramework OCR (JOCR)
            ColorBackend(),      # HSV 颜色空间轮廓检测
            YOLOBackend(),       # YOLO11 游戏对象检测
        ]
```

- **模板匹配**：OpenCV SIFT 特征 + 直接匹配，同时集成 MaaFramework `post_recognition`
- **OCR**：MaaFramework 内置 OCR (JOCR)
- **颜色分析**：HSV 颜色空间轮廓检测
- **YOLO**：Ultralytics YOLO11 推理
- **场景分类**：`SceneUnderstandingService` 综合多源结果，通过评分签名（required elements、color、OCR keywords、fallback）分类页面
- **页面历史**：维护页面历史栈和 dominant-page 追踪

### MaaEnd — 资源驱动识别

MaaEnd 的场景识别完全依赖：
- `assets/resource/image/` 中的模板图片（按功能分目录，基准分辨率 1280x720）
- MaaFramework 原生的 `TemplateMatch`、`OCR`、`ColorMatch` pipeline 节点
- 识别逻辑硬编码在 pipeline JSON 中
- 支持绿幕模板处理

## 8. Go Service 自定义逻辑

### MaaEnd — 30+ 业务包

MaaEnd 的 Go 服务通过 `maa-framework-go/v4` 注册 Custom Action/Recognition：

**通用组件** (`common/`):
| 包 | 功能 |
|----|------|
| `subtask` | 子任务调度器（continue/strict/random_choice） |
| `expressionrecognition` | OCR 数值表达式求值（`{NodeA} >= {NodeB}`） |
| `schedule` | 按星期几门控 |
| `pipelineoverride` | 运行时动态覆盖 Pipeline 节点 |
| `attachregex` | 将关键词拼成正则写回 OCR 节点 |
| `clearhitcount` | 清除节点命中计数 |
| `falseaction` | 始终返回失败的 Action |
| `poststop` | 异步停止当前任务 |
| `autoalt` | Alt+点击/长按/滑动 |

**业务组件**：
| 包 | 功能 |
|----|------|
| `autofight` | 实时战斗辅助（30 帧窗口分析敌人/技能/血量） |
| `autostockpile` | 自动囤货（决策引擎、商品扫描、阈值管理） |
| `essencefilter` | 基质筛选（智能识别词条） |
| `maptracker` | 小地图追踪 |
| `scenemanager` | 万能场景跳转 |
| `puzzle-solver` | 拼图求解 |
| 其他 | accountswitch, autoecofarm, autosell, creditshopping, deliveryjobs 等 |

**注册机制**：
```go
func registerAll() {
    resource.EnsureResourcePathSink()
    // Pre-Check: aspectratio, hdrcheck, processcheck, cursormove
    // General: subtask, clearhitcount, pipelineoverride, expressionrecognition, ...
    // Business: accountswitch, autofight, essencefilter, maptracker, ...
}
```

### IEA — 无等效机制

IEA 没有 Go Service 或 C++ 自定义逻辑扩展。所有"自定义"能力都在 Python 层实现：
- 导航：`VlmWalkNavigator`（VLM 决策循环）
- 场景理解：`SceneUnderstandingService`（多后端融合）
- 设备控制：`AndroidRuntime`（JSON-RPC daemon + scrcpy）

## 9. 设备控制差异

### IEA — 双轨控制 + JSON-RPC Daemon

- **ADB 通道**：通过 `AndroidRuntime`（Python + adbutils）直接控制
  - 支持截图、点击、滑动、按键、shell 命令
  - 支持 scrcpy 镜像（v2.7 tunnel_forward 协议，PyAV 解码 H.264/H.265/AV1）
  - **JSON-RPC Daemon**：后台线程暴露 TCP 接口，mmap 零拷贝传输截图
  - 跨进程单例模式（`_clients: Dict[serial, AndroidRuntime]`）
- **MaaFramework 通道**：通过 `MaaEndRuntime` 的 `AdbController` 控制

### MaaEnd — MaaFramework 原生控制

- 通过 `interface.json` 声明控制器类型
- **Win32-Front**：前台窗口截屏/输入（ScreenDC + Seize）
- **ADB**：MaaFramework 内置 ADB 控制
- **PlayCover**：macOS PlayCover 平台适配
- **Wlroots**：Linux Wlroots 合成器适配
- 无独立 GUI，通过 MaaEnd.exe 或外部调用运行

## 10. 每日全套实现对比

### MaaEnd 的 DailyFull 预设

MaaEnd 的每日全套是**纯任务序列**，包含 20+ 个子任务，每个任务包含详细的游戏自动化逻辑（点击、等待、识别）：

```json
// assets/tasks/preset/DailyFull.json
VisitFriends → DijiangRewards → CreditShoppingN2 → DeliveryJobs → SellProduct → AutoStockpile → AutoStockStaple → AutoSell → EnvironmentMonitoring → ...
```

### IEA 的 Daily 执行

```python
# src/core/service/runtime.py
def _daily_run(self, params):
    preset_name = options.get("preset", "DailyFull")
    ok = self.execute("preset.run", {"name": preset_name, "serial": serial})
    return {"status": "success" if ok else "error", ...}
```

IEA 的每日全套是**对 MaaEnd 预设的一层调用**：
- IEA 负责连接管理、配置加载、错误处理、结果包装
- 实际执行逻辑完全委托给 MaaEnd
- IEA 特有：返回结构化 JSON 状态（`maaend_connected`、`flow`、`preset`）

## 11. 测试与开发工具

| 维度 | IEA | MaaEnd |
|------|-----|--------|
| **测试框架** | pytest | MaaTools (`@nekosu/maa-tools`) |
| **测试覆盖** | 单元测试（CLI、LLM、运行时、GUI） | pipeline 校验 + 节点集成测试 |
| **代码检查** | 基础 lint | `maa-tools check` + Prettier |
| **构建系统** | 无（纯 Python） | CMake (C++) + pnpm (TS) + Go build + Python build_and_install.py |
| **资源生成** | 手工维护 | 自动化 pipeline 生成器（Node.js） |
| **CI/CD** | 无 | GitHub Actions（check/test/format/install/i18n-sync/optimize-img） |
| **Git 子模块** | 无 | MaaUtils、MaaEnd-AI（YOLO/ONNX 模型）、MaaEndTestset |
| **编码规范** | PEP 8 | 严格编码规范（禁止硬延迟、首轮命中、原子化操作） |

## 12. 扩展机制对比

### IEA — Python 可编程扩展

- 新能力通过 Python 类实现（继承/组合）
- 导航、场景理解、LLM 集成都是纯 Python 代码
- CLI/GUI 通过 `IstinaRuntime.execute()` 统一路由（30+ 命令）
- 易于快速原型开发
- 多设备序列支持（`_android_clients: Dict[serial, AndroidRuntimeProxy]`）

### MaaEnd — 四层声明式扩展

1. **Pipeline 层**：JSON 定义流程（无需编译，热重载）
2. **Task 层**：JSON 定义任务入口和选项
3. **Preset 层**：JSON 定义任务序列
4. **Agent 层**：Go/C++ 实现复杂算法
   - 注册机制：`registerAll()` → `maa.AgentServerRegisterCustomAction/Recognition`
   - Pipeline 中通过 `"action": "Custom", "custom_action": "FeatureAction"` 调用

## 13. 总结

| 维度 | IEA | MaaEnd |
|------|-----|--------|
| **定位** | 上层智能协调器 + AI 增强 | 原生游戏自动化引擎 |
| **核心优势** | AI/ML 集成（VLM、LLM、YOLO）、多模态导航、Python 生态、GUI/CLI 统一 | 性能（C++/Go）、稳定性、游戏内自动化深度、跨平台支持 |
| **开发效率** | 高（Python 动态特性，无需编译） | 中（需要编译，多语言协作） |
| **运行效率** | 中（Python 解释器开销） | 高（原生 C++/Go） |
| **可扩展性** | 易于添加新 AI 能力（Python 类） | 需要多语言协作，但 Pipeline 热重载 |
| **维护成本** | 低（单语言） | 高（多语言、多构建系统、严格规范） |
| **每日全套** | 调用 MaaEnd 的 `DailyFull` 预设 | 20+ 任务的纯 JSON 序列 |

**核心结论**：

IEA 和 MaaEnd 是**互补的父子关系**。MaaEnd 提供了扎实的游戏自动化基础（任务、pipeline、资源、控制器、Go/C++ 算法），而 IEA 在此基础上增加了：

1. **AI 能力层**：VLM 导航 (`nav3`)、LLM 对话 (`llm.chat`)、YOLO 对象检测、多后端场景理解
2. **统一运行时**：`IstinaRuntime` 统一封装设备、自动化、LLM、导航
3. **桌面交互**：PyQt6 GUI + CLI 双入口，JSON-RPC 进程隔离
4. **设备增强**：scrcpy 镜像、mmap 零拷贝截图、JSON-RPC daemon

IEA 的每日全套实际上是通过调用 MaaEnd 的预设实现的，两者的差异主要在"谁来做决策"（IEA 的 VLM/LLM vs MaaEnd 的 Pipeline FSM）和"用什么语言实现"（Python vs Go/C++）。

## 14. 设计语言参考

### 鹰角网络设计语言

> 本文件持续收集鹰角网络（Hypergryph）相关产品的设计思路，作为本项目 GUI/平面美术优化的参考来源。

#### 14.1 游戏知识库提取（`game_knowledge_base.json`）
- **产品**：明日方舟：终末地
- **包名**：`com.hypergryph.endfield`
- **参考域名**：`ak.hypergryph.com`、`endfield.hypergryph.com`
- **核心视觉元素**：
  - 基地主界面为“多面板叠加”结构
  - 游戏场景以“蓝色主导”（93.9%）
  - 存在大量工业科幻风格按钮与面板（基础工业一期/二期/三期、原料开采、物流运输等）
  - UI 元素命名带有终端/工业感：`TerminalNotice`、`EnvironmentMonitoringButton`、`WorldMenuBaker` 等
- **当前已知交互模式**：
  - 顶部行：通知、信用点、任务领取
  - 左侧列：环境监测、好友列表、拍照
  - 右侧列：世界菜单、委托领取、背包
  - 底部行：进入按钮、任务领取、任务标签

#### 14.2 鹰角产品设计共性（持续补充）
- **明日方舟（Arknights）**
  - 深色底 + 高对比信息色（黑/白/蓝/黄/红）
  - 等宽/终端风格字体用于系统信息，标题使用粗体无衬线
  - 卡片式布局，大量使用 1px 细线分割与微弱发光边框
  - 按钮状态极简：默认/悬停/按下/禁用，几乎无渐变，以透明度区分
  - 图标与文字严格对齐，间距遵循 4px/8px 网格

- **明日方舟：终末地（Endfield）**
  - 继承 Arknights 的深色工业科幻语言
  - 3D 场景 UI 叠加在游戏画面上，保持低侵入性
  - 面板采用半透明深色底 + 蓝色描边（项目当前统一使用低调蓝 #5c7cfa）
  - 文字信息层级清晰：主标题 > 次级 > 辅助 > 禁用

#### 14.3 设计 token 清单

| Token | 用途 | 鹰角参考 |
|-------|------|----------|
| `primary` | 主按钮、选中态、高亮 | #5c7cfa（低调蓝） |
| `success` | 成功状态、在线 | #5c7cfa（与 primary 统一） |
| `danger` | 错误、停止、删除 | #ff3355 |
| `accent_gold` | 重要提示、稀有 | #fffa00 |
| `bg_primary` | 主背景 | #0a0a0f |
| `surface` | 卡片/面板底 | rgba(16,16,26,0.88) |
| `border` | 分割线/描边 | rgba(92,124,250,0.15) |
| `font_display` | 标题 | Microsoft YaHei UI Bold |
| `font_body` | 正文 | Microsoft YaHei UI Regular |

## 15. GUI 设计审计

> 基于 `src/gui/pyqt6/` 代码库的静态审计，持续更新。

### 15.1 当前架构概览

| 文件 | 角色 | 状态 |
|------|------|------|
| `main.py` | 入口 | 正常 |
| `main_window.py` | 主窗口 + 导航 + 预览 | 正常 |
| `cli_bridge.py` | CLI 子进程桥接 | 正常 |
| `theme/theme_manager.py` | 主题系统 | 单主题（arknight），QSS + widget_styles |
| `pages/maaend_control_page.py` | 核心控制台（任务/预设/队列/日志） | 正常 |
| `pages/device_settings_page.py` | 设备连接 | 正常 |
| `pages/settings_page.py` | 设置 | 正常 |
| `pages/log_page.py` | 日志查看 | 正常 |
| `pages/prts_full_intelligence_page.py` | 全智能/LLM 控制中心 | 正常 |
| `responsive.py` | 响应式 | 正常 |

### 15.2 发现的问题

#### 15.2.1 内联样式与主题系统脱节
- `theme_manager.py` 已有完整的 QSS 主题和 `ThemeManager`
- 但 `maaend_control_page.py` 中定义了 `CARD_STYLE`、`BTN_ACTIVE`、`LIST_STYLE` 等大量字符串常量
- 这些常量直接硬编码颜色值（如 `rgba(16,16,26,0.85)`），与主题系统的 token 完全重复且未同步
- **影响**：未来修改主题色时，需要同时改 `theme_manager.py` 和多个页面文件，极易遗漏

#### 15.2.2 按钮标签与行为一致性
- 当前 `_add_task_to_queue_btn` 标签为 `"Add Task"`，连接 `_add_to_queue`；`_run_queue_btn` 标签为 `"Run"`，连接 `_run_queue`。
- 已不存在 `_run_task` 方法，标签与行为一致。

#### 15.2.3 页面间视觉节奏不一致
- `SettingsPage`、`LogPage`、`DeviceSettingsPage` 使用 `settingsHero` / `ScrollArea` + 16px 边距
- `MaaEndControlPage` 使用 `QVBoxLayout` + `GroupBox` + `Splitter`，边距为 16px 但卡片内边距为 2px，过于紧凑
- 缺乏统一的页面 Hero（标题区域）模式

#### 15.2.4 信息密度与可读性
- `maaend_control_page.py` 的队列表格使用 `QTableWidget`，但列宽与内容自适应不佳
- 任务/预设列表项选中态与悬停态对比度接近，快速扫视时边界模糊
- 日志区使用 HTML span 着色，但缺少统一的消息类型配色规范

#### 15.2.5 响应式断点单一
- `responsive.py` 只有 `normal` / `compact` 两个模式，且仅在宽度 <960 或高度 <720 时切换
- 鹰角产品在不同 DPI / 缩放比下都有良好的信息密度调整，本项目缺少 DPI 感知的字体/间距缩放

#### 15.2.6 图标系统
- `theme/icons.py` 已提供状态图标映射（running/success 等）
- 当前大部分按钮已移除图标，仅保留纯文本

### 15.3 建议优化方向

1. **统一样式来源**：页面内联样式全部迁移到 `theme_manager.py` / `widget_styles.py`，通过 `ThemeManager` 读取
2. **统一页面骨架**：所有页面采用 `HeroHeader + ScrollArea + 卡片组` 结构
3. **DPI 感知**：在 `responsive.py` 中引入 `QScreen.logicalDotsPerInch`，动态调整字体与间距
4. **微动效**：利用 `ANIMATION_CONFIG`，为按钮悬停、面板展开添加 120-200ms 过渡

## 16. 持续优化待办清单

> 按优先级排序，不设截止日期。每完成一项更新状态并追加到 `docs/TASK_LOG.md`。

### P0 — 立即修复
- [ ] 将页面内联样式常量迁移到 `ThemeManager`，消除重复颜色值

### P1 — 本轮迭代
- [ ] 统一所有页面的 Hero 标题区域样式（`SettingsPage`、`LogPage`、`DeviceSettingsPage`）
- [ ] 为队列列表增加图标列（状态指示器）
- [ ] 优化 `QTableWidget` 列宽自适应与行高
- [ ] 建立 `gui/pyqt6/icons.py` 图标映射（使用 Qt resource 或 SVG）

### P2 — 后续优化
- [ ] 引入 DPI 感知的响应式系统（`QScreen.logicalDotsPerInch`）
- [ ] 为按钮/面板添加微动效（120-200ms fade/scale）
- [ ] 建立平面美术规范文档（间距网格、字体层级、色彩使用比例）
- [ ] 为不同分辨率提供两套布局（1280x720 vs 1440x900）
- [ ] 预览区增加“全屏预览”与“复制到剪贴板”

### P3 — 长期探索
- [ ] 支持自定义主题（深色/浅色/高对比）
- [ ] 为不同设备类型优化触摸目标尺寸（平板/触屏）
- [ ] 多语言文案对齐鹰角官方术语
- [ ] 无障碍支持（屏幕阅读器、高对比度模式）
