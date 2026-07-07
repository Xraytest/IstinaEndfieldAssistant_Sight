# 代码审查报告：函数命名一致性 & 跨模块功能对接

> 审查范围：`src/core/service/runtime.py`、`src/core/service/maa_end/runtime.py`、`src/core/capability/device/android_runtime.py`、`src/core/capability/device/adb_manager.py`、`src/core/capability/element_recognition/recognizer.py`、`src/core/capability/element_recognition/scene_service.py`、`src/core/capability/element_recognition/pipeline/pipeline_runner.py`、`src/core/capability/element_recognition/tasks/task_runner.py`、`src/core/capability/llm/client.py`、`src/core/capability/llm/runtime.py`、`src/core/service/navigation/navigator.py`、`src/core/service/navigation/vlm_walk_navigator.py`、`src/cli/handlers.py`、`src/cli/istina.py`、`src/gui/pyqt6/pages/maaend_control_page.py`、`src/gui/pyqt6/cli_bridge.py`

---

## 总览

| 严重度 | 数量 |
|--------|------|
| High | 7 |
| Medium | 13 |
| Low | 17 |

---

## 一、Runtime & Device 层

### High

1. **`MaaEndRuntime.disconnect()` 泄漏 agent 进程**  
   `src/core/service/maa_end/runtime.py:255-262` 直接置空字段，未调用 `_cleanup_partial()` 终止 `go-service.exe`。  
   **修复**：在 `disconnect()` 中先调用 `self._cleanup_partial()`。

2. **Daemon 忽略 `serial` 参数（tap/swipe/keyevent/shell）**  
   `src/core/capability/device/android_runtime.py:467,470,480,483` 使用 `self._serial`，但 `startScrcpy`/`screenshot` 已支持 `params.get("serial", self._serial)`。  
   **修复**：统一为 `params.get("serial", self._serial)`。

### Medium

3. **`AndroidRuntimeProxy.adb_manager` 命名误导**  
   `src/core/service/runtime.py:39-40` 返回 `AndroidRuntime`，而非 `ADBDeviceManager`。  
   **修复**：改名为 `default_client` 或返回真实管理器。

4. **`MaaEndRuntime.screenshot()` 缺少 `serial` 参数**  
   `src/core/service/maa_end/runtime.py:529` 与 `AndroidRuntime.screenshot(serial)` 签名不一致。  
   **修复**：添加可选 `serial` 或文档说明其 per-device 约束。

5. **`device_address` 默认值不一致**  
   `MaaEndRuntime` 默认 `"localhost:16512"`，但 `IstinaRuntime.maaend()` 回退到 `"default"`，会导致 `AdbController` 连接失败。  
   **修复**：统一默认地址或在 `MaaEndRuntime.__init__` 中校验。

6. **`version()` 未暴露给 `AndroidRuntimeProxy`**  
   Daemon 与 `AndroidRuntime` 已实现，但 Proxy 未转发。  
   **修复**：在 Proxy 中添加 `version()`。

7. **`ADBDeviceManager` 路径解析策略不一致**  
   `AndroidRuntime` 使用 `get_project_root()` 拼接，`MaaEndRuntime` 按原始路径解析。  
   **修复**：统一使用 `get_project_root()`。

8. **`tasks()`/`presets()` 在空字典时反复重载**  
   `self._tasks or self.load_tasks()` 在空 dict 时为 falsy，导致每次调用都走磁盘。  
   **修复**：改为 `if not self._tasks: self.load_tasks(); return self._tasks`。

9. **`load_interface()` 缺少异常处理**  
   `src/core/service/maa_end/runtime.py:104-108` 未 try/except，`load_tasks()`/`load_presets()` 均已包裹。  
   **修复**：添加异常处理并返回 `{}`。

### Low

10. **`_pick_port()` 死代码**  
    `android_runtime.py:380-381` 仅作后备，实际 `_Daemon.start()` 绑定端口 0 后设置 `_tcp_port`，永不进入。  
    **修复**：删除或补充注释。

