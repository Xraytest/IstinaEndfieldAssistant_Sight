#!/usr/bin/env python3
"""
识别引擎 - MaaEnd 式多源融合识别系统

实现 MaaEnd 的核心识别能力：
1. 模板匹配（TemplateMatch）- OpenCV SIFT 特征匹配
2. 颜色匹配（ColorMatch）- OpenCV HSV 颜色轮廓检测
3. 组合识别（And/Or）
4. OCR 识别 - MaaFw Pipeline 内建 OCR 引擎

参考：MaaEnd-2/assets/resource/pipeline/Common/
"""

import cv2
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import sys

from utils.paths import get_project_root, ensure_src_path
ensure_src_path(__file__)


class RecognitionEngine:
    """识别引擎，支持 MaaEnd 式节点识别

    OCR 通过 MaaFw Pipeline 系统调用（内建 OCR 引擎）。
    本引擎负责：模板匹配、颜色匹配、组合逻辑。
    """

    def __init__(self, assets_dir: str = None):
        self.assets_dir = Path(assets_dir) if assets_dir else Path(get_project_root(__file__)) / "assets"

    # ── 主分发 ─────────────────────────────────────────────────

    def recognize(self, img: np.ndarray, node_config: Dict[str, Any]) -> Tuple[bool, Any]:
        """执行节点识别"""
        node_type = node_config.get("type", "")

        if node_type == "TemplateMatch":
            return self._template_match(img, node_config)
        elif node_type == "ColorMatch":
            return self._color_match(img, node_config)
        elif node_type == "And":
            return self._and_recognize(img, node_config)
        elif node_type == "Or":
            return self._or_recognize(img, node_config)
        elif node_type == "OCR":
            # OCR 通过 MaaFw Pipeline 执行，此处返回提示
            return False, {"reason": "OCR 需通过 MaaFw Pipeline 执行，请使用 Tasker.post_recognition()"}
        elif isinstance(node_config, str):
            return False, None
        return False, None

    # ── 模板匹配（SIFT 特征匹配，尺度不变）─────────────────

    def _template_match(self, img: np.ndarray, config: Dict[str, Any]) -> Tuple[bool, Any]:
        """SIFT 特征匹配 — 尺度/旋转不变，远超传统模板匹配

        config: {template: str, roi: [x,y,w,h], threshold: float (最小匹配点数)}
        
        返回格式:
        - 成功：(True, {"bbox": [x1, y1, x2, y2], "center": [cx, cy], "matches": int, "confidence": float})
        - 失败：(False, {"matches": int})
        """
        template_path = config.get("template", "")
        roi = config.get("roi")
        min_matches = config.get("threshold", 10)  # reinterpret as min matches

        if not Path(template_path).is_absolute():
            template_path = self.assets_dir / template_path

        template = cv2.imread(str(template_path))
        if template is None:
            return False, {"error": "template not found"}

        x, y = 0, 0
        if roi:
            rx, ry, rw, rh = roi
            search_img = img[ry:ry+rh, rx:rx+rw]
            x, y = rx, ry
        else:
            search_img = img

        # SIFT 检测器
        sift = cv2.SIFT_create()

        # 转换为灰度
        gray_tmpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        gray_src = cv2.cvtColor(search_img, cv2.COLOR_BGR2GRAY)

        kp1, des1 = sift.detectAndCompute(gray_tmpl, None)
        kp2, des2 = sift.detectAndCompute(gray_src, None)

        if des1 is None or des2 is None or len(des1) < 4 or len(des2) < 4:
            return False, {"matches": 0}

        # FLANN 匹配
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(des1, des2, k=2)

        # Lowe's ratio test
        good = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                good.append(m)

        if len(good) >= min_matches:
            # 计算匹配区域边界框
            pts = [kp2[m.trainIdx].pt for m in good]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            
            # 转换为全局坐标
            global_x1 = int(min_x) + x
            global_y1 = int(min_y) + y
            global_x2 = int(max_x) + x
            global_y2 = int(max_y) + y
            
            # 计算中心点
            cx = int((global_x1 + global_x2) / 2)
            cy = int((global_y1 + global_y2) / 2)
            
            # 计算置信度（匹配点数归一化）
            confidence = min(1.0, len(good) / 20.0)
            
            return True, {
                "bbox": [global_x1, global_y1, global_x2, global_y2],
                "center": [cx, cy],
                "matches": len(good),
                "confidence": confidence,
                "template": template_path
            }

        return False, {"matches": len(good)}

    # ── 颜色匹配（轮廓检测，非像素分布）─────────────────────

    def _color_match(self, img: np.ndarray, config: Dict[str, Any]) -> Tuple[bool, Any]:
        """颜色元素检测：在 ROI 内查找至少 min_contours 个指定颜色的连通区域

        config: {roi: [x,y,w,h], lower: [h,s,v], upper: [h,s,v],
                 min_area: int, min_contours: int}
        
        返回格式:
        - 成功：(True, {"contours": int, "bboxes": [[x1,y1,x2,y2],...], "centers": [[cx,cy],...], "total_area": int})
        - 失败：(False, {"contours": int})
        """
        roi = config.get("roi")
        lower = np.array(config.get("lower"))
        upper = np.array(config.get("upper"))
        min_area = config.get("min_area", 30)
        min_contours = config.get("min_contours", 1)

        x_offset, y_offset = 0, 0
        if roi:
            rx, ry, rw, rh = roi
            img_crop = img[ry:ry+rh, rx:rx+rw]
            x_offset, y_offset = rx, ry
        else:
            img_crop = img

        hsv = cv2.cvtColor(img_crop, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower, upper)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_contours = []
        bboxes = []
        centers = []
        total_area = 0
        
        for c in contours:
            area = cv2.contourArea(c)
            if area >= min_area:
                valid_contours.append(c)
                total_area += area
                
                # 计算边界框
                x, y, w, h = cv2.boundingRect(c)
                # 转换为全局坐标
                global_x1 = x + x_offset
                global_y1 = y + y_offset
                global_x2 = x + w + x_offset
                global_y2 = y + h + y_offset
                bboxes.append([global_x1, global_y1, global_x2, global_y2])
                
                # 计算中心点
                cx = global_x1 + w // 2
                cy = global_y1 + h // 2
                centers.append([cx, cy])

        if len(valid_contours) >= min_contours:
            return True, {
                "contours": len(valid_contours),
                "bboxes": bboxes,
                "centers": centers,
                "total_area": total_area
            }

        return False, {"contours": len(valid_contours)}

    # ── 组合识别 ───────────────────────────────────────────────

    def _and_recognize(self, img: np.ndarray, config: Dict[str, Any]) -> Tuple[bool, Any]:
        """And：所有子节点都匹配，聚合所有 bbox 信息"""
        all_bboxes = []
        all_centers = []
        
        for node in config.get("nodes", []):
            ok, result = self.recognize(img, node)
            if not ok:
                return False, None
            # 聚合 bbox 信息
            if result:
                if "bbox" in result:
                    all_bboxes.append(result["bbox"])
                if "bboxes" in result:
                    all_bboxes.extend(result["bboxes"])
                if "center" in result:
                    all_centers.append(result["center"])
                if "centers" in result:
                    all_centers.extend(result["centers"])
        
        return True, {"bboxes": all_bboxes, "centers": all_centers}

    def _or_recognize(self, img: np.ndarray, config: Dict[str, Any]) -> Tuple[bool, Any]:
        """Or：任一子节点匹配即成功（短路求值），返回第一个匹配的完整信息"""
        for node in config.get("nodes", []):
            ok, result = self.recognize(img, node)
            if ok:
                return True, result
        return False, None


