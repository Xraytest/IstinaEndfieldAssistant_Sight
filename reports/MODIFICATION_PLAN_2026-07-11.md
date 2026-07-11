# 修改方案（基于自动代码分析报告对照）

> **生成时间**：2026-07-11
> **依据**：`reports/auto/` 75 份自动审查报告 + 对当前 `main` 分支的**代码级复验**
> **目标**：列出**仍未落实**的发现，给出逐项可执行的修改方案（文件:行、当前问题、修改要点、估算工作量）。
> **范围**：仅覆盖复验后判定为"开放项"的内容；已修复项见 `AUTO_ANALYSIS_SUMMARY_2026-07-11.md` §2.1。

---

## 0. 复验结论：已修复 vs 仍开放

**本轮复验新增确认"已修复"的子项**（报告曾标记、代码已落实，佐证实现工作持续推进）：

| 报告编号 | 当前代码证据 |
|---|---|
| CFG-10 | `llm/runtime.py:257` 注释"防止路径遍历逃逸（CFG-10）"，绝对路径越界退化为文件名 |
| REC-7  | `template_registry.py:23-27` `_lock = threading.Lock()` + 双重检查锁 |
| LLM-06 | `llm/runtime.py:44` `_owned_pids_lock`；add/discard 均加锁 |
| LLM-08 | `llm/runtime.py:56` `list(_instances.values())` 快照遍历，无并发风险 |
| PN-3   | `pipeline_node.py:119,136-139` `_lock` + `merge` 加锁 |
| H-13/C7 部分 | `maa_end/runtime.py:237/243/248/256` 失败路径均调 `_cleanup_partial` |

**仍开放项（本方案主体）共 14 项**，按优先级分 3 层。

---

## 第一层：安全加固（P1，Medium，资源耗尽/路径遍历）

### M1 — SEC-02 交互式 CLI 输入无长度上限（内存耗尽）
- **位置**：`src/cli/istina.py:343`（`buffer += chunk` 前）
- **问题**：`--interactive` 模式下 `buffer` 无上限，恶意/故障 stdin 可灌爆内存。
- **修改**：
  ```python
  # 模块顶部或函数内
  MAX_INPUT_LENGTH = 1 * 1024 * 1024  # 1MB
  ...
  if len(buffer) >= MAX_INPUT_LENGTH:
      self_logger.error("CLI 交互循环: 输入超过最大长度", length=len(buffer))
      _write_result({"status": "error", "message": f"input exceeds {MAX_INPUT_LENGTH} bytes"})
      buffer = ""
      continue
  buffer += chunk
  ```
- **工作量**：~2 行。

### M2 — SEC-03 CLIBridge stdout 缓冲区无上限（GUI 内存耗尽）
- **位置**：`src/gui/pyqt6/cli_bridge.py:166`（`self._stdout_buffer += data` 处）
- **问题**：子进程输出大量无换行数据时 `_stdout_buffer` 无限增长。
- **修改**：
  ```python
  MAX_STDOUT_BUFFER = 4 * 1024 * 1024  # 4MB
  self._stdout_buffer += data
  if len(self._stdout_buffer) > MAX_STDOUT_BUFFER:
      self._logger.error(LogCategory.GUI, "CLI stdout 缓冲区超上限，已清空", size=len(self._stdout_buffer))
      self._stdout_buffer = ""
      self.commandError.emit(" ".join(self._last_command), "CLI output exceeded buffer limit")
      continue
  ```
- **工作量**：~4 行。

### M3 — SEC-01 `--out` 路径遍历（任意位置写入）
- **位置**：`src/cli/handlers.py:34-37`（`_write_or_base64` 中 `out = Path(out_path)`）
- **问题**：`--out` 接受任意绝对/相对路径，可写到项目目录外。
- **修改**：在解析后立即约束在项目根内（或专用 `outputs/` 目录）：
  ```python
  out = Path(out_path).expanduser()
  root = get_project_root().resolve()
  resolved = out.resolve()
  if root not in resolved.parents and resolved != root:
      return {"status": "error", "message": f"--out 路径越界，禁止写入项目外: {out_path}"}
  out.parent.mkdir(parents=True, exist_ok=True)
  out.write_bytes(data)
  ```