11. **不可达的 `if not self.connected` 块**  
    `_daily_run/_harvest_run/_analyze_run/_explore_run/_nav_to` 中，`_ensure_maaend_ready()` 之后必然 connected。  
    **修复**：移除死代码或将检查前移。

12. **误导性类名**  
    - `IstinaRuntime` 实际是 Facade/Dispatcher。  
    - `AndroidRuntimeProxy` 是 Adapter。  
    - `MaaEndRuntime` docstring 声称 "mirror MaaEnd" 但实为本地 bridge。  
    **修复**：重命名或更新 docstring。

13. **重复 `screenshot` 分发分支**  
    `runtime.py:204-205` 与 `:220-221` 重复处理 `"screenshot"`，前者使后者不可达。  
    **修复**：移除早期返回或合并。

14. **`_run_task`/`_run_preset` 冗余 legacy 检查**  
    `runtime.py:293-295, 304-305`。  
    **修复**：简化逻辑。

---

## 二、Element Recognition & Task 层

### High

1. **`PipelineRunner` 泄漏 MaaFW 运行时耦合**  
   `pipeline_runner.py:29` 名为通用图执行器，却直接导入并调用 `maa.tasker`、`maa.pipeline`（lines 19-20, 173, 246）。  
   **修复**：提取 `MaaFWMatcherAdapter` 并注入。

2. **`TaskRunner` 无法向 `PipelineRunner` 注入 `maa_tasker`**  
   `task_runner.py:16-24` 构造默认 `PipelineRunner()` 时无 `maa_tasker` 参数，导致任务执行永久锁定 OpenCV 回退，而元素识别可使用 MaaFW。  
   **修复**：向 `TaskRunner.__init__` 添加 `maa_tasker` 并转发。

### Medium

3. **`SceneUnderstandingService` 死参数 `template_threshold`**  
   `scene_service.py:27` 接收但未转发给 `EndfieldElementRecognizer`。  
   **修复**：移除或转发。

4. **`_evaluate_and`/`_evaluate_or` 使用伪造 `DirectHit` 节点 hack**  
   `pipeline_runner.py:309-343` 创建假 `PipelineNode` 仅用于按字符串解析子节点名，语义不清。  
   **修复**：改为直接按名称查找图节点。

5. **`_wait_for_freeze()` 空实现**  
   `pipeline_runner.py:378-380` 为 `pass`，静默忽略配置。  
   **修复**：实现或删除配置项。

6. **`ColorBackend.recognize_gameplay_scene()` 职责错位**  
   `color_backend.py:97` 执行 3D 场景理解（蓝色占比、肤色检测），不属于颜色匹配。  
   **修复**：迁移到 `SceneGeometryAnalyzer`。

### Low

7. **模块 docstring 声称 "5 种识别技术"**  
   `recognizer.py:4-9` 将页面分类列为第 5 种后端，实际是后处理步骤。  
   **修复**：修正描述。

8. **`SceneUnderstandingService` 与 `EndfieldElementRecognizer` YOLO 默认值不一致**  
   Service 默认 `False`，Recognizer 默认 `True`。  
   **修复**：统一或文档说明。

9. **`OCRBackend.set_maa_tasker()` 死 API**  
   从未被调用，`maa_tasker` 总通过构造函数传入。  
   **修复**：删除。

10. **`YOLOBackend.is_loaded()` 暴露但无人消费**  
    **修复**：删除或内部使用。

11. **`TemplateBackend._match_single()` SIFT 阈值魔法数**  
    `threshold * 20` 无注释解释单位转换。  
    **修复**：添加常量或注释。

---

## 三、LLM & Navigation 层

### High

1. **`LlmClient.health_check()` 端点路径错误**  
   `client.py:74` 使用 `f"{base_url}/health"`，但 `base_url` 已含 `/v1`，得到 `/v1/health`（404）。  
   `runtime.py:106` 使用正确根路径。  
   **修复**：`client.py` 改为 `base_url.split('/v1',1)[0] + '/health'`。

