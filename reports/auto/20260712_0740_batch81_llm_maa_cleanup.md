# 审计批次 81 — LLM 子进程异常诊断静默丢弃 / MaaEnd Agent 清理异常静默吞噬 + 审计批次 80

**生成时间**: 2026-07-12 07:40
**覆盖文件**: `llm/runtime.py`, `maa_end/runtime.py`
**审计方法**: 静态代码逻辑分析，无测试执行
**前置去重**: 已读取 `reports/CODE_REVIEW_WARNS.md`，新发现跳过 FP-01~08、FX-01~10、DUP-A~J、O-01~O-24

---

## 新增发现（2 项）

### LLM-02 — `_try_start` 中 `communicate()` 失败被静默丢弃，误导性错误日志

**等级**: BUG / 中
**位置**: `llm/runtime.py:354-368`

**问题代码**:

```python
# llm/runtime.py:354-368
if self._process.poll() is not None:
    out, err = b"", b""
    try:
        out, err = self._process.communicate(timeout=2)
    except Exception:              # ← 异常被静默吞掉
        pass
    self._logger.error(
        "llama-server exited early (code=%s): stdout=%r stderr=%r",
        self._process.returncode,  # ← 可能为 None
        out.decode("utf-8", errors="replace")[:2000] if out else "",
        err.decode("utf-8", errors="replace")[:2000] if err else "",
    )
    return False
```

**根因分析**:

当 `poll()` 返回非 None（进程已退出）时，代码调用 `communicate(timeout=2)` 获取可能的 stdout/stderr 输出。但 `communicate()` 在以下场景会抛异常：
- `TimeoutExpired`: 进程已退出但管道仍有数据未读完（2 秒超时）
- `OSError`: 管道已关闭或被系统回收
- 其他意外异常

`except Exception: pass` 静默吞掉这些异常后，`out` 和 `err` 仍为 `b""`，`self._process.returncode` 可能为 `None`（取决于进程状态）。日志输出将显示为：

```
llama-server exited early (code=None): stdout='' stderr=''
```

这完全掩盖了真正的启动失败原因。开发者无法得知 llama-server 究竟输出了什么错误（如 CUDA 不可用、模型文件损坏、端口冲突），误以为是进程"静默退出"。

**与 O-23 的区别**: O-23 覆盖 `_start_agent` 的 go-service stdout/stderr 被重定向到 DEVNULL。LLM-02 是**不同问题**：`_try_start` 的 Popen 已经使用了 `PIPE`（诊断友好），但 `communicate()` 的异常处理导致诊断信息在读取阶段丢失。两者不重叠。

**影响面**:
- **中**：llama-server 启动失败是常见场景（模型文件缺失、CUDA 版本不匹配、显存不足）。当前行为导致每次启动失败都输出误导性日志，用户和开发者都无法定位真正原因。

**修复建议**:

```python
try:
    out, err = self._process.communicate(timeout=2)
except Exception as exc:
    self._logger.warning(
        "llama-server communicate() 失败: %s (code=%s)",
        exc, self._process.returncode,
    )
    out, err = b"", b""
self._logger.error(
    "llama-server exited early (code=%s): stdout=%r stderr=%r",
    self._process.returncode if self._process.returncode is not None else "unknown",
    out.decode("utf-8", errors="replace")[:2000] if out else "<empty>",
    err.decode("utf-8", errors="replace")[:2000] if err else "<empty>",
)
```

---

### MAA-08 — `_start_agent` 中 `process.wait()` 超时后 `process.kill()` 调用链异常静默吞噬

**等级**: BUG / 中
**位置**: `maa_end/runtime.py:485-493`

**问题代码**:

```python
# maa_end/runtime.py:485-493
if process is not None and process.poll() is None:
    try:
        process.terminate()
        try:
            process.wait(timeout=3)
        except Exception:          # ← line 490: wait() 超时后 attempt kill
            process.kill()         # ← kill() 可能抛异常
    except Exception:              # ← line 492: kill() 的异常也被吞掉
        pass
```

**根因分析**:

该代码位于 `_start_agent` 的 `except Exception as exc:` 块内（line 483），处理 Agent 启动失败后的进程清理：

1. `process.terminate()` — 发送 SIGTERM，通常成功
2. `process.wait(timeout=3)` — 等待 3 秒让进程退出
3. `except Exception:` (line 490) — wait 超时或失败，尝试 `process.kill()`
4. `except Exception: pass` (line 492) — **kill() 的异常被静默吞掉**

两个问题：
- **问题 A**: 如果 `wait()` 超时后 `kill()` 抛异常（如权限不足、进程已死但对象未更新），line 492 的 `pass` 将异常完全丢弃。`process` 可能仍在运行，但 `_agent_process` 和 `_agent_client` 在 line 494-495 被设为 `None`。后续代码认为 Agent 已清理，实际存在僵尸/残留进程。
- **问题 B**: `returncode` 可能为 `None`（进程仍在运行），但代码不检查，直接继续清理。

**对比 O-06/O-07**: O-06 和 O-07 覆盖 daemon 线程 join 超时后的 UAF 风险（`_connect_with_timeout` 和 `_wait_job`）。MAA-08 是**不同问题**：关注 `process.kill()` 调用链中的异常处理，而非线程 join。

**影响面**:
- **中**：Agent 启动失败时残留进程会占用端口（agent_id 端口），下次启动会因端口冲突而失败。由于异常被静默吞掉，用户只看到"启动 Agent 失败"，不知道还有残留进程阻塞。

**修复建议**:

```python
if process is not None and process.poll() is None:
    try:
        process.terminate()
        try:
            process.wait(timeout=3)
        except Exception as wait_exc:
            self.logger.warning("agent process wait() 超时，尝试 kill", error=str(wait_exc))
            try:
                process.kill()
            except Exception as kill_exc:
                self.logger.warning("agent process kill() 失败", error=str(kill_exc))
    except Exception as exc:
        self.logger.warning("agent process 清理异常", error=str(exc))
```

---

## 审计结论（批次 80）

| 批次 | 审计对象 | 结论 |
|------|---------|------|
| 批次 80 | VLM-01 (`_frame_to_base64` cv2.imencode 失败无防护) | **结论正确**。当前代码已修复（`ok, buf = cv2.imencode(...)` + `if not ok or buf is None`），对应 O-22。批 80 报告准确描述了修复前的缺陷和修复方案。 |
| 批次 80 | MAA-07 (`_start_agent` stdout/stderr DEVNULL) | **结论正确**。当前代码仍为 `subprocess.DEVNULL`（未修复），对应 O-23。批 80 报告准确指出 LLM-01 使用 `PIPE` 作为对比参照。 |
| 批次 80 | ADB-01 (adb_manager adbutils 回退不记录异常) | **结论正确**。当前代码仍为 `except Exception:` 无日志（未修复），对应 O-24。批 80 报告准确对比了 `get_devices()` 有日志而 `shell`/`screencap` 无日志的不一致性。 |

**批次 80 全部 3 项结论经本批次逐项源码复核确认准确，无需修正。**

---

## 风险摘要

| 级别 | 数量 | 涉及项 |
|------|------|--------|
| BUG（中） | 2 | LLM-02 (communicate() 异常丢弃误导日志), MAA-08 (kill() 异常静默吞噬) |
| 高风险 | 0 | — |
| 低风险/代码质量 | 0 | — |

**本轮无低风险发现。**

---

*批次 81 报告 | 仅分析，无文件修改*