# VLM-QWEN3-01: Qwen3.5-4B thinking 模式导致 VLM 输出不可解析

> 日期: 2026-07-15
> 类别: 行为异常 / VLM 导航
> 状态: 已修复

## 1. 根因分析

### 直接原因
`VlmWalkNavigator.walk_to_tracking()` 调用 `LlmClient.chat_async()` 后，VLM 回复全部为自然语言描述（"The user wants me to control a character in a 3D game based on a screenshot..."），而非 JSON 动作。`_parse_action()` 5 级解析全部失败，30 步 VLM 调用 100% unparseable。

### 根本原因
Qwen3.5-4B 是 reasoning 模型，**默认 thinking = 1**。在 thinking 模式下，模型输出 `reasoning_content`（自然语言推理）而非 `content`（最终 JSON）。`LlmClient.chat()` 行 65-67 虽然有 `if not content: content = message.get("reasoning_content")` 的 fallback，但：

1. **`/no_think` 指令对小模型不可靠**：上一轮在 prompt 末尾追加 `/no_think` 指令（Qwen3 官方推荐的软开关），但 Qwen3.5-4B 不遵循，仍输出 reasoning_content。
2. **`-rea off` 启动参数未生效**：`LlamaServerRuntime._build_args()` 行 319-321 默认 `reasoning="off"`，但 llama-server 的 `-rea off` 控制的是它是否自动注入 thinking 控制到 chat template，而非 Qwen3 chat template 内部的 `enable_thinking` 变量。
3. **max_tokens=128 截断 thinking**：thinking 模式下模型先输出长篇推理，128 tokens 不够完成推理就到达 max_tokens，导致 `content` 字段为空，`reasoning_content` 被截断成不可解析的片段。

### 调用链
```
VlmWalkNavigator.walk_to_tracking()
  → LlmClient.chat_async(prompt="/no_think\n...")
    → payload = {"messages":..., "max_tokens":128}  # 缺少 chat_template_kwargs
      → llama-server 渲染 chat template（enable_thinking 默认 True）
        → Qwen3.5-4B 输出 reasoning_content（自然语言）
          → _parse_action() 5 级解析全部失败
            → history.append({"action": "parse_error"})
```

## 2. 修改方案

### 2.1 LlmClient 新增 chat_template_kwargs 透传
**文件**: `src/core/capability/llm/client.py`

`chat()` 与 `chat_async()` 新增 `chat_template_kwargs: Optional[Dict[str, Any]]` 参数，非 None 时写入 payload：
```python
if chat_template_kwargs is not None:
    payload["chat_template_kwargs"] = chat_template_kwargs
```

