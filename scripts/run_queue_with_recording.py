"""运行完整队列并启用视频录制（无 GUI 测试路径）

复现 GUI 的 _maybe_start_recording() → run_queue() → _maybe_stop_recording() 流程。
通过直接调用 runtime API + QueueVideoRecorder 实现等效行为，避免依赖用户手动点击。

关键设计：
  - run_queue 在独立线程中执行；主线程监控并支持超时/信号优雅退出
  - 任何退出路径（正常/超时/Ctrl+C）都会调用 recorder.stop() 完成 MP4 写入
  - 与 GUI 不同：直接 kill 进程会破坏 MP4 头；本脚本必须优雅停止
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from core.foundation.logger import init_logger, get_logger
from core.foundation.paths import ensure_src_path

ensure_src_path()
init_logger()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", default="127.0.0.1:16416")
    parser.add_argument("--queue-file", default=str(ROOT / "config" / "user_queue.json"))
    parser.add_argument("--only-tasks", default=None,
                        help="Comma-separated task names to keep (others filtered out).")
    parser.add_argument("--max-runtime-s", type=float, default=1800.0,
                        help="Hard cap on total queue runtime (default 30 min).")
    parser.add_argument("--per-task-timeout-s", type=float, default=600.0,
                        help="Per-task stop_request after this many seconds (default 10 min).")
    args = parser.parse_args()

    logger = get_logger("test_runner")
    logger.info("=== Test runner start ===", serial=args.serial, queue=args.queue_file,
                only=args.only_tasks, max_runtime_s=args.max_runtime_s,
                per_task_timeout_s=args.per_task_timeout_s)

    # 1. 读取 常用队列.json
    queue_file = Path(args.queue_file)
    if not queue_file.is_file():
        logger.error("Queue file not found", path=str(queue_file))
        return 1
    queue_data = json.loads(queue_file.read_text(encoding="utf-8"))
    queue_items = queue_data.get("queue_items", [])
    task_options = queue_data.get("task_options", {})
    if args.only_tasks:
        keep = {t.strip() for t in args.only_tasks.split(",") if t.strip()}
        queue_items = [it for it in queue_items if it.get("name") in keep]
        logger.info("Filtered queue by --only-tasks", kept=list(keep), count=len(queue_items))
    logger.info("Queue loaded", count=len(queue_items),
                task_names=[it.get("name") for it in queue_items])

    # 2. 初始化 runtime
    from core.service.runtime import IstinaRuntime

    runtime = IstinaRuntime()
    serial = args.serial
    logger.info("Connecting to device", serial=serial)
    if not runtime.connect(serial=serial):
        logger.error("Failed to connect")
        return 1
    logger.info("Connected; scrcpy daemon started")

    # 3. 等待 scrcpy 首帧（info 文件存在）
    safe_serial = serial.replace(":", "_").replace("/", "_").replace("\\", "_")
    info_path = ROOT / "cache" / "ipc" / f"android-{safe_serial}.info"
    logger.info("Waiting for scrcpy info file", path=str(info_path))
    scrcpy_ready = False
    for i in range(60):
        if info_path.is_file():
            try:
                info = json.loads(info_path.read_text(encoding="utf-8"))
                w = int(info.get("frame_mmap_size", 0))
                if w > 0:
                    scrcpy_ready = True
                    logger.info("scrcpy ready", attempt=i, info_path=str(info_path))
                    break
            except Exception:
                pass
        time.sleep(1)
    if not scrcpy_ready:
        logger.error("scrcpy daemon did not become ready in 60s")
        return 1

    # 4. 启动 QueueVideoRecorder
    from gui.pyqt6.queue_video_recorder import QueueVideoRecorder
    recorder = QueueVideoRecorder(serial)
    if not recorder.start():
        logger.error("QueueVideoRecorder failed to start (scrcpy not ready)")
        return 1
    logger.info("Recording started", output_path=recorder.output_path)

    # 5. 加载队列到 MaaEndRuntime
    maaend = runtime.maaend(serial=serial)
    maaend.clear_queue()
    for entry in queue_items:
        name = entry.get("name")
        opts = dict(entry.get("options") or {})
        if name in task_options:
            base_opts = task_options[name]
            for k, v in base_opts.items():
                opts.setdefault(k, v)
        maaend.add_task(name, opts)
    logger.info("Queue loaded into MaaEndRuntime", count=len(maaend.queue()))

    # 6. 在独立线程中运行队列；主线程监控信号与超时
    stop_event = threading.Event()
    queue_result: dict = {"ok": False, "exception": None}

    def run_in_thread():
        try:
            queue_result["ok"] = maaend.run_queue()
        except Exception as exc:
            queue_result["exception"] = exc
            logger.exception("Queue run exception", error=str(exc))
        finally:
            stop_event.set()

    def request_stop_handler(signum, frame):
        logger.warning("Signal received, requesting stop", signum=signum)
        maaend.request_stop()

    # 注册信号（Windows 下仅 SIGINT/SIGBREAK 真正可用）
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, request_stop_handler)
    if hasattr(signal, "SIGBREAK"):
        try:
            signal.signal(signal.SIGBREAK, request_stop_handler)
        except Exception:
            pass
    if hasattr(signal, "SIGTERM"):
        try:
            signal.signal(signal.SIGTERM, request_stop_handler)
        except Exception:
            pass

    t0 = time.time()
    thread = threading.Thread(target=run_in_thread, name="queue-runner", daemon=True)
    thread.start()
    logger.info("Queue thread started")

    # 监控：max-runtime-s 强制停止
    while not stop_event.is_set():
        elapsed = time.time() - t0
        if elapsed > args.max_runtime_s:
            logger.warning("Max runtime exceeded, requesting stop",
                           elapsed_s=elapsed, max_s=args.max_runtime_s)
            maaend.request_stop()
            break
        stop_event.wait(timeout=1.0)

    # 等待线程退出（最多 30s 让出队列 + finalize）
    thread.join(timeout=30.0)
    if thread.is_alive():
        logger.error("Queue thread did not exit cleanly within 30s after stop request")
    else:
        logger.info("Queue thread exited", elapsed_s=time.time() - t0)

    # 7. 停止录制（finalize MP4）
    try:
        path = recorder.stop()
        logger.info("Recording stopped", path=path, frames=recorder.frame_count)
    except Exception as exc:
        logger.exception("Failed to stop recorder", error=str(exc))
        path = None

    # 8. 输出汇总
    summary = {
        "ok": queue_result["ok"],
        "exception": str(queue_result["exception"]) if queue_result["exception"] else None,
        "video_path": recorder.output_path,
        "frames": recorder.frame_count,
        "elapsed_s": round(time.time() - t0, 2),
        "queue_size": len(queue_items),
        "queue_names": [it.get("name") for it in queue_items],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if queue_result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