2. **`LlamaServerRuntime` atexit 清理硬编码端口**  
   `runtime.py:42` 固定 `[9998]`，若配置改端口则失效。  
   **修复**：实例级维护端口列表。

### Medium

3. **`model` 硬编码为 `"local"`**  
   `client.py:50`。若服务端启用严格模型校验会 400。  
   **修复**：从配置或 `/v1/models` 动态获取。

4. **`subprocess.Popen` 使用 `PIPE` 死锁风险**  
   `runtime.py:279` 长时间运行进程未消费 stdout/stderr。  
   **修复**：重定向到 `DEVNULL` 或文件。

5. **`to_coords_vlm` 的 `level_id` 回退策略不一致**  
   `navigator.py:233,243` 硬编码 `"lv001"`，而 `to_coords` 使用 `_resolve_current_level`。  
   **修复**：VLM 路径复用当前层级推断。

### Low

6. **重复 GPU 参数**  
   `runtime.py:231-232` 同时传 `-ngl` 与 `--n-gpu-layers`。  
   **修复**：保留其一。

7. **`_resolve_current_level` 对空字符串过于保守**  
   `navigator.py:325-330` 空字符串返回 `None`。  
   **修复**：明确空字符串与 `None` 的语义。

8. **截图/解码逻辑重复**  
   `Navigator._get_frame` 与 `VlmWalkNavigator._grab_frame` 完全相同。  
   **修复**：提取为公共函数。

9. **`import time` 在循环内部**  
   `runtime.py:588`。  
   **修复**：移到模块顶部。

---

## 四、CLI & GUI 层

### High

1. **按钮标签与行为不匹配**  
   `maaend_control_page.py:517-520` 标签为 `"添加任务"`，但连接 `_run_task`（立即执行）。  
   **修复**：改标签为 `"运行任务"` 或改连接到 `_add_to_queue`。

2. **选项合并顺序错误（4 处）**  
   `saved` 覆盖当前 UI/队列值，应为 UI 值稳赢。  
   - `_run_task` `:1321-1322`  
   - `_add_to_queue` preset `:788-795`  
   - `_add_to_queue` task `:805-808`  
   - `_runtime_queue_runner` `:870-874`  
   **修复**：`options = dict(saved) if saved else {}; options.update(ui_options)`。

3. **队列执行器中 preset 分支死代码**  
   `maaend_control_page.py:866-868` 因 preset 展开为 task，永不命中。  
   **修复**：删除分支或允许真正 preset 条目。

### Medium

4. **`self._queue_items` 缓存脆弱**  
   多处读取缓存而非 `queue_state.queue_items`。  
   **修复**：统一使用 `queue_state.queue_items`。

5. **`_load_state()` 死方法**  
   `maaend_control_page.py:1161-1204` 定义了但从未调用。  
   **修复**：删除。

### Low

6. **CLI `--timeout` 静默丢弃**  
   `handlers.py:283` 传入 `timeout`，但 `_run_task` 与 `MaaEndRuntime.run_task` 均不接受。  
   **修复**：移除参数或实现超时。

7. **`_sync_execute` 的 `isinstance(params, int)` 死代码**  
   `maaend_control_page.py:363-366`。  
   **修复**：删除。

8. **`_build_args` JSON 参数路径未被 GUI 使用**  
   `cli_bridge.py:71-80`。  
   **修复**：删除或文档说明。

9. **`scene nav` 别名易混淆**  
   `handlers.py:424-426` 映射到 `nav.to`。  
   **修复**：保持现状但补充注释。

---

## 五、跨模块调用链检查

### 5.1 Runtime → MaaEnd → Device

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `IstinaRuntime.maaend()` → `MaaEndRuntime` | ✅ | 结构正确 |
| `IstinaRuntime.android()` → `AndroidRuntimeProxy` → `AndroidRuntime` → `_Daemon` | ✅ | 存在 serial 忽略 bug（见上文 High #2） |
| `IstinaRuntime.disconnect()` → `MaaEndRuntime.disconnect()` | ⚠️ | 泄漏 agent 进程（见上文 High #1） |

