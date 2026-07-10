# 最近 120 个 Commit 审计报告

**审计日期**: 2026-07-08
**审计范围**: `git log --oneline -n 120`（2026-07-06 至 2026-07-08）
**审计方法**: AgentSwarm 4 维度并行审计 + 已有报告交叉验证 + 关键代码位置详查
**已有基准**: `reports/test_report_2026-07-07.md`、`reports/function_naming_anomalies_report.md`

---

## 一、隐患与错误修改清单

### 1.1 高危（需立即处理）

| # | Commit | 文件路径 | 问题描述 |
|---|--------|---------|---------|
| 1 | **未提交** | `src/core/service/runtime.py` | `_harvest_run` 已改为 `task.run`，但 `_daily_run` 仍使用 `preset.run`，dispatch 逻辑不一致。直接导致 CLI 业务命令持续返回 `error`。 |
| 2 | **未提交** | `tests/test_istina_cli_commands.py` | 移除 `nav/daily/harvest/analyze/explore` 五个测试的 `skipif` 装饰器，使其在无设备环境下强制运行；`nav` 目标从 `hub` 改为 `CloseGame`。未提交测试与未提交 runtime 修改耦合，回归风险极高。 |
| 3 | 0447387 | `src/gui/pyqt6/pages/maaend_control_page.py` | 修改 57 行（去除手动保存，改为自动保存），仅同步修改 2 行测试。该页面在 2026-07-07 测试报告中已因 `QProgressBar` 导入问题导致 10 个测试全部 FAILED，本次大幅重构后回归风险极高。 |
| 4 | 753a44a | `src/core/capability/llm/runtime.py` | LlamaServerRuntime 重构为全局单例，新增 `_instances` 注册表、`_owned_pids` PID 追踪、`_shutdown_owned` 进程清理逻辑，共 73 行改动。无任何对应测试覆盖单例模式或进程生命周期。 |
| 5 | 28423fc | `src/core/service/runtime.py` | `_run_task/_run_preset` 在 `maaend_control_page.py` 中已重命名为 `_add_task_to_queue/_apply_preset_to_queue`，但 `runtime.py` 仍保留旧方法名（2 处定义 + 2 处调用），造成跨层命名不一致。 |
| 6 | 28423fc | `src/gui/pyqt6/pages/maaend_control_page.py:635` | 注释中仍引用旧名称 `_run_preset`，文档残留。 |

### 1.2 中危（建议近期处理）

| # | Commit | 文件路径 | 问题描述 |
|---|--------|---------|---------|
| 7 | 578ca5e / 753a44a | `src/core/capability/llm/runtime.py` | LlamaServerRuntime 单例重构被拆分为两个 commit（message 完全相同），分别修改不同文件。建议 squash 为单一 commit。 |
| 8 | 45545d3 | `src/gui/pyqt6/theme/theme_manager.py` | 单 commit 删除 455 行、修改 10 个文件，将多主题系统退化为单主题，变更面过广。无对应主题/样式测试验证简化后的行为。 |
| 9 | cf55282 | `src/core/service/runtime.py` | 按需加载重构，将 `MaaEndRuntime`、`LlmClient` 等顶层导入改为 `TYPE_CHECKING + 运行时延迟导入`。虽同步更新了 `test_istina_runtime.py`，但 31 行核心模块改动中涉及 import 语义的根本变化。 |
| 10 | 8785a8a | `src/core/capability/device/android_runtime.py` | daemon screenshot 增加 scrcpy-ADB 回退逻辑，并重启 scrcpy session。31 行改动无测试覆盖，且 `_ScrcpySession.start` 的线程重置逻辑未经测试验证。 |
| 11 | bf11527 | `src/core/capability/device/android_runtime.py` | 为 screenshot 路径添加端到端日志，将 `except Exception: pass` 改为记录异常。修改了 18 行核心设备控制代码，但无对应测试，可能暴露此前被吞掉的异常路径。 |
| 12 | 1ff403f/241758f/34b6b00/99104a2/c887d5f | `src/cli/istina.py` | 连续 5 个 commit 修复交互模式 I/O 编码（stdin bytes、stdout.buffer UTF-8、get_logger 导入、异常处理）。高频 hotfix 表明交互循环本身稳定性差，且均无单元测试覆盖 `_interactive_loop`。 |

### 1.3 低危（观察/优化）

