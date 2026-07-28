"""用 MaaFW OCR 全屏扫描当前屏幕，识别界面状态。"""
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
    controller = maaend._controller
    if tasker is None or controller is None:
        print("tasker/controller 未就绪")
        return 2
    if not maaend._wait_for_tasker_ready(wait_s=5.0, rebuild_on_stuck=True):
        print("Tasker 未就绪")
        return 3
    job = controller.post_screencap()
    if not maaend._wait_job(job, timeout_s=10.0):
        print("截图失败")
        return 4
    img = controller.cached_image
    if img is None:
        print("cached_image 为空")
        return 5
    print(f"图像尺寸: {img.shape}")

    from maa.pipeline import JOCR, JRecognitionType

    # 大量常见关键词，用于探测当前界面
    keywords = [
        # 主世界
        "UID", "uid", "工业计划", "工業計劃", "工业简报", "工業簡報",
        "ENDFIELD", "Endfield", "总控中枢", "總控中樞", "地区建设", "地區建設",
        "据点管理", "據點管理", "协议同步", "協議同步", "探索",
        # 启动/登录
        "开始游戏", "開始遊戲", "Start", "点击任意位置继续", "點擊任意位置繼續",
        "点击", "點擊", "Continue", "Tap", "Click",
        "登录", "登錄", "账号", "帳號", "密码", "密碼", "请输入",
        # 加载
        "加载", "載入", "Loading", "loading", "正在加载", "正在載入",
        # 弹窗
        "知道了", "长时间未操作", "自动结束", "自动结",
        "确认", "確認", "取消", "OK", "Ok",
        # 好友
        "好友", "好友列表", "拜访", "助力", "线索", "線索",
        # 菜单
        "菜单", "選單", "返回", "退出", "关闭", "關閉",
        # 任务
        "任务", "任務", "进行中", "ALL", "传送", "傳送",
        # 信用商店
        "信用", "商店", "购物",
        # 帝江号
        "帝江", "会客室", "制造舱", "培養艙", "培养舱",
        # 设置
        "设置", "設定", "修复", "修復",
        # 通用
        "的", "了", "是", "在", "请", "请选择",
    ]
    ocr_param = JOCR(
        expected=keywords,
        roi=[0, 0, img.shape[1], img.shape[0]],
        threshold=0.3,
        only_rec=True,  # only_rec=True 时返回所有识别到的文本，expected 不做过滤
    )
    ocr_job = tasker.post_recognition(JRecognitionType.OCR, ocr_param, img)
    detail = ocr_job.wait().get()
    if not detail:
        print("OCR 无结果")
        return 6
    print("=== OCR 全屏识别结果（only_rec=True）===")
    hit_count = 0
    for node in detail.nodes:
        if node.recognition:
            all_results = node.recognition.all_results
            if all_results:
                for r in all_results:
                    box = r.box
                    if hasattr(box, "x"):
                        coords = (box.x, box.y, box.w, box.h)
                    else:
                        coords = tuple(box)
                    text = getattr(r, "text", "") or ""
                    score = getattr(r, "score", 0) or 0
                    if text:
                        print(f"  text={text!r} score={score:.2f} box={coords}")
                        hit_count += 1
    print(f"总计 {hit_count} 个文本块")
    return 0


if __name__ == "__main__":
    sys.exit(main())
