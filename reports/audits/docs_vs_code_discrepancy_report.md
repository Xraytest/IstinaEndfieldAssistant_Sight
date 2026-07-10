# 文档与代码实现差异报告

> 生成日期：2026-07-10
> 对比范围：`docs/` 全部 10 篇文档 vs `src/` 当前实现（含 `config/client_config.json`）
> 方法：逐篇比对文档中的结构描述、行为声明、行号引用与修复状态标记，并对关键声明做源码级核实（`grep` / 直接读文件；必要时借助 code-explorer 子代理做全树映射）。

---

## 0. 结论速览

文档整体质量较高，但存在三类主要差异：

1. **已修复的缺陷仍被文档写成"未修复的已知问题"**（4 处）——主要是 LLM/超时相关，文档落后于一线的修复提交。
2. **结构性描述与当前代码不符**（5 处）——含路径写错、命令数过时、属性重命名、死方法已删除、配置样本与真实配置不符。
3. **行号引用普遍失效**——大量 `file:line` 已漂移，需重新校准或改为语义定位。

值得肯定的是：另有若干条目经核实**与现状一致**（如 `_apply_log_filter` 空实现、PipelineRunner 仍耦合 MaaFW、ColorBackend 职责错位、识别后端 docstring 仍写"5 种"），本报告一并列出以保持客观。

---

## 1. 已修复却被文档描述为"未修复"的条目

| # | 文档 / 位置 | 文档所述（未修复） | 代码实际（已修复） | 核实位置 |
|---|------------|------------------|------------------|---------|
| D1 | `docs/GUI_CLI_AND_AUTOMATION.md` §1.1「错误 1 P0」：默认超时 1200ms 导致全部任务失败 | `_sync_execute(..., timeout_ms=1200)`，P0 未修 | 默认超时已改为 **300000ms（5 分钟）** | `src/gui/pyqt6/pages/maaend_control_page.py:319` |
| D2 | `docs/LLM_AND_NAVIGATION.md` §2 Medium#4：`subprocess.Popen` 用 `PIPE` 死锁风险 | 长时间进程未消费 stdout/stderr | 已重定向到 **`subprocess.DEVNULL`** | `src/core/capability/llm/runtime.py:320` |
| D3 | `docs/LLM_AND_NAVIGATION.md` §2 High#1：`LlamaServerRuntime` atexit 清理硬编码端口 `[9998]` | 固定 `[9998]`，改端口则失效 | `_atexit_cleanup` 现**遍历 `_instances.values()`** 清理所有实例，不再硬编码 | `src/core/capability/llm/runtime.py:52-58` |
| D4 | `docs/LLM_AND_NAVIGATION.md` §2 Low#6：重复 GPU 参数（`-ngl` 与 `--n-gpu-layers`） | 同时传两个参数 | 仅传 **`-ngl`**，无 `--n-gpu-layers` | `src/core/capability/llm/runtime.py:273` |

> 说明：D1–D4 与 `docs/TASK_LOG.md` 2026-07-10 的修复记录一致（超时/线程安全/资源清理等已落地），文档未同步更新修复结论。其中 D3 仅 `get_default_instance()`（`runtime.py:82`）仍硬编码 `9998` 作为"默认实例"查找键，属残留而非清理逻辑错误，但文档 High#1 的整体修复结论现已成立。

---

## 2. 结构性描述与代码实现不符

