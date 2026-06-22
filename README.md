# IstinaEndfieldAssistant Sight - 本地版

《明日方舟：终末地》游戏自动化工具 - **纯本地推理版本**

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

