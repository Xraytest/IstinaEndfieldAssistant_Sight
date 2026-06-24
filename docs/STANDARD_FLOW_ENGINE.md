# 标准流执行引擎 v2

基于JSON配置的可扩展标准流系统，支持本地2B模型、自动截图记录、视觉subagent分析和提示词自动优化。

## 特性

- ✅ **配置驱动**: 所有流程定义和提示词存储在JSON配置文件中
- ✅ **变量化参数**: 坐标、页面类型等可配置，便于适配不同设备
- ✅ **自动截图序列**: 执行过程中自动保存每步截图，形成"视频式"记录
- ✅ **视觉subagent分析**: 使用Qwen3.6-Max分析执行质量，识别卡点
- ✅ **提示词自动优化**: 基于分析结果自动改进提示词
- ✅ **本地2B默认**: 默认使用本地2B模型（qwen3.5-2b），API回退
- ✅ **Agent集成**: 可与AgentExecutor集成，利用云端VLM

## 文件结构

```
config/standard_flows/
├── flows_config.json      # 主配置文件
└── backups/              # 配置自动备份

scripts/
├── standard_flow_engine.py      # 核心引擎（本地2B执行）
├── agent_standard_flow_integration.py  # AgentExecutor集成
├── prompt_optimizer.py          # 提示词自动优化器
└── test_new_flow_engine.py      # 单元测试

cache/
└── flow_<name>_<timestamp>/    # 执行记录目录
    ├── screenshots/            # 截图序列
    ├── execution_report.json   # 执行报告
    └── visual_analysis.json    # 视觉分析结果
```

## 快速开始

### 1. 基础测试

```bash
# 测试配置加载
python scripts/test_new_flow_engine.py

# 执行单个流程（本地2B模型）
python scripts/standard_flow_engine.py --flow daily_quest --local-only

# 执行所有流程
python scripts/standard_flow_engine.py --flow all

# 执行但不记录截图（快速测试）
python scripts/standard_flow_engine.py --flow daily_quest --no-record
```

### 2. 视觉分析

```bash
# 执行并自动分析
python scripts/standard_flow_engine.py --flow daily_quest

# 仅分析已有记录
python scripts/standard_flow_engine.py --flow daily_quest --analyze-only --session-dir cache/flow_daily_quest_20260604_123456

# 跳过分析
python scripts/standard_flow_engine.py --flow daily_quest --skip-analysis
```

### 3. 自动优化提示词

```bash
# 执行并自动优化提示词（会修改配置文件）
python scripts/standard_flow_engine.py --flow daily_quest --optimize-prompts

# 批量优化所有流程（迭代2次）
python scripts/prompt_optimizer.py --flows all --iterations 2

# 干运行（仅分析，不修改）
python scripts/prompt_optimizer.py --flows daily_quest --dry-run
```

## 配置说明

### flows_config.json 结构

```json
{
  "version": "1.0",
  "variables": {
    "coords": {
      "signin_entry": [640, 360],
      "claim_all": [960, 540]
    },
    "pages": {
      "world_map": "world_map",
      "main_menu": "main_menu"
    }
  },
  "flows": {
    "daily_quest": {
      "enabled": true,
      "description": "Complete daily quests",
      "steps": [
        {
          "id": "detect_screen",
          "action": "detect_screen",
          "description": "Detect current screen",
          "prompt_template": "Analyze screen... Output JSON: {\"action\": \"none\", \"page_type\": \"...\"}"
        },
        // ... more steps
      ]
    }
  },
  "execution": {
    "default_temperature": 0.3,
    "max_retries": 3,
    "record_video": true,
    "analysis_model": "Qwen3.6-Max-Preview-thinking"
  }
}
```

### 步骤定义字段

- `id`: 步骤唯一标识（用于优化追踪）
- `action`: 动作类型（detect_screen, navigate, check, claim, back等）
- `description`: 步骤描述
- `prompt_template`: 发给模型的提示词，支持变量替换 `{{coords.signin_entry}}`