| # | 文档 / 位置 | 文档所述 | 代码实际 | 核实位置 |
|---|------------|---------|---------|---------|
| D5 | `docs/ARCHITECTURE.md` §2 代码片段：`MaaEndRuntime.load_tasks` | "递归扫描 `MaaEnd/assets/tasks/**/*.json`" | 默认根目录是 **`3rd-part/maaend`**；`load_tasks` 经 `_resolve_asset_path("tasks")` 读取 `3rd-part/maaend/tasks`（或 `3rd-part/maaend/assets/tasks`）。文档写死的 `MaaEnd/assets/tasks` 路径与本项目"双目录铁律"（`docs/RUNTIME_DEVICE_AND_MAAEND.md` §0）自相矛盾 | `src/core/service/maa_end/runtime.py:89-90, 133-134` |
| D6 | `docs/GUI_CLI_AND_AUTOMATION.md` §7.3 / `docs/CODE_QUALITY_AND_CLEANUP.md` §2.3 等："`CLIDispatch.dispatch()` → runtime.execute() ✅ 19 个分支全部映射" | 19 个命令分支 | 实际顶层命令 **≥21 个**（新增 `nav2`、`nav3`），文档计数已过时 | `src/cli/handlers.py:49-89`（`if args.command ==` 共 21 处） |
| D7 | `docs/RUNTIME_DEVICE_AND_MAAEND.md` §8 / `docs/CODE_QUALITY_AND_CLEANUP.md` §4 命名对照表：`AndroidRuntimeProxy.adb_manager` | "命名暗示返回 ADBDeviceManager，实际返回 AndroidRuntime ❌ 不匹配" | `AndroidRuntimeProxy` **已无 `adb_manager` 属性**，重命名为 **`default_client`**（只读属性）；且委托机制由"手动转发每个方法"改为 `__getattr__` 魔法委托 | `src/core/service/runtime.py:86-92` |
| D8 | `docs/GUI_CLI_AND_AUTOMATION.md` §6.3 Low#5：`_load_state()` 死方法 | "maaend_control_page.py:1161-1204 定义了但从未调用" | 全文件 **不存在 `_load_state`**（0 处引用），该方法已被删除 | `grep` 全 `src` 无命中 |
| D9 | `docs/LLM_AND_NAVIGATION.md` §1.5「推荐配置」与 §1.1：`model_path`=`models/LLM/Qwen3.5-4B-UD-Q4_K_XL.gguf`、`port`=9998、上下文 32768 | 以 Qwen3.5-4B 为例给出性能调优数据 | 真实 `config/client_config.json`：`model_path`=`/models/test.gguf`、`port`=**1234**；其余（ngl/context/threads/kv/q8_0/batch/ubatch/no_repack/no_cont_batching）与文档一致 | `config/client_config.json:30-46` |

> D5 特别值得注意：ARCHITECTURE 的示例把 `MaaEnd/assets/tasks` 当成加载来源，而同一仓库的 RUNTIME 文档明确"只有 `3rd-part/maaend/` 才被调用"。两篇文档相互打架，且 ARCHITECTURE 的写法会让读者误以为 IEA 从 `MaaEnd/`（源码镜像）读取任务。

---

## 3. 经核实"与现状一致"的条目（可信性对照）

为避免"文档全错"的误判，以下条目经源码核实**准确反映当前代码**，应在更新文档时保留其正确性（其中多数是"已知问题"仍真实存在）：

| # | 文档声明 | 核实结果 | 位置 |
|---|---------|---------|------|
| V1 | `docs/GUI_LOG_CATEGORIES.md` §1：`_apply_log_filter` 是空占位，`_log_text` 尚未真正按级别过滤 | **准确**：方法体为 `pass` | `maaend_control_page.py:1542-1547` |
| V2 | `docs/RECOGNITION_PIPELINE_AND_TASKS.md` Medium#6 / 命名表：`ColorBackend.recognize_gameplay_scene` 做 3D 场景理解（蓝占比/肤色检测），职责错位 | **准确且仍存在**：方法实现蓝像素占比、肤色轮廓、角色/物体检测 | `color_backend.py:97-135` |
| V3 | 同上 High#1：`PipelineRunner` 泄漏 MaaFW 运行时耦合 | **准确且未修**：仍 `from maa.pipeline import`、`from maa.tasker import Tasker`，并调用 `_maa_tasker.post_recognition` | `pipeline_runner.py:17-19, 151, 175, 239, 248` |
| V4 | 同上 High#2：`TaskRunner` 无法向 `PipelineRunner` 注入 `maa_tasker` | **准确且未修**：`self._pipeline_runner = pipeline_runner or PipelineRunner()` 未传 `maa_tasker` | `tasks/task_runner.py:23` |
| V5 | `docs/RECOGNITION_PIPELINE_AND_TASKS.md` Low#7：模块 docstring 声称"5 种识别技术" | **准确**：代码 docstring 仍为"整合 5 种识别技术"，实际为 4 后端 + 1 后处理 | `recognizer.py:4` |
| V6 | `docs/RUNTIME_DEVICE_AND_MAAEND.md` High#1/#2 标记"✅ 已修复"（disconnect 泄漏 agent、Daemon 忽略 serial） | **准确**：`disconnect()` 调 `_cleanup_partial` 并 `wait()`；`_Daemon._dispatch` 用 `params.get("serial", self._serial)` | `maa_end/runtime.py`、`android_runtime.py` |
| V7 | `docs/ARCHITECTURE.md` §15.1："5 个页面 + CLIBridge" | **准确**：`main_window.py` 仅注册 5 个页面；`scripting/scripting_page.py`（`ScriptingPage`）未接入主导航，属独立/实验模块，不构成第 6 个页面 | `main_window.py:30-34, 192-200` |