| # | Commit | 文件路径 | 问题描述 |
|---|--------|---------|---------|
| 13 | 28423fc | `src/gui/pyqt6/theme/theme_manager.py` | `rgba(25, 209, 255, 0.10)` 在 theme_manager.py 内出现 7 次，建议提取为常量。 |
| 14 | 51b1e24 | 6 个 dashboard/theme 文件 | 更早 commit 中添加的实验性代码在本 commit 中被整体删除（891 行），反映前期缺乏设计冻结机制。 |
| 15 | 6bc2ecd | 4 个孤立文件及 4 个未调用方法 | 死代码清理规范执行，无残留引用。 |
| 16 | 28423fc | `src/gui/pyqt6/pages/maaend_control_page.py` | `_run_task` → `_add_task_to_queue` 等函数重命名后，测试同步更新但幅度有限，可能与 GUI 调用侧引用不一致。 |

---

## 二、重复修复与反复修改模式

### 2.1 Hotfix 聚集区

| 文件路径 | 120 commit 内修改次数 | 特征 |
|---------|---------------------|------|
| `src/gui/pyqt6/pages/maaend_control_page.py` | **41 次** | 队列持久化、任务名称显示、按钮布局、自动保存等多类问题反复修复，是最大风险点。 |
| `src/gui/pyqt6/theme/theme_manager.py` | **19 次** | 主题系统从多主题简化到单一主题，颜色从紫(#5c7cfa)改到蓝(#19d1ff)。 |
| `src/gui/pyqt6/theme/widget_styles.py` | **17 次** | 样式反复调整，缺乏设计冻结。 |
| `src/cli/istina.py` | **5 次连续修复** | `_interactive_loop` 在 5 个连续 commit 中被修复（编码、异常处理、导入缺失），无测试。 |
| `src/core/service/runtime.py` | **6+ 次** | 按需加载、dispatch 逻辑、LLM 连接等多类重构。 |

### 2.2 "先建后拆" 浪费

`widget_perf.py`、`widget_notification.py`、`chart_widget.py` 在 1-2 个 commit 中添加，在 `51b1e24` 中全部删除（891 行）。反映 GUI 优化过程中缺乏设计冻结机制。

### 2.3 重构序列问题

- LlamaServerRuntime 单例重构（578ca5e / 753a44a）message 完全相同，但分别修改不同文件，建议 squash。
- CLI 交互模式连续 5 个 fix commit（1ff403f → c887d5f），说明实现未充分考虑 Windows 兼容性。

---

## 三、文档与代码一致性差距

### 3.1 高严重级不一致

| 文档 | 问题 | Commit/文件 |
|-----|------|------------|
| `docs/TASK_LOG.md` | 存在未提交的矛盾条目（01:11 与 06:10 关于自动连接的决策互相冲突） | 时间戳缺乏校验 |
| `docs/TASK_LOG.md` | 23:13 条目声称修改了 3 个文件但 git 中无任何对应变更 | 虚拟记录 |
| `docs/TASK_LOG.md` | 0447387 暴露了时间戳批量修正和时序倒置问题 | 0447387 |
| `docs/TASK_LOG.md` | 4035aa1 的 commit message 声称删除页面文件，实际仅移除导航引用 | 4035aa1 |

### 3.2 中严重级不一致

| 文档 | 问题 | 文件 |
|-----|------|------|
| `reports/function_table.md` | 仍引用已删除的 `agent_page.py` | 28423fc |
| `reports/test_report_2026-07-07.md` | 引用了虚拟环境依赖路径 `maa/agent_client.py` 而非项目源码 | - |
| `reports/function_naming_anomalies_report.md` | 声称全部修复但工作区仍有未提交改动 | - |
| `docs/CHAIN_RECONSTRUCTION_REPORT.md` | 仍引用已删除文件 | - |

### 3.3 系统性模式

- TASK_LOG 时间戳缺乏校验机制，允许倒置和批量修正。
- 报告未随文件删除同步更新（`agent_page.py` 等）。
- 未提交变更累积导致文档与代码状态脱节。

---

## 四、关键代码位置详查

### 4.1 Dispatch 逻辑不一致（高危 #1）

**位置**: `src/core/service/runtime.py`

```python
# Line 427-449: _daily_run 使用 preset.run
def _daily_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
    ...
    ok = self.execute("preset.run", {"name": preset_name, "serial": serial})  # Line 441

# Line 451-473: _harvest_run 使用 task.run
def _harvest_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
    ...
    ok = self.execute("task.run", {"name": task_name, "options": options, "serial": serial})  # Line 465
```

**影响**: `daily.run` 与 `harvest.run` 走不同的 MaaEnd 命令，导致 CLI 返回结果格式不一致。

### 4.2 跨层命名不一致（高危 #5）

**位置**: `src/core/service/runtime.py` vs `src/gui/pyqt6/pages/maaend_control_page.py`

```python
# runtime.py Line 366-381: 保留旧方法名
def _run_task(self, params: Dict[str, Any]) -> bool:      # Line 366
def _run_preset(self, params: Dict[str, Any]) -> bool:    # Line 375

# maaend_control_page.py Line 1262-1286: 已重命名
def _add_task_to_queue(self):       # Line 1262
def _apply_preset_to_queue(self):   # Line 1286
```

**影响**: GUI 层调用 `_add_task_to_queue`，但 runtime 层仍暴露 `_run_task`，形成两层命名鸿沟。

### 4.3 注释残留（高危 #6）

**位置**: `src/gui/pyqt6/pages/maaend_control_page.py:635`

```python
# 添加预设到队列 = 覆盖现有队列（清空再填充），不是追加；与 _run_preset 共享同一覆盖语义。
```

**问题**: 注释中引用已重命名的 `_run_preset`，实际应为 `_apply_preset_to_queue`。

### 4.4 LlamaServerRuntime 单例重构（高危 #4）

**位置**: `src/core/capability/llm/runtime.py`

```python
# Line 26: 全局单例注册表
_instances: Dict[int, LlamaServerRuntime] = {}

# Line 36: PID 追踪集合
self._owned_pids: Set[int] = set()

# Line 53-59: 进程清理逻辑
def _shutdown_owned(self) -> None:
    if not self._owned_pids:
        return
    self._http_shutdown()
    self._kill_tracked_process()
    self._owned_pids.clear()

# Line 62-69: 单例获取
@classmethod
def get_instance(cls, config: Dict[str, Any]) -> LlamaServerRuntime:
    port = int(config.get("port", 9998))
    if port not in cls._instances:
        cls._instances[port] = cls(config)
    instance = cls._instances[port]
    instance._config = config
    return instance
```

**问题**: 73 行核心逻辑无测试覆盖，atexit 清理可能与 GC 冲突（已知 `test_istina_runtime.py` 中 `maa.agent_client.__del__` 触发访问违规）。

### 4.5 CLI 交互循环连续修复（中危 #12）

**位置**: `src/cli/istina.py:259-309`

```python
def _interactive_loop(parser: argparse.ArgumentParser) -> int:
    runtime = IstinaRuntime()
    buffer = ""
    self_logger = get_logger(__name__)
    while True:
        chunk = None
        try:
            chunk = sys.stdin.read(1)                    # Line 266: bytes 兼容
        except Exception as exc:
            self_logger.error("CLI 交互循环: stdin 读取异常", error=str(exc))
            break
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8", errors="replace")  # Line 274: bytes 解码
        ...
        try:
            payload = (_json_dumps(result) + "\n").encode("utf-8", errors="replace")
            sys.stdout.buffer.write(payload)             # Line 305: UTF-8 输出
            sys.stdout.buffer.flush()
        except Exception as exc:
            self_logger.error("CLI 交互循环: stdout 写入异常", error=str(exc))
```

**问题**: 5 个连续 commit（1ff403f → c887d5f）在此函数上打补丁，无任何单元测试。

### 4.6 重复颜色值硬编码（低危 #13）

**位置**: `src/gui/pyqt6/theme/theme_manager.py`

```python
# Line 74: "info_container": "rgba(25, 209, 255, 0.10)"
# Line 79: "success_container": "rgba(25, 209, 255, 0.10)"
# Line 84: "tertiary_container": "rgba(25, 209, 255, 0.10)"
# Line 104: "secondary_container": "rgba(25, 209, 255, 0.10)"
# Line 111: "border_light": "rgba(25, 209, 255, 0.10)"
# Line 117: "selection_bg": "rgba(25, 209, 255, 0.10)"
# Line 121: "shadow_cyan": "rgba(25, 209, 255, 0.05)"
```

共 7 处重复，建议提取为 `PRIMARY_CYAN = "25, 209, 255"` 常量拼接。

### 4.7 测试绕过与目标篡改（中危 #2）

**位置**: `tests/test_istina_cli_commands.py`

```python
# Line 76: 原命令目标为 "hub"
for command in [["system", "env"], ["system", "disk"], ["device", "info"], ["nav", "hub"]]:

# Line 158: 未提交修改将目标改为 "CloseGame"
def test_nav_command_returns_success_with_target() -> None:
    returncode, parsed, _ = _run_cli(["nav", "CloseGame"])
```

**问题**: `skipif` 装饰器被移除，业务命令在 CI 无设备环境下强制执行；`nav` 目标被篡改。

---

## 五、经验总结与改进建议

### 5.1 立即行动项

1. **修复未提交的 dispatch 不一致**：`src/core/service/runtime.py:441` `_daily_run` 应同步改为 `task.run` 或回滚 `_harvest_run`，确保 dispatch 路径统一；同时为 `_daily_run`、`_harvest_run`、`_analyze_run` 添加单元测试，覆盖 preset/task 分发逻辑。
2. **恢复基础测试**：`maaend_control_page.py` 当前 10 个测试全部 FAILED（`QProgressBar` 导入缺失），建议立即修复导入问题，恢复基础初始化测试。
3. **Squash 重复 commit**：将 578ca5e 和 753a44a squash 为单一 commit，message 为 "refactor: LlamaServerRuntime 全局单例并修复进程管理漏洞"。

### 5.2 短期改进项

4. **为高频修改模块补充测试**：
   - `_interactive_loop`（`src/cli/istina.py:259`）：模拟 stdin/stdout 的 bytes/str/异常场景，避免每次 release 后都出现编码相关 hotfix。
   - `LlamaServerRuntime` 单例（`src/core/capability/llm/runtime.py:62`）：验证 `get_instance` 同一端口返回同一对象、PID 追踪正确性、atexit 清理不误杀其他实例。
   - `android_runtime screenshot` 回退路径：mock 测试验证 scrcpy 帧获取失败时正确回退 ADB screencap。

5. **建立 GUI 页面修改 checklist**：任何修改 `src/gui/pyqt6/pages/*.py` 的 commit，必须同步检查对应 `tests/test_*.py` 是否覆盖关键初始化路径。

6. **主题/样式常量提取**：`theme_manager.py` 中 7 处 `rgba(25, 209, 255, 0.10)` 建议提取为常量，避免硬编码分散。

### 5.3 长期机制改进

7. **设计冻结机制**：GUI 优化周期应设置设计冻结点，避免"先建后拆"的浪费（如 dashboard widget 先建 3 个再删 891 行）。
8. **TASK_LOG 校验机制**：增加时间戳顺序校验和文件修改验证，防止虚拟记录和时序倒置。
9. **文档同步检查**：任何删除文件的 commit 必须同步更新引用该文件的所有报告和文档。
10. **重构粒度控制**：单 commit 删除 455 行、修改 10 个文件（如 45545d3）的变更面过广，建议拆分为多个小 commit。

---

## 六、审计统计

| 指标 | 数值 |
|------|------|
| 审计 commit 总数 | 120 |
| 高危隐患数 | 6 |
| 中危隐患数 | 6 |
| 低危隐患数 | 4 |
| Hotfix 聚集区 | 3 个（maaend_control_page、istina.py、android_runtime） |
| 文档不一致 | 7 处 |
| 重复重构需 squash | 1 组（578ca5e/753a44a） |
| 关键代码位置详查 | 8 处 |

---

## 七、附录：关键文件修改频率

| 文件路径 | 120 commit 内修改次数 | 主要问题类型 |
|---------|---------------------|-------------|
| `src/gui/pyqt6/pages/maaend_control_page.py` | 41 | 队列持久化、任务名称、按钮布局、自动保存 |
| `src/gui/pyqt6/theme/theme_manager.py` | 19 | 主题简化、颜色调整、图标移除 |
| `src/gui/pyqt6/theme/widget_styles.py` | 17 | QSS 样式反复调整 |
| `src/cli/istina.py` | 5 | I/O 编码、异常处理、导入修复 |
| `src/core/service/runtime.py` | 6+ | 按需加载、dispatch、LLM 连接 |
| `src/core/capability/llm/runtime.py` | 2 | 单例重构、PID 追踪 |
| `src/core/capability/device/android_runtime.py` | 2 | screenshot 回退、scrcpy session |

---

*本报告基于 git 历史静态审计，未修改任何代码。所有代码位置均通过 `grep -n` 和 `git show` 验证。*
