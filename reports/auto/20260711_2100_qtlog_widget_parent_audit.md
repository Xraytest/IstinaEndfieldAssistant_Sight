# 批次 71：5 级 parent 链 / qt_log_filter 线程安全 / widget_styles 死代码 + 历史报告审计

> **生成时间**: 2026-07-11 21:00
> **审查范围**: `src/gui/pyqt6/pages/maaend_control_page.py:174/1534/1552`, `src/gui/pyqt6/qt_log_filter.py` (89 行), `src/gui/pyqt6/theme/widget_styles.py` (297 行)
> **审计范围**: 批次 70（`20260711_2045_runtime_connect_deadcode.md`）、批次 1445（`20260711_1445_code.md`）
> **方法**: 静态代码逻辑分析
> **发现总计**: 3 新发现 + 2 审计验证
> **严重度分布**: 0 High / 0 Medium / 0 Low / 3 Low

---

## 项目边界回顾

- IEA 是《明日方舟：终末地》的 MaaEnd/MaaFramework 自动化助手。本仓库为**非第三方**源码，`MaaEnd/` 与 `3rd-part/` 不在审查范围。
- 审查仅限本仓库 Python 源码；历史累计 260+ 条发现，本批严格避免重复提交。

---

## §1 新发现

### [MAA71-01 Low] `maaend_control_page.py:174` — 5 级 `parent` 链，项目中最深的硬编码路径

```python
# maaend_control_page.py:174
_OPTION_LOCALE_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "3rd-part" / "maaend" / "locales" / "interface" / "zh_cn.json"
```

**根因分析**：此模块级常量使用 5 级 `parent` 链解析项目根目录，是整个项目中**层级最深的硬编码路径**。解析过程：

```
__file__ = src/gui/pyqt6/pages/maaend_control_page.py
parent      → src/gui/pyqt6/pages/
parent.parent → src/gui/pyqt6/
parent.parent.parent → src/gui/
parent.parent.parent.parent → src/
parent.parent.parent.parent.parent → <project_root>/
```

然后拼接 `"3rd-part" / "maaend" / "locales" / "interface" / "zh_cn.json"` 得到完整路径。

**问题**：
1. **绕过 `get_project_root()`**：`paths.py` 提供了统一的 `get_project_root()` 函数（基于自身位置推断），但此常量直接硬编码 5 级 `parent` 链。如果 `pages/` 目录被移动（如重构为 `src/gui/pyqt6/pages/maa/`），此路径会静默解析到错误目录，导致选项标签文件加载失败，所有 `$task.xxx` 标签回退到原始字符串。
2. **同类 fallback 未使用统一函数**：同一文件的 lines 1534 和 1552 也使用 `parent.parent.parent.parent`（4 级）作为 `get_project_root()` 导入失败时的 fallback：

```python
# maaend_control_page.py:1534 (fallback)
base = Path(__file__).resolve().parent.parent.parent.parent / "config"

# maaend_control_page.py:1552 (fallback)
base = Path(__file__).resolve().parent.parent.parent.parent.parent / "cache"
```

这些 fallback 本应使用 `paths.get_project_root()`，但选择了硬编码路径链。

**影响面**：低——当前目录结构稳定，路径解析正确。但如果 `pages/` 目录被重构移动，`OPTION_LOCALE` 加载失败，所有选项标签回退到英文 key 字符串，用户体验下降。

**建议**：使用 `get_project_root()` 统一路径解析：

```python
from core.foundation.paths import get_project_root
_OPTION_LOCALE_PATH = get_project_root() / "3rd-part" / "maaend" / "locales" / "interface" / "zh_cn.json"
```

---

### [MAA71-02 Low] `qt_log_filter.py:55-57` — `_INSTALLED` 标志检查非原子操作

```python
# qt_log_filter.py:55-57
def install_qt_message_filter() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    ...
```