- **工作量**：~5 行。

### M4 — CFG-09 `--config` 路径越界
- **位置**：`src/core/service/runtime.py:468-471`（`_resolve_config_path` 直接返回 `self._config_path`）
- **问题**：`--config` 指定项目外路径也会被加载。
- **修改**：
  ```python
  def _resolve_config_path(self) -> Path:
      if self._config_path is not None:
          p = Path(self._config_path).expanduser().resolve()
          root = get_project_root().resolve()
          if root not in p.parents and p != root:
              self._logger.warning(LogCategory.MAIN, "config 路径越界，回退默认", path=str(p))
              return root / "config" / "client_config.json"
          return p
      return get_project_root() / "config" / "client_config.json"
  ```
- **工作量**：~6 行。

---

## 第二层：输入边界 & 配置校验（P2，Medium/Low）

### M5 — SEC-04 tap/swipe 坐标无范围检查
- **位置**：`src/cli/handlers.py:419`（`tap`）、`428-433`（`swipe`）
- **问题**：`int()` 后无范围约束，超大值导致触摸注入异常。
- **修改**：新增校验 helper，taps/swipe 调用前检查：
  ```python
  def _check_coord(v: Any, name: str) -> Optional[Dict[str, Any]]:
      try:
          iv = int(v)
      except (TypeError, ValueError):
          return {"status": "error", "message": f"invalid {name}: {v!r}"}
      if not (0 <= iv <= 65535):
          return {"status": "error", "message": f"{name} out of range [0,65535]: {iv}"}
      return None
  ```
  在 `_handle_device_tap`/`_handle_device_swipe` 内对每个坐标先调 `_check_coord`，非 None 则直接 return。
- **工作量**：~12 行（函数 + 两处调用）。

### M6 — SEC-05 nav3 walk 坐标/地图名无校验
- **位置**：`src/cli/handlers.py:889-892`（`_handle_nav3` walk 分支）
- **问题**：`x`/`y` 为 float 无范围，`map_name` 未验证。
- **修改**：在组装 params 前校验：
  ```python
  if action == "walk":
      try:
          fx, fy = float(args.x), float(args.y)
      except (TypeError, ValueError):
          return {"status": "error", "message": "invalid nav3 walk coords"}
      if not (math.isfinite(fx) and math.isfinite(fy)) or abs(fx) > 1e6 or abs(fy) > 1e6:
          return {"status": "error", "message": "nav3 walk coords out of range"}
      if not str(getattr(args, "map_name", "")).strip():
          return {"status": "error", "message": "empty nav3 map_name"}
      return runtime.execute("nav3.walk", {...})
  ```
- **工作量**：~10 行。

### M7 — CFG-12/CFG-15 配置加载 bare-except 静默回退 `{}`
- **位置**：`src/core/service/runtime.py:458-466`（`_load_config`）
- **问题**：任何异常（JSON 错误/权限不足）都被吞，静默回退默认配置，用户无法诊断。
- **修改**：拆分异常类型并给出可定位的告警；追加最小 schema 校验：
  ```python
  def _load_config(self) -> Dict[str, Any]:
      path = self._resolve_config_path()
      if not path.exists():
          self._logger.info(LogCategory.MAIN, "配置文件不存在，使用默认值", path=str(path))
          return {}
      try:
          with open(path, "r", encoding="utf-8") as f:
              data = json.load(f)
      except json.JSONDecodeError as e:
          self._logger.error(LogCategory.MAIN, "配置 JSON 解析失败", path=str(path), error=str(e))
          return {}
      except PermissionError as e:
          self._logger.error(LogCategory.MAIN, "配置无读取权限", path=str(path), error=str(e))
          return {}
      except OSError as e:
          self._logger.error(LogCategory.MAIN, "配置读取失败", path=str(path), error=str(e))
          return {}
      if not isinstance(data, dict):
          self._logger.error(LogCategory.MAIN, "配置根不是对象", path=str(path))
          return {}
      # 最小 schema 校验：关键字段缺失给出明确告警
      llm = data.get("llm", {}) or {}
      if not str(llm.get("model_path", "")).strip():
          self._logger.warning(LogCategory.MAIN, "配置缺少 llm.model_path，LLM 将无法启动", path=str(path))
      return data
  ```