---

## 4. 行号引用普遍失效

文档大量使用 `file:line` 精确定位，但代码经多次修复后行号已漂移。代表性偏差：

- `_apply_log_filter`：文档写 `maaend_control_page.py:1539`，实际 `:1542`。
- `MaaEndRuntime` 多处引用 `runtime.py:282 / :529`（disconnect / screenshot），与当前实现不符。
- `android_runtime.py:470-488`（Daemon 分发）、`:614 / :186 / :83 / :76`（scrcpy 各组件）等定位需重新校准。
- `maaend_control_page.py` 的 `:1317–:1479`、`:340`、`:819`、`:704`、`:1569` 等执行/队列日志源标签位置均已变动。

**建议**：文档中的修复清单/调用链表保留"✅/⚠️/❌"状态与语义描述即可，行号改为"函数名 + 目录"定位（如 `MaaEndRuntime.load_tasks`），避免维护成本。

---

## 5. 优先级建议（更新文档）

### P0 — 立即修正（避免误导后续开发）
- **D9**：`LLM_AND_NAVIGATION.md` 的配置样本与 `config/client_config.json` 严重不符（模型、端口），且性能章节基于不存在的 Qwen3.5-4B 配置。应改为"示例配置 / 占位说明"，或同步为真实可运行配置。
- **D1 / D2 / D3 / D4**：将"已修复"的结论写回对应文档（GUI_CLI §1.1、LLM §2 的 High#1/Medium#4/Low#6），或加"✅ 已修复 @2026-07-10"标记，避免读者以为仍是 P0/P1 缺陷。

### P1 — 本轮迭代
- **D5**：修正 ARCHITECTURE §2 代码片段中 `load_tasks` 的扫描路径，统一为 `3rd-part/maaend/tasks`，与 RUNTIME §0 铁律对齐。
- **D6**：将 `CLIDispatch` 分支计数由 19 更新为实际值（≥21），或直接写"全部 `args.command` 分支已映射"。
- **D7**：更新命名对照表——`adb_manager` 已更名为 `default_client`，且委托机制为 `__getattr__` 转发；相应结论（"适配器而非代理"）需重述。

### P2 — 后续清理
- **D8**：删除 GUI_CLI §6.3 Low#5 关于 `_load_state` 的条目（方法已不存在）。
- **行号引用（第 4 节）**：批量复核并移除/语义化过时的 `file:line`。

---

## 6. 完整核查清单（含未发现问题）

