#!/usr/bin/env python3
"""基于真实设备反馈验证 _verify_screen_change 效果

使用方法：
  1. 确保 ADB 设备已连接
  2. 运行脚本：python verify_screen_change_manual.py
  3. 观察控制台输出，确认画面变化检测和多源分析正常
"""

import sys
import time
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from core.foundation.logger import init_logger, get_logger, LogCategory
from core.capability.device.adb_manager import ADBDeviceManager
from core.capability.device.device_detector import DeviceDetector
from core.capability.input.screenshot.screen_capture import ScreenCapture

init_logger()
logger = get_logger(LogCategory.MAIN)


def _adb_binary():
    candidates = [
        str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"),
        str(PROJECT_ROOT.parent / "IstinaEndfieldAssistant" / "3rd-part" / "adb" / "adb.exe"),
        "adb",
    ]
    for c in candidates:
        if Path(c).exists() or c == "adb":
            return c
    return "adb"


def adb_screencap(serial: str):
    """通过 ADB 截图，返回 PNG bytes（与 standard_flow_engine.py 一致）"""
    import subprocess
    adb_path = _adb_binary()
    try:
        proc = subprocess.run(
            [adb_path, "-s", serial, "shell", "screencap", "-p"],
            capture_output=True, timeout=10
        )
        if proc.returncode == 0:
            return proc.stdout
    except Exception as e:
        logger.error(LogCategory.MAIN, f"screenshot failed: {e}")
    return None


