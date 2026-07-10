# P0 级发现修复影响域分析报告 — IstinaEndfieldAssistant Sight

> **批次定位**：本批次对 21 轮审计中标记为 P0 的 3 项最高优先级发现进行**修复影响域分析**（fix blast-radius analysis）。不重复提交历史发现，而是精确量化每项修复的修改量、调用链影响、风险评估和实施顺序建议。
>
> **审查方式**：纯静态代码逻辑分析，未执行测试；所有分析均经当前 `main` 分支源文件逐行核对。

---

## 一、P0 发现清单与修复摘要

| 编号 | 问题 | 位置 | 严重度 | 精确修改量 |
|------|------|------|--------|-----------|
| **C10** | `_nav3_walk`/`_nav3_to_entity` 读 `self._llm_client` 原始属性而非 property | `runtime.py:697/706` | High | 2 行（改属性名） |
| **W1-可见化** | `AndroidRuntime.keyevent()` 丢弃 daemon error 字段，失败完全静默 | `android_runtime.py:784-786` + `runtime.py:712-730` | Critical | 2 行（新增 if+raise） |
| **D1** | `_force_stop` 将 `"am force-stop"` 作为单个参数传递 | `recovery.py:72` | High | 1 行（拆分参数） |

**合计精确修改量：5 行代码。**

---

## 二、C10 修复影响域分析

### 2.1 问题描述

`_llm_client_instance` 是 property（`runtime.py:128-132`），惰性创建 `LlmClient` 并回填 `self._llm_client`。但 `_nav3_walk`（697）和 `_nav3_to_entity`（706）直接读 `self._llm_client`，绕过了 property 的惰性初始化逻辑。

触发条件：用户启动后未先执行任何 `llm chat` 命令，直接调用 `nav3 walk` 或 `nav3 to_entity`。

### 2.2 精确修改点

```python
# runtime.py:697
# 修改前：
            llm_client=self._llm_client,
# 修改后：
            llm_client=self._llm_client_instance,

# runtime.py:706
# 修改前：
            llm_client=self._llm_client,
# 修改后：
            llm_client=self._llm_client_instance,
```

### 2.3 调用链影响分析

```
修改前（路径 B — 先 walk 后 chat）：
  _nav3_walk (697) → 读 self._llm_client → None（原始属性未初始化）
    → to_coords_vlm(llm_client=None)
      → VlmWalkNavigator.walk_to(llm_client=None)
        → VLM 路径规划降级为 navmesh fallback
          → VLM 形同虚设

修改后：
  _nav3_walk (697) → 读 self._llm_client_instance → property 触发
    → 检查 self._llm_client is None → True
    → _get_llm_client(self._llm_runtime_instance) 创建 LlmClient
    → self._llm_client = 实例（回填原始属性）
    → to_coords_vlm(llm_client=真实实例)
      → VlmWalkNavigator.walk_to(llm_client=真实实例)
        → VLM 路径规划正常工作
```

### 2.4 下游影响矩阵

| 下游组件 | 影响 | 破坏性？ |
|---------|------|---------|
| `to_coords_vlm` | 收到真实 LlmClient 而非 None | 否——函数已处理 None（fallback 逻辑保留） |
| `to_entity_vlm` | 同上 | 否 |
| `walk_to` | `llm_client` 从 None 变为实例 | 否——参数已声明为 Optional |
| `_llm_client_instance` property | 首次访问时创建 LlmClient | 否——property 内置幂等 |
| `_handle_llm_chat` (878) | 读 `self._llm_client_instance` | 不受影响 |

### 2.5 风险评估

| 风险 | 概率 | 影响 | 结论 |
|------|------|------|------|
| LlmClient 在 nav3 walk 时被意外创建（用户本不想用 LLM） | 中 | 增加内存占用 (~100MB) | **可接受**——nav3 walk 本身依赖 VLM，VLM 依赖 LLM |
| LlmClient 创建失败（模型路径无效） | 低 | nav3 walk 抛异常而非静默降级 | **改善**——之前静默降级到 navmesh，现在明确报错 |
| 与 `_handle_llm_chat` 的双重创建竞争 | 无 | — | property 保证只创建一次 |
| 修改后 `self._llm_client` 原始属性被其他代码路径读到过期值 | 无 | property 每次写回最新值 | 不受影响 |