| 文档 | 核查点 | 结论 |
|------|-------|------|
| ARCHITECTURE | 分层目录结构 (src/core/capability 等) | ✅ 准确 |
| ARCHITECTURE | §2 `load_tasks` 扫描路径 | ❌ D5（路径写错） |
| ARCHITECTURE | §15.1 五个页面 + 状态"正常" | ✅ 准确（V7） |
| ARCHITECTURE | §15.2.2 `_run_task` 已不存在 | ✅ 准确 |
| ARCHITECTURE | §14 设计语言/色彩 token | ⚠️ 未逐项核实（非行为声明，略） |
| RUNTIME_DEVICE_AND_MAAEND | §0 双目录铁律 | ✅ 准确 |
| RUNTIME_DEVICE_AND_MAAEND | High#1/#2 已修复 | ✅ 准确（V6） |
| RUNTIME_DEVICE_AND_MAAEND | §8 命名对照表 `adb_manager` | ❌ D7（已重命名） |
| RUNTIME_DEVICE_AND_MAAEND | §3 各 `file:line` 定位 | ⚠️ 行号漂移（第 4 节） |
| RECOGNITION_PIPELINE_AND_TASKS | High#1 PipelineRunner 耦合 MaaFW | ✅ 准确且未修（V3） |
| RECOGNITION_PIPELINE_AND_TASKS | High#2 TaskRunner 未注入 maa_tasker | ✅ 准确且未修（V4） |
| RECOGNITION_PIPELINE_AND_TASKS | Medium#6 ColorBackend 职责错位 | ✅ 准确且仍存在（V2） |
| RECOGNITION_PIPELINE_AND_TASKS | Low#7 docstring "5 种" | ✅ 准确（V5） |
| GUI_CLI_AND_AUTOMATION | §1.1 错误1 超时 1200ms | ❌ D1（已改 300000） |
| GUI_CLI_AND_AUTOMATION | §6.3 Low#4 选项合并顺序 | ✅ 与 TASK_LOG 修复一致 |
| GUI_CLI_AND_AUTOMATION | §6.3 Low#5 `_load_state` 死方法 | ❌ D8（已删除） |
| GUI_CLI_AND_AUTOMATION | §7.3 "19 个分支" | ❌ D6（≥21） |
| GUI_LOG_CATEGORIES | §1 `_apply_log_filter` 空占位 | ✅ 准确（V1） |
| GUI_LOG_CATEGORIES | 四类日志面 / 分类维度 | ✅ 与代码一致（未逐项深挖） |
| LLM_AND_NAVIGATION | §1.5 推荐配置（模型/端口） | ❌ D9（与 client_config 不符） |
| LLM_AND_NAVIGATION | High#1 atexit 硬编码端口 | ❌ D3（已改为遍历实例） |
| LLM_AND_NAVIGATION | Medium#4 Popen PIPE | ❌ D2（已改 DEVNULL） |
| LLM_AND_NAVIGATION | Low#6 重复 GPU 参数 | ❌ D4（仅 -ngl） |
| CODE_QUALITY_AND_CLEANUP | §2.3 "19 个分支" | ❌ D6 |
| CODE_QUALITY_AND_CLEANUP | §4 命名对照表 `adb_manager` | ❌ D7 |
| WORKFLOW | 四段式问题报告规则 | ✅ 流程约定，与代码无关 |
| TASK_LOG | 2026-07-10 修复记录 | ✅ 与 D1/D2/D3 代码现状吻合 |

**统计**：发现文档与代码不符点 **9 处**（D1–D9），其中"已修复被写成未修复"4 处、"结构性不符"5 处；经核实准确的条目 **7 处**（V1–V7）；行号类问题 1 类。

---

## 7. 文档修订状态（2026-07-10 已执行）

以代码为权威，已将全部 9 处不符（D1–D9）修正回对应文档：

| # | 文档 | 修订动作 |
|---|------|---------|
| D1 | `docs/GUI_CLI_AND_AUTOMATION.md` | §1.1 错误 1、§2 P0#1、§3 根因总结、§8 P0 清单：标记默认超时已修复为 300000ms |
| D2 | `docs/LLM_AND_NAVIGATION.md` | §2 Medium#4、§4 P1 清单：标记 Popen 已重定向 DEVNULL |
| D3 | `docs/LLM_AND_NAVIGATION.md` | §2 High#1、§4 P0 清单：标记 atexit 已改遍历实例；补充 `get_default_instance()` 残留 9998（P3） |
| D4 | `docs/LLM_AND_NAVIGATION.md` | §2 Low#6、§4 P2 清单：标记重复 GPU 参数已移除（仅 `-ngl`） |
| D5 | `docs/ARCHITECTURE.md` | §2 `load_tasks` 片段：扫描路径改为 `3rd-part/maaend/tasks`（经 `_resolve_asset_path`） |
| D6 | `docs/GUI_CLI_AND_AUTOMATION.md`、`docs/RUNTIME_DEVICE_AND_MAAEND.md`、`docs/CODE_QUALITY_AND_CLEANUP.md` | "19 个分支" → "21 个分支"（CLI 顶层命令数） |
| D7 | `docs/RUNTIME_DEVICE_AND_MAAEND.md`、`docs/CODE_QUALITY_AND_CLEANUP.md`、§3 Medium#3 | `adb_manager` → `default_client` + `__getattr__` 委托；命名表结论更新为 ✅ |
| D8 | `docs/GUI_CLI_AND_AUTOMATION.md` | §6.2 Low#5、§8 P2 清单：标记 `_load_state()` 已删除（0 引用） |
| D9 | `docs/LLM_AND_NAVIGATION.md` | §1.1/§1.3/§1.5：模型 `/models/test.gguf`、端口 1234、移除重复 `--n-gpu-layers`、`parallel` 改 2，与 `config/client_config.json` 对齐 |

> 行号类问题（第 4 节）未逐条重校，建议长期改为"函数名 + 目录"语义定位；`get_default_instance()` 硬编码 9998 与若干未修复的"已知问题"（选项合并顺序、to_coords_vlm 回退、PipelineRunner 耦合等）仍按原状保留在文档中。
