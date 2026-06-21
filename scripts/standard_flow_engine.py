#!/usr/bin/env python3
"""
标准流执行引擎 - 基于JSON配置的可扩展标准流系统

特性:
1. 从JSON加载流程配置（可自定义）
2. 变量化坐标和参数
3. 自动截图记录（视频式序列）
4. 集成视觉subagent分析
5. 提示词自动优化循环
6. 支持本地2B模型默认运行

用法:
  python standard_flow_engine.py --flow daily_quest [--local-only] [--analyze-only]
"""

import sys, os, json, time, base64, hashlib, re, argparse, subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

sys.path.insert(0, str(PROJECT_ROOT / "3rd-party" / "python-packages"))

from core.adb_utils import ADB, adb_screencap
from core.game_coords import Coords
from core.page_analyzer import HighPrecisionPageAnalyzer
from core.vlm_client import VLMClient

# MaaFramework 触控适配器
from device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig, MAAFW_AVAILABLE


# ══════════════════════════════════════════════════════════════════
# 配置加载器
# ══════════════════════════════════════════════════════════════════

class FlowConfig:
    """标准流配置管理器"""

    def __init__(self, config_path: str = None):
        if config_path:
            self.config_path = config_path
        else:
            # 尝试多个位置
            possible_paths = [
                PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json",
                PROJECT_ROOT / "config" / "flows_config.json",
                PROJECT_ROOT / "flows_config.json",
            ]
            for p in possible_paths:
                if p.exists():
                    self.config_path = str(p)
                    break
            else:
                self.config_path = str(PROJECT_ROOT / "config" / "standard_flows" / "flows_config.json")
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] 加载配置失败: {e}")
            return {"flows": {}, "variables": {}, "execution": {}}

    def get_flow(self, flow_name: str) -> Optional[Dict[str, Any]]:
        return self._config.get("flows", {}).get(flow_name)

    def get_variable(self, key: str, default: Any = None) -> Any:
        parts = key.split('.')
        val = self._config.get("variables", {})
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                return default
        return val if val is not None else default

    def substitute_variables(self, text: str) -> str:
        """替换提示词中的变量占位符"""
        # 替换 {{coords.signin_entry}} 等
        def repl(match):
            var_key = match.group(1)
            return str(self.get_variable(var_key, match.group(0)))
        return re.sub(r'\{\{([^}]+)\}\}', repl, text)

    @property
    def execution_config(self) -> Dict[str, Any]:
        return self._config.get("execution", {})

    @property
    def all_flows(self) -> List[str]:
        return list(self._config.get("flows", {}).keys())

    def is_flow_enabled(self, flow_name: str) -> bool:
        flow = self.get_flow(flow_name)
        return flow.get("enabled", True) if flow else False


# ══════════════════════════════════════════════════════════════════
# 多源画面分析器 — MaaFw 金色元素 + OCR 文字 + VLM 综合判断
# ══════════════════════════════════════════════════════════════════

