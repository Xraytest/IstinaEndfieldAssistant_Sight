# 2026-07-13 选择性选项与数值选项无法保存

## 根因分析

`_build_option_editor` 在渲染选项控件期间，`_render_option_row` 末尾调用 `_refresh_sub_options(name)`，后者在结束时调用 `_save_options()`。

此时 `_focused_queue_index` 已指向新切换的队列行，`_save_options` 会执行 `update_queue_item_options(row, options)`，将**默认值**写入队列实例的 options 字段——覆盖了用户之前保存的选项值。

随后 `_apply_saved_option_values` 从同一队列实例读取 options 进行恢复，但读到的已是默认值，恢复无效。

**影响范围**：所有选项类型均受影响，但选择性选项（select）和数值选项（input）最明显：
- select 默认值是第一项，通常与用户选择不同
- input 默认值是空字符串，任何已输入的数值都会丢失
- switch 默认通常是 "No"（关闭态），与用户设置 "Yes" 不同时也会丢失
- checkbox 默认全不选，影响同理

## 修改方案

1. 新增 `_is_building_editor` 标志（`__init__` 中初始化为 False）
2. `_build_option_editor` 在渲染前设 `_is_building_editor = True`，在 `finally` 块中设回 False
3. `_save_options` 开头检查 `_is_building_editor`，为 True 时直接返回，跳过保存
4. `_build_option_editor` 渲染+恢复完成后（`finally` 之后），调用一次 `_save_options()` 保存恢复后的值

这样渲染期间的多次 `_save_options` 调用被全部跳过，队列实例的 options 保持原始保存值不变，`_apply_saved_option_values` 能正确读取并恢复。

## 影响面

- **正面影响**：切换队列条目时选项不再被重置为默认值；所有选项类型（switch/select/checkbox/input）均能正确保存和恢复
- **无负面影响**：渲染完成后的单次 `_save_options` 确保队列实例 options 与 UI 一致
- `_on_queue_focus_changed` 的 flush 逻辑不受影响（它直接调用 `_collect_options` 而非 `_save_options`）
- `refresh()` 中的 `QTimer.singleShot(0, _build_option_editor)` 不受影响（延迟调用时 `_is_building_editor` 已为 False）

## 非期待变化

无。`_save_options` 在用户交互时（非渲染期间）行为不变，每次值变更仍立即保存。