# ═══════════════════════════════════════════════════════════════
# MaaFw Pipeline OCR 封装
# ═══════════════════════════════════════════════════════════════

class MaaFwPipelineOCR:
    """通过 MaaFw Tasker + Resource 管道系统执行 OCR

    用法:
        from maa import Tasker, Resource, Controller
        from maa.pipeline import JRecognitionType, JOCR

        # 创建 Tasker 并绑定 Resource/Controller
        tasker = Tasker()
        resource = Resource()
        controller = Controller()
        tasker.bind(resource, controller)

        # 执行 OCR
        ocr_param = JOCR(
            expected=["领取", "Claim"],
            roi=(0, 0, 1280, 720)
        )
        job = tasker.post_recognition(JRecognitionType.OCR, ocr_param, image)
        detail = job.get()
    """

    @staticmethod
    def create_ocr_param(expected: List[str], roi: Tuple[int, int, int, int] = (0, 0, 0, 0),
                         threshold: float = 0.3) -> Dict[str, Any]:
        """
        创建 OCR 识别参数（JSON 格式，用于 Pipeline 配置）

        Args:
            expected: 期望匹配的文本列表（支持正则表达式）
            roi: 识别区域 (x, y, w, h)
            threshold: 置信度阈值

        Returns:
            OCR 参数字典
        """
        return {
            "type": "OCR",
            "param": {
                "expected": expected,
                "roi": list(roi),
                "threshold": threshold
            }
        }

    @staticmethod
    def doc():
        """返回 MaaFw OCR 使用文档"""
        return """
MaaFw Pipeline OCR 使用指南
==========================

1. 通过 Tasker.post_recognition() 执行 OCR:
   from maa import Tasker, JRecognitionType
   from maa.pipeline import JOCR

   ocr_param = JOCR(
       expected=["领取", "Claim", "(?i)collect"],  # 支持正则
       roi=(0, 0, 1280, 720),
       threshold=0.3
   )
   job = tasker.post_recognition(JRecognitionType.OCR, ocr_param, image)

2. 在 Pipeline JSON 中配置 OCR:
   {
       "CheckClaimButton": {
           "recognition": {
               "type": "OCR",
               "param": {
                   "expected": ["领取", "一键领取", "Claim"],
                   "roi": [950, 60, 330, 640],
                   "threshold": 0.3
               }
           },
           "action": {"type": "Click"}
       }
   }

3. OCR 结果格式（重要：包含完整坐标信息供 LLM 决策）:
   RecognitionDetail(
       hit: bool,                          # 是否匹配期望文本
       box: (x, y, w, h),                  # 匹配位置边界框
       all_results: list[RecognitionResult],  # 所有识别结果
       best_result: RecognitionResult       # 最佳匹配结果
   )
   
   RecognitionResult 包含:
   - text: str              # 识别的文本
   - bbox: [x1, y1, x2, y2] # 文本边界框（全局坐标）
   - center: [cx, cy]       # 文本中心点
   - confidence: float      # 置信度

4. 支持的特性:
   - 多语言自动检测（中文/英文/日文/韩文）
   - 正则表达式匹配（如 (?i) 不区分大小写）
   - ROI 区域识别
   - 置信度阈值过滤
   - 文本排序（Horizontal/Vertical/Area 等）
   - **返回完整坐标信息，LLM 可根据坐标自行决定点击位置**
"""