这是 Qwen3 官方推荐的方式（[Qwen3 Quickstart](https://qwen.readthedocs.io/en/latest/getting_started/quickstart.html)），通过 `chat_template_kwargs.enable_thinking=False` 在请求粒度关闭 thinking 模式，llama-server 会传给 chat template 渲染。

### 2.2 VlmWalkNavigator 调用时关闭 thinking
**文件**: `src/core/service/navigation/vlm_walk_navigator.py`

`walk_to()` 与 `walk_to_tracking()` 调用 `chat_async()` 时传入：
```python
chat_template_kwargs={"enable_thinking": False},
```

同时：
- 去掉 prompt 中的 `/no_think` 指令（与 `enable_thinking=False` 冗余，且对小模型不可靠）
- prompt 末尾追加 `"Respond with ONLY the JSON action, nothing else."` 强化格式约束

### 2.3 System prompt 添加 few-shot example
`_DEFAULT_SYSTEM_PROMPT` 与 `_TRACKING_SYSTEM_PROMPT` 末尾添加 1-3 个 example，帮助小模型理解输出格式：
```
Example — if the marker is visible ahead:
{"action": "forward", "duration": 1.5}

Example — if the marker is to the left of the screen:
{"action": "turn_left"}

Example — if you have reached a dungeon portal/collection node:
{"action": "arrived"}
```

### 2.4 _parse_action keyword fallback 重写为 4 级
覆盖小模型在 thinking 模式被关闭失败时返回自然语言描述的情况：

1. **arrived/interact/danger 优先**：匹配 "arrived"/"reached the"/"dungeon portal"/"interact"/"press f"/"obstacle"/"cliff" 等
2. **方向动作词**：匹配 "move forward"/"turn left"/"strafe right" 等动作短语
3. **场景描述词**：匹配 "on the left"/"quest marker ahead"/"follow the path" 等场景描述（VLM 描述了追踪标识相对位置但未明确动作词）
4. **兜底 forward**：匹配 "move"/"walk"/"go" 等泛动作词，避免 VLM 决策无所作为

### 2.5 修复 _ACTION_KEYCODE_MAP NameError
**文件**: `src/core/service/navigation/vlm_walk_navigator.py` 行 485

`_execute_action()` 中 `_ACTION_KEYCODE_MAP.get(act)` 改为 `self._ACTION_KEYCODE_MAP.get(act)`。`_ACTION_KEYCODE_MAP` 是类属性，被当作模块级名称引用导致 `NameError: name '_ACTION_KEYCODE_MAP' is not defined`。

## 3. 影响面

### 修改涉及函数
- `LlmClient.chat()` / `chat_async()` / `_chat_async_target()` — 新增 `chat_template_kwargs` 参数
- `VlmWalkNavigator.walk_to()` / `walk_to_tracking()` — 调用时传 `chat_template_kwargs={"enable_thinking": False}`
- `VlmWalkNavigator._parse_action()` — keyword fallback 重写
- `VlmWalkNavigator._execute_action()` — `self._ACTION_KEYCODE_MAP` 修复
- `_DEFAULT_SYSTEM_PROMPT` / `_TRACKING_SYSTEM_PROMPT` — 添加 few-shot example

### 调用点
- `Navigator.to_coords_vlm()` / `to_tracking_vlm()` 调用 `VlmWalkNavigator`，间接受益
- `IstinaRuntime._material_farm_once()` / `_material_collect_run()` 调用 `nav3.walk` / `nav3.walk_tracking`，间接受益
- 其他 LlmClient 调用方（如 SceneUnderstandingService）不受影响（`chat_template_kwargs` 默认 None，行为不变）

## 4. 非期待变化

### 副作用评估
1. **`chat_template_kwargs` 兼容性**：llama-server 较新版本（b4000+）支持该字段。若使用旧版 llama-server，该字段会被忽略，thinking 模式仍开启，但 `_parse_action` 的 4 级 fallback 能处理大部分自然语言回复。
2. **`enable_thinking=False` 对非 Qwen3 模型无影响**：该参数是 Qwen3 chat template 特有，其他模型的 chat template 会忽略未知变量。
3. **keyword fallback 误判风险**：4 级 fallback 中"兜底 forward"可能在 VLM 实际想 stop 时误判为 forward。但对比"无所作为"（return None 导致 parse_error），forward 是更合理的兜底（VLM 决策不应无所作为）。

### 回退策略
若 `chat_template_kwargs={"enable_thinking": False}` 导致 llama-server 报错（旧版不支持），可在 `LlmClient.chat()` 中 try/except，失败时去掉该字段重试。但当前测试确认 llama-server 正常处理。

## 5. 验证结果

### 测试环境
- 设备: 192.168.1.12:16512 (SM-F721N)
- 模型: Qwen3.5-4B-UD-Q4_K_XL.gguf (port 9998)
- llama-server: PID 493604, 启动时间 16:12:17

### 修复前（16:07-16:14，commit ee953fd）
- MaterialFarm 武陵: 10 步 VLM 全部 unparseable
- 错误: `name '_ACTION_KEYCODE_MAP' is not defined`
- VLM 回复: "The user wants me to control a character in a 3D game based on a screenshot..."

### 修复后（16:32-16:38，commit 0b61baf）
- MaterialFarm 武陵: 6 步 VLM 全部执行，**零 unparseable**，零 NameError
- MaterialCollect 5 路线: 30 步 VLM 全部执行，**零 unparseable**，零 NameError
- stuck 检测正常工作（Route2 step 5, Route4 step 3-4）

### 端到端流程
- ✅ VLM 步行循环正常工作
- ✅ 动作执行正常（keyevent 触发）
- ⚠️ AutoFight 因 ONNX CUDA DLL 缺失（`cudnn64_9.dll`）失败 — 环境问题，非 VLM 修复范围
- ⚠️ MaterialCollect `partial` 状态 — 测试只走 6 步，且游戏未选中采集任务追踪，VLM 无追踪标识可跟

### 连通性测试
直接 HTTP 请求验证 `chat_template_kwargs.enable_thinking=False` 生效：
```
POST http://127.0.0.1:9998/v1/chat/completions
{
  "model": "local",
  "messages": [...],
  "chat_template_kwargs": {"enable_thinking": false}
}

Response:
content: {"action": "forward", "duration": 1.5}
reasoning_content: (empty)
finish_reason: stop
```