class ScreenAnalyzer:
    """多源画面分析器：YOLO 元素检测 + OCR 文字 + VLM 综合判断"""

    def __init__(self, maafw_executor=None, llama_url="http://127.0.0.1:8080"):
        self._maafw = maafw_executor
        self._llama_url = llama_url
        self._yolo = None

    def _get_yolo(self):
        """懒加载 YOLO 模型"""
        if self._yolo is None:
            try:
                from ultralytics import YOLO
                self._yolo = YOLO("yolo11n.pt")
                print("[YOLO] yolo11n 模型加载成功")
            except Exception as e:
                print(f"[YOLO] 加载失败: {e}")
                self._yolo = False
        return self._yolo if self._yolo is not False else None

    def analyze(self, img) -> dict:
        """综合分析画面，返回页面类型和依据"""
        import cv2, numpy as np

        result = {
            "page_type": "unknown",
            "yolo_objects": [],
            "ocr_text": "",
            "vlm_judgment": "",
            "sources": []
        }

        # 1. YOLO 元素检测
        yolo_objects = self._detect_yolo(img)
        result["yolo_objects"] = yolo_objects
        if yolo_objects:
            result["sources"].append("yolo")

        # 2. OCR 文字识别（VLM）
        ocr_text = self._ocr_via_vlm(img)
        result["ocr_text"] = ocr_text
        if ocr_text:
            result["sources"].append("ocr")

        # 3. VLM 综合判断（融合 YOLO + OCR 信息）
        result["vlm_judgment"] = self._vlm_classify(img, yolo_objects, ocr_text)
        result["sources"].append("vlm")

        # 4. 关键词快速分类
        result["page_type"] = self._classify_by_keywords(ocr_text, yolo_objects)

        return result

    def _detect_yolo(self, img) -> list:
        """YOLO11 通用物体检测"""
        yolo = self._get_yolo()
        if yolo is None:
            return []
        try:
            results = yolo(img, verbose=False)
            objects = []
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        cls_id = int(box.cls[0])
                        cls_name = r.names[cls_id]
                        conf = float(box.conf[0])
                        if conf > 0.3:
                            xyxy = box.xyxy[0].tolist()
                            cx = int((xyxy[0] + xyxy[2]) / 2)
                            cy = int((xyxy[1] + xyxy[3]) / 2)
                            objects.append({
                                "class": cls_name, "confidence": round(conf, 2),
                                "cx": cx, "cy": cy,
                                "w": int(xyxy[2] - xyxy[0]),
                                "h": int(xyxy[3] - xyxy[1])
                            })
            return objects[:30]
        except Exception as e:
            print(f"[YOLO] 检测异常: {e}")
            return []

    def _ocr_via_vlm(self, img) -> str:
        """通过 llama-server VLM 做 OCR 文字提取（禁用 thinking 模式）

        超时 15 秒，失败返回空字符串以允许关键词分类器降级工作。
        """
        import cv2, base64, json, urllib.request
        try:
            _, buf = cv2.imencode('.png', img)
            img_b64 = base64.b64encode(buf).decode()
            req = urllib.request.Request(
                f"{self._llama_url}/v1/chat/completions",
                data=json.dumps({
                    "messages": [{"role": "user", "content": [
                        {"type": "text", "text": "列出画面中所有可见的文字，每行一个。如果没有文字就说'无文字'。不要添加任何解释。"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                    ]}],
                    "max_tokens": 300,
                    "temperature": 0,
                    "chat_template_kwargs": {"enable_thinking": False}
                }).encode(),
                headers={"Content-Type": "application/json"}
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
            content = resp["choices"][0]["message"].get("content", "").strip()
            if not content:
                content = resp["choices"][0]["message"].get("reasoning_content", "").strip()
            return content
        except Exception as e:
            print(f"  [OCR] VLM 不可用: {e}")
            return ""

    def _vlm_classify(self, img, yolo_objects: list, ocr_text: str) -> str:
        """VLM 综合判断画面类型（融合 YOLO + OCR 信息）

        超时 15 秒，失败返回空字符串，由关键词分类器兜底。
        """
        import cv2, base64, json, urllib.request
        try:
            yolo_summary = "YOLO检测: " + (", ".join(
                f"{o['class']}({o['confidence']})" for o in yolo_objects[:10]
            ) if yolo_objects else "无检测")

            prompt = (
                f"OCR文字: {ocr_text[:300]}\n"
                f"{yolo_summary}\n\n"
                "请判断当前画面属于哪种类型, 只回答一个词: title(标题/登录画面), loading(加载中), "
                "world(探索世界), quest_panel(任务面板), settings(设置菜单), other(其他)"
            )

            _, buf = cv2.imencode('.png', img)
            img_b64 = base64.b64encode(buf).decode()
            req = urllib.request.Request(
                f"{self._llama_url}/v1/chat/completions",
                data=json.dumps({
                    "messages": [{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                    ]}],
                    "max_tokens": 100,
                    "temperature": 0,
                    "chat_template_kwargs": {"enable_thinking": False}
                }).encode(),
                headers={"Content-Type": "application/json"}
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
            content = resp["choices"][0]["message"].get("content", "").strip()
            if not content:
                content = resp["choices"][0]["message"].get("reasoning_content", "").strip()
            return content
        except Exception as e:
            print(f"  [VLM] 分类不可用: {e}")
            return ""

    def _classify_by_keywords(self, ocr_text: str, yolo_objects: list) -> str:
        """基于 OCR 关键词 + YOLO 快速分类（不依赖 VLM）"""
        text = ocr_text.lower()
        yolo_classes = [o["class"] for o in yolo_objects]

        # 标题/登录画面 — 有"点击进入"等提示文字
        if any(kw in text for kw in ["点击进入", "进入游戏", "开始游戏", "tap to start", "touch to start"]):
            return "title"
        # 标题画面 — YOLO 未检测到任何物体，且 OCR 无 HUD 文字
        if not yolo_objects and not text.strip():
            return "title"
        # 加载中
        if any(kw in text for kw in ["加载中", "loading", "now loading", "正在加载资源", "loading resource"]):
            return "loading"
        # 适龄提示画面（游戏启动前的合规页面）
        if any(kw in text for kw in ["适龄提示", "cadpa", "12+", "沪ICP"]):
            return "title"
        # 鹰角网络 logo 画面
        if any(kw in text for kw in ["鹰角网络", "hypergryph", "mountain contour", "恒形山"]):
            return "title"
        # 退出对话框
        if any(kw in text for kw in ["退出", "确认退出", "结束", "exit", "quit"]):
            return "exit_dialog"
        # 登出/超时
        if any(kw in text for kw in ["登出", "超时", "重新登录", "会话过期"]):
            return "logout_dialog"
        # 设置菜单
        if any(kw in text for kw in ["设置", "settings", "性能", "画面", "声音", "语言"]):
            return "settings"
        # 任务面板
        if any(kw in text for kw in ["每日任务", "每周任务", "任务", "日程", "daily", "weekly", "quest"]):
            return "quest_panel"
        # 探索世界 — YOLO 检测到 person（角色）+ 有探索/工业等 HUD 文字
        if "person" in yolo_classes and any(kw in text for kw in ["探索", "工业", "基地"]):
            return "world"
        # 探索世界 — 有角色（游戏内3D场景）
        if "person" in yolo_classes:
            return "world"
        # 探索世界 — 有顶部栏 HUD 文字
        if any(kw in text for kw in ["探索", "工业", "基地"]):
            return "world"
        # 按钮特征：有领取/确认相关文字
        if any(kw in text for kw in ["领取", "确认", "确定", "claim", "ok"]):
            return "quest_panel"
        return "unknown"


def main():
    print("=" * 60)
    print("真实设备反馈验证：_verify_screen_change")
    print("=" * 60)

    # 1. 连接设备
    adb_path = _adb_binary()
    dm = ADBDeviceManager(adb_path=adb_path, timeout=10)
    devices = dm.get_devices()
    if not devices:
        print("[FAIL] 未检测到 ADB 设备")
        return 1
    serial = devices[0].serial
    print(f"[OK] 设备: {serial}")

    detector = DeviceDetector(dm)
    device_type = str(detector.detect_device_type(serial))
    print(f"[OK] 设备类型: {device_type}")

    sc = ScreenCapture(adb_manager=dm)

    # 2. 初始化 ScreenAnalyzer
    try:
        screen_analyzer = ScreenAnalyzer()
        print("[OK] ScreenAnalyzer 初始化成功")
    except Exception as e:
        print(f"[FAIL] ScreenAnalyzer 加载失败: {e}")
        return 1

    # 3. 执行 3 轮截图 + 分析（模拟流程中的多次 _verify_screen_change）
    last_hash = None
    for i in range(1, 4):
        print(f"\n[轮次 {i}/3]")
        img = adb_screencap(serial)
        if not img:
            print("  [FAIL] 截图失败")
            continue

        h = hashlib.md5(img).hexdigest()[:8]
        if last_hash is None:
            print(f"  [基线] 首帧 hash={h[:4]}")
            last_hash = h
        elif last_hash == h:
            print(f"  [WARN] 画面无变化 ({h[:4]})")
        else:
            old = last_hash[:4]
            last_hash = h
            print(f"  [OK] 画面变化 {old}→{h[:4]}")

        # 多源分析（与 _verify_screen_change 一致）
        import numpy as np
        import cv2
        np_img = np.frombuffer(img, dtype=np.uint8)
        print(f"  [DEBUG] np_img.shape={np_img.shape}, dtype={np_img.dtype}")
        cv_img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        if cv_img is not None:
            rotated = cv2.rotate(cv_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            resized = cv2.resize(rotated, (1280, 720))
            analysis = screen_analyzer.analyze(resized)
            print(f"  [画面] YOLO={len(analysis['yolo_objects'])}obj "
                  f"OCR={analysis['ocr_text'][:60].replace(chr(10), ' ')}")
            if analysis.get("page_type") and analysis["page_type"] != "unknown":
                print(f"  [判断] {analysis['page_type']}")
            else:
                print("  [判断] unknown（未识别到明确页面类型）")
        else:
            print(f"  [FAIL] 图像解码失败, img_len={len(img)}")
            # 保存前 16 字节用于诊断
            print(f"  [DEBUG] header={img[:16]}")
            debug_path = PROJECT_ROOT / 'cache' / 'debug_screenshot.png'
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            with open(debug_path, 'wb') as f:
                f.write(img)
            print(f"  [DEBUG] raw screenshot saved to {debug_path}")

        # 轮次间等待，观察设备状态变化
        if i < 3:
            print("  等待 2 秒...")
            time.sleep(2)

    print("\n" + "=" * 60)
    print("验证完成：请根据以上输出判断 _verify_screen_change 是否符合预期")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