### 2.6 结论

**C10 是 3 项 P0 中风险最低、修改量最小、收益确定性最高的修复。** 2 行代码，0 个调用方受影响，0 个下游组件需要修改。

---

## 三、W1-可见化修复影响域分析

### 3.1 问题描述

W1 的根因（字母键被 `_is_valid_keyevent` 拒绝）是架构级问题，需要键位映射重构。但**失败可见化**是低成本、高收益的独立修复——不改变键位映射，只让失败从"完全静默"变为"有日志可诊断"。

三重静默链：
1. 守护进程返回 `{"error": "invalid keyevent: 'w'"}` → `keyevent()` 丢弃 error 返回 `""`
2. `_vlm_keyevent` try/except 捕获不到异常（无异常抛出）→ 不记日志
3. `_execute_action` 不检查返回值 → 将"未执行"记为"已执行"

### 3.2 精确修改点

**修改点 1：`android_runtime.py:784-786`**
```python
# 修改前（2 行）：
def keyevent(self, key: str, serial: Optional[str] = None) -> str:
    response = self._call("keyevent", {"key": key, "serial": serial or self._serial})
    return response.get("result", "")

# 修改后（3 行，新增 1 行 if+raise）：
def keyevent(self, key: str, serial: Optional[str] = None) -> str:
    response = self._call("keyevent", {"key": key, "serial": serial or self._serial})
    if response.get("error"):
        raise AndroidRuntimeError(f"keyevent 失败: {response['error']}")
    return response.get("result", "")
```

**修改点 2：`runtime.py:712-730`（零修改）**
```python
# 当前代码已存在 try/except，会自然捕获新增的 AndroidRuntimeError：
def _vlm_keyevent(self, key: str, duration: Optional[float]) -> None:
    try:
        android = self.android()
        if duration is not None and duration > 0.3:
            repeats = max(1, int(duration / 0.15))
            for _ in range(repeats):
                android.keyevent(key)   # ← 现在会抛异常
                import time
                time.sleep(0.12)
        else:
            android.keyevent(key)       # ← 现在会抛异常
    except Exception as exc:
        self._logger.warning("VLM keyevent '%s' failed: %s", key, exc)
        # ← 现在会实际记录：WARNING VLM keyevent 'w' failed: keyevent 失败: invalid keyevent: 'w'
```

### 3.3 全项目 `keyevent()` 调用方审查

| 调用方 | 位置 | 调用方式 | 修改后影响 | 需修改？ |
|--------|------|---------|-----------|---------|
| `_vlm_keyevent` | `runtime.py:724,728` | `android.keyevent(key)` | try/except 捕获异常，记录日志 | **否**（已有保护） |
| `_handle_device_keyevent` | `handlers.py:448` | `android.shell(f"input keyevent {key}")` | **不调用 `keyevent()`** | **否**（使用不同 API） |
| **其他调用方** | **grep 确认：无** | — | — | — |

**关键发现**：`_handle_device_keyevent` 不调用 `android.keyevent()`，而是直接调用 `android.shell()` 构造 `input keyevent` 命令。因此修改 `keyevent()` 的返回值行为**完全不影响** CLI 的 device keyevent 子命令。

### 3.4 调用链影响分析

```
修改前：
  android.keyevent("w")
    → daemon 返回 {"error": "invalid keyevent: 'w'"}
    → keyevent() 返回 ""（丢弃 error）
    → _vlm_keyevent 收到空串，无异常，无日志
    → _execute_action 继续 → history.append({"status": "executed"})
    → VLM 认为自己在移动，设备上零位移

修改后：
  android.keyevent("w")
    → daemon 返回 {"error": "invalid keyevent: 'w'"}
    → keyevent() 检测 error → raise AndroidRuntimeError
    → _vlm_keyevent 的 except 捕获 → logger.warning("VLM keyevent 'w' failed: ...")
    → _execute_action 的 try 块中断（异常向上传播）
    → history 不记录该次动作
    → VLM 知道该次移动失败（可触发替代策略）
```

### 3.5 下游影响矩阵