### 5.2 Scene → Recognizer → Backends

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `SceneUnderstandingService.identify()` → `EndfieldElementRecognizer.recognize()` | ✅ | |
| `EndfieldElementRecognizer` → `TemplateBackend/OCRBackend/ColorBackend/YOLOBackend` | ✅ | |
| `EndfieldElementRecognizer` → `PipelineRunner` (via TemplateBackend) | ⚠️ | MaaFW 注入仅在 TemplateBackend 中，TaskRunner 路径缺失（见上文 High #2） |

### 5.3 CLI/GUI → Runtime

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `CLIDispatch.dispatch()` → `runtime.execute()` | ✅ | 19 个分支全部映射 |
| `MaaEndControlPage._sync_execute()` → `CLIBridge.execute()` | ✅ | 存在死代码（见上文 Low #7） |
| GUI 选项序列化 → Runtime options | ⚠️ | 合并顺序错误（见上文 High #2） |

### 5.4 LLM & Navigation

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `LlamaServerRuntime` → `llama-server` 进程 | ✅ | 死锁风险（见上文 Medium #4） |
| `LlmClient.chat()` → `/v1/chat/completions` | ✅ | `health_check()` 端点错误（见上文 High #1） |
| `Navigator.to_coords_vlm()` → `VlmWalkNavigator` | ✅ | `level_id` 回退不一致（见上文 Medium #5） |
| `_vlm_keyevent()` → `AndroidRuntimeProxy.keyevent()` | ✅ | 签名匹配 |

---

## 六、修复优先级建议

### P0 — 立即修复
- [ ] `MaaEndRuntime.disconnect()` 调用 `_cleanup_partial()`
- [ ] Daemon `_dispatch` 统一使用 `params.get("serial", self._serial)`
- [ ] `LlmClient.health_check()` 修正端点路径
- [ ] `LlamaServerRuntime` atexit 清理改为实例级端口列表

### P1 — 本次迭代
- [ ] GUI 选项合并顺序：`options = dict(saved) or {}; options.update(current)`
- [ ] 按钮标签 `"添加任务"` → `"运行任务"`（或改连接）
- [ ] 删除 `_runtime_queue_runner` 中死代码 `preset` 分支
- [ ] `TaskRunner` 支持注入 `maa_tasker`，或提取 `MaaFWMatcherAdapter`
- [ ] `to_coords_vlm` 复用 `_resolve_current_level`

### P2 — 后续清理
- [ ] 统一 `adb_path` 解析策略
- [ ] 统一 `device_address` 默认值
- [ ] 删除死方法/死代码（`_load_state`、`_pick_port`、`_build_args` JSON 路径等）
- [ ] 提取公共截图解码函数
- [ ] 修正误导性类名与 docstring

---

## 七、附录：命名 vs 实现对照表

| 函数/类 | 命名暗示 | 实际实现 | 结论 |
|---------|----------|----------|------|
| `AndroidRuntimeProxy.adb_manager` | 返回 ADBDeviceManager | 返回 AndroidRuntime | ❌ 不匹配 |
| `AndroidRuntimeProxy` | 透明代理 | 手动转发每个方法 | ⚠️ 适配器而非代理 |
| `IstinaRuntime` | 单一运行时 | 多运行时门面/调度器 | ⚠️ 命名过宽 |
| `MaaEndRuntime` | 镜像 MaaEnd 进程 | 本地资源加载 + Tasker bridge | ⚠️ docstring 需更新 |
| `PipelineRunner` | 纯图执行器 | 嵌入 MaaFW SDK + 颜色匹配 | ❌ 违反 SRP |
| `ColorBackend.recognize_gameplay_scene` | 颜色匹配 | 3D 场景理解 | ❌ 职责错位 |
| `EndfieldElementRecognizer` 模块 docstring | 5 种后端 | 4 种后端 + 1 个后处理 | ❌ 描述不准确 |