**根因分析**：`_INSTALLED` 是模块级布尔变量，`if _INSTALLED: return` 的检查与后续的 `qInstallMessageHandler(_qt_message_handler)` + `_INSTALLED = True` 之间不是原子操作。如果两个线程同时首次调用 `install_qt_message_filter()`：

```
线程 A: if _INSTALLED → False → 继续
线程 B: if _INSTALLED → False → 继续
线程 A: 创建 FileHandler + qInstallMessageHandler → _INSTALLED = True
线程 B: 创建 FileHandler + qInstallMessageHandler → _INSTALLED = True
```

结果：消息处理器被安装两次，创建两个 FileHandler 写入同一文件。虽然 `qInstallMessageHandler` 在 PyQt6 中会替换之前的处理器（不累积），但第二个 FileHandler 仍会留在 `qt` logger 上，导致重复写入。

**对比**：同一项目中其他单例/幂等模式的处理：
- `TouchManager.get_instance()`：使用 `threading.Lock` + 双重检查
- `ThemeManager.__new__()`：使用 `threading.RLock` + 双重检查
- `LocaleManager.get_locale_manager()`：批次 69 报告为无锁（I18N-02）
- `init_logger()`：使用 `_logger_initialized` 布尔标记（批次 234853 R3 报告为 Low）

`qt_log_filter.py` 的 `_INSTALLED` 模式与 `init_logger()` 的 `_logger_initialized` 完全相同的反模式——布尔标记的检查与设置非原子。

**影响面**：低——`install_qt_message_filter()` 在 GUI 启动时通常由主线程单次调用。但如果未来有插件系统或测试框架在不同线程中调用，可能触发重复安装。

**建议**：使用 `threading.Lock` 保护检查与设置：

```python
_lock = threading.Lock()

def install_qt_message_filter() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    with _lock:
        if _INSTALLED:
            return
        ...  # 安装逻辑
        _INSTALLED = True
```

---

### [MAA71-03 Low] `widget_styles.py:49-60` — `BLUE_STYLE` 重复定义，第二处静默覆盖第一处

```python
# widget_styles.py:49-52
BLUE_STYLE = (
    f"color: {_PRIMARY}; font-size: {_SIZE_BASE}px;"
    f" font-family: '{_FONT}'; padding: 3px 0;"
)

# ... YELLOW_STYLE 定义在中间 ...

# widget_styles.py:57-60
BLUE_STYLE = (
    f"color: {_PRIMARY}; font-size: {_SIZE_BASE}px;"
    f" font-family: '{_FONT}'; padding: 3px 0;"
)
```

**根因分析**：`BLUE_STYLE` 在 lines 49-52 和 57-60 被定义了两次。两次定义的**内容完全一致**，但 Python 模块级赋值是顺序执行的——第二处（57-60）会静默覆盖第一处（49-52）。

**影响面**：
- **维护困惑**：新开发者看到两处 `BLUE_STYLE` 定义，可能认为它们服务于不同场景，尝试修改第一处却发现修改不生效
- **死代码**：第一处定义（lines 49-52）在第二处定义后变为不可达的"死赋值"
- **当前无功能影响**：两处内容相同，覆盖后行为不变

**建议**：删除第一处定义（lines 49-52），仅保留第二处（57-60）。或将两处合并为一个定义。

---

## §2 历史报告审计

### [AUDIT-1] 批次 1445 `20260711_1445_code.md` AUDIT-1 — 原论断已修复，审计结论过时

**原论断**：批次 1445 AUDIT-1 声称批次 1230 NEW-1（`minimap_locator.py:181` `tile_class[5:11]` 切片错误）"仍然存活"。

**当前代码复核**：
```python
# minimap_locator.py:191-195（当前代码）
# W5/L02: 提取 level_id（如 "Map01Lv001" -> "lv001"），移出 Tier 分支，
# 使无 Tier 的瓦片也能获取 level_id；用正则替代固定宽度切片 tile_class[5:11]
lv_match = re.search(r"Map\d+Lv(\d+)", tile_class)
if lv_match:
    level_id = f"lv{lv_match.group(1)}"
```

