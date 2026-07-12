# 预览状态高频闪烁（STALE-01）

**时间**: 2026-07-13 03:00
**影响**: GUI 预览状态指示器在"● 实时"和"已断开"之间以 ~66ms 周期高频闪烁
**严重度**: 中（功能可用但 UX 严重劣化，日志被刷屏）

## 1. 根因分析

### 现象
用户反馈"实时与断开不时反复快速切换，并且画面正确"。日志 `logs/main.log` L13620-13679
显示 3 秒内数十次 "scrcpy frame reader 已启动" → "frame reader 过期，重启" 循环。

### 根因链
1. **daemon 编码器停滞**：scrcpy 的 `c2.android.avc.encoder` 在静态画面下仅按
   `i-frame-interval=2s` 产出关键帧，MaaEnd screencap 并发竞争时可能停滞更久。
   停滞期间 daemon 不写 mmap，header 中的 `ts = int(time.time())` 不更新。

2. **is_stale 基于 daemon 时钟误判**：`ScrcpyFrameReader.is_stale(max_age=5.0)` 使用
   daemon 写入的 `ts`（`int(time.time())` 秒级截断）判断过期。编码器停滞 >5s 时
   `is_stale` 返回 True，即使 reader 刚读到一帧。

3. **停止 reader 重置 _last_frame_count**：`_refresh_preview` 在 `is_stale` 返回 True 时
   调用 `_stop_frame_reader()`，将 `_last_frame_count` 重置为 -1。

4. **重建 reader 后同一旧帧被当新帧**：下次 33ms 轮询重建 reader，`read_frame()`
   发现 `count != -1`（count 是 daemon 写入的当前值，未变），将同一旧帧当作新帧
   读取，返回 QImage → 状态设为"● 实时"。

5. **66ms 闪烁循环**：33ms 后再次轮询，`count == _last_frame_count` → `read_frame()`
   返回 None → `is_stale` 仍 True（daemon ts 仍旧）→ "已断开" + 停止 reader →
   33ms 后重建 → "实时" → 重复。

### 时序图
```
t=0ms   reader 重建 → read_frame (count: -1→N) → "实时"
t=33ms  read_frame (count==N, None) → is_stale(True) → "已断开" + stop reader
t=66ms  reader 重建 → read_frame (count: -1→N) → "实时"
t=99ms  read_frame (count==N, None) → is_stale(True) → "已断开" + stop reader
...     66ms 周期循环
```

## 2. 修改方案

### scrcpy_frame_reader.py
1. **新增 `_last_new_frame_gui_ts` 字段**：记录 GUI 进程时钟下最后一次成功读到
   新帧的时刻（`time.time()`，浮点秒精度）。
2. **`read_frame()` 更新此字段**：当 `count != _last_frame_count`（真正的新帧）时
   更新 `_last_new_frame_gui_ts = time.time()`。
3. **`is_stale()` 改用 GUI 时钟**：`max_age` 从 5.0 提升到 10.0，判断基于
   `_last_new_frame_gui_ts` 而非 daemon 的 `ts`。daemon 的 `ts` 是 `int(time.time())`
   秒级截断，且编码器停滞时不更新，不适合作为过期判断依据。
4. **`stop()` 重置新字段**。

### main_window.py `_refresh_preview`
1. **is_stale 时不停止 reader**：移除 `_stop_frame_reader()` 调用。reader 保持存活，
   `_last_frame_count` 保留，同一旧帧不会被重复当新帧读取。
2. **仅更新状态指示器**：`is_stale` 返回 True 时仅 `set_status("已断开")`，不停止
   reader、不记录 warning 日志（避免 30fps 日志刷屏）。
3. **max_age 从 5.0 提升到 10.0**：更容忍编码器停滞（i-frame-interval=2s + MaaEnd
   screencap 竞争可能导致 >5s 无帧）。
4. **编码器恢复后自动恢复**：daemon 的 scrcpy session 有自己的重建机制
  （`_recv_exact max_stalls=3`，90s 强制重建），恢复后写新帧到 mmap，
   `read_frame()` 检测到 `count` 变化 → "● 实时"。

## 3. 影响面

| 组件 | 影响 |
|------|------|
| 预览状态指示 | 修复：不再高频闪烁，仅在持续 10s 无新帧时显示"已断开" |
| 预览画面 | 无变化：新帧到达时仍正常更新 |
| 日志 | 改善：消除 30fps 的 "frame reader 过期，重启" 刷屏 |
| reader 生命周期 | 变化：stale 时不再 stop/restart，仅在 disconnect/closeEvent 时停止 |
| daemon 侧 | 无变化：`_on_scrcpy_frame` 回调逻辑不变 |

## 4. 非期待变化

1. **编码器长期停滞（>10s）时状态持续"已断开"**：这是正确行为 — daemon 的 scrcpy
   session 会在 90s 后强制重建，恢复后状态自动回 "实时"。用户也可手动重新连接。

2. **reader 不停止可能导致 mmap 文件句柄保持打开**：仅在 disconnect/closeEvent 时
   释放。正常使用场景下无影响（disconnect 时 `_stop_frame_reader()` 仍被调用）。

3. **`_reader_retry_after` 不再在 stale 路径设置**：该字段仅用于 `start()` 失败时
   的 2s 重试延迟，stale 路径不再 stop/restart 所以不需要。
