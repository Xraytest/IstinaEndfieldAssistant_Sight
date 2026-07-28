#!/usr/bin/env python3
"""加载 maaend_task_state.json 队列并执行（支持 CloudCN 等自定义选项）。"""

import json, sys
from pathlib import Path

# 保证 src/ 在 sys.path 中（必须在任何 core.* import 之前）
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from core.foundation.paths import ensure_src_path
ensure_src_path(__file__)

from core.foundation.logger import LogCategory, get_logger

logger = get_logger()

# 1. 加载状态文件
state_path = Path("config/maaend_task_state.json")
state = json.loads(state_path.read_text(encoding="utf-8"))
queue_items = state.get("queue_items", [])

if not queue_items:
    logger.error(LogCategory.MAIN, "队列为空，无可执行任务")
    sys.exit(1)

logger.info(LogCategory.MAIN, "已加载队列", total=len(queue_items))

# 2. 启动 IstinaRuntime 并连接设备
from core.service.runtime import IstinaRuntime
from core.service.maa_end.runtime import MaaEndRuntime

runtime = IstinaRuntime()
ok = runtime.connect()
if not ok:
    logger.error(LogCategory.MAIN, "设备连接失败")
    sys.exit(1)

logger.info(LogCategory.MAIN, "设备连接成功")

# 3. 填充队列到 MaaEndRuntime 实例
maaend_runtime: MaaEndRuntime = runtime.maaend()
for item in queue_items:
    name = item.get("name")
    options = item.get("options", {})
    if name:
        maaend_runtime.add_task(name, options)
        logger.info(LogCategory.MAIN, "已添加队列任务", task=name, options=options)

logger.info(LogCategory.MAIN, "队列已填充，开始执行", total=len(queue_items))

# 4. 执行队列
result = maaend_runtime.run_queue()
if result:
    logger.info(LogCategory.MAIN, "队列执行完成，全部成功")
else:
    logger.warning(LogCategory.MAIN, "队列执行完成但存在失败任务")

sys.exit(0 if result else 1)