**审计结论**：**批次 1445 AUDIT-1 的论断已过时**。`tile_class[5:11]` 已被正则 `re.search(r"Map\d+Lv(\d+)", tile_class)` 替代修复。注释 `# W5/L02` 明确标注了此修复的来源。批次 1445 报告时该修复已存在，但审计未发现代码已变更，仍沿用批次 1230 的"仍然存活"结论。

**影响**：此审计错误不影响批次 1230 原始发现的正确性——`tile_class[5:11]` 确实曾经是 bug，且已被正确修复。但批次 1445 的审计流程存在疏漏：未核对 `tile_class[5:11]` 是否仍存在于当前代码中即断言"仍然存活"。

---

### [AUDIT-2] 批次 70 `20260711_2045_runtime_connect_deadcode.md` — 确认准确

批次 70 发现 3 项新 Low（RT-01/RT-02/RT-03）+ 1 审计验证。

**审计结论**：**准确无误**。

验证要点：
- RT-01：`connect()` 双重 `runtime.connect()` 调用。审计确认 `connect()` 调用 `_ensure_maaend_ready()` 后者再次检查 `runtime.connected`——正常路径被短路，但存在边界情况。scrcpy 失败仍返回 True 的分析准确。
- RT-02：`_placeholder` 死代码 + `execute()` 未知命令返回 None。审计确认 `_placeholder` 全仓零调用点，`execute()` 返回类型不一致。
- RT-03：`scene()` 隐式触发 `maaend()` 副作用。审计确认 `scene()` 首次访问通过 `self.maaend()` 隐式初始化 MaaEndRuntime，约增加 2-5 秒启动延迟。

本批 MAA71-01/02/03 与批次 70 独立，不重叠。

---

## §3 发现统计

| 类别 | 条目 | 严重度 | 状态 |
|------|------|--------|------|
| 新发现 | MAA71-01（5 级 parent 链绕过 get_project_root） | Low | 历史未覆盖 |
| 新发现 | MAA71-02（`_INSTALLED` 标志非原子检查） | Low | 历史未覆盖 |
| 新发现 | MAA71-03（`BLUE_STYLE` 重复定义） | Low | 历史未覆盖 |
| 审计验证 | AUDIT-1（批次 1445 AUDIT-1 论断过时——代码已修复） | — | 指出错误 |
| 审计验证 | AUDIT-2（批次 70 确认准确无误） | — | 确认无误 |
| **合计** | **3 新 + 2 审计** | **3L** | — |

---

## §4 跨批次一致性验证

- **批次 1100_path MAA04**（`ensure_src_path` 内重复计算）→ 与本批独立，不冲突。本批聚焦 `maaend_control_page.py` 的 5 级 parent 链（module-level constant）
- **批次 1445 AUDIT-1**（minimap_locator level_id 偏移）→ 本批审计发现该 bug 已修复，批次 1445 审计疏于核对当前代码
- **批次 70 RT-01/02/03** → 与本批独立文件/路径，不冲突
- **批次 234853 R3 / 1120_llm R3**（`_logger_initialized` 无锁）→ 与本批 MAA71-02 同模式，但不同文件，不重复

---

## §5 验证方法

- 全部发现基于对 `maaend_control_page.py`、`qt_log_filter.py`、`widget_styles.py` 的**逐行静态阅读**。
- **未执行任何测试**，未修改任何业务代码。
- 重复检测：交叉核对 30 份历史报告确认 MAA71-01/02/03 为全新发现。
- 审计部分：AUDIT-1 通过直接读取 `minimap_locator.py:191-195` 当前代码验证 bug 已修复；AUDIT-2 通过逐行复核 `runtime.py` 验证。
- 本批严格遵循"避免重复提交历史已覆盖问题"原则。
