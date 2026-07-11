# scrcpy _decode_loop TimeoutError 修复报告

> 日期: 2026-07-11
> 模块: `src/core/capability/device/android_runtime.py`
> 类型: 行为异常（日志噪声 + 会话重建延迟）

## 1. 根因分析

### 直接原因

`_decode_loop` 内层帧循环中，`fileobj.read(12)`（line 285）在 scrcpy 流停滞时阻塞等待数据。socket 超时设为 30s（line 242: `sock.settimeout(30.0)`），超时后抛出 `TimeoutError`，该异常穿透 `_decode_loop` → `_run()`，被 line 122 的 `except Exception:` 捕获，以 `[ERROR] scrcpy 会话异常` + 完整 traceback 记录。

### 根本原因

1. **KEEPALIVE-01 检测在阻塞读取期间为死代码**：line 282 的 keep-alive 检查（10s 无帧则 break）仅在循环迭代间执行。`fileobj.read(12)` 是阻塞调用，一旦进入读取，循环不迭代，keep-alive 检查无法触发，直到 socket 超时（30s）抛出 `TimeoutError`。
2. **socket 超时（30s）与 keep-alive 间隔（10s）不匹配**：导致会话停滞检测需 30s 而非预期的 10s。
3. **`TimeoutError` 未被单独捕获**：被通用 `except Exception:` 捕获后以 ERROR 级别 + traceback 记录，产生日志噪声，实际只是可恢复的通道超时。

### 代码位置

- `android_runtime.py:242` — `sock.settimeout(30.0)`（影响握手 + 解码循环）
- `android_runtime.py:282-285` — keep-alive 检查 + `fileobj.read(12)`
- `android_runtime.py:120-123` — `_run()` 的 `except Exception:` 捕获

### 日志证据

```
[2026-07-11 21:38:46] [ERROR] [core.capability.device.android_runtime:exception:87] [Thread-6 (_run)] [-] scrcpy 会话异常
Traceback (most recent call last):
  File "...android_runtime.py", line 119, in _run
    self._decode_loop()
  File "...android_runtime.py", line 282, in _decode_loop
    header = fileobj.read(12)
             ^^^^^^^^^^^^^^^^
  File "socket.py", line 720, in readinto
TimeoutError: timed out
```

## 2. 修改方案

**最小可行修改**（2 处改动）：

### 改动 1: `_run()` 添加 `except TimeoutError` (line 120-121)

将 `TimeoutError` 从通用 `except Exception:` 中分离，以 WARNING 级别记录（无 traceback），表明这是可恢复的通道超时：

```python
except TimeoutError:
    self._logger.warning("scrcpy socket 读取超时，准备重建会话")
except Exception:
    self._logger.exception("scrcpy 会话异常")
```

### 改动 2: 内层 decode 循环前降低 socket 超时至 10s (line 278)

在 `self._codec.open()` 之后、内层 `while` 循环之前，将 socket 超时从 30s 降为 10s，匹配 KEEPALIVE-01 的间隔：

```python
self._codec.open()

sock.settimeout(10.0)
try:
    while not self._stop_event.is_set():
        ...
```

这样 scrcpy 流停滞时，`fileobj.read(12)` 在 10s 后超时（而非 30s），与 keep-alive 意图一致，加速会话重建。

## 3. 影响面

| 调用点 / 组件 | 影响 |
|---|---|
| `_run()` (line 110) | 新增 `except TimeoutError` 分支，`TimeoutError` 不再走 `except Exception` |
| `_decode_loop` 内层循环 (line 278+) | socket 超时从 30s 降为 10s，仅影响帧读取阶段 |
| 握手阶段 (line 245-261) | **不受影响** — 仍使用 line 242 的 30s 超时，仅在进入内层循环前才降为 10s |
| `_ScrcpySession.get_latest_frame()` | 无变化 |
| `AndroidRuntime.screenshot()` / daemon 截图路径 | 无变化 — 会话超时后仍由下次截图请求触发重建 |
| GUI 预览定时器 | 无变化 — 预览请求仍通过 daemon 路由 |
| 日志输出 | `TimeoutError` 从 `[ERROR]` + traceback 降级为 `[WARNING]`，减少噪声 |

## 4. 非期待变化

### 可能的副作用

1. **慢速设备误判**：若设备端 scrcpy 编码耗时超过 10s（极端情况），可能导致误超时。但 scrcpy 连接本地 127.0.0.1，正常帧间隔为毫秒级，10s 已留充分余量。
2. **首次帧等待**：`_start` 方法中已有独立的 15s 首帧超时（line 88-93），与本次修改无关。

### 回退策略

- 回退改动 2（删除 line 278 `sock.settimeout(10.0)`）即可恢复 30s socket 超时行为。
- 回退改动 1（删除 line 120-121 `except TimeoutError` 块）即可恢复 ERROR+traceback 日志。
- 两处改动相互独立，可单独回退。

### 验证

- `py_compile` 语法检查通过。
- 逻辑上：`TimeoutError` 是 `OSError` 子类，Python 3.10+ 中 `socket.timeout` 即 `TimeoutError`，`except TimeoutError` 能正确捕获。
- 行为上：会话超时后清理流程不变（`finally` 块仍执行 `_close_codec` + `_cleanup`），下次截图请求仍触发 scrcpy 重建。
