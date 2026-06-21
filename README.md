# IstinaEndfieldAssistant Sight - 本地版

《明日方舟：终末地》游戏自动化工具 - **纯本地推理版本**

> 本版本移除了所有云端依赖，使用本地 llama-cpp-python 进行 VLM 推理，无需 IstinaPlatform 服务器。

## 特性

- ✅ **纯本地推理** - 使用 llama-cpp-python，无需网络连接
- ✅ **GUI + CLI** - 双模式支持
- ✅ **模型管理** - 本地 GGUF 模型下载与管理
- ✅ **标准流引擎** - 配置驱动的自动化流程
- ✅ **UI 探索** - 自动探索游戏界面
- ✅ **战斗控制** - 实时 VLM 战斗辅助

## 快速开始

### 1. 环境要求

- Python 3.10+
- Windows 10/11
- NVIDIA GPU (推荐，CUDA 12.1+)
- 至少 8GB 显存（运行 2B 模型）

### 2. 安装依赖

```bash
cd IstinaEndfieldAssistant_Sight
pip install -r requirements.txt
```

### 3. 下载模型

首次运行会自动检测并提示下载模型。推荐模型：

- `qwen3.5-2b-q8_0.gguf` - 2B 参数，Q8 量化，最低配置
- `qwen3.5-7b-q4_0.gguf` - 7B 参数，Q4 量化，推荐配置

### 4. 启动

**方式一：批处理脚本**

```bash
start.bat
```

**方式二：直接运行 GUI**

```bash
python src/gui/pyqt6/main.py
```

**方式三：CLI 模式**

```bash
python scripts/istina.py <subcommand>
```

## CLI 命令

### 系统诊断

```bash
python scripts/istina.py system doctor    # 全面系统诊断
python scripts/istina.py system env       # 环境变量检查
python scripts/istina.py system disk      # 磁盘使用情况
python scripts/istina.py system perf      # 性能测试
```

### 设备管理

```bash
python scripts/istina.py device status    # 设备状态
python scripts/istina.py device screenshot  # 截图
python scripts/istina.py device info      # 设备信息
```

### 场景采集

```bash
python scripts/istina.py scene capture --count 20    # 采集 20 张截图
python scripts/istina.py scene nav <page>            # 导航到页面
python scripts/istina.py scene analyze -i "..."      # VLM 分析画面
```

### 标准流引擎

```bash
# 执行单个流程
python scripts/standard_flow_engine.py --flow daily_quest

# 执行所有流程
python scripts/standard_flow_engine.py --flow all

# 视觉分析 + 提示词优化
python scripts/standard_flow_engine.py --flow daily_quest --optimize-prompts
```

## 配置

配置文件位于 `config/client_config.json`：

```json
{
  "inference": {
    "mode": "local",
    "model_name": "qwen3.5-2b",
    "gpu_layers": -1,
    "temperature": 0.7
  },
  "device": {
    "serial": "localhost:16512"
  }
}
```

## 目录结构

```
IstinaEndfieldAssistant_Sight/
├── src/
│   ├── cli/                      # CLI 模块
│   ├── core/                     # 核心逻辑
│   │   ├── element_analysis/     # UI 元素分析
│   │   │   ├── element_analyzer.py        # 统一分析器（合并本地/云端）
│   │   ├── cloud/                # Agent 引擎
│   │   │   ├── agent_executor.py           # 统一 Agent（合并本地/云端）
│   │   │   └── managers/
│   │   │       └── local_log_manager.py   # 本地日志
│   │   ├── local_inference/      # 本地推理
│   │   ├── adb_utils.py          # ADB 工具
│   │   ├── vlm_utils.py          # VLM 分析工具（从 adb_utils 拆分）
│   │   ├── state_detector.py     # 状态检测器（从 DeviceStateManager 拆分）
│   │   └── state_recovery.py     # 状态恢复策略（从 DeviceStateManager 拆分）
│   ├── device/                   # 设备层
│   └── gui/pyqt6/                # GUI 界面
├── scripts/                      # 独立脚本
│   ├── istina.py                 # CLI 入口
│   └── standard_flow_engine.py   # 标准流引擎
├── config/
│   └── client_config.json        # 配置文件
├── models/                       # 模型存储
├── cache/                        # 缓存目录
├── logs/                         # 日志目录
└── start.bat                     # 启动脚本
```

## 与原版差异

| 功能 | 原版 | 本地版 |
|------|------|--------|
| 推理方式 | 云端/本地混合 | 纯本地 |
| 服务器依赖 | 需要 IstinaPlatform | 无需服务器 |
| 多用户支持 | ✅ | ❌ |
| 云端模型 | ✅ | ❌ |
| 离线使用 | 部分 | 完全 |
| 认证系统 | ✅ | ❌ |

## 已知限制

1. **GPU 必需** - 本地推理需要 NVIDIA GPU（CUDA 支持）
2. **模型大小** - 受限于本地显存，最大支持 7B 模型
3. **推理速度** - 本地推理速度取决于 GPU 性能
4. **GUI 部分功能** - 部分依赖云端的 GUI 页面已移除

## 故障排除

### GPU 检测失败

```bash
python scripts/istina.py gpu status
python scripts/istina.py gpu cuda-check
```

### 模型加载失败

检查 `config/client_config.json` 中的 `model_name` 是否正确，并确保模型已下载至 `models/` 目录。

### ADB 连接失败

确保模拟器/设备已启动，且 ADB 端口正确（默认 `localhost:16512`）。
