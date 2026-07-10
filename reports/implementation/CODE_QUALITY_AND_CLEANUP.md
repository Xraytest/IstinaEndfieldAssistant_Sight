# 代码质量与清理

## 1. 死代码与孤立代码清理记录

**清理日期**：2026-07-07  
**清理范围**：`src/`（排除 `MaaEnd/` 及发行版目录）  
**执行方式**：删除孤立文件与未调用方法，未修改模块化架构，未新增测试代码

---

### 已删除文件

| 文件路径 | 删除原因 |
|---|---|
| `src/core/foundation/utils.py` | 全项目无引用。`safe_parse_json()`、`safe_call()`、`log_exception()` 在 `src/`、`scripts/`、`tests/` 范围内均未被调用。 |
| `src/core/foundation/constants.py` | 全项目无引用。`DEFAULT_DEVICE_ADDRESS`、`DEFAULT_ADB_PATH` 未使用，硬编码字符串直接出现在业务代码中。 |
| `src/core/capability/adb_utils.py` | 便捷导入模块，无任何模块引用。`ADBDeviceManager as ADB` 与 `TouchManager` 的便捷别名未使用。 |
| `src/core/capability/input/screenshot/screen_capture.py` | `ScreenCapture` 类完全未被实例化或导入。实际截图通过 `ADBDeviceManager.screencap()` 完成。 |

### 已删除方法

| 文件 | 删除方法 | 删除原因 |
|---|---|---|
| `src/core/capability/element_recognition/element_info.py` | `PageInfo.get_elements_by_type()` | 全项目无调用 |
| `src/core/capability/element_recognition/element_info.py` | `PageInfo.get_elements_by_source()` | 全项目无调用 |
| `src/core/capability/element_recognition/element_info.py` | `PageInfo.find_element()` | 全项目无调用 |
| `src/gui/pyqt6/pages/prts_full_intelligence_page.py` | `set_analysis_mode()` | 全项目无调用 |

### 验证方式

- 对上述所有符号做全项目 `grep`，`src/`、`scripts/`、`tests/` 范围内均无引用。
- `cli/handlers.py` 中 `base64`、`os`、`platform`、`shutil`、`datetime`、`Path` 等导入均有实际调用，**未删除**。
- `TaskLoader`/`TaskRunner` 被 `scripts/verify_ocr_integration.py` 和 `tests/test_template_pipeline.py` 引用，**未删除**。

### 架构保持现状

- `cli/handlers` → `core/service/runtime` → `core/foundation` + `core/capability` 三层架构保持不变。
- 未对 `Navigator` 子模块、识别后端注入等架构问题做修改。
- 未新增任何测试代码。

## 2. 跨模块调用链汇总

### 2.1 Runtime → MaaEnd → Device

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `IstinaRuntime.maaend()` → `MaaEndRuntime` | ✅ | 结构正确 |
| `IstinaRuntime.android()` → `AndroidRuntimeProxy` → `AndroidRuntime` → `_Daemon` | ✅ | `_Daemon._dispatch()` 已统一使用 `params.get("serial", self._serial)` |
| `IstinaRuntime.disconnect()` → `MaaEndRuntime.disconnect()` | ✅ | `disconnect()` 已调用 `_cleanup_partial()` 终止 agent 进程 |

### 2.2 Scene → Recognizer → Backends

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `SceneUnderstandingService.identify()` → `EndfieldElementRecognizer.recognize()` | ✅ | |
| `EndfieldElementRecognizer` → `TemplateBackend/OCRBackend/ColorBackend/YOLOBackend` | ✅ | |
| `EndfieldElementRecognizer` → `PipelineRunner` (via TemplateBackend) | ⚠️ | MaaFW 注入仅在 TemplateBackend 中，TaskRunner 路径缺失 |

### 2.3 CLI/GUI → Runtime

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `CLIDispatch.dispatch()` → `runtime.execute()` | ✅ | 21 个分支全部映射 |
| `MaaEndControlPage._sync_execute()` → `CLIBridge.execute()` | ✅ | 存在死代码 |
| GUI 选项序列化 → Runtime options | ⚠️ | 合并顺序错误 |

### 2.4 LLM & Navigation

| 调用链 | 状态 | 备注 |
|--------|------|------|
| `LlamaServerRuntime` → `llama-server` 进程 | ✅ | 死锁风险 |
| `LlmClient.chat()` → `/v1/chat/completions` | ✅ | |
| `Navigator.to_coords_vlm()` → `VlmWalkNavigator` | ✅ | `level_id` 回退不一致 |
| `_vlm_keyevent()` → `AndroidRuntimeProxy.keyevent()` | ✅ | 签名匹配 |

## 3. 修复优先级建议

### P0 — 立即修复
- [ ] `LlamaServerRuntime` atexit 清理改为实例级端口列表

### P1 — 本次迭代
- [ ] GUI 选项合并顺序：`options = dict(saved) or {}; options.update(current)`
- [ ] `TaskRunner` 支持注入 `maa_tasker`，或提取 `MaaFWMatcherAdapter`
- [ ] `to_coords_vlm` 复用 `_resolve_current_level`

### P2 — 后续清理
- [ ] 统一 `adb_path` 解析策略
- [ ] 统一 `device_address` 默认值
- [ ] 删除死方法/死代码（`_load_state`、`_build_args` JSON 路径等）
- [ ] 提取公共截图解码函数
- [ ] 修正误导性类名与 docstring

## 4. 命名 vs 实现对照表

| 函数/类 | 命名暗示 | 实际实现 | 结论 |
|---------|----------|----------|------|
| `AndroidRuntimeProxy.default_client` | 返回 ADBDeviceManager | `__getattr__` 委托 `AndroidRuntime` 单例，`default_client` 返回当前 serial 的 client | ✅ 已收敛为 Adapter |
| `AndroidRuntimeProxy` | 透明代理 | `__getattr__` 自动委托 `AndroidRuntime` 单例 | ✅ 适配器 |
| `IstinaRuntime` | 单一运行时 | 多运行时门面/调度器 | ⚠️ 命名过宽 |
| `MaaEndRuntime` | 镜像 MaaEnd 进程 | 本地资源加载 + Tasker bridge | ⚠️ docstring 需更新 |
| `PipelineRunner` | 纯图执行器 | 嵌入 MaaFW SDK + 颜色匹配 | ❌ 违反 SRP |
| `ColorBackend.recognize_gameplay_scene` | 颜色匹配 | 3D 场景理解 | ❌ 职责错位 |
| `EndfieldElementRecognizer` 模块 docstring | 5 种后端 | 4 种后端 + 1 个后处理 | ❌ 描述不准确 |