# ═══════════════════════════════════════════════════════════════
# 预定义状态节点（参考 MaaEnd，适配 OpenCV 实现）
# ═══════════════════════════════════════════════════════════════

PREDEFINED_STATES = {
    # ── 取消按钮（对话框区域 SIFT，阈值=5 最小匹配点） ──
    "CancelButton": {
        "type": "Or",
        "nodes": [
            {
                "type": "TemplateMatch",
                "template": "Common/Button/CancelButtonType1.png",
                "roi": [200, 500, 700, 500],
                "threshold": 5
            },
            {
                "type": "TemplateMatch",
                "template": "Common/Button/CancelButtonType2.png",
                "roi": [200, 500, 700, 500],
                "threshold": 5
            }
        ]
    },

    # ── 世界页面（左上角小 ROI SIFT） ──
    "InWorld": {
        "type": "Or",
        "nodes": [
            {
                "type": "TemplateMatch",
                "template": "SceneManager/WorldMenu.png",
                "roi": [0, 0, 200, 200],
                "threshold": 5
            },
            {
                "type": "TemplateMatch",
                "template": "Common/Button/RegionalDevelopmentButton.png",
                "roi": [0, 0, 300, 100],
                "threshold": 5
            }
        ]
    },

    # ── 任务图标（右上角 ROI，高阈值防误匹配） ──
    "TaskIcon": {
        "type": "TemplateMatch",
        "template": "SceneManager/TaskIcon.png",
        "roi": [700, 30, 300, 150],
        "threshold": 15
    },

    # ── 黄色确认按钮（颜色轮廓 + 模板双验证） ──
    "YellowConfirmButton": {
        "type": "And",
        "nodes": [
            {
                "type": "ColorMatch",
                "roi": [200, 500, 700, 500],
                "lower": [28, 100, 100],
                "upper": [29, 255, 255],
                "min_area": 100,
                "min_contours": 1
            },
            {
                "type": "TemplateMatch",
                "template": "Common/Button/YellowConfirmButtonType1.png",
                "roi": [200, 500, 700, 500],
                "threshold": 5
            }
        ]
    },

    # ── 菜单列表（颜色验证，OCR 需 MaaFw Pipeline） ──
    "InMenuList": {
        "type": "And",
        "nodes": [
            {
                "type": "ColorMatch",
                "roi": [0, 1760, 200, 200],
                "lower": [90, 35, 35],
                "upper": [191, 83, 85],
                "min_area": 30,
                "min_contours": 2
            }
        ],
        "note": "OCR 部分需通过 MaaFw Pipeline 执行"
    },

    # ── 行动手册（OCR 需 MaaFw Pipeline） ──
    "InOperationalManual": {
        "note": "需通过 MaaFw Pipeline OCR 执行:\n" +
                "  ocr_param = JOCR(expected=['行动手册', 'Operational Manual'], roi=(0, 0, 215, 60))"
    }
}


# ═══════════════════════════════════════════════════════════════
# 测试代码
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from pathlib import Path

    # recognition_engine.py 在 src/core/recognition/
    SRC_DIR = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(SRC_DIR))

    print("=" * 60)
    print("识别引擎测试（MaaFw OCR + OpenCV 模板/颜色匹配）")
    print("=" * 60)

    # 打印 MaaFw OCR 使用文档
    print("\nMaaFw OCR 使用指南:")
    print(MaaFwPipelineOCR.doc())

    # 测试预定义状态
    print("\n预定义状态节点:")
    for name, config in PREDEFINED_STATES.items():
        print(f"  - {name}: {config.get('type', 'N/A')}")
