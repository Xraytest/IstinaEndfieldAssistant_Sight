"""探测当前场景状态：尝试 SceneAnyEnterWorld 并报告节点轨迹。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from core.foundation.paths import ensure_src_path

ensure_src_path()

from core.foundation.logger import init_logger

init_logger()

from core.service.runtime import IstinaRuntime


def main() -> int:
    runtime = IstinaRuntime()
    if not runtime.connect(serial="127.0.0.1:16416"):
        print("连接失败")
        return 1
    maaend = runtime.maaend()
    tasker = maaend._tasker
    if tasker is None:
        print("tasker 未就绪")
        return 2
    if not maaend._wait_for_tasker_ready(wait_s=5.0, rebuild_on_stuck=True):
        print("Tasker 未就绪")
        return 3

    # 直接 post_task 入口 SceneAnyEnterWorld（不使用 override）
    print("=== 尝试 SceneAnyEnterWorld（短超时 30s）===")
    try:
        job = tasker.post_task("SceneAnyEnterWorld", {})
    except Exception as e:
        print(f"post_task 异常: {e}")
        return 4
    ok = maaend._wait_job(job, timeout_s=30.0)
    print(f"任务结果: {ok}")
    try:
        detail = job.get()
        if detail:
            print(f"节点数量: {len(detail.nodes)}")
            for i, node in enumerate(detail.nodes):
                name = getattr(node, "name", "") or ""
                completed = getattr(node, "completed", False)
                succeeded = getattr(node, "succeeded", False)
                rec = getattr(node, "recognition", None)
                rec_hit = bool(rec and rec.hit)
                print(f"  [{i}] name={name!r} completed={completed} succeeded={succeeded} rec_hit={rec_hit}")
    except Exception as e:
        print(f"获取 detail 失败: {e}")
    return 0 if ok else 5


if __name__ == "__main__":
    sys.exit(main())
