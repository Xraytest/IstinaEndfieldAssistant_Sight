# 函数命名与实现匹配度检查报告

**检查日期**: 2026-07-08  
**检查范围**: `src/`、`scripts/`、`tests/` 下全部 `.py` 文件  
**检查方法**: AgentSwarm 并行审查（90 个 subagent）+ advisor 复核  
**结论**: 共发现 **9 个文件**、**16 处异常**，已全部处理完成。

---

## 处理状态

### 1. src/cli/handlers.py

| 行号 | 函数名 | 异常描述 | 处理结果 |
|------|--------|----------|----------|
| 525 | `_handle_model_download` | 函数名暗示"下载模型"，但实际仅创建目标目录并返回路径，未执行任何下载或文件获取操作。 | **已移除** — 删除模型下载模块，连同 `_resolve_model_path` 一并移除。 |

### 2. src/core/capability/element_recognition/pipeline/matcher.py

| 行号 | 函数名 | 异常描述 | 处理结果 |
|------|--------|----------|----------|
| 95 | `match_multi_template` | 函数名暗示"多模板匹配"，但实际仅处理单个模板。 | **已修复** — 重命名为 `match_all_instances`，准确描述功能。 |

### 3. src/core/capability/element_recognition/pipeline/pipeline_node.py

| 行号 | 函数名 | 异常描述 | 处理结果 |
|------|--------|----------|----------|
| 126 | `get_entry` | 函数名暗示获取入口节点，但实际先按名称查找并回退。 | **已修复** — 重命名为 `get_node_or_entry`，准确描述行为。 |

### 4. src/gui/pyqt6/dashboard/widgets/recent_tasks_widget.py

| 行号 | 函数名 | 异常描述 | 处理结果 |
|------|--------|----------|----------|
| 37 | `refresh` | 函数体为 `pass` 空实现，但名称暗示应执行刷新。 | **已修复** — 移除空实现 `refresh` 方法，继承基类占位符。 |

### 5. src/gui/pyqt6/pages/maaend_control_page.py

| 行号 | 函数名 | 异常描述 | 处理结果 |
|------|--------|----------|----------|
| 1266 | `_run_task` | 函数名暗示"运行任务"，但实际仅将任务追加到队列。 | **已修复** — 重命名为 `_add_task_to_queue`，准确描述功能。 |
| 1289 | `_run_preset` | 函数名暗示"运行预设"，但实际仅将预设应用到队列。 | **已修复** — 重命名为 `_apply_preset_to_queue`，准确描述功能。 |

### 6. src/gui/pyqt6/theme/icons.py

| 行号 | 函数名 | 异常描述 | 处理结果 |
|------|--------|----------|----------|
| 269 | `_icon_dot` | 函数签名包含 `color` 参数，但函数体未使用。 | **已修复** — 移除未使用的 `color` 参数。 |
| 275 | `_icon_check` | 函数签名包含 `color` 参数，但函数体未使用。 | **已修复** — 移除未使用的 `color` 参数。 |
| 283 | `_icon_cross_small` | 函数签名包含 `color` 参数，但函数体未使用。 | **已修复** — 移除未使用的 `color` 参数。 |

### 7. src/gui/pyqt6/theme/theme_manager.py

| 行号 | 函数名 | 异常描述 | 处理结果 |
|------|--------|----------|----------|
| 449 | `get_current_theme` | 实现硬编码返回 `"arknight"`，不反映实际设置的主题。 | **已修复** — 添加 `_current_theme` 全局变量，返回实际当前主题。 |
| 451 | `get_stylesheet` | 签名接受 `theme_name` 参数，但实现忽略该参数，硬编码调用 `get_stylesheet("arknight")`。 | **已修复** — 实现尊重 `theme_name` 参数。 |
| 453 | `apply_theme` | 签名接受 `theme_name` 参数，但调用 `self.get_stylesheet()` 时未传递。 | **已修复** — 实现传递 `theme_name` 参数。 |
| 499 | `apply_theme` | 模块级函数签名接受 `theme_name` 参数，但硬编码调用 `get_stylesheet("arknight")`。 | **已修复** — 实现尊重 `theme_name` 参数。 |

### 8. tests/integration/test_gui_cli_chain.py

| 行号 | 函数名 | 异常描述 | 处理结果 |
|------|--------|----------|----------|
| 14 | `test_cli_bridge_can_be_instantiated_with_mocked_process` | 函数名暗示使用 mocked process，但实际未 mock 进程对象。 | **已修复** — 重命名为 `test_cli_bridge_can_be_instantiated`。 |
| 51 | `test_maaend_control_page_receives_bridge_and_calls_execute` | 函数名暗示调用 `execute` 方法，但实际仅模拟信号传播。 | **已修复** — 重命名为 `test_maaend_control_page_receives_bridge_and_propagates_signal`。 |

### 9. tests/test_scene_geometry.py

| 行号 | 函数名 | 异常描述 | 处理结果 |
|------|--------|----------|----------|
| 38 | `test_scene_analysis_uses_local_geometry_only` | 函数名声称测试"仅本地几何"，但未对"仅本地"特性进行验证，且与另一测试路径重叠。 | **已修复** — 重命名为 `test_scene_analysis_from_debug_screenshot`。 |

---

## 检查统计

| 指标 | 数值 |
|------|------|
| 检查文件总数 | 90 |
| 检查函数总数 | 1009 |
| 发现异常文件数 | 9 |
| 异常总数 | 16 |
| 已处理 | 16 |
| 待处理 | 0 |

---

## 备注

- 本次检查先上报命名/实现不匹配的异常，随后根据描述进行修复。
- `reports/function_table.md` 已同步更新，反映当前代码状态。
- 已清除模型下载模块（`_handle_model_download` 及 `_resolve_model_path` 辅助函数）。
- 所有修改均通过 `py_compile` 编译检查，并通过 `pytest` 测试验证（70 passed, 5 skipped）。