class ScreenAnalyzer:
    """多源画面分析器：YOLO 元素检测 + 金色元素 + OCR 文字 + VLM 综合判断"""

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
            # 如果 content 为空但有 reasoning_content，使用 reasoning_content
            if not content:
                content = resp["choices"][0]["message"].get("reasoning_content", "").strip()
            return content
        except Exception as e:
            print(f"  [OCR] VLM 不可用: {e}")
            return ""

    def _vlm_classify(self, img, yolo_objects: list, ocr_text: str) -> str:
        """VLM 综合判断画面类型（融合 YOLO + 金色元素 + OCR 信息）

        超时 15 秒，失败返回空字符串，由关键词分类器兜底。
        """
        import cv2, base64, json, urllib.request
        try:
            yolo_summary = "YOLO检测: " + (", ".join(
                f"{o['class']}({o['confidence']})" for o in yolo_objects[:10]
            ) if yolo_objects else "无检测")
            golden_summary = "金色元素：已弃用"  # 金色元素机制已移除

            prompt = (
                f"OCR文字: {ocr_text[:300]}\n"
                f"{yolo_summary}\n"
                f"{golden_summary}\n\n"
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
        """基于 OCR 关键词 + YOLO 快速分类（不依赖 VLM 和金色元素）"""
        text = ocr_text.lower()
        yolo_classes = [o["class"] for o in yolo_objects]

        # === 异常状态检测 ===

        # OCR 失效时的降级判断（VLM OCR 超时返回"无文字"）
        # 退出对话框：OCR 为空 + 有 button 元素
        if (not text.strip() or text == "无文字") and "button" in yolo_classes:
            return "exit_dialog"
        # 世界页面：OCR 为空 + 无 person
        if (not text.strip() or text == "无文字") and "person" not in yolo_classes:
            return "world"

        # 标题/登录画面 — 有"点击进入"等提示文字
        if any(kw in text for kw in ["点击进入", "进入游戏", "开始游戏", "tap to start", "touch to start"]):
            return "title"
        # 标题画面 — YOLO 未检测到 person（无角色），且 OCR 无 HUD 文字
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


# ══════════════════════════════════════════════════════════════════
# 屏幕差异检测工具（基于 MaaEnd 思路）
# ══════════════════════════════════════════════════════════════════

def screen_diff(img1, img2) -> int:
    """
    计算两张图片的差异像素数
    
    用于验证点击操作是否有效：
    - 差异 > 500000：画面变化大，操作有效
    - 差异 < 100000：画面几乎无变化，操作可能无效
    
    Args:
        img1: 操作前截图 (numpy array)
        img2: 操作后截图 (numpy array)
    
    Returns:
        差异像素数
    """
    import cv2, numpy as np
    if img1 is None or img2 is None:
        return 0
    if img1.shape != img2.shape:
        # 尺寸不同，resize 到相同
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
    d = cv2.absdiff(img1, img2)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, t = cv2.threshold(g, 30, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(t)


def close_exit_dialog_with_verify(adb, screen_analyzer, tap_func):
    """
    关闭退出对话框（多坐标尝试 + 画面验证）
    
    基于 MaaEnd 的 CancelButton 思路：
    1. 尝试多个候选坐标
    2. 通过画面变化验证点击是否有效
    3. 一旦成功立即返回
    
    Args:
        adb: ADB 实例
        screen_analyzer: ScreenAnalyzer 实例
        tap_func: 点击函数 (x, y) -> None
    
    Returns:
        (success, best_coord, best_diff)
    """
    import cv2, numpy as np, time
    from core.adb_utils import adb_screencap
    
    # 候选坐标：基于 1920x1080 分辨率，覆盖取消按钮的可能位置
    cancel_candidates = [
        (600, 750),   # 默认估计
        (550, 730),   # 偏左上
        (650, 770),   # 偏右下
        (580, 740),   # 偏左
        (620, 760),   # 偏右
        (540, 720),   # 更左上
        (660, 780),   # 更右下
    ]
    
    best_coord = None
    best_diff = 0
    
    for i, (cx, cy) in enumerate(cancel_candidates):
        # 截图
        before = adb_screencap()
        if before is None:
            continue
        before_img = cv2.imdecode(np.frombuffer(before, np.uint8), cv2.IMREAD_COLOR)
        if before_img is None:
            continue
        
        # 验证当前是否仍在退出对话框
        before_rotated = cv2.rotate(before_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        before_resized = cv2.resize(before_rotated, (1280, 720))
        analysis = screen_analyzer.analyze(before_resized)
        if analysis["page_type"] != "exit_dialog":
            print(f"    [跳过] 当前不是退出对话框 ({analysis['page_type']})")
            return True, best_coord, best_diff
        
        print(f"    [尝试 {i+1}/{len(cancel_candidates)}] 点击 ({cx}, {cy})...", end=" ")
        
        # 点击
        tap_func(cx, cy)
        time.sleep(1.5)
        
        # 截图验证
        after = adb_screencap()
        if after is None:
            print("截图失败")
            continue
        after_img = cv2.imdecode(np.frombuffer(after, np.uint8), cv2.IMREAD_COLOR)
        if after_img is None:
            print("截图解码失败")
            continue
        
        # 计算画面变化
        diff = screen_diff(before_img, after_img)
        
        # 验证是否关闭成功
        after_rotated = cv2.rotate(after_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        after_resized = cv2.resize(after_rotated, (1280, 720))
        analysis2 = screen_analyzer.analyze(after_resized)
        
        print(f"diff={diff:,} {analysis['page_type']}->{analysis2['page_type']}")
        
        # 记录最佳坐标
        if diff > best_diff:
            best_diff = diff
            best_coord = (cx, cy)
        
        # 判断是否成功关闭
        # 条件 1：画面变化大（>50 万像素）
        # 条件 2：不再是退出对话框
        if diff > 500000 and analysis2["page_type"] != "exit_dialog":
            print(f"    [成功] 对话框已关闭")
            return True, (cx, cy), diff
        elif diff > 200000:
            # 画面有一定变化，假设已关闭
            print(f"    [可能成功] 画面有变化，假设已关闭")
            return True, (cx, cy), diff
        
        # 恢复退出对话框状态（按返回）
        adb.back()
        time.sleep(1)
    
    print(f"    [失败] 所有坐标尝试失败 (best_diff={best_diff:,})")
    return False, best_coord, best_diff


# ══════════════════════════════════════════════════════════════════
# 流程记录器（增强版）
# ══════════════════════════════════════════════════════════════════

@dataclass
class StepRecord:
    """单步执行记录"""
    step_id: int
    step_key: str
    action: str
    description: str
    prompt: str
    decision: str
    screenshot_path: str
    timestamp: float
    success: bool = True
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class FlowRecorder:
    """增强流程记录器 - 自动截图序列"""

    def __init__(self, session_name: str = "standard_flow", record_video: bool = True, device_addr: str = None):
        self.session_name = session_name
        self.record_video = record_video
        self.device_addr = device_addr
        self.steps: List[StepRecord] = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.session_dir = str(PROJECT_ROOT / "cache" / f"flow_{session_name}_{timestamp}")
        self.screenshots_dir = os.path.join(self.session_dir, "screenshots")
        os.makedirs(self.screenshots_dir, exist_ok=True)
        print(f"[recorder] 会话目录: {self.session_dir}")
        print(f"[recorder] 截图目录: {self.screenshots_dir}")

    def capture_screenshot(self, step_id: int, action: str) -> str:
        """捕获并保存截图"""
        if not self.record_video:
            return ""

        img = adb_screencap(serial=self.device_addr) if self.device_addr else adb_screencap()
        ts = time.time()
        h = hashlib.md5(img).hexdigest()[:8] if img and len(img) > 100 else "none"
        fname = f"step_{step_id:03d}_{action}_{ts:.0f}_{h}.png"
        fpath = os.path.join(self.screenshots_dir, fname)

        if img and len(img) > 100:
            with open(fpath, "wb") as f:
                f.write(img)
        return fpath

    def record_step(self, step_id: int, step_key: str, action: str, description: str,
                    prompt: str, decision: str, success: bool = True,
                    error: str = "", metadata: Dict = None) -> StepRecord:
        """记录单步执行"""
        screenshot = self.capture_screenshot(step_id, action) if self.record_video else ""
        record = StepRecord(
            step_id=step_id,
            step_key=step_key,
            action=action,
            description=description,
            prompt=prompt,
            decision=decision,
            screenshot_path=screenshot,
            timestamp=time.time(),
            success=success,
            error=error,
            metadata=metadata or {}
        )
        self.steps.append(record)

        status = "OK" if success else "FAIL"
        print(f"  [{status}] step {step_id}: {action} - {description[:60]}")
        return record

    def export_report(self) -> Dict[str, Any]:
        """导出完整报告"""
        return {
            "session": self.session_name,
            "total_steps": len(self.steps),
            "success_count": sum(1 for s in self.steps if s.success),
            "fail_count": sum(1 for s in self.steps if not s.success),
            "duration_seconds": self.steps[-1].timestamp - self.steps[0].timestamp if len(self.steps) >= 2 else 0,
            "steps": [
                {
                    "step_id": s.step_id,
                    "step_key": s.step_key,
                    "action": s.action,
                    "description": s.description,
                    "prompt_preview": s.prompt[:200],
                    "decision_preview": s.decision[:200],
                    "screenshot": s.screenshot_path,
                    "success": s.success,
                    "error": s.error,
                    "metadata": s.metadata,
                }
                for s in self.steps
            ],
        }

    def get_analysis_payload(self) -> List[Dict[str, Any]]:
        """生成给视觉subagent的分析载荷"""
        payload = []
        for s in self.steps:
            img_data = None
            if s.screenshot_path and os.path.exists(s.screenshot_path):
                with open(s.screenshot_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode()
            payload.append({
                "step": s.step_id,
                "step_key": s.step_key,
                "action": s.action,
                "description": s.description,
                "prompt": s.prompt,
                "decision": s.decision,
                "success": s.success,
                "error": s.error,
                "metadata": s.metadata,
                "screenshot_base64": img_data,
            })
        return payload


# ══════════════════════════════════════════════════════════════════
# 本地2B模型引擎（复用test_standard_flow.py的实现）
# ══════════════════════════════════════════════════════════════════

class Local2BEngine:
    """本地2B模型推理接口（使用 llama-server.exe 子进程）"""

    def __init__(self):
        self._engine = None
        self._model_name = None
        self._model_path = None
        self._loaded = False
        self._using_api = False
        self._api_client = None
        self._server_process = None
        self._server_port = 8080
        self._model_type = None

    def _find_llama_server(self) -> str:
        project_root = Path(__file__).resolve().parent.parent
        candidates = [
            project_root / "3rd-party" / "llama-cpp" / "llama-server.exe",
            Path("C:/Users/xray/Desktop/workflow/llamacpp/llamacpp-cuda124/llama-server.exe"),
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return "llama-server"

    def _find_model(self) -> tuple[Optional[str], Optional[str]]:
        from core.local_inference.model_manager import ModelManager
        manager = ModelManager()
        available = manager.get_available_models()
        if not available:
            return None, None
        for info in available:
            if info.name == "qwen3.5-4b-ud-q4_k_xl" and info.local_path and Path(info.local_path).exists():
                return info.name, str(info.local_path)
        for info in available:
            if info.name == "qwen3.5-2b-qwen3.6-plus-distilled-f16" and info.local_path and Path(info.local_path).exists():
                return info.name, str(info.local_path)
        for info in available:
            if info.local_path and Path(info.local_path).exists():
                return info.name, str(info.local_path)
        return None, None

    def _start_server(self, model_path: str) -> bool:
        server_exe = self._find_llama_server()
        gpu_layers = self._calc_gpu_layers()

        cmd = [
            server_exe,
            "--model", model_path,
            "--port", str(self._server_port),
            "--host", "127.0.0.1",
            "--ctx-size", "8192",
            "--n-gpu-layers", str(gpu_layers),
            "--parallel", "1",
            "--no-webui",
        ]
        mmproj = Path(model_path).parent / "mmproj-F16.gguf"
        if mmproj.exists():
            cmd += ["--mmproj", str(mmproj)]
        import subprocess
        try:
            self._server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            try:
                self._server_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except Exception as e:
                print(f"[2b] 启动 llama-server 失败: {e}")
                return False
        import time
        for _ in range(60):
            time.sleep(1)
            try:
                import urllib.request
                req = urllib.request.urlopen(f"http://127.0.0.1:{self._server_port}/health", timeout=2)
                if req.status == 200:
                    print(f"[2b] llama-server 已就绪 (port {self._server_port}, n-gpu-layers={gpu_layers})")
                    return True
            except Exception:
                pass
            if self._server_process.poll() is not None:
                _, stderr = self._server_process.communicate()
                print(f"[2b] llama-server 退出: {stderr.decode('utf-8', errors='replace')[:500]}")
                return False
        print("[2b] llama-server 启动超时")
        return False

    def _calc_gpu_layers(self) -> int:
        """根据可用显存动态计算GPU层数"""
        try:
            r = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.free,memory.total', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=10
            )
            parts = r.stdout.strip().split(',')
            free_mib = int(parts[0].strip())
            total_mib = int(parts[1].strip())
            free_gb = free_mib / 1024
            print(f"[GPU] 可用显存: {free_gb:.1f}GB / {total_mib/1024:.0f}GB")

            # 预留3GB给游戏渲染，剩余用于模型
            available = max(0, free_gb - 3.0)
            # 模型约3GB，每层约占30MB
            if available >= 8:
                return 99
            elif available >= 6:
                return 70
            elif available >= 4:
                return 40
            elif available >= 2:
                return 15
            else:
                return 0
        except Exception:
            return 10

    def load(self) -> bool:
        if self._loaded:
            return True

        # Check if server already running
        import urllib.request
        try:
            req = urllib.request.urlopen(f"http://127.0.0.1:{self._server_port}/health", timeout=3)
            if req.status == 200:
                print(f"[2b] llama-server 已在运行 (port {self._server_port})")
                self._server_process = True  # sentinel - not None, triggers API path
                self._loaded = True
                self._using_api = False
                return True
        except Exception:
            pass

        model_name, model_path = self._find_model()
        if not model_path:
            print("[2b] 无本地模型可用，回退到 API")
            return self._load_api()

        print(f"[2b] 尝试启动本地模型服务: {model_name}")
        if self._start_server(model_path):
            self._model_name = model_name
            self._model_path = model_path
            self._loaded = True
            self._using_api = False
            return True

        print("[2b] 本地服务启动失败，回退到 API")
        return self._load_api()

    def _load_api(self) -> bool:
        try:
            from openai import OpenAI
            self._api_client = OpenAI(
                base_url='https://ms-ens-6d80e112-9e63.api-inference.modelscope.cn/v1',
                api_key='ms-4a16f9dc-5d45-48d7-874d-2f5a7f25bf2d',
            )
            self._using_api = True
            self._loaded = True
            print("[2b] ModelScope API 已就绪 (gemma-4-E2B-it)")
            return True
        except ImportError:
            print("[2b] openai 库未安装，无法使用API")
            return False
        except Exception as e:
            print(f"[2b] API初始化失败: {e}")
            return False

    def generate(self, prompt: str, system_prompt: str = "",
                  max_tokens: int = 512, temperature: float = 0.3,
                  image_base64: str = None) -> str:
        if not self._loaded:
            if not self.load():
                return '{"error": "模型加载失败，本地服务和API均不可用"}'

        if self._server_process is not None and not self._using_api:
            try:
                from openai import OpenAI
                client = OpenAI(base_url=f"http://127.0.0.1:{self._server_port}/v1", api_key="none")
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                user_content = []
                if image_base64:
                    user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}})
                user_content.append({"type": "text", "text": prompt})
                messages.append({"role": "user", "content": user_content})
                resp = client.chat.completions.create(
                    model="local-model",
                    messages=messages,
                    max_tokens=max(max_tokens, 512),
                    temperature=temperature,
                )
                msg = resp.choices[0].message
                content = (msg.content or "").strip()
                reasoning = (getattr(msg, 'reasoning_content', None) or "").strip()
                if not content and reasoning:
                    return reasoning
                return content
            except Exception as e:
                return '{"error": "本地推理失败: %s"}' % e
        else:
            return self._api_generate(prompt, system_prompt, max_tokens, temperature)

    def _api_generate(self, prompt: str, system_prompt: str = "",
                      max_tokens: int = 512, temperature: float = 0.3) -> str:
        if not self._api_client:
            return '{"error": "API客户端未初始化"}'
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = self._api_client.chat.completions.create(
                model='AtomicChat/gemma-4-E2B-it-assistant-GGUF',
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False,
            )
            return response.choices[0].message.content
        except Exception as e:
            return '{"error": "API调用失败: %s"}' % e

    def is_local(self) -> bool:
        return not self._using_api

    def __del__(self):
        if self._server_process is not None:
            try:
                self._server_process.terminate()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════
# 视觉subagent分析器（使用SubAgentQwen）
# ══════════════════════════════════════════════════════════════════

class VisualAnalyzer:
    """使用视觉subagent分析执行记录"""

    def __init__(self, model: str = None):
        self.model = model
        self._agent = None

    def _get_agent(self):
        if self._agent is None:
            # 尝试多个路径
            try:
                from skills.subagent_qwen.subagent_client import SubAgentQwen
            except ImportError:
                try:
                    from .skills.subagent_qwen.subagent_client import SubAgentQwen
                except ImportError:
                    # 直接加载模块
                    import importlib.util
                    spec = importlib.util.spec_from_file_location(
                        "subagent_client",
                        PROJECT_ROOT / ".kilo" / "skills" / "subagent-qwen" / "subagent_client.py"
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    SubAgentQwen = module.SubAgentQwen
            self._agent = SubAgentQwen()
        return self._agent

    def analyze_execution(self, recorder: FlowRecorder, flow_name: str) -> Dict[str, Any]:
        """分析执行记录，返回优化建议"""
        agent = self._get_agent()
        payload = recorder.get_analysis_payload()

        if not payload:
            return {"error": "无步骤可分析"}

        analysis_prompt = f"""你是游戏自动化质量分析专家。分析以下标准流「{flow_name}」的{len(payload)}步执行记录。

对每一步，评估:
1. 截图画面是否与预期相符
2. 模型决策是否正确
3. 执行是否成功
4. 失败原因（如有）

返回JSON:
{{
  "overall_assessment": "整体评价",
  "success_rate": 0.0,
  "step_analyses": [
    {{
      "step": 序号,
      "step_key": "步骤键名",
      "action": "动作名",
      "screen_correct": true/false,
      "decision_correct": true/false,
      "execution_success": true/false,
      "issues": ["问题1", "问题2"],
      "suggestion": "具体优化建议"
    }}
  ],
  "bottlenecks": ["主要卡点"],
  "prompt_optimizations": {{
    "step_key": "优化后的完整提示词"
  }},
  "coordinate_adjustments": {{
    "step_key": {{"x": 新X, "y": 新Y}}  // 如需调整坐标
  }}
}}
"""

        system_prompt = "你是游戏自动化QA专家。仔细分析每帧截图与执行记录，给出结构化反馈。"

        # 构建消息（采样截图以避免token超限）
        messages = [{"role": "system", "content": system_prompt}]
        user_content = [{"type": "text", "text": analysis_prompt}]

        max_images = min(len(payload), 15)
        step_indices = list(range(0, len(payload), max(1, len(payload) // max_images)))[:max_images]

        for idx in step_indices:
            step = payload[idx]
            if step.get("screenshot_base64"):
                user_content.append({
                    "type": "text",
                    "text": f"\n--- Step {step['step']}: {step['step_key']} ({step['action']}) ---\n"
                            f"描述: {step['description']}\n"
                            f"提示词: {step['prompt'][:150]}...\n"
                            f"决策: {step['decision'][:150]}...\n"
                            f"成功: {step['success']}\n"
                })
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{step['screenshot_base64']}"}
                })

        messages.append({"role": "user", "content": user_content})

        try:
            result = agent.analyze(
                task="分析标准流执行质量并提供优化建议",
                system_prompt=None,
                model=self.model,
                temperature=0.1,
                max_tokens=8192,
                context={"analysis_prompt": analysis_prompt, "total_steps": len(payload)}
            )

            if result["success"]:
                analysis_text = result["analysis"]
                json_match = re.search(r'\{[\s\S]*\}', analysis_text)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group())
                        print(f"[analyzer] 收到结构化分析结果")
                        return parsed
                    except json.JSONDecodeError as e:
                        print(f"[analyzer] JSON解析失败: {e}")
                        return {"raw_analysis": analysis_text}
                return {"raw_analysis": analysis_text}
            else:
                return {"error": f"分析失败: {result.get('error')}"}
        except Exception as e:
            return {"error": f"分析异常: {e}"}


# ══════════════════════════════════════════════════════════════════
# 标准流执行器
# ══════════════════════════════════════════════════════════════════

class StandardFlowExecutor:
    """基于配置的标准流执行器"""

    def __init__(self, config: FlowConfig, model_engine: Local2BEngine = None, recorder: FlowRecorder = None, 
                 device_addr: str = "localhost:16512", adb_path: str = None):
        self.config = config
        self.model = model_engine or Local2BEngine()
        self.recorder = recorder
        self.device_addr = device_addr
        self.adb_path = adb_path or str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe")
        self.adb = ADB(device_addr)
        self._stop_requested = False

        # 初始化 MaaFramework 触控（所有触控必须通过 MaaFw 而非直接 ADB）
        self._maafw = None
        if MAAFW_AVAILABLE:
            try:
                maafw_config = MaaFwTouchConfig(
                    adb_path=self.adb_path,
                    address=device_addr,
                    screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,
                    input_methods=3,  # MaaTouch 模式
                )
                executor = MaaFwTouchExecutor(maafw_config)
                if executor.connect():
                    self._maafw = executor
                    print(f"[MaaFw] 触控初始化成功，分辨率: {executor.get_resolution()}")
                else:
                    print("[MaaFw] 连接失败，回退到 ADB 直接触控")
            except Exception as e:
                print(f"[MaaFw] 初始化异常: {e}，回退到 ADB 直接触控")
        else:
            print("[MaaFw] MaaFramework 未安装，使用 ADB 直接触控")

        # 初始化画面分析器
        self.screen_analyzer = ScreenAnalyzer(maafw_executor=self._maafw)
        self.page_analyzer = HighPrecisionPageAnalyzer()
        self.vlm_client = VLMClient({"vlm_mode": "local"})

    def stop(self):
        self._stop_requested = True

    # ── MaaFw 触控路由 ──────────────────────────────────────
    def _tap(self, x: int, y: int) -> bool:
        """触控点击：使用 MaaFw（优先），回退 ADB subprocess"""
        if self._maafw and self._maafw.connected:
            return self._maafw.click(x, y)
        import subprocess
        try:
            r = subprocess.run(
                [self.adb_path, "-s", self.device_addr, "shell", "input", "tap", str(x), str(y)],
                capture_output=True, timeout=5
            )
            return r.returncode == 0
        except Exception:
            return False

    def _swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """触控滑动：优先 MaaFw，回退 ADB"""
        if self._maafw and self._maafw.connected:
            return self._maafw.swipe(x1, y1, x2, y2, duration)
        from core.adb_utils import adb_swipe
        return adb_swipe(x1, y1, x2, y2, duration)

    def _back(self) -> bool:
        """返回键：MaaFw keyevent(4)（优先），回退 ADB subprocess"""
        if self._maafw and self._maafw.connected:
            job = self._maafw.post_keyevent(4)
            if job is not None:
                job.wait()
                return job.succeeded
        import subprocess
        try:
            r = subprocess.run(
                [self.adb_path, "-s", self.device_addr, "shell", "input", "keyevent", "4"],
                capture_output=True, timeout=5
            )
            return r.returncode == 0
        except Exception:
            return False

    def _extract_action(self, analysis: str, expected_action: str) -> tuple[str, Optional[list], Dict]:
        """从模型分析文本中提取动作（不依赖JSON）"""
        act = {"action": "none", "coords": None, "page": "other", "reason": ""}

        # 弹窗检测
        popup_texts = ['自动登出', '长时间没有操作', '维护', '断开连接', '提示', '通知']
        confirm_texts = ['确认', '确定', 'OK', 'OK', '是']
        cancel_texts = ['取消', '关闭', 'Cancel', '返回']

        has_popup = any(p in analysis for p in popup_texts)
        has_confirm = any(c in analysis for c in confirm_texts)
        has_cancel = any(c in analysis for c in cancel_texts)

        if has_popup and has_confirm:
            act["action"] = "tap"
            act["coords"] = [540, 960]
            act["page"] = "popup"
            act["reason"] = "弹窗确认"
            return act["action"], act["coords"], act

        # 页面类型检测
        if any(w in analysis for w in ['世界地图', '探索', '小地图', 'minimap', 'world_map']):
            act["page"] = "world_map"
        elif any(w in analysis for w in ['任务', 'quest', '委托', '日常', '周常']):
            act["page"] = "quest_ui"
        elif any(w in analysis for w in ['主菜单', '主页', 'main_menu', 'signin', '签到']):
            act["page"] = "main_menu"
        elif any(w in analysis for w in ['加载', 'loading', 'NOW LOADING']):
            act["page"] = "loading_screen"

        # 提取坐标
        import re
        coord_match = re.search(r'\((\d{2,4})[,，\s]+(\d{2,4})\)', analysis)
        if coord_match:
            act["coords"] = [int(coord_match.group(1)), int(coord_match.group(2))]
        else:
            coord_match = re.search(r'(?:坐标|位置|按钮).*?(\d{2,4})[,，\s]+(\d{2,4})', analysis)
            if coord_match:
                act["coords"] = [int(coord_match.group(1)), int(coord_match.group(2))]

        # 根据预期动作决定实际动作
        if expected_action == "detect_screen":
            act["action"] = "none"
        elif expected_action == "check":
            act["action"] = "none"
        elif expected_action == "back":
            act["action"] = "back"
        elif expected_action == "claim":
            if act.get("page") == "quest_ui":
                act["action"] = "claim"
                if not act["coords"]:
                    act["coords"] = [960, 540]
            else:
                act["action"] = "none"
        elif expected_action == "navigate":
            if act.get("page") == "world_map":
                act["action"] = "tap"
                act["coords"] = [82, 45]
            elif act.get("page") == "main_menu":
                act["action"] = "tap"
                act["coords"] = [540, 360]
            else:
                act["action"] = "back"

        return act["action"], act["coords"], act

    def _extract_action_fallback(self, analysis: str, expected_action: str, retry_count: int) -> tuple[str, Optional[list], Dict]:
        """备选动作方案（当主方案无效时）"""
        fallback = [
            ["tap", [498, 690], {"action": "tap", "page": "popup", "reason": "备选位置1"}],
            ["tap", [540, 700], {"action": "tap", "page": "popup", "reason": "备选位置2"}],
            ["tap", [540, 660], {"action": "tap", "page": "popup", "reason": "备选位置3"}],
            ["back", None, {"action": "back", "page": "popup", "reason": "返回键"}],
            ["wait", None, {"action": "wait", "page": "loading", "reason": "等待"}],
        ]
        idx = min(retry_count, len(fallback) - 1)
        return fallback[idx][0], fallback[idx][1], fallback[idx][2]

    def _restart_game(self):
        """重启游戏 - 使用 MaaFw stop_app + start_app"""
        if self._maafw and self._maafw.connected:
            self._maafw.stop_app("com.hypergryph.endfield")
            time.sleep(3)
            self._maafw.start_app("com.hypergryph.endfield")
        else:
            adb_path = str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe")
            subprocess.run([adb_path, "-s", f'{device_addr}', "shell", "am", "force-stop", "com.hypergryph.endfield"],
                          capture_output=True, timeout=10)
            time.sleep(3)
            subprocess.run([adb_path, "-s", f'{device_addr}', "shell",
                          "monkey", "-p", "com.hypergryph.endfield",
                          "-c", "android.intent.category.LAUNCHER", "1"],
                          capture_output=True, timeout=15)
        time.sleep(30)
        for _ in range(3):
            self._tap(540, 960)
            time.sleep(2)

    def execute_flow(self, flow_name: str) -> bool:
        """执行指定标准流 — 每步动作后依据画面分析验证结果"""
        flow_config = self.config.get_flow(flow_name)
        if not flow_config:
            print(f"[ERROR] 未找到流程: {flow_name}")
            return False

        steps = flow_config.get("steps", [])
        nav_coords = self.config.get_variable("nav_coords", {})

        print(f"\n{'='*60}")
        print(f"执行: {flow_name} - {flow_config.get('description','')}")
        print(f"步骤: {len(steps)}")
        print(f"{'='*60}\n")

        self._stop_requested = False
        all_success = True

        for i, step_cfg in enumerate(steps):
            if self._stop_requested:
                break

            step_id = i + 1
            step_action = step_cfg.get("action", "none")
            step_desc = step_cfg.get("desc", str(step_cfg))

            print(f"\n[步骤 {step_id}/{len(steps)}] {step_desc}")
            print("-" * 50)

            # === navigate: 精确坐标导航 ===
            if step_action == "navigate":
                target = step_cfg.get("target", "explore")
                # "explore"/"world" = 回到世界地图，用返回键回退
                if target in ("explore", "world", "world_map"):
                    print(f"  [NAV] 导航到 {target}: 连续按返回键回退到世界")
                    for _ in range(6):
                        self._back()
                        self.adb.wait(1.5)
                    self._verify_screen_change()
                    success = True
                else:
                    coords = nav_coords.get(target, [540, 360])
                    print(f"  [NAV] 导航到 {target}: {coords}")
                    self._tap(coords[0], coords[1])
                    self.adb.wait(step_cfg.get("wait", 2))
                    self._verify_screen_change()
                    success = True

            # === tap: 点击指定坐标 ===
            elif step_action == "tap":
                coords_raw = step_cfg.get("coords")
                if isinstance(coords_raw, str) and "{{" in coords_raw:
                    var_key = coords_raw.strip("{}").strip()
                    coords = self.config.get_variable(var_key, nav_coords.get(step_cfg.get("target",""), [540, 360]))
                elif isinstance(coords_raw, list):
                    coords = coords_raw
                else:
                    coords = nav_coords.get(step_cfg.get("target",""), [540, 360])
                print(f"  [TAP] 点击 {coords}")
                self._tap(coords[0], coords[1])
                self.adb.wait(step_cfg.get("wait", 2))
                self._verify_screen_change()
                success = self._verify_tap_result(step_cfg, coords)

            # === claim: 一键领取 ===
            elif step_action == "claim":
                coords = nav_coords.get("claim_all", [960, 540])
                print(f"  [CLAIM] 领取: {coords}")
                self._tap(coords[0], coords[1])
                self.adb.wait(2)
                self._verify_screen_change()
                success = True

            # === check: 高精度页面分析（使用新分析器）===
            elif step_action == "check":
                img_bytes = adb_screencap()
                if img_bytes:
                    import numpy as np
                    import cv2
                    np_img = np.frombuffer(img_bytes, dtype=np.uint8)
                    cv_img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
                    if cv_img is not None:
                        result = self.page_analyzer.analyze(cv_img)
                        page_type = result["page_type"]
                        confidence = result["confidence"]
                        features = result["features"]
                        print(f"  [CHECK] 页面={page_type} 置信度={confidence:.2f} "
                              f"left_bar={features.get('left_bar_brightness', 0):.0f} "
                              f"green={features.get('green_pixels_top_right', 0):.0f}")
                        
                        # 检查 expect 字段
                        expected = step_cfg.get("expect")
                        if expected:
                            if page_type == expected or (expected == "world" and page_type in ("world", "world_transition")):
                                print(f"  [OK] 页面匹配预期: {expected}")
                                success = True
                            else:
                                print(f"  [WARN] 页面不匹配预期: 期望={expected} 实际={page_type}")
                                success = False
                        else:
                            success = True
                    else:
                        success = False
                else:
                    success = False

            # === back: 返回 ===
            elif step_action == "back":
                print(f"  [BACK] 返回键")
                self._back()
                self.adb.wait(2)
                self._verify_screen_change()
                success = True

            # === swipe: 滑动/移动 ===
            elif step_action == "swipe":
                start_coords = step_cfg.get("start", [200, 1700])
                end_coords = step_cfg.get("end", [200, 1400])
                duration_ms = step_cfg.get("duration", 1000)
                print(f"  [SWIPE] {start_coords} -> {end_coords} ({duration_ms}ms)")
                self._swipe(start_coords[0], start_coords[1],
                           end_coords[0], end_coords[1], duration_ms)
                self.adb.wait(1)
                self._verify_screen_change()
                success = True

            # === long_press: 长按 ===
            elif step_action == "long_press":
                coords = step_cfg.get("coords", [540, 960])
                duration_ms = step_cfg.get("duration", 2000)
                print(f"  [LONG_PRESS] {coords} ({duration_ms}ms)")
                if self._maafw and self._maafw.connected:
                    self._maafw.long_press(coords[0], coords[1], duration_ms)
                else:
                    # ADB 回退：原地 swipe 模拟长按
                    from core.adb_utils import adb_swipe
                    adb_swipe(coords[0], coords[1], coords[0], coords[1], duration_ms)
                self.adb.wait(1)
                self._verify_screen_change()
                success = True

            # === wait: 等待指定时间 ===
            elif step_action == "wait":
                duration = step_cfg.get("duration", step_cfg.get("wait", 2))
                print(f"  [WAIT] 等待 {duration} 秒")
                self.adb.wait(duration)
                success = True

            else:
                print(f"  [WARN] 未知动作类型：{step_action}")
                success = True

            # 记录
            if self.recorder:
                self.recorder.record_step(
                    step_id=step_id, step_key=step_cfg.get("id",""),
                    action=step_action, description=step_desc,
                    prompt="", decision=f"action={step_action}",
                    success=success,
                    metadata={"step": step_cfg}
                )

            status = "OK" if success else "FAIL"
            print(f"  [{status}]")

            # 更新全局成功状态
            all_success = all_success and success

            self.adb.wait(1)

        print(f"\n流程完成: {'成功' if all_success else '有失败步骤'}\n")
        return all_success

    def _verify_screen_change(self):
        """验证画面变化 + 多源页面类型识别"""
        img = adb_screencap()
        if img:
            import numpy as np
            h = hashlib.md5(img).hexdigest()[:8]
            if self._last_hash is None:
                self._last_hash = h
            elif self._last_hash == h:
                print(f"  [WARN] 画面无变化 ({h[:4]})")
            else:
                old = self._last_hash[:4]
                self._last_hash = h
                print(f"  [OK] 画面变化 {old}→{h[:4]}")

            # 多源分析 (需旋转到横屏)
            np_img = np.frombuffer(img, dtype=np.uint8)
            import cv2
            cv_img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
            if cv_img is not None:
                # 旋转：1920x1080 竖屏 → 1280x720 横屏
                rotated = cv2.rotate(cv_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                resized = cv2.resize(rotated, (1280, 720))
                analysis = self.screen_analyzer.analyze(resized)
                print(f"  [画面] YOLO={len(analysis['yolo_objects'])}obj "
                      f"btn "
                      f"OCR={analysis['ocr_text'][:60].replace(chr(10),' ')}")
                if analysis['page_type'] != 'unknown':
                    print(f"  [判断] {analysis['page_type']}")

    def _analyze_page(self) -> tuple:
        """截图并分析当前画面，返回 (page_type, confidence, features)"""
        import numpy as np
        import cv2
        img = adb_screencap()
        if not img:
            return "unknown", 0.0, {}
        np_img = np.frombuffer(img, dtype=np.uint8)
        cv_img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        if cv_img is None:
            return "unknown", 0.0, {}

        result = self.page_analyzer.analyze(cv_img)
        return result["page_type"], result["confidence"], result["features"]

    def _verify_tap_result(self, step_cfg: dict, coords: list) -> bool:
        """验证 tap 后是否到达预期页面，若路由错误则恢复重试"""
        page, confidence, features = self._analyze_page()
        left_bar = features.get('left_bar_brightness', 0)
        green = features.get('green_pixels_top_right', 0)
        print(f"  [验证] 页面={page} 置信度={confidence:.2f} left_bar={left_bar:.0f} green={green:.0f}")

        # 用户指定的预期页面
        expect = step_cfg.get("expect", "")

        # 自动推断预期页面
        if not expect:
            step_id = step_cfg.get("id", "")
            desc = step_cfg.get("desc", "")
            if any(kw in step_id.lower() for kw in ["quest", "task", "daily", "weekly"]):
                expect = "quest_panel"
            elif any(kw in desc for kw in ["任务", "面板", "每日", "每周"]):
                expect = "quest_panel"
            elif any(kw in desc for kw in ["菜单", "menu"]):
                expect = "world"

        # 页面匹配判断
        if not expect:
            return True
        if page == expect:
            return True
        if expect == "world" and page in ("world", "world_transition"):
            return True
        if expect == "quest_panel" and page in ("quest_panel",):
            return True

        # ── 不匹配：低置信度时尝试 VLM，否则简单恢复 ──
        print(f"  [路由错误] 预期={expect} 实际={page}，尝试恢复...")

        # 退出对话框恢复
        if page == "exit_dialog":
            print("  [恢复] 退出对话框，尝试关闭...")
            cancel_candidates = [(600, 750), (540, 720), (660, 780), (580, 730), (620, 770)]
            for cx, cy in cancel_candidates:
                self._tap(cx, cy)
                self.adb.wait(1.5)
                p, _, _ = self._analyze_page()
                if p != "exit_dialog":
                    print(f"  [恢复] 关闭成功，当前={p}")
                    if p == expect:
                        return True
                    break

        # 触发VLM决策恢复（仅当OpenCV不确定时）
        if confidence < 0.5 or page == "unknown":
            img = adb_screencap()
            if img:
                cv_img = cv2.imdecode(np.frombuffer(img, np.uint8), cv2.IMREAD_COLOR)
                if cv_img is not None:
                    ctx = {"expected_page": expect, "step_desc": step_cfg.get("desc", ""),
                           "last_action": f"点击 ({coords[0]},{coords[1]})"}
                    vlm = self.vlm_client.decide_action(cv_img,
                        {"page_type": page, "confidence": confidence, "features": features}, ctx)
                    print(f"  [VLM恢复] 建议={vlm.get('suggested_action','?')} → {vlm.get('reason','')[:80]}")
                    if vlm.get("suggested_action") == "back":
                        self._back()
                        self.adb.wait(2)

        # 通用恢复：按两次返回
        for _ in range(3):
            self._back()
            self.adb.wait(0.5)
        return False

    def _recover_from_stuck(self, page: str):
        """从卡页状态恢复（增强版 - 处理自动登出等异常弹窗）"""
        print(f"[PATROL] 恢复操作: 尝试离开 {page}")
        try:
            if page in ("loading_screen",):
                print("  [PATROL] 等待加载完成...")
                time.sleep(5)
                return

            # 自动登出弹窗特殊处理：点击确认按钮
            print("  [PATROL] 尝试点击确认/关闭按钮...")
            confirm_btns = [(540, 960), (640, 660), (540, 700), (400, 660)]
            for x, y in confirm_btns:
                self._tap(x, y)
                time.sleep(1)

            # 按返回键
            print("  [PATROL] 按返回键...")
            self._back()
            time.sleep(1)

            # 再点一次屏幕中央
            print("  [PATROL] 点击屏幕中央...")
            self._tap(540, 500)
            time.sleep(1)

        except Exception as e:
            print(f"  [PATROL] 恢复操作失败: {e}")

    def _parse_and_execute(self, decision_text: str, expected_action: str) -> tuple[bool, str, Optional[Dict]]:
        """解析决策JSON并执行动作"""
        try:
            clean_decision = re.sub(r'<think>[\s\S]*?</think>', '', decision_text)
            clean_decision = re.sub(r'```(?:json)?\s*', '', clean_decision).strip()

            if not clean_decision:
                return False, f"空响应。原始响应: {decision_text[:200]}", None

            parsed_json = self._extract_json(clean_decision)
            if not parsed_json:
                json_match = re.search(r'\{[\s\S]*\}', clean_decision)
                if json_match:
                    try:
                        parsed_json = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass
            if not parsed_json:
                return False, f"无法解析JSON。原始响应: {decision_text[:200]}", None

            action = parsed_json.get("action", "")
            if not action:
                return False, "JSON缺少action字段", parsed_json

            if "error" in parsed_json and parsed_json["error"]:
                return False, str(parsed_json["error"]), parsed_json

            if "result" in parsed_json and parsed_json["result"] in ("failed", "prerequisite_failed", "dialog_blocked", "unexpected_dialog"):
                return False, f"结果状态: {parsed_json['result']}", parsed_json
            if "status" in parsed_json and parsed_json["status"] in ("failed", "error", "failed_after_retries"):
                return False, f"状态: {parsed_json['status']}", parsed_json

            return self._execute_action(action, parsed_json)

        except Exception as e:
            return False, f"执行异常: {e}。原始响应: {decision_text[:100]}", None

    def _extract_json(self, text: str) -> Optional[Dict]:
        """提取最外层JSON对象（增强版）"""
        if not text:
            return None

        # 方法1: 直接尝试解析整个文本
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 方法2: 查找第一个 { 到最后一个 } 之间的内容
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass

        # 方法3: 逐字符匹配最外层JSON
        depth = 0
        start = -1
        for i, c in enumerate(text):
            if c == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0 and start >= 0:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        continue
        return None

    def _execute_action(self, action: str, data: Dict) -> tuple[bool, str, Dict]:
        """执行具体动作（使用模型返回的action）"""
        try:
            # 支持的action类型
            supported_actions = {
                "tap", "back", "claim", "dialog_close", "wait", "none"
            }

            if action not in supported_actions:
                print(f"[WARN] 不支持的action: '{action}'，支持: {supported_actions}")
                self.adb.wait(2)
                return False, f"不支持的action: {action}", data

            if action == "tap":
                coords = data.get("coords")
                if coords and len(coords) == 2:
                    x, y = int(coords[0]), int(coords[1])
                    print(f"  [ADB] 点击 ({x}, {y})")
                    success = self._tap(x, y)
                    if not success:
                        print(f"  [ADB-ERROR] 点击失败 (返回 {success})")
                        return False, "ADB点击失败", data
                else:
                    # 尝试根据target或使用默认坐标
                    target = data.get("target", "").lower()
                    if "signin" in target or "签到" in target:
                        coords = self.config.get_variable("coords.signin_entry", [640, 360])
                        print(f"  [ADB] 使用预设坐标签到: {coords}")
                        success = self._tap(*coords)
                        if not success:
                            return False, "ADB点击失败", data
                    elif "claim" in target or "领取" in target:
                        coords = self.config.get_variable("coords.claim_all", [960, 540])
                        print(f"  [ADB] 使用预设坐标领取: {coords}")
                        success = self._tap(*coords)
                        if not success:
                            return False, "ADB点击失败", data
                    else:
                        # 没有坐标，无法执行
                        print(f"  [WARN] tap动作缺少coords，target='{target}'")
                        return False, "tap动作缺少coords参数", data
                self.adb.wait(2)
                return True, "", data

            elif action == "back":
                print("  [ADB] 返回键 (keyevent 4)")
                success = self.adb.keyevent(4)
                if not success:
                    print(f"  [ADB-ERROR] 返回键失败")
                    return False, "ADB返回键失败", data
                self.adb.wait(2)
                return True, "", data

            elif action == "claim":
                coords = self.config.get_variable("coords.claim_all", [960, 540])
                print(f"  [ADB] 领取按钮: {coords}")
                success = self._tap(*coords)
                if not success:
                    return False, "ADB点击失败", data
                self.adb.wait(1)
                return True, "", data

            elif action == "dialog_close":
                # 处理弹窗：点击取消按钮
                coords = data.get("coords")
                if coords and len(coords) == 2:
                    print(f"  [ADB] 关闭弹窗: {coords}")
                    success = self._tap(coords[0], coords[1])
                    if not success:
                        return False, "ADB点击失败", data
                else:
                    # 默认取消按钮位置
                    print("  [ADB] 关闭弹窗: 默认位置 (400, 660)")
                    success = self._tap(400, 660)
                    if not success:
                        return False, "ADB点击失败", data
                self.adb.wait(1)
                return True, "", data

            elif action == "wait":
                duration = data.get("duration", 3)
                print(f"  [ADB] 等待 {duration} 秒")
                self.adb.wait(duration)
                return True, "", data

            elif action == "none":
                # 不需要执行动作
                print("  [ADB] 无操作 (none)")
                self.adb.wait(1)
                return True, "", data

            else:
                self.adb.wait(2)
                return True, "", data

        except Exception as e:
            import traceback
            print(f"[EXCEPTION] {e}")
            traceback.print_exc()
            return False, f"动作执行异常: {e}", data


# ══════════════════════════════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="标准流执行引擎 v2 - 配置驱动 + 视觉分析")
    parser.add_argument("--flow", choices=["daily_quest", "weekly_quest", "resource_collection",
                                            "base_management", "character_ascension",
                                            "weapon_crafting", "event_rewards",
                                            "delivery_mission", "dungeon_grinding", "auto_move", "all"],
                        default="daily_quest", help="要执行的流程")
    parser.add_argument("--local-only", action="store_true",
                        help="强制使用本地2B模型（失败则退出）")
    parser.add_argument("--analyze-only", action="store_true",
                        help="仅分析已有记录（不执行）")
    parser.add_argument("--skip-analysis", action="store_true",
                        help="执行但不分析")
    parser.add_argument("--no-record", action="store_true",
                        help="不记录截图")
    parser.add_argument("--optimize-prompts", action="store_true",
                        help="根据分析结果自动优化提示词")
    parser.add_argument("--session-dir", type=str,
                        help="分析已有记录目录（与--analyze-only配合使用）")

    parser.add_argument("--device", type=str, default="localhost:16512",
                        help="ADB 设备地址（默认：localhost:16512）")
    args = parser.parse_args()
    
    # 设备地址
    device_addr = args.device
    print(f"[配置] ADB 设备地址：{device_addr}")

    # 加载配置
    config = FlowConfig()
    exec_config = config.execution_config

    # 初始化记录器
    recorder = FlowRecorder(
        session_name=args.flow,
        record_video=not args.no_record,
        device_addr=device_addr
    ) if not args.analyze_only else None

    # 初始化模型引擎
    engine = Local2BEngine()
    ok = engine.load()
    if not ok:
        print("[ERROR] 模型加载失败")
        return 1
    if args.local_only and not engine.is_local():
        print("[ERROR] --local-only 但本地模型不可用")
        return 1
    model_type = "本地2B" if engine.is_local() else "API (exploration_deep)"
    print(f"模型模式: {model_type}")

    # 执行流程
    if args.analyze_only:
        # 仅分析模式
        if not args.session_dir:
            print("[ERROR] --analyze-only 需要指定 --session-dir")
            return 1

        session_dir = args.session_dir
        print(f"[analyze-only] 分析已有记录: {session_dir}")

        report_path = os.path.join(session_dir, "execution_report.json")
        if not os.path.exists(report_path):
            print(f"[ERROR] 未找到执行报告: {report_path}")
            return 1

        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)

        print(f"  流程: {report.get('session')}")
        print(f"  总步骤: {report.get('total_steps')}")
        print(f"  成功率: {report.get('success_count')}/{report.get('total_steps')}")

        # 分析
        analyzer = VisualAnalyzer(model=exec_config.get("analysis_model"))
        # 注意：完整实现需要从report重建recorder.steps
        # 这里先输出基本信息
        analysis = {
            "info": "Analysis of existing report",
            "report_file": report_path,
            "total_steps": report.get("total_steps", 0),
            "success_rate": report.get("success_count", 0) / max(report.get("total_steps", 1), 1)
        }

        analysis_path = os.path.join(session_dir, "visual_analysis.json")
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        print(f"分析已保存: {analysis_path}")

        return 0

    # 正常执行模式
    adb_path = str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe")
    executor = StandardFlowExecutor(config, engine, recorder, device_addr, adb_path)

    # 初始化 MaaFw 触控（用于前置导航点击）
    _maafw_preamble = None
    if MAAFW_AVAILABLE:
        try:
            _maafw_config = MaaFwTouchConfig(
                adb_path=str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe"),
                address=f'{device_addr}',
                screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,
                input_methods=MaaFwTouchConfig.INPUT_ADB_SHELL,
            )
            _maafw_preamble = MaaFwTouchExecutor(_maafw_config)
            if _maafw_preamble.connect():
                print("[MaaFw] 前置触控初始化成功")
            else:
                _maafw_preamble = None
        except Exception as e:
            print(f"[MaaFw] 前置初始化失败: {e}")
            _maafw_preamble = None

    def _preamble_tap(x, y):
        """前置触控：仅使用 ADB 原生 tap（避免 MaaFw 坐标空间混淆和 fortl 崩溃）"""
        return subprocess.run([adb_path, "-s", f'{device_addr}', "shell", "input", "tap", str(x), str(y)],
                            capture_output=True, timeout=5).returncode == 0

    # 确保游戏运行
    print("\n[前置] 启动游戏...")
    # 先强制停止旧实例，再 monkey 启动新实例（避免状态污染）
    subprocess.run([adb_path, "-s", f'{device_addr}', "shell", "am", "force-stop", "com.hypergryph.endfield"],
                  capture_output=True, timeout=10)
    time.sleep(3)
    subprocess.run([adb_path, "-s", f'{device_addr}', "shell", "input", "keyevent", "3"],
                  capture_output=True, timeout=5)
    time.sleep(1)
    r = subprocess.run([adb_path, "-s", f'{device_addr}', "shell",
                      "monkey", "-p", "com.hypergryph.endfield",
                      "-c", "android.intent.category.LAUNCHER", "1"],
                      capture_output=True, timeout=15)
    print(f"  启动: {r.stdout.decode(errors='replace')[:120]}")
    # 游戏需要经历 logo→适龄提示→加载→标题→世界 等多个画面
    print("  快速过标题画面...")
    time.sleep(12)
    # 连续点击中央跳过所有弹窗和标题（10次，每次间隔2秒）
    for i in range(10):
        _preamble_tap(960, 540)
        time.sleep(2)
    # 等待加载画面完成
    print("  等待加载完成...")
    time.sleep(20)

    # 验证页面（最多 8 次尝试）
    print("[前置] 验证页面...")
    _analyzer = ScreenAnalyzer(maafw_executor=_maafw_preamble)
    import numpy as np
    import cv2

    # 初始化高精度页面分析器（替换旧的金色元素计数）
    _page_analyzer = HighPrecisionPageAnalyzer()
    _vlm_client = VLMClient({"vlm_mode": "local"})

    def _classify_page(cv_img):
        """使用多特征分析器判断页面类型"""
        if cv_img is None:
            return {"page_type": "unknown", "confidence": 0.0, "features": {}}
        return _page_analyzer.analyze(cv_img)

    def _classify_with_vlm(cv_img, expected_page="world", step_desc=""):
        """OpenCV 优先，不确定时 VLM 介入决策"""
        result = _classify_page(cv_img)
        if VLMClient.should_invoke_vlm(result, expected_page):
            context = {
                "expected_page": expected_page,
                "step_desc": step_desc,
                "last_action": "按返回键/点击中央"
            }
            vlm_result = _vlm_client.decide_action(cv_img, result, context)
            print(f"  [VLM] 决策：{vlm_result.get('suggested_action', '?')} → {vlm_result.get('reason', '')[:80]}")
            # 用 VLM 结果覆盖 page_type
            result["page_type"] = vlm_result.get("page_type", result["page_type"])
            result["confidence"] = max(result["confidence"], vlm_result.get("confidence", 0))
            result["vlm_action"] = vlm_result
        return result

    # 保留旧的金色元素计数方法（用于降级/调试）
    def _count_gold_elements(cv_img):
        """计算金色元素数量（页面类型判断依据）"""
        if cv_img is None:
            return 0
        # 旋转到横屏并 resize
        img_rot = cv2.rotate(cv_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        img_resized = cv2.resize(img_rot, (1280, 720))
        hsv = cv2.cvtColor(img_resized, cv2.COLOR_BGR2HSV)
        lower_gold = np.array([25, 100, 100])
        upper_gold = np.array([35, 255, 255])
        mask = cv2.inRange(hsv, lower_gold, upper_gold)
        kernel = np.ones((3,3),np.uint8)
        dilated_mask = cv2.dilate(mask, kernel, iterations=2)
        eroded_mask = cv2.erode(dilated_mask, kernel, iterations=1)
        contours, _ = cv2.findContours(eroded_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return len([c for c in contours if cv2.contourArea(c) > 50])
    
    def _classify_page_by_gold(gold_count):
        """基于金色元素数量判断页面类型"""
        if gold_count >= 22:
            return "quest_panel"
        elif gold_count >= 18:
            return "world"
        elif gold_count >= 15:
            return "world_low_gold"
        elif gold_count >= 12:
            return "exit_dialog"
        elif gold_count >= 8:
            return "menu"
        else:
            return "other"
    
    def _close_exit_dialog():
        """关闭退出对话框，尝试多个候选坐标"""
        cancel_candidates = [
            (600, 750),   # 默认坐标
            (540, 720),   # 偏左上
            (660, 780),   # 偏右下
            (580, 730),   # 偏左
            (620, 770),   # 偏右
        ]
        
        for cx, cy in cancel_candidates:
            _preamble_tap(cx, cy)
            time.sleep(1.5)
            
            # 验证是否关闭成功
            r = subprocess.run([adb_path, "-s", f'{device_addr}', "exec-out", "screencap", "-p"],
                              capture_output=True, timeout=10)
            if r.returncode == 0 and len(r.stdout) > 1000:
                np_img = np.frombuffer(r.stdout, dtype=np.uint8)
                cv_img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
                if cv_img is not None:
                    page_result = _classify_page(cv_img)
                    page_type = page_result["page_type"]
                    confidence = page_result["confidence"]
                    if page_type != "exit_dialog":
                        print(f"[前置] 成功关闭退出对话框，当前={page_type} (置信度 {confidence:.2f})")
                        return True
        
        print("[前置] 未能关闭退出对话框")
        return False
    
    page = "unknown"
    nav_success = False
    for preamble_attempt in range(8):
        r = subprocess.run([adb_path, "-s", f'{device_addr}', "exec-out", "screencap", "-p"],
                          capture_output=True, timeout=10)
        if r.returncode == 0 and len(r.stdout) > 1000:
            np_img = np.frombuffer(r.stdout, dtype=np.uint8)
            cv_img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
            if cv_img is not None:
                # 使用 VLM 增强的页面分类（OpenCV 优先，不确定时 VLM 介入）
                page_result = _classify_with_vlm(cv_img, expected_page="world",
                                                 step_desc="前置验证：确保进入游戏世界")
                page_type = page_result["page_type"]
                confidence = page_result["confidence"]
                features = page_result["features"]
                
                # 同时保留旧的 VLM 分析（用于 OCR 文本）
                analysis = _analyzer.analyze(cv_img)
                ocr_text = analysis.get("ocr_text", "")[:80]
                page = page_type  # 更新 page 变量用于后续分支判断
                
                print(f"  [前置 {preamble_attempt+1}/8] 页面={page_type} (置信度 {confidence:.2f})")
                print(f"    特征：left_bar={features.get('left_bar_brightness', 0):.1f} green={features.get('green_pixels_top_right', 0):.0f} OCR={ocr_text}")

                # 成功条件：world 页面且置信度 > 0.5
                if page_type == "world" and confidence > 0.5:
                    print("[前置] ✅ 已进入游戏世界")
                    nav_success = True
                    break
                elif page_type == "quest_panel":
                    # 在任务面板，按返回
                    print("[前置] 在任务面板，按返回...")
                    subprocess.run([adb_path, "-s", f'{device_addr}', "shell", "input", "keyevent", "4"],
                                  capture_output=True, timeout=5)
                    time.sleep(3)
                    continue
                elif page_type == "exit_dialog":
                    # 退出对话框，点击取消按钮
                    print("[前置] 检测到退出对话框，尝试关闭...")
                    if not _close_exit_dialog():
                        print("[前置] 退出对话框无法关闭，尝试按返回...")
                        subprocess.run([adb_path, "-s", f'{device_addr}', "shell", "input", "keyevent", "4"],
                                      capture_output=True, timeout=5)
                        time.sleep(2)
                    continue
                elif page_type == "unknown":
                    # unknown — 点击中央并等待
                    print("[前置] 未知画面，点击中央...")
                    _preamble_tap(960, 540)
                    time.sleep(5)
                elif page_type == "world_transition":
                    # 中间状态，等待一下再重试
                    print("[前置] 中间状态，等待 2 秒...")
                    time.sleep(2)
                    continue
                elif page == "loading":
                    print("[前置] 加载中，等待 30 秒...")
                    time.sleep(30)
                elif page_type == "title" or page_type == "enter_game_prompt":
                    print("[前置] 进入游戏准备画面，点击进入...")
                    _preamble_tap(960, 540)
                    time.sleep(5)
                    continue
                else:
                    # 其他 — 点击中央并等待
                    print("[前置] 其他画面，点击中央...")
                    _preamble_tap(960, 540)
                    time.sleep(5)
        else:
            time.sleep(3)
    
    if not nav_success:
        print(f"[前置] ⚠️  未能确认进入世界页面 (最终页面={page})")
        print("[提示] 将继续执行流程，但可能会失败")
    else:
        print(f"[前置] ✅ 页面验证完成")



    # 清理前置 MaaFw（后续由 StandardFlowExecutor 管理）
    if _maafw_preamble:
        _maafw_preamble.disconnect()
        _maafw_preamble = None

    # 执行流程
    flows_to_run = []
    if args.flow == "all":
        for flow_name in config.all_flows:
            if config.is_flow_enabled(flow_name):
                flows_to_run.append(flow_name)
    else:
        flows_to_run = [args.flow]

    overall_success = True
    for flow_name in flows_to_run:
        print(f"\n{'='*60}")
        print(f"开始执行: {flow_name}")
        print(f"{'='*60}")
        success = executor.execute_flow(flow_name)
        if not success:
            overall_success = False
        print(f"\n流程完成: {'成功' if success else '有失败步骤'}")

    # 导出报告
    if recorder:
        report = recorder.export_report()
        report_path = os.path.join(recorder.session_dir, "execution_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n执行报告已保存: {report_path}")

    # 视觉分析
    if not args.skip_analysis:
        analyzer = VisualAnalyzer(model=exec_config.get("analysis_model"))

        if args.analyze_only and args.session_dir:
            # 分析已有记录
            print("\n[analyze-only] 加载已有记录...")
            session_dir = args.session_dir
            report_path = os.path.join(session_dir, "execution_report.json")
            if not os.path.exists(report_path):
                print(f"[ERROR] 未找到执行报告: {report_path}")
                return 1

            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)

            # 重建记录器对象
            recorder = FlowRecorder(session_name=report.get("session", "unknown"), record_video=False)
            # 这里简化处理，实际需要从报告重建steps
            print(f"[analyze-only] 分析目录: {session_dir}")
            print(f"[analyze-only] 步骤数: {report.get('total_steps', 0)}")

            analysis = analyzer.analyze_execution(recorder, args.flow)
        elif recorder:
            # 分析刚执行的记录
            print("\n" + "=" * 60)
            print("开始视觉分析...")
            analysis = analyzer.analyze_execution(recorder, args.flow)
            analysis_path = os.path.join(recorder.session_dir, "visual_analysis.json")
            with open(analysis_path, "w", encoding="utf-8") as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2)
            print(f"分析结果已保存: {analysis_path}")
        else:
            print("[WARN] 无记录可分析")
            return 0

        # 输出优化建议
        if "prompt_optimizations" in analysis:
            print("\n" + "=" * 60)
            print("提示词优化建议:")
            print("=" * 60)
            for step_key, optimized in analysis.get("prompt_optimizations", {}).items():
                print(f"\n[{step_key}]")
                print(f"  {optimized[:300]}...")

        if "bottlenecks" in analysis:
            print("\n卡点分析:")
            for b in analysis.get("bottlenecks", []):
                print(f"  - {b}")

        # 自动优化提示词（如果启用）
        if args.optimize_prompts and "prompt_optimizations" in analysis:
            print("\n" + "=" * 60)
            print("正在优化配置文件...")
            optimized_count = 0
            for step_key, new_prompt in analysis.get("prompt_optimizations", {}).items():
                # 找到对应的流程和步骤
                for flow_name, flow_data in config._config.get("flows", {}).items():
                    for step in flow_data.get("steps", []):
                        if step["id"] == step_key:
                            old_prompt = step["prompt_template"]
                            if old_prompt != new_prompt:
                                step["prompt_template"] = new_prompt
                                optimized_count += 1
                                print(f"  已更新: {flow_name}.{step_key}")

            if optimized_count > 0:
                # 保存优化后的配置
                backup_path = config.config_path + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                import shutil
                shutil.copy2(config.config_path, backup_path)
                print(f"  原配置已备份: {backup_path}")

                with open(config.config_path, 'w', encoding='utf-8') as f:
                    json.dump(config._config, f, ensure_ascii=False, indent=2)
                print(f"  配置已优化并保存 ({optimized_count} 处更新)")
            else:
                print("  无需优化（所有提示词已是最新的）")

    print("\n完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
