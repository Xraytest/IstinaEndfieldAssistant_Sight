# 标准流引擎 v2 - 快速入门

## 已完成的工作

✅ **配置化标准流系统**
- JSON配置文件（`config/standard_flows/flows_config.json`）
- 变量化坐标和参数
- 7个标准流程：daily_quest, weekly_quest, resource_collection, base_management, character_ascension, weapon_crafting, event_rewards

✅ **自动截图录制**
- 每步自动截图保存
- 形成"视频式"序列记录
- 存储于 `cache/flow_<name>_<timestamp>/screenshots/`

✅ **视觉subagent分析**
- 使用Qwen3.6-Max分析执行质量
- 识别卡点和失败原因
- 输出结构化优化建议

✅ **提示词自动优化**
- 基于分析结果自动改进提示词
- 配置自动备份
- 支持批量迭代优化

✅ **本地2B模型默认**
- 默认使用本地qwen3.5-2b模型
- API自动回退
- 可通过 `--local-only` 强制本地

✅ **AgentExecutor集成**
- `agent_standard_flow_integration.py`
- 可无缝切换云端VLM执行

## 核心文件

| 文件 | 说明 |
|------|------|
| `config/standard_flows/flows_config.json` | 主配置文件（所有流程定义） |
| `scripts/standard_flow_engine.py` | 核心引擎（本地2B执行+记录+分析） |
| `scripts/prompt_optimizer.py` | 提示词自动优化器 |
| `scripts/agent_standard_flow_integration.py` | AgentExecutor集成 |
| `scripts/test_new_flow_engine.py` | 单元测试 |
| `docs/STANDARD_FLOW_ENGINE.md` | 完整文档 |

## 5分钟快速测试

```bash
# 1. 验证配置加载
python scripts/test_new_flow_engine.py

# 2. 执行daily_quest流程（使用本地2B，不记录截图加速）
python scripts/standard_flow_engine.py --flow daily_quest --no-record

# 3. 执行并自动分析（需要server运行）
# python scripts/standard_flow_engine.py --flow daily_quest

# 4. 干运行优化器（仅分析，不修改）
python scripts/prompt_optimizer.py --flows daily_quest --dry-run
```

## 使用示例

### 执行单个流程
```bash
python scripts/standard_flow_engine.py --flow daily_quest --local-only
```

### 执行所有流程
```bash
python scripts/standard_flow_engine.py --flow all
```

### 分析已有记录
```bash
# 先执行一次，记住输出中的session目录，例如：
# cache/flow_daily_quest_20260604_143022

python scripts/standard_flow_engine.py --flow daily_quest \
  --analyze-only --session-dir cache/flow_daily_quest_20260604_143022
```

### 自动优化提示词
```bash
# 执行并优化（会修改配置文件，先备份）
python scripts/standard_flow_engine.py --flow daily_quest --optimize-prompts

# 批量优化所有流程，迭代3次
python scripts/prompt_optimizer.py --flows all --iterations 3
```

## 输出目录结构

```
cache/
└── flow_daily_quest_20260604_143022/
    ├── screenshots/
    │   ├── step_001_detect_screen_1234567890_abc123.png
    │   ├── step_002_navigate_1234567891_def456.png
    │   └── ...
    ├── execution_report.json    # 执行统计
    └── visual_analysis.json     # 视觉分析结果（含优化建议）
```

## 配置变量

在提示词中使用 `{{variable.key}}` 语法：

```json
{
  "variables": {
    "coords": {
      "signin_entry": [640, 360],
      "claim_all": [960, 540]
    }
  }
}
```

提示词示例：
```
点击签到按钮: {{coords.signin_entry}}
当前页面: {{current_page}}
```

## 与现有系统兼容

- ✅ 保持与 `test_standard_flow.py` 的独立运行
- ✅ `StandardReasoningPage` GUI仍可使用
- ✅ 配置文件独立，不影响现有代码
- ✅ AgentExecutor可选择性集成

## 下一步建议

1. **测试所有流程**：`python scripts/standard_flow_engine.py --flow all --no-record`
2. **干运行优化器**：检查优化建议质量
3. **应用优化**：`--optimize-prompts` 改进提示词
4. **Agent集成**：在GUI中使用 `agent_standard_flow_integration.py`

## 故障排除

### 问题：ModuleNotFoundError: No module named 'skills'
**解决**：确保运行目录为项目根目录，或使用绝对路径导入。

### 问题：配置文件未找到
**解决**：配置文件应在 `config/standard_flows/flows_config.json`

### 问题：模型加载失败
**解决**：
- 本地模式：`pip install llama-cpp-python`
- 或使用API回退（默认）

### 问题：截图失败
**解决**：检查ADB连接 `adb devices`，确保 localhost:16512 在线

## 技术要点

- **路径设置**：所有脚本使用 `PROJECT_ROOT / "src"` 添加到 sys.path
- **JSON解析**：使用平衡花括号提取，支持think标签
- **错误处理**：严格检查action、result、status字段
- **变量替换**：正则 `\{\{([^}]+)\}\}` 替换配置变量
- **视觉分析**：采样关键帧（最多15张）避免token超限

---

**完成时间**：2026-06-04
**版本**：v2.0
**默认模型**：本地 qwen3.5-2b（API回退）