- **工作量**：~20 行。

### M8 — SEC-06 脚本回放强制 `editingFinished`（by-design，仅加注释）
- **位置**：`src/gui/pyqt6/scripting/player.py:168-169`
- **问题**：`setText` 不触发 `editingFinished`，代码显式 `emit()`，属自动化预期行为。
- **修改**：仅补注释说明这是刻意行为，不改动逻辑：
  ```python
  widget.setText(text)
  # 刻意 emit：脚本回放需要触发与真实用户编辑相同的验证/保存流程
  widget.editingFinished.emit()
  ```
- **工作量**：~1 行注释。

---

## 第三层：资源/并发健壮性（P3，Medium/Low，技术债）

### M9 — N6 `_encode_binary` fd 泄漏
- **位置**：`src/core/capability/device/android_runtime.py:564-595`（`finally` 只 `mm.close()`，未 `os.close(fd)`）
- **问题**：异常路径下 `fd` 永不关闭，文件描述符泄漏。
- **修改**：`finally` 中补 `os.close(fd)`（在 `mm.close()` 之后）：
  ```python
  finally:
      if mm is not None:
          try: mm.close()
          except Exception: pass
      if fd is not None:       # ← 新增
          try: os.close(fd)
          except Exception: pass
  ```
- **工作量**：~3 行。

### M10 — C7/N10 原生资源未显式 dispose
- **位置**：`src/core/service/maa_end/runtime.py:311-345`（`_cleanup_partial`）
- **问题**：`_tasker`/`_resource`/`_controller` 仅置 None，未释放 MaaFW 原生资源，长期运行累积泄漏。
- **修改**：在置 None 前尝试显式释放（依赖 MaaFW 暴露的销毁接口，需先确认 API）：
  ```python
  try:
      if self._tasker is not None:
          try: self._tasker.destroy() if hasattr(self._tasker, "destroy") else None
          except Exception as exc: self.logger.warning(..., error=str(exc))
          self._tasker = None
  ...
  # 同法处理 self._resource / self._controller（若有 destroy/dispose）
  ```
  > 实现前需 `grep` 确认 MaaFW `Resource`/`AdbController`/`Tasker` 是否提供 `destroy()`/`dispose()`；若无，则该项降级为"记录待 MaaFW 升级"，不强行调用。
- **工作量**：~15 行（含 API 确认）。

### M11 — N11 `load_tasks`/`load_presets` 无并发锁
- **位置**：`src/core/service/maa_end/runtime.py:133` / `160`
- **问题**：并发调用会竞争 `self._tasks`/`self._presets`。
- **修改**：类内加 `self._load_lock = threading.Lock()`（若尚未存在），在 `load_tasks`/`load_presets` 函数体包 `with self._load_lock:`。
- **工作量**：~3 行 + 1 处声明。

### M12 — D10 `TouchManager.get_instance` 无锁
- **位置**：`src/core/capability/device/touch_manager.py:58-64`
- **问题**：类方法单例无锁，并发首访可能建多实例。
- **修改**：加 `threading.Lock` 双重检查：
  ```python
  _instance = None
  _lock = threading.Lock()
  @classmethod
  def get_instance(cls, adb_path="3rd-part/adb/adb.exe", device_address=None):
      if cls._instance is None:
          with cls._lock:
              if cls._instance is None:
                  cls._instance = cls(adb_path, device_address)
      return cls._instance
  ```
- **工作量**：~5 行。

