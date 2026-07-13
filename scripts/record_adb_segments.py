"""分段录制 ADB 屏幕录像，用于 DailyFull 执行过程记录。

由于 adb shell screenrecord 最大连续时长为 180 秒，本脚本以 180 秒为一片段循环录制，
直到检测到停止信号文件（--stop-file）存在后，等待当前片段结束并退出。
"""
import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def run(args: argparse.Namespace) -> int:
    stop_path = Path(args.stop_file)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    adb = Path(args.adb)
    serial = args.serial
    segment_seconds = min(args.segment_seconds, 180)
    max_segments = args.max_segments

    segment_index = 0
    while True:
        if stop_path.exists():
            print(f"[{datetime.now().isoformat()}] 检测到停止信号，结束录制")
            break
        if max_segments > 0 and segment_index >= max_segments:
            print(f"[{datetime.now().isoformat()}] 达到最大片段数 {max_segments}，结束录制")
            break

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        remote_path = f"/data/local/tmp/daily_segment_{timestamp}_{segment_index:03d}.mp4"
        local_path = out_dir / f"daily_segment_{timestamp}_{segment_index:03d}.mp4"

        cmd = [
            str(adb),
            "-s", serial,
            "shell", "screenrecord",
            "--time-limit", str(segment_seconds),
            "--size", args.size,
            "--bit-rate", str(args.bit_rate),
            remote_path,
        ]
        print(f"[{datetime.now().isoformat()}] 开始录制片段 {segment_index}: {remote_path}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # 等待 screenrecord 完成（180 秒）或检测到停止信号
        while proc.poll() is None:
            time.sleep(1)
            if stop_path.exists():
                # 发送 SIGINT 不太容易跨 adb；这里直接等待当前片段自然结束
                print(f"[{datetime.now().isoformat()}] 已请求停止，等待当前片段录制完成...")

        proc.wait()

        # 拉取到本地
        pull_cmd = [str(adb), "-s", serial, "pull", remote_path, str(local_path)]
        pull_result = subprocess.run(pull_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if pull_result.returncode == 0 and local_path.exists() and local_path.stat().st_size > 0:
            print(f"[{datetime.now().isoformat()}] 片段保存成功: {local_path}")
            # 删除设备端文件
            subprocess.run([str(adb), "-s", serial, "shell", "rm", remote_path],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            print(f"[{datetime.now().isoformat()}] 拉取片段失败: {pull_result.stderr or pull_result.stdout}")

        segment_index += 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="分段录制 ADB 屏幕录像")
    parser.add_argument("--adb", default="3rd-part/adb/adb.exe", help="adb 可执行文件路径")
    parser.add_argument("--serial", required=True, help="设备 serial")
    parser.add_argument("--output-dir", required=True, help="本地输出目录")
    parser.add_argument("--stop-file", default=".stop_record", help="停止信号文件路径")
    parser.add_argument("--segment-seconds", type=int, default=180, help="每段最大秒数（默认 180，adb 上限）")
    parser.add_argument("--max-segments", type=int, default=0, help="最大片段数，0 表示无限制")
    parser.add_argument("--size", default="1280x720", help="视频分辨率")
    parser.add_argument("--bit-rate", default="8000000", help="视频比特率")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