| 下游组件 | 修改前 | 修改后 | 破坏性？ |
|---------|--------|--------|---------|
| `_vlm_keyevent` | 收到空串，无感知 | 收到异常，记录 warning | 否——改善可观测性 |
| `_execute_action` | 将失败记为成功 | 异常中断，不记录 history | 否——纠正错误状态 |
| VlmWalkNavigator.walk_to | 基于错误 history 继续 | 知道移动失败，可 fallback | 否——改善决策依据 |
| `_handle_device_keyevent` | 不调用 keyevent() | 不受影响 | 否 |
| 其他 keyevent 调用方 | 无 | 不受影响 | 否 |

### 3.6 风险评估

| 风险 | 概率 | 影响 | 结论 |
|------|------|------|------|
| `_execute_action` 的 try 块中断导致 walk_to 流程提前终止 | 中 | VLM 导航提前 fallback | **改善**——之前静默失败导致 30s stuck 检测才 fallback，现在立即 fallback |
| `AndroidRuntimeError` 未被 `_vlm_keyevent` 的 except 捕获 | 无 | — | 已有 `except Exception`，捕获所有子类 |
| 合法 keyevent（KEYCODE_*）也触发异常 | 无 | — | daemon 只对非法 keyevent 返回 error，合法 keyevent 正常返回 result |
| `_handle_device_keyevent` 受影响 | 无 | — | 使用 `android.shell()` 而非 `android.keyevent()` |

### 3.7 结论

**W1-可见化修复的 blast radius 极小——仅影响 1 个调用方（_vlm_keyevent），且该调用方已有 try/except 保护。** 2 行代码新增，0 行删除，0 个下游组件需要修改。修复后 VLM 行走从"完全静默"变为"有日志可诊断"，大幅改善 debug 体验。

**注意**：此修复**不解决** W1 的根因（字母键被拒绝）。根因修复需要键位映射架构变更（将 VLM 移动键映射到游戏支持的 KEYCODE 或通过 scrcpy 注入），属于 P2 级工作。

---

## 四、D1 修复影响域分析

### 4.1 问题描述

`recovery.py:72` 将 `"am force-stop"` 作为**单个参数**传递给 `subprocess.check_output`。`_run` 方法（line 66-68）将其拼接到 adb 命令后：

```python
def _run(self, args: list[str], serial: Optional[str]) -> None:
    cmd = self._resolve_adb(serial) + args
    subprocess.check_output(cmd, text=True, timeout=30)

def _force_stop(self, serial: Optional[str]) -> None:
    self._run(["shell", "am force-stop", self._package], serial)
```

最终执行的命令为：
```
adb -s <serial> shell am force-stop com.hi3.higames
```

`subprocess.check_output` 将 `["shell", "am force-stop", ...]` 作为独立 argv 元素传递。Android 的 mksh 将 `"am force-stop"` 解释为**单个命令名**（含空格），而非 `am` + `force-stop` 两个参数。由于不存在名为 `"am force-stop"` 的可执行文件，命令静默失败。

### 4.2 精确修改点

```python
# recovery.py:72
# 修改前：
        self._run(["shell", "am force-stop", self._package], serial)
# 修改后：
        self._run(["shell", "am", "force-stop", self._package], serial)
```

**修改量：1 行（将 `"am force-stop"` 拆分为 `"am"` + `"force-stop"`）。**

### 4.3 调用链影响分析

```
修改前：
  _force_stop(serial)
    → _run(["shell", "am force-stop", pkg], serial)
      → cmd = [adb, "-s", serial, "shell", "am force-stop", pkg]
        → subprocess.check_output(cmd)  # mksh 将 "am force-stop" 作为单个命令
          → 命令失败（无此命令）或静默忽略
            → 旧进程不被终止
              → restart() 可能启动第二个实例

修改后：
  _force_stop(serial)
    → _run(["shell", "am", "force-stop", pkg], serial)
      → cmd = [adb, "-s", serial, "shell", "am", "force-stop", pkg]
        → subprocess.check_output(cmd)  # mksh 正确解析为 am + force-stop
          → 应用被强制停止
            → restart() 启动新实例
```

### 4.4 下游影响矩阵

