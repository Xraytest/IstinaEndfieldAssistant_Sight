# 预览未正确更新设备真实画面 — 四阶段问题分析

**日期**: 2026-07-12  
**报告类型**: 行为异常  
**影响组件**: GUI 预览 / scrcpy 通道 / AndroidDaemon 截图  

## 1. 根因分析

### 现象
GUI 预览区域显示冻结/过时的画面，不反映设备当前真实屏幕状态。日志中持续出现：
```
[INFO] scrcpy socket 等待数据中（server 存活，不重建） bytes_read=0 bytes_expected=12
```
每 30s 重复一次，持续 2 分钟以上。

### 根因链（3 个独立缺陷叠加）

**缺陷 A: `_recv_exact` 编码器停滞时无限等待**
- 位置: `android_runtime.py:_recv_exact` (原 line 261-294)
- `socket.timeout` 时仅检查 server 进程是否存活。存活则 `stall_count += 1`（仅用于日志去重），然后 `continue` 无限循环。
- `stall_count` 从未触发会话重建。当模拟器软件编码器 (`c2.android.avc.encoder`) 停滞（server 存活但不产出帧数据），decode loop 永远卡在 `_recv_exact` 中。
- 日志 `bytes_read=0 bytes_expected=12` 确认：socket 30s 超时，0 字节到达，server 仍存活 → 继续等待 → 永远不会收到数据。

**缺陷 B: `_cleanup` 未清除 `_latest_frame`**
- 位置: `android_runtime.py:_cleanup` (原 line 455-457)
- `_cleanup` 设置 `_last_frame_ts = 0.0` 但未清除 `_latest_frame`。
- 会话重建后，`get_latest_frame()` 仍返回上一会话的过时帧。新会话在首帧到达前（或新会话同样停滞时），预览持续显示旧帧。

**缺陷 C: `get_latest_frame` 无新鲜度检查**
- 位置: `android_runtime.py:get_latest_frame` (原 line 103-107)
- 仅检查 `_latest_frame is None`，不检查帧的时间戳。
- 即使帧已过期数分钟，只要 `_latest_frame` 非 None 就返回。daemon 截图处理器将此过时帧编码为 PNG 返回给 GUI，预览显示冻结画面。

### 触发条件
模拟器软件编码器在以下场景停滞：
1. MaaEnd screencap (ADB) 与 scrcpy SurfaceEncoder 并发竞争 → 编码器 ~16s 停滞
2. 静态画面下软件编码器不产出 P 帧，仅按关键帧间隔产出（正常 2s/帧）
3. 编码器进入永久停滞状态（server 进程存活但零输出）

### 未能自愈的原因
缺陷 A 使 decode loop 无法检测到永久停滞（server 存活即继续等待），缺陷 B+C 使过时帧在会话重建后仍被返回。三者叠加导致预览永远显示停滞前的最后一帧。

## 2. 修改方案

全部修改集中在 `src/core/capability/device/android_runtime.py`，共 4 处：

### 修复 A: `_recv_exact` 添加最大停滞次数
```python
max_stalls = 3  # 3 × 30s = 90s 无数据后强制重建
...
elif stall_count >= max_stalls:
    self._logger.warning(
        "scrcpy socket 连续 %d 次超时（server 存活但编码器停滞），强制重建会话" % stall_count,
        ...
    )
    return None  # 触发 _run 循环重建会话
```
90s 无数据后返回 None，`_decode_loop` 退出，`_run` 的 finally 块重建会话。

### 修复 B: `_cleanup` 清除 `_latest_frame`
```python
def _cleanup(self) -> None:
    self._close_codec()
    self._last_frame_ts = 0.0
    with self._lock:
        self._latest_frame = None  # 新增
```
会话重建后不再返回上一会话的过时帧。

### 修复 C: `get_latest_frame` 添加新鲜度检查
```python
def get_latest_frame(self, max_age: float = 30.0) -> Optional[np.ndarray]:
    with self._lock:
        if self._latest_frame is None:
            return None
        if self._last_frame_ts > 0 and (time.time() - self._last_frame_ts) > max_age:
            return None  # 帧过期
        return self._latest_frame
```
30s 内未更新的帧视为过期，返回 None。正常关键帧间隔 2s，30s 阈值有充足余量。

