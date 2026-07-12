"""读取 config/maaend_task_state.json 中的当前队列并执行。

用法:
  3rd-part/python/python.exe scripts/run_current_queue.py --serial 192.168.1.12:16512 --timeout 90
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from core.service.runtime import IstinaRuntime
from core.foundation.paths import ensure_src_path

ensure_src_path(__file__)


def main():
    parser = argparse.ArgumentParser(description="执行当前队列")
    parser.add_argument("--serial", default=None, help="device serial")
    parser.add_argument("--timeout", type=float, default=90, help="task timeout in seconds")
    args = parser.parse_args()

    state_path = ROOT / "config" / "maaend_task_state.json"
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)

    queue_items = state.get("queue_items", [])
    if not queue_items:
        print("队列为空")
        return 1

    print(f"队列共 {len(queue_items)} 项:")
    for i, item in enumerate(queue_items):
        print(f"  {i+1}. {item.get('name')}")

    runtime = IstinaRuntime()
    maaend = runtime.maaend(args.serial)

    if not runtime._ensure_maaend_ready(maaend):
        print("MaaEnd runtime 未就绪")
        return 1

    maaend.clear_queue()
    for item in queue_items:
        name = item.get("name", "")
        options = item.get("options") or {}
        maaend.add_task(name, options)

    print(f"\n开始执行队列 (timeout={args.timeout}s)")
    ok = maaend.run_queue(timeout=args.timeout)
    print(f"\n队列执行结果: {'成功' if ok else '存在失败'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
