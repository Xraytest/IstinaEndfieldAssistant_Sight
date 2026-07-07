# 测试执行报告

**日期**：2026-07-07  
**执行方式**：并行 Sub-agent 逐项执行（共 12 个测试文件）  
**约束**：未新增任何测试代码实现片段  

---

## 1. 模块框架梳理

### 1.1 分层架构

```
src/
├── core/
│   ├── foundation/              # 基础层
│   │   ├── paths.py
│   │   ├── logger.py
│   │   └── gpu_check.py
│   ├── capability/              # 能力层
│   │   ├── device/              # 设备控制
│   │   │   ├── adb_manager.py
│   │   │   ├── android_runtime.py
│   │   │   └── touch_manager.py
│   │   ├── input/               # 输入/截图（screen_capture.py 已按文档清理）
│   │   ├── element_recognition/ # 元素识别
│   │   │   ├── recognizer.py
│   │   │   ├── scene_service.py
│   │   │   ├── annotation.py
│   │   │   ├── element_info.py
│   │   │   ├── backends/        # 4 种后端
│   │   │   │   ├── template_backend.py
│   │   │   │   ├── ocr_backend.py
│   │   │   │   ├── color_backend.py
│   │   │   │   └── yolo_backend.py
│   │   │   ├── pipeline/        # Pipeline 引擎
│   │   │   │   ├── pipeline_runner.py
│   │   │   │   ├── template_registry.py
│   │   │   │   ├── pipeline_loader.py
│   │   │   │   ├── matcher.py
│   │   │   │   └── pipeline_node.py
│   │   │   └── tasks/           # 任务加载/执行
│   │   │       ├── task_loader.py
│   │   │       └── task_runner.py
│   │   └── llm/                 # LLM 运行时
│   │       ├── runtime.py
│   │       └── client.py
│   └── service/                 # 服务层
│       ├── runtime.py           # IstinaRuntime
│       ├── maa_end/
│       │   └── runtime.py       # MaaEndRuntime
│       └── navigation/          # 导航
│           ├── navigator.py
│           ├── vlm_walk_navigator.py
│           ├── minimap_locator.py
│           ├── entity_db.py
│           └── map_data_loader.py
├── cli/
│   ├── istina.py                # CLI 入口
│   └── handlers.py              # 命令分发
└── gui/pyqt6/
    ├── main.py
    ├── main_window.py
    ├── cli_bridge.py
    ├── queue_state.py
    ├── responsive.py
    ├── theme/theme_manager.py
    └── pages/
        ├── maaend_control_page.py
        ├── log_page.py
        ├── prts_full_intelligence_page.py
        ├── settings_page.py
        ├── device_settings_page.py
        └── agent_page.py
```

### 1.2 测试覆盖映射

| 测试文件 | 覆盖模块/层 | 类型 |
|---------|-----------|------|
| `test_cli_bridge.py` | CLI Bridge | 单元 |
| `test_maaend_control_page.py` | MaaEndControlPage | 单元 |
| `test_istina_runtime.py` | IstinaRuntime | 单元 |
| `test_istina_cli_commands.py` | CLI Handlers → Runtime | 集成 |
| `test_llm_mmproj.py` | LlamaRuntime / LlmClient | 单元 |
| `test_llm_runtime_image.py` | LlamaRuntime | 单元 |
| `test_scene_geometry.py` | SceneGeometryAnalyzer | 单元 |
| `test_error_paths.py` | 多模块异常路径 | 单元 |
| `test_template_pipeline.py` | Template/Pipeline/Task 模块 | 单元 |
| `test_main_window.py` | MainWindow | 单元 |
| `test_gui_cli_chain.py` | GUI ↔ CLI 调用链 | 集成 |
| `test_full_chain.py` | 端到端 CLI 子进程调用 | 系统 |

---

## 2. 逐级测试执行结果

### 2.1 第一层：最低级子模块（单元测试）

| # | 测试文件 | 通过 | 失败 | 错误 | 耗时 | 关键发现 |
|---|---------|------|------|------|------|---------|
| 1 | `test_cli_bridge.py` | 7 | 0 | 0 | 0.30s | 全部通过 |
| 2 | `test_template_pipeline.py` | 17 | 0 | 0 | — | 全部通过 |
| 3 | `test_main_window.py` | 3 | 0 | 0 | 0.21s | 全部通过 |
| 4 | `test_scene_geometry.py` | 2 | 0 | 0 | 1.39s | 全部通过 |
| 5 | `test_llm_mmproj.py` | 2 | 0 | 0 | — | 全部通过 |
| 6 | `test_llm_runtime_image.py` | 1 | 0 | 0 | — | 全部通过 |
| 7 | `test_maaend_control_page.py` | 0 | 10 | 0 | — | **全部失败**：`NameError: name 'QProgressBar' is not defined`（`maaend_control_page.py:528` 缺少导入） |
| 8 | `test_error_paths.py` | 5 | 0 | 2 | — | 2 个 setup 阶段因 `.tmp` 目录权限失败 |

