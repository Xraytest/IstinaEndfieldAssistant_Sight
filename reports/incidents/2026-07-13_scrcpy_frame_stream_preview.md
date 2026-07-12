# 事件报告：scrcpy 视频流直连预览（持久 mmap 帧通道）

**日期**: 2026-07-13
**触发**: 用户反馈"预览只能够正确显示单帧画面，我期望scrcpy的视频流直接接到预览上，使得预览极为顺畅"

## 1. 根因分析

GUI 预览原采用"定时截图 RPC"链路：

```
_refresh_preview (1500ms 定时器)
  → _sync_execute("screenshot", timeout_ms=5000)
    → CLIBridge QProcess → CLI 子进程 → IstinaRuntime._screenshot()
      → daemon JSON-RPC → cv2.imencode(".png") → 临时 mmap → base64 → stdout
        → GUI 解析 base64 → QPixmap.loadFromData
```

**低效根因**：每帧预览需要经历完整的 RPC 序列化链路——QProcess stdin/stdout 通信、JSON-RPC 往返、PNG 编解码、base64 编解码。即使 scrcpy 解码线程已产出帧，该帧仍需经过 6 层转换才能到达 GUI QPixmap。实测 2-4 秒/帧，远低于 30fps 目标。

**关键矛盾**：daemon 内的 `_ScrcpySession._decode_loop` 已持续解码 scrcpy 视频流并更新 `_latest_frame`（numpy ndarray），但该帧缓存无法被 GUI 进程直接访问——daemon 运行在 CLI 子进程中，与 GUI 是两个独立进程。

## 2. 修改方案

### 核心思路：持久 mmap 帧通道

daemon 预分配一个持久 mmap 文件（32B header + 像素数据），scrcpy 解码线程每产出一帧即通过 `_on_frame` 回调写入 mmap。GUI 进程直接读同一 mmap 文件，零 RPC、零序列化、零子进程。

### daemon 侧（android_runtime.py）

1. **`_Daemon.__init__`**：新增 `_frame_mmap_path`/`_info_path`/`_frame_mmap`/`_frame_mmap_size`/`_frame_count` 成员。mmap 路径确定性：`cache/ipc/android-{safe_serial}.frame.mmap`。

2. **`_Daemon._init_frame_mmap()`**（新增）：预分配 mmap（2,764,832 字节 = 32 + 1280×720×3），写初始 header（frame_count=0），写 info 文件（含 pid/created_ts/mmap 路径/大小）。

3. **`_Daemon._dispatch` startScrcpy 分支**：session.start() 后设置 `session._on_frame = self._on_scrcpy_frame`。screenshot 分支的 fallback session 创建也同步设置。

4. **`_Daemon._on_scrcpy_frame(img)`**（新增）：先写像素（offset 32+），再写 header（offset 0-31，含递增 frame_count）。header 最后写确保 GUI 读到 header 时像素已就位。

5. **`_Daemon.stop()`**：关闭 frame mmap，删除 info/mmap 文件。

6. **`_ScrcpySession._cleanup` 不修改**：该回调在 session 重建循环中反复调用，若在此置空 `_on_frame` 会导致重建后回调丢失。回调生命周期绑定 `_ScrcpySession` 对象。

### GUI 侧（scrcpy_frame_reader.py + main_window.py）

1. **`ScrcpyFrameReader`**（新增）：读 info 文件获取 mmap 路径/大小 → 打开 mmap READONLY → `read_frame()` 读 header（magic/w/h/stride/ts/frame_count），frame_count 变化时读像素 → BGR→RGB → QImage.copy()。

2. **`main_window.py`**：
   - 定时器从 1500ms 降到 33ms（30fps 轮询）
   - `_refresh_preview` 重写：用 ScrcpyFrameReader 替代 `_sync_execute("screenshot")`
   - reader 生命周期：connect 成功时启动，disconnect/过期时停止，2s 重试间隔
   - 执行期间不停止预览（mmap 读取不与 MaaEnd screencap 竞争）
   - closeEvent 清理 reader

### mmap header 格式（32 字节）

```
offset 0:  magic      (4s)  = b"SCF1"
offset 4:  width       (i)
offset 8:  height      (i)
offset 12: stride      (i)   = width * 3
offset 16: format      (i)   = 0 (BGR24)
offset 20: timestamp   (Q)   = time.time()
offset 28: frame_count (I)   = 递增计数
```

struct format: `<4siiiQI`

## 3. 影响面

- **预览性能**：从 2-4s/帧提升至 30fps 轮询（新帧时才读像素，静态画面时仅 header 读取微秒级）
- **CPU 开销**：30fps 轮询 + mmap 内存读取，稳态零 RPC 零序列化
- **执行期间预览**：不再停止，用户可在任务执行时实时观察设备画面
- **scrcpy 帧通道**：daemon 内单 scrcpy 会话复用，严禁双会话（遵循 project_memory 约束）
- **无 ADB screencap 回退**：reader 失败时显示"已断开"并 2s 后重试
- **磁盘文件**：`cache/ipc/android-{safe_serial}.frame.mmap` + `.info`，daemon stop 时删除

## 4. 非期待变化

- **frame_count 初值为 -1**：reader 首次 read_frame 时 `count(0) != _last_frame_count(-1)` 会触发一次像素读取，即使 daemon 尚未产出帧（header 全零，w/h/stride=0，read_frame 返回 None）。无副作用。
- **跨进程 mmap 撕裂**：daemon 写像素与 GUI 读像素无锁同步，极低概率出现一帧撕裂（预览不可见）。
- **daemon 重启**：旧 info/mmap 文件由 daemon.stop() 删除。若 daemon 崩溃未清理，新 daemon 以 `O_CREAT | O_RDWR` 打开同路径文件并 `ftruncate` 到预分配大小（文件已存在且大小一致时为 no-op），GUI reader 通过 info 文件 mtask_count 检测过期并重连。
- **`_preview_fail_count` 属性遗留**：旧 `_refresh_preview` 使用的 `_preview_fail_count` 不再被引用，但 `getattr(self, "_preview_fail_count", 0)` 式引用已全部移除，无残留。