### 修复 D: daemon 截图处理器添加 ADB screencap 回退
```python
# scrcpy 无帧/帧过期时，回退 ADB screencap
self._logger.info("daemon screenshot scrcpy 无帧/帧过期，回退 ADB screencap", serial=serial)
try:
    png_data = self._adb_manager.screencap(serial)
    if png_data and len(png_data) > 4 and png_data[:4] == b"\x89PNG":
        return self._encode_binary(png_data)
except Exception as exc:
    self._logger.error("ADB screencap 回退失败", serial=serial, error=str(exc))
return {"error": "screenshot failed: scrcpy 无帧且 ADB 回退失败"}
```
替换原 H-01 的 `"scrcpy not ready"` 错误返回。当 scrcpy 无帧/帧过期时，使用 ADB screencap 确保预览显示真实画面。ADB screencap 与 scrcpy 使用不同机制（`screencap` 命令 vs MediaCodec 编码），在编码器停滞时仍可工作。

### 修复协同关系
- 修复 A: 90s 内检测编码器停滞并触发会话重建（治本）
- 修复 B+C: 重建期间不返回过时帧（防止冻结画面）
- 修复 D: 重建期间通过 ADB 回退保持预览实时性（治标，确保用户体验）

## 3. 影响面

### 直接影响
- **GUI 预览**: 预览现在始终显示设备真实画面。scrcpy 正常时走 scrcpy 帧；scrcpy 停滞时 90s 内切换到 ADB screencap；会话重建后恢复 scrcpy。
- **CLI screenshot 命令**: 同样受益于 ADB 回退。`_handle_device_screenshot` → `android.screenshot()` → daemon → scrcpy/ADB 回退。
- **任务执行中的截图**: `_prepare_screen` (maa_end/runtime.py) 调用 `android.screenshot()`，也走 daemon 路径，同样受益。

### 间接影响
- **H-01 策略变更**: 原 H-01 决策"scrcpy 无帧即视为未就绪，不回退 ADB"被部分推翻。新策略区分两种情况：
  - scrcpy 启动阶段无帧（`_latest_frame is None` 且 `_last_frame_ts == 0`）：仍不回退（避免启动竞争）
  - scrcpy 运行中帧过期（`_last_frame_ts > 0` 但超 30s）：回退 ADB（编码器停滞）
- **scrcpy + ADB 并发**: ADB screencap 回退期间会与 scrcpy server 共存。但 scrcpy 编码器已停滞（不产出帧），不存在活跃竞争。会话重建后 scrcpy 恢复，ADB 回退自动停止。

### 性能影响
- ADB screencap 比 scrcpy 帧慢（~500ms vs ~50ms），但仅在回退期间生效，不影响正常预览。
- 90s 会话重建周期：重建开销约 3-5s（推 jar、启动 server、握手），可接受。

## 4. 非期待变化

### 需关注
1. **ADB screencap 失败时预览显示"已断开"**: 如果 ADB screencap 也失败（设备真断开），daemon 返回 error，GUI 连续 3 次失败后显示"已断开"。这是正确行为，但用户可能误以为连接断了而实际只是编码器停滞 + ADB 临时失败。
2. **会话重建期间预览闪烁**: 90s 停滞 → 会话重建（3-5s）→ 期间 ADB 回退 → 重建完成恢复 scrcpy。可能有短暂画面切换。可接受。
3. **`max_age=30.0` 阈值**: 如果模拟器关键帧间隔被修改为 >30s（当前 2s），正常静态画面也会触发 ADB 回退。需确保 `i-frame-interval=2` 配置不变。

### 不受影响
- 任务执行流程：`_on_execution_state_changed` 停止预览定时器，任务执行期间不截图，不受此修复影响。
- MaaEnd pipeline 截图：MaaEnd 使用自己的 AdbController，不走 daemon 截图路径，不受影响。
- scrcpy 正常工作时的性能：`get_latest_frame` 新增一次 `time.time()` 调用和比较，开销可忽略。