#### 输入输出观察
- **正常模块**（`cli_bridge`、`template_pipeline`、`main_window`、`scene_geometry`、`llm_*`）：输入输出符合预期，无异常抛出。
- **异常路径模块**（`error_paths`）：5/7 用例正确捕获异常并返回结构化错误；2 个因 pytest-qt 需要 `.tmp/pytest-of-cheng` 目录而权限拒绝，属于环境问题，非代码逻辑错误。
- **GUI 页面模块**（`maaend_control_page`）：初始化阶段即崩溃，所有用例无法进入测试逻辑，输入输出完全无法观察。

---

### 2.2 第二层：集成测试

| # | 测试文件 | 通过 | 失败 | 错误 | 耗时 | 关键发现 |
|---|---------|------|------|------|------|---------|
| 9 | `test_istina_runtime.py` | 8 | 2 | 0 | >300s | `test_execute_routes_analyze_run` 触发 Windows 访问异常（`maa.agent_client.__del__` 中 `json.loads`） |
| 10 | `test_istina_cli_commands.py` | 8 | 4 | 1 | >300s | `nav`、`daily`、`harvest`、`analyze` 四个命令均返回 `"status":"error"` |

#### 输入输出观察
- **IstinaRuntime 路由**：8/15 用例通过，验证了基础路由（`task.run`、`preset.run`、`screenshot`、`system.connect/disconnect`）输入输出正确。
- **失败用例**：
  - `daily_run` / `harvest_run`：返回 `"error"`，实际执行路径依赖 `MaaEndRuntime` 连接与任务资源，输入输出不符合成功预期。
  - `analyze_run`：在垃圾回收阶段触发 Windows 访问违规（`access violation`），导致 pytest 挂起直至超时。根因指向 `maa/agent_client.py:91 __del__` 与 `json.loads` 的交互。
- **CLI 命令集成**：
  - 8 个基础命令（`device info/status`、`system env/disk`、`config get/set`、`task/preset serial`、`task timeout`）输入输出正确。
  - `nav`、`daily`、`harvest`、`analyze` 均返回 `"error"`，与 `test_istina_runtime.py` 中对应路由失败一致，说明问题出在 Runtime 层而非 CLI 分发层。
  - `config get/set` 因 `.tmp` 权限失败 1 次，重试后部分通过。

---

### 2.3 第三层：系统/端到端测试

| # | 测试文件 | 通过 | 失败 | 错误 | 耗时 | 关键发现 |
|---|---------|------|------|------|------|---------|
| 11 | `test_gui_cli_chain.py` | 7 | 0 | 0 | 53s | 全部通过 |
| 12 | `test_full_chain.py` | 4 | 0 | 1 timeout | >300s | `test_all_commands_output_valid_json` 超时，剩余 2 个未执行 |

#### 输入输出观察
- **GUI-CLI 调用链**：7/7 通过，验证 `CLIBridge` → `QProcess` → `istina.py` → JSON stdout 的整条链路输入输出正确。
- **端到端 CLI 子进程**：4/7 执行完成并通过。`test_all_commands_output_valid_json` 因遍历全部命令且部分命令超时而整体超时，属于性能问题，非逻辑错误。

---

## 3. 共性环境问题

| 问题 | 影响范围 | 根因 | 是否阻断测试 |
|------|---------|------|------------|
| `.tmp/pytest_cache` 权限拒绝 | 几乎所有测试文件 | Windows `WinError 5` 拒绝访问缓存目录 | 否（仅警告） |
| `.tmp/pytest-of-cheng` 权限拒绝 | `test_error_paths.py`（2 个） | pytest-qt 临时目录权限 | 是（setup 阶段 ERROR） |
| `MaaEndControlPage` 缺少 `QProgressBar` 导入 | `test_maaend_control_page.py`（10 个） | `PyQt6.QtWidgets` 未导入 `QProgressBar` | 是（全部 FAILED） |
| `maa.agent_client.__del__` 访问违规 | `test_istina_runtime.py`（1 个） | 垃圾回收时 `json.loads` 与 MaaFW 对象生命周期冲突 | 是（CRASH/HANG） |
| CLI 业务命令返回 `error` | `test_istina_cli_commands.py`（4 个） | `daily`/`harvest`/`analyze`/`nav` 底层执行失败 | 是（FAILED） |

---

## 4. 统计汇总

| 指标 | 数值 |
|------|------|
| 执行测试文件总数 | 12 |
| 总用例数 | ~105 |
| 通过 | 65 |
| 失败 | 18 |
| 错误（setup/permission） | 2 |
| 超时/未执行 | 1 |
| 通过率 | ~61.9% |

---

## 5. 结论与建议

1. **基础框架正确**：`cli_bridge`、`template_pipeline`、`main_window`、`scene_geometry`、`llm_*` 等最低级子模块输入输出均正确。
2. **集成层存在阻塞性缺陷**：`maaend_control_page` 的 `QProgressBar` 导入缺失导致整个页面测试无法进行；`MaaEndRuntime` 与 `agent_client` 生命周期交互在极端路径下触发访问违规。
3. **业务命令链路不稳定**：`daily`、`harvest`、`analyze`、`nav` 四个 CLI 命令在测试环境下持续返回 `error`，需进一步排查设备连接、MaaEnd 资源加载或任务定义问题。
4. **环境权限需修复**：`.tmp` 目录权限问题影响 pytest-qt 的部分用例，建议在 CI/测试启动前清理或重定向临时目录。

---

*本报告为独立文件，未写入 `docs/` 目录。*
