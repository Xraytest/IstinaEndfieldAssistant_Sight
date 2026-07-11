# 审计批次 89 — REC-02 特征提取异常静默 / REC-03 目录加载异常静默 + 审计批次 88

**生成时间**: 2026-07-12 10:15
**覆盖文件**: `recognizer.py`, `device_settings_page.py`, `handlers.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 新增发现（2 项）

### REC-02 — `_extract_features` 异常静默返回空特征字典

**等级**: 代码质量 / 低
**位置**: `recognizer.py:407-432`

**问题代码**:

```python
# recognizer.py:407-432
def _extract_features(self, screen: np.ndarray) -> Dict[str, Any]:
    """Extract screen features for downstream classification."""
    try:
        h, w = screen.shape[:2]
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        left_bar = gray[:, max(0, w // 20):w // 6]
        left_bar_brightness = float(np.mean(left_bar)) if left_bar.size > 0 else 0
        green_lower = np.array([35, 50, 50])
        green_upper = np.array([85, 255, 255])
        green_mask = cv2.inRange(hsv, green_lower, green_upper)
        top_right_green = green_mask[0:h // 5, max(0, w * 3 // 4):w]
        green_pixels_top_right = int(cv2.countNonZero(top_right_green))
        return {
            "left_bar_brightness": round(left_bar_brightness, 1),
            "green_pixels_top_right": green_pixels_top_right,
            "full_brightness": round(float(np.mean(gray)), 1),
            "resolution": [w, h],
        }
    except Exception:
        return {}
```

**根因分析**:

`_extract_features` 用裸 `except Exception` 捕获所有异常（包括 `cv2.error`、内存不足、无效输入），返回空字典 `{}`。调用方 `_score_page` 收到空特征后无法计算颜色/亮度特征，仅依赖模板/OCR 匹配得分。页面分类准确率下降但无任何警告日志。

**调用链**:

```
recognize(screen)
  └── _classify_page(screen, elements)
        └── _extract_features(screen)  ← 静默失败返回 {}
              └── _score_page 缺少特征数据 → 分类置信度下降
```

**影响面**:
- **低**：正常游戏画面不会触发异常。仅在 frame 内存损坏、OpenCV 版本异常等边缘场景下静默降级，页面分类准确率下降。

**修复建议**:

```python
def _extract_features(self, screen: np.ndarray) -> Dict[str, Any]:
    try:
        ...
    except Exception as exc:
        self._logger.warning("特征提取失败", error=str(exc))
        return {}
```

---

### REC-03 — `_load_catalog` 异常静默且日志级别过低

**等级**: 代码质量 / 低
**位置**: `recognizer.py:453-469`

**问题代码**:

```python
# recognizer.py:453-469
def _load_catalog(self, catalog_path: str) -> None:
    """Load element catalog from JSON."""
    if not catalog_path:
        return
    try:
        path = Path(catalog_path)
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._catalog = data.get("elements", {})
        self._page_signatures = data.get("page_signatures", {})
        logger.info(f"Element catalog loaded: {len(self._catalog)} elements, "
                   f"{len(self._page_signatures)} page signatures")
    except Exception as e:
        logger.debug(f"Catalog load failed: {e}")
```

**根因分析**:

`_load_catalog` 用裸 `except Exception` 捕获所有异常，仅以 `logger.debug` 级别记录。这意味着：
- 文件不存在 → 静默返回（可接受，无日志噪音）
- JSON 语法错误 → 仅 debug 日志，用户无感知
- 权限错误 → 仅 debug 日志，用户无感知

当 catalog 加载失败后，`self._catalog` 和 `self._page_signatures` 保持空字典（默认值）。后续 `recognize()` 调用时所有模板/OCR/YOLO 匹配均无法找到目标元素，页面分类始终返回 "unknown"。

**与 SET-01 的关系**: SET-01 覆盖 `settings_page.py:221-228` `_read_config` 仅捕获 `JSONDecodeError`。REC-03 覆盖 `recognizer.py:453-469` `_load_catalog` 捕获所有 Exception 但日志级别过低。两者不同。

**影响面**:
- **低**：catalog 文件通常随项目分发，不存在路径/权限问题。仅在文件损坏或手动编辑出错时触发。

**修复建议**:

```python
def _load_catalog(self, catalog_path: str) -> None:
    if not catalog_path:
        return
    try:
        ...
    except FileNotFoundError:
        logger.info(f"Catalog file not found: {catalog_path}")
    except json.JSONDecodeError as exc:
        logger.error(f"Catalog JSON parse failed: {catalog_path} — {exc}")
    except Exception as exc:
        logger.error(f"Catalog load failed: {catalog_path} — {exc}")
```

---

## 审计结论（批次 88）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 88 | DEVICE-04 (`_on_command_error` 不重置 `_connected`) | **结论正确**。`device_settings_page.py:217-223` 处理 `commandError` 信号时恢复按钮状态但不重置 `self._connected`。若 connect 命令异常（daemon 未运行等），`_connected` 仍为 True 导致预览/重连逻辑错误。 |
| 批次 88 | CLI-04 (`_handle_device_info/monitor` 误导性 "success") | **结论正确**。`handlers.py:400-406` 和 `handlers.py:486-496` 均无 `default_client is None` 检查，daemon 未运行/无设备时返回 "success" 空结果，用户无法区分连接问题。 |

**批次 88 全部 2 项新发现经本批次逐项源码复核确认准确，无需修正。**

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| 代码质量（低） | 2 | REC-02 (_extract_features 异常静默), REC-03 (_load_catalog 异常静默且日志级别过低) |
| 高风险 | 0 | — |
| 中风险 | 0 | — |

**本轮无中高风险发现。**

---

*批次 89 报告 | 仅分析，无文件修改*