### M13 — PL-3 `_loaded_modules` 无锁
- **位置**：`src/core/capability/element_recognition/pipeline/pipeline_loader.py:21,37`
- **问题**：`self._loaded_modules.add(...)` 并发不安全。
- **修改**：构造加 `self._lock = threading.Lock()`，`add` 前 `with self._lock:`（如需"已加载"判断可同步读取）。
- **工作量**：~3 行。

### M14 — D1 `_force_stop` 参数构造（疑为误报，防御性拆分）
- **位置**：`src/core/capability/device/recovery.py:72`
- **问题**：`["shell","am force-stop",pkg]` —— 经 `adb shell` argv 空格拼接语义分析，等价于正确 `am force-stop pkg`（与 `consolidated` 报告"D1 经复核为误判"一致）。但拆分为逐元素更清晰且零风险。
- **修改**（可选，低优先）：
  ```python
  self._run(["shell", "am", "force-stop", self._package], serial)
  ```
  > 建议先实测 `adb shell am force-stop <pkg>` 确认当前写法已生效；若生效则**不改动**以避免无意义 churn。
- **工作量**：~1 行（可选）。

---

## 执行顺序建议

1. **P1（M1–M4）**：安全相关、改动小、收益明确，建议首批落地。
2. **P2（M5–M8）**：边界校验 + 配置可诊断性，第二批。
3. **P3（M9–M13）**：资源/并发健壮性，按子系统排期；M10 需先确认 MaaFW API。
4. **M14**：实测后决定是否改（很可能不改）。

## 总工作量估算
- 新增代码约 **90–110 行**，分布在 9 个文件。
- 无架构性重构，全部为局部加固，blast radius 小。
- 建议配套：每个修改点以报告编号注释标记（如 `# SEC-02`），延续此前"按报告逐条落实"的可追溯习惯。

---

## 实施记录（2026-07-11 16:58）

> 已逐项阅读当前代码实际实现后落地。9 个文件全部通过 linter（0 错误）。

| 项 | 文件 | 状态 |
|---|---|---|
| M1 SEC-02 | `src/cli/istina.py` | ✅ 已落地（1MB 输入上限） |
| M2 SEC-03 | `src/gui/pyqt6/cli_bridge.py` | ✅ 已落地（4MB stdout 缓冲上限） |
| M3 SEC-01 | `src/cli/handlers.py` | ✅ 已落地（`--out` 项目根约束） |
| M4 CFG-09 | `src/core/service/runtime.py` | ✅ 已落地（`--config` 越界回退） |
| M5 SEC-04 | `src/cli/handlers.py` | ✅ 已落地（tap/swipe 坐标 `[0,65535]`） |
| M6 SEC-05 | `src/cli/handlers.py` | ✅ 已落地（nav3 坐标/地图名校验） |
| M7 CFG-12/15 | `src/core/service/runtime.py` | ✅ 已落地（异常拆分 + schema 告警） |
| M8 SEC-06 | `src/gui/pyqt6/scripting/player.py` | ✅ 仅补注释（by-design） |
| M9 N6 | `src/core/capability/device/android_runtime.py` | ⏭️ **跳过**：复验发现 `fd` 已在 `finally` 关闭（564-596），已修复 |
| M10 C7/N10 | `src/core/service/maa_end/runtime.py` | ✅ 已落地（`_cleanup_partial` 显式释放 resource/controller） |
| M11 N11 | `src/core/service/maa_end/runtime.py` | ✅ 已落地（`load_tasks`/`load_presets` 加锁） |
| M12 D10 | `src/core/capability/device/touch_manager.py` | ✅ 已落地（单例 DCL 加锁） |
| M13 PL-3 | `src/core/capability/element_recognition/pipeline/pipeline_loader.py` | ✅ 已落地（`_loaded_modules` 加锁） |
| M14 D1 | `src/core/capability/device/recovery.py` | ✅ 已落地（防御性拆分 argv） |

**结论**：方案 14 项中 13 项已落地，1 项（M9/N6）经复验确认代码早已修复，无需改动。本轮修复覆盖全部仍开放的安全加固（P1）、输入边界/配置校验（P2）与资源/并发健壮性（P3）发现。
