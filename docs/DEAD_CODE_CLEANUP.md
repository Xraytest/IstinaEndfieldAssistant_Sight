# 死代码与孤立代码清理记录

**清理日期**：2026-07-07  
**清理范围**：`src/`（排除 `MaaEnd/` 及发行版目录）  
**执行方式**：删除孤立文件与未调用方法，未修改模块化架构，未新增测试代码

---

## 已删除文件

| 文件路径 | 删除原因 |
|---|---|
| `src/core/foundation/utils.py` | 全项目无引用。`safe_parse_json()`、`safe_call()`、`log_exception()` 在 `src/`、`scripts/`、`tests/` 范围内均未被调用。 |
| `src/core/foundation/constants.py` | 全项目无引用。`DEFAULT_DEVICE_ADDRESS`、`DEFAULT_ADB_PATH` 未使用，硬编码字符串直接出现在业务代码中。 |
| `src/core/capability/adb_utils.py` | 便捷导入模块，无任何模块引用。`ADBDeviceManager as ADB` 与 `TouchManager` 的便捷别名未使用。 |
| `src/core/capability/input/screenshot/screen_capture.py` | `ScreenCapture` 类完全未被实例化或导入。实际截图通过 `ADBDeviceManager.screencap()` 完成。 |

## 已删除方法

| 文件 | 删除方法 | 删除原因 |
|---|---|---|
| `src/core/capability/element_recognition/element_info.py` | `PageInfo.get_elements_by_type()` | 全项目无调用 |
| `src/core/capability/element_recognition/element_info.py` | `PageInfo.get_elements_by_source()` | 全项目无调用 |
| `src/core/capability/element_recognition/element_info.py` | `PageInfo.find_element()` | 全项目无调用 |
| `src/gui/pyqt6/pages/prts_full_intelligence_page.py` | `set_analysis_mode()` | 全项目无调用 |

## 验证方式

- 对上述所有符号做全项目 `grep`，`src/`、`scripts/`、`tests/` 范围内均无引用。
- `cli/handlers.py` 中 `base64`、`os`、`platform`、`shutil`、`datetime`、`Path` 等导入均有实际调用，**未删除**。
- `TaskLoader`/`TaskRunner` 被 `scripts/verify_ocr_integration.py` 和 `tests/test_template_pipeline.py` 引用，**未删除**。

## 架构保持现状

- `cli/handlers` → `core/service/runtime` → `core/foundation` + `core/capability` 三层架构保持不变。
- 未对 `Navigator` 子模块、识别后端注入等架构问题做修改。
- 未新增任何测试代码。