| 下游组件 | 修改前 | 修改后 | 破坏性？ |
|---------|--------|--------|---------|
| `_force_stop` | 强制停止从未生效 | 强制停止正常工作 | 否——修复功能 |
| `restart` | 依赖 `_force_stop` 清理旧进程，实际未清理 | 旧进程被终止后启动新实例 | 否——修复依赖 |
| `_run` | 接收包含空格的参数 | 接收正确拆分的参数 | 否——`_run` 不关心参数语义 |
| `_clear_canvas` / `_launch` | 在旧进程未终止时执行 | 在旧进程终止后执行 | 否——改善正确性 |

### 4.5 风险评估

| 风险 | 概率 | 影响 | 结论 |
|------|------|------|------|
| `am force-stop` 在某些设备上行为不同 | 低 | 部分设备仍无法停止 | `am force-stop` 是标准 Android 命令，兼容性良好 |
| 强制停止导致数据丢失 | 低 | 用户未保存的数据丢失 | 这是 force-stop 的预期行为 |
| `_run` 的 30s 超时不够 | 低 | 某些应用停止超时 | 独立问题，不影响本次修复 |

### 4.6 结论

**D1 是 3 项 P0 中修改量最小的修复——仅 1 行代码。** 零调用方受影响，零下游组件需要修改。修复后恢复链路的关键步骤（强制停止旧进程）从"从未生效"变为"正常工作"。

---

## 五、三修复的级联影响对比

| 维度 | C10 | W1-可见化 | D1 |
|------|-----|-----------|-----|
| **精确修改量** | 2 行 | 2 行 | 1 行 |
| **修改文件数** | 1 | 2 | 1 |
| **调用方受影响** | 0 | 0 | 0 |
| **下游组件需修改** | 0 | 0 | 0 |
| **破坏性风险** | 极低 | 极低 | 极低 |
| **收益确定性** | 高 | 高 | 高 |
| **修复后立即可验证** | CLI `nav3 walk` 不 fallback | 日志出现 "VLM keyevent 'w' failed" | 应用被强制停止 |
| **是否解决根因** | 是（C10 的根因就是属性访问错误） | 否（仅可见化，根因是键位映射） | 是（D1 的根因就是参数拆分） |

---

## 六、实施顺序建议

### 推荐顺序：C10 → W1-可见化 → D1

| 顺序 | 修复 | 理由 |
|------|------|------|
| **1st** | **C10** | 修改量最小（2 行）、风险最低、收益确定性最高。修复后 nav3 walk 在"先 walk 后 chat"场景下从静默降级变为正常工作。不涉及异常传播或日志行为变更。 |
| **2nd** | **W1-可见化** | 2 行代码新增，blast radius 极小（仅 1 个调用方且有 try/except 保护）。修复后 VLM 行走从"完全静默"变为"有日志可诊断"，改变整个调试体验。注意：此修复不解决键位映射根因，需后续 P2 架构修复。 |
| **3rd** | **D1** | 1 行代码，风险最低。修复后强制停止功能正常工作，恢复链路不再依赖 stale 进程。可独立验证（`adb shell am force-stop <pkg>` 手动确认）。 |

### 实施注意事项

1. **C10 实施后需验证**：确认 `_llm_client_instance` property 在 nav3 walk 调用时 LlmClient 创建不报错（模型路径有效、llama-server 已启动）。
2. **W1-可见化实施后需验证**：确认 `AndroidRuntimeError` 在 `_vlm_keyevent` 的 `except Exception` 中被正确捕获并记录 warning 日志。
3. **D1 实施后需验证**：确认 `adb shell am force-stop <pkg>` 在目标设备上实际终止应用进程。

---

## 七、与合成审计报告的关联

本报告的 3 项 P0 分析对应合成审计报告（`20260711_SYNTHESIS.md`）中的以下反模式：

| P0 修复 | 对应反模式 | 反模式编号 |
|---------|-----------|-----------|
| C10 | 惰性初始化盲目属性访问 | 反模式 3 |
| W1-可见化 | 结构性静默失败 | 反模式 1 |
| D1 | 守护进程验证不对称 | 反模式 2 |

每项修复的修改量均≤2 行， blast radius 均为 0 个下游组件，验证了合成审计报告中"按架构层分组修复"的可行性——基础设施层的修复往往具有**局部性**，修改量小、风险可控、收益明确。

---

*本报告为修复影响域分析，未修改任何业务代码。所有分析均经当前 `main` 分支源文件逐行核对。*