### 变量替换

提示词中可以使用双大括号引用变量：

```
点击签到按钮: {{coords.signin_entry}}
当前页面: {{current_page}}
```

变量来源：
- `variables.coords.*` - 坐标配置
- `variables.pages.*` - 页面类型常量
- `{{current_page}}` - 运行时注入的上下文

## 与AgentExecutor集成

```python
from scripts.agent_standard_flow_integration import AgentStandardFlowRunner
from core.cloud.agent_executor import AgentExecutor

# 初始化AgentExecutor（需传入communicator等依赖）
agent_executor = AgentExecutor(...)

# 创建runner
runner = AgentStandardFlowRunner(agent_executor)

# 运行标准流（使用Agent云端VLM）
result = runner.run_flow("daily_quest")
print(f"成功率: {result['success_count']}/{result['total_steps']}")
```

优势：
- 利用云端大模型（Qwen3.6-Max）决策
- 自动记录执行过程
- 可结合视觉分析优化

## 提示词优化循环

### 工作流程

1. 执行流程并记录完整截图序列
2. 视觉subagent分析每步质量
3. 提取优化建议（prompt_optimizations字段）
4. 自动更新配置文件（创建备份）
5. （可选）重新执行验证效果

### 优化标准

分析器会检查：
- 截图画面是否与预期相符
- 模型决策是否正确
- 执行是否成功
- 失败原因和卡点

优化建议包括：
- 更清晰的页面识别提示
- 更准确的坐标指导
- 更好的错误处理
- 上下文增强

## 输出目录

每次执行在 `cache/` 下创建时间戳目录：

```
cache/flow_daily_quest_20260604_143022/
├── screenshots/
│   ├── step_001_detect_screen_1234567890_abc123.png
│   ├── step_002_navigate_1234567891_def456.png
│   └── ...
├── execution_report.json      # 执行统计
└── visual_analysis.json       # 视觉分析结果
```

## 故障排除

### 问题：模型加载失败

```
[2b] llama-cpp-python 未安装, 回退到 API 调用
```

- 本地模式：`pip install llama-cpp-python`
- API回退：确保server运行在127.0.0.1:9999

### 问题：配置文件未找到

确保配置文件在以下位置之一：
- `config/standard_flows/flows_config.json`（推荐）
- `config/flows_config.json`
- 项目根目录 `flows_config.json`

### 问题：截图失败

检查ADB连接：
```bash
adb devices
# 应显示 localhost:16512 device
```

## 性能建议

- **本地2B模型**：首次加载较慢（~30s），后续快速
- **截图记录**：每步约100-300KB PNG，完整流程5-10MB
- **视觉分析**：Qwen3.6-Max分析15张图约60-120秒
- **优化建议**：建议每轮执行后手动审核优化建议再应用

## 扩展新流程

1. 编辑 `config/standard_flows/flows_config.json`
2. 在 `flows` 对象中添加新流程
3. 定义steps数组，每个step包含id、action、description、prompt_template
4. 使用 `{{variable}}` 语法引用配置变量
5. 运行测试：`python scripts/standard_flow_engine.py --flow your_flow`

## 最佳实践

1. **提示词设计**：
   - 明确页面类型定义
   - 提供失败处理策略
   - 要求严格JSON输出
   - 包含上下文理解（如"这是第X步"）

2. **坐标配置**：
   - 在 `variables.coords` 集中管理
   - 使用实际截图测量的坐标
   - 提供合理的默认值

3. **优化迭代**：
   - 先干运行分析（`--dry-run`）
   - 审核优化建议再应用
   - 保留备份以便回滚

4. **Agent模式**：
   - 复杂流程使用AgentExecutor
   - 标准流保持轻量本地执行
   - 需要视觉理解时切换Agent

## 版本历史

- **v2.0** (2026-06-04): 配置化、自动优化、Agent集成
- **v1.0** (早期): 硬编码提示词，无优化
