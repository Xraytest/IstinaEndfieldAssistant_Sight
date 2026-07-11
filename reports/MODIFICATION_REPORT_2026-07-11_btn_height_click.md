# 修改报告 — 执行/停止按钮高度不统一且无法点击

日期：2026-07-11
文件：src/gui/pyqt6/pages/maaend_control_page.py

## 一、根因分析

### 现象1：执行按钮无法被点击
- `_retry_btn`（底部「执行」按钮）在创建时调用 `setEnabled(False)`（原 L641）。
- `_update_execution_ui()` 方法负责按 `self._is_executing` 刷新按钮启用状态（`_retry_btn.setEnabled(not self._is_executing)`）。
- 但该方法**仅在** `_start_execution`（L1834）与 `_on_execution_finished`（L1851）两处被调用，`__init__` 从不调用。
- 因此页面初始化后 `_retry_btn` 永远保持 `setEnabled(False)`，初始 `_is_executing=False` 本应让按钮启用，却因缺少初始化刷新而一直禁用 → 无法点击。
- 同理 `_stop_btn` 也保持 disabled，但停止按钮在未执行时禁用是正确行为，不受此 bug 影响。

### 现象2：执行按钮与停止按钮高度不统一
- `_stop_btn` 使用 `BTN_STOP` 样式，`_retry_btn` 使用 `BTN_DEFAULT` 样式。
- 二者 QSS 高度规则一致（均 `min-height: 24px` + `padding: 3px 10px` + `border: 2px`），但 QSS `min-height` 在 QPushButton 上的实际渲染受字体/内容/平台影响，未显式固定时两个按钮可能因状态差异（disabled 灰度渲染）产生视觉高度不一致。

## 二、修改方案

1. **修复无法点击**：在 `__init__` 末尾（所有信号连接之后）追加 `self._update_execution_ui()`，使页面初始化即按当前 `_is_executing=False` 刷新按钮状态 → 执行按钮启用、停止按钮禁用。
2. **修复高度不统一**：给 `_stop_btn` 与 `_retry_btn` 各加 `setFixedHeight(36)`，强制固定高度，消除 QSS 渲染差异，确保两按钮绝对等高。36px 兼顾点击便利性与视觉协调。

## 三、影响面

- **直接影响**：底部「停止」「执行」两个按钮。
  - 执行按钮：初始化后立即可点击；高度固定 36px。
  - 停止按钮：高度固定 36px；启用逻辑不变（仍由 `_is_executing` 控制）。
- `_update_execution_ui()` 在 `__init__` 调用时，依赖的所有按钮（`_apply_preset_to_queue_btn`/`_run_queue_btn`/`_add_queue_btn`/`_queue_up_btn`/`_queue_down_btn`/`_queue_clear_btn`/`_stop_btn`/`_retry_btn`/`_progress_bar`/`_status_label`）均已在 `_setup_ui()`（L325）中创建完成，调用安全。
- `_status_label` 会被设置为 idle 文案与 BLUE_STYLE，与预期一致。
- `execution_state_changed` 信号会在初始化时 emit 一次 `False`，监听方需能幂等处理（现有监听均为状态同步，无副作用）。
- 不影响执行流程（`_start_execution`/`_on_execution_finished` 仍正常调用 `_update_execution_ui`）。

## 四、非期待变化

- 底部按钮高度从 QSS `min-height: 24px`（实际约 24-30px 浮动）变为固定 36px，视觉上会比之前略高且更统一。若与队列区按钮（`_run_queue_btn` 等，仍用 QSS 24px）产生新的高度差，属预期外但用户未要求的视觉不一致——如需统一可后续给所有按钮统一 `setFixedHeight`。
- `execution_state_changed` 信号在 `__init__` 额外 emit 一次，若未来有监听方在该信号上做非幂等操作（如计数），需注意。当前无此监听。

## 五、方法改进（同日）

- **问题**：上述方案用 `setFixedHeight(36)` 固定高度。但 Qt 中 `setFixedHeight` 设置的 `maximumHeight` 会与 QSS 的 `min-height: 24px`（经 padding/border 放大后实际 widget 最小高度可能 > 36）冲突，导致 `max < min` 矛盾，按钮实际高度由 QSS 强制值决定且可能两按钮渲染不等高。
- **改进**：移除 `setFixedHeight(36)`，改用 QSS 层面统一高度——给两个按钮的 `setStyleSheet` 追加 `QPushButton { min-height: 36px; max-height: 36px; }`。QSS 后定义覆盖原 `min-height: 24px`，且 `max-height` 同时锁定上限，两按钮在 QSS 盒模型内绝对等高，不再与 widget 级 `setFixedHeight` 冲突。
- **影响**：仅底部 `_stop_btn` 与 `_retry_btn`，其他按钮不受影响。

## 六、方法改进二（同日，最终方案）

- **问题**：方法改进一用纯 QSS `min-height/max-height: 36px`，但 Qt QSS 对 QPushButton 的 `max-height` 支持不可靠（常被忽略），`min-height` 只保证下限不锁定上限，widget 仍可能被内容撑高，两按钮渲染仍有偏差。
- **改进**：组合用法——QSS 追加 `QPushButton { min-height: 0px; }` 把原 `min-height: 24px` 覆盖为 0（消除 QSS 强制最小高度与 setFixedHeight 的冲突），再用 `setFixedHeight(36)` 在 widget 级别锁定 `minimumHeight=maximumHeight=36`。QSS 不再强制更高，fixedHeight 完全生效，两按钮绝对等高 36px。
- **要点**：单独 `setFixedHeight` 会与 QSS `min-height` 冲突（max<min 矛盾）；单独 QSS `max-height` 对 QPushButton 不可靠。两者组合（QSS 让步 + widget 锁定）是可靠方案。
