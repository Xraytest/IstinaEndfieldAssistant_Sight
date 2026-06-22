"""
多模态游戏画面分析系统 [已废弃]

此模块功能已被 HighPrecisionPageAnalyzerV2 (core/page_analyzer.py) 替代。
HighPrecisionPageAnalyzerV2 使用 RecognitionEngine 进行模板匹配和颜色匹配，
速度更快、维护更集中。

保留此文件仅用于参考，新代码请使用 page_analyzer.py。

原功能：基于多特征融合（空间布局/颜色/纹理/模板/OCR/YOLO）判断页面类型
"""

import warnings
warnings.warn(
    "advanced_analyzer.py 已废弃，请使用 core.page_analyzer.HighPrecisionPageAnalyzerV2",
    DeprecationWarning, stacklevel=2
)

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import hashlib


class PageType(Enum):
    """页面类型枚举"""
    UNKNOWN = "unknown"
    TITLE = "title"           # 标题/登录画面
    LOADING = "loading"       # 加载画面
    WORLD = "world"           # 探索世界 (3D 场景)
    QUEST_PANEL = "quest_panel"  # 任务面板
    SETTINGS = "settings"     # 设置菜单
    EXIT_DIALOG = "exit_dialog"  # 退出对话框
    LOGOUT_DIALOG = "logout_dialog"  # 登出对话框
    EVENT_PANEL = "event_panel"  # 活动面板
    MENU = "menu"             # 系统菜单
    BASE_INDUSTRY = "base_industry"  # 基建界面
    CHARACTER = "character"   # 角色界面
    MAP = "map"               # 地图界面


@dataclass
class SpatialFeatures:
    """空间布局特征"""
    # 导航栏区域 UI 密度 (顶部 10% 区域)
    nav_bar_density: float = 0.0
    
    # 中央面板区域 UI 密度 (中央 50% 区域)
    center_panel_density: float = 0.0
    
    # 边缘区域 UI 密度 (四边 10% 区域)
    edge_density: float = 0.0
    
    # UI 元素聚类数量
    ui_clusters: int = 0
    
    # 最大连续 UI 区域面积
    max_ui_area: float = 0.0


@dataclass
class ColorFeatures:
    """颜色特征"""
    # 金色元素数量
    golden_count: int = 0
    
    # 金色元素总面积占比
    golden_ratio: float = 0.0
    
    # 金色元素空间分布熵
    golden_entropy: float = 0.0
    
    # 整体颜色直方图 (HSV, 32 -bin)
    hsv_histogram: np.ndarray = field(default_factory=lambda: np.zeros(32))
    
    # 亮度均值和标准差
    brightness_mean: float = 0.0
    brightness_std: float = 0.0
    
    # 饱和度均值
    saturation_mean: float = 0.0


@dataclass
class TextureFeatures:
    """纹理特征"""
    # 边缘密度 (Canny 边缘占比)
    edge_density: float = 0.0
    
    # LBP 均匀直方图
    lbp_histogram: np.ndarray = field(default_factory=lambda: np.zeros(10))
    
    # 高频能量占比 (FFT)
    high_freq_energy: float = 0.0
    
    # 梯度方向直方图 (HOG, 9-bin)
    hog_histogram: np.ndarray = field(default_factory=lambda: np.zeros(9))


@dataclass
class TemplateMatchResult:
    """模板匹配结果"""
    template_name: str
    similarity: float  # 0-1 相似度
    position: Tuple[int, int]  # 匹配位置 (x, y)
    detected: bool = False  # 是否检测到 (相似度>阈值)


@dataclass
class PageAnalysisResult:
    """页面分析结果"""
    # 预测页面类型
    predicted_type: PageType = PageType.UNKNOWN
    
    # 置信度 (0-1)
    confidence: float = 0.0
    
    # 各特征分数
    spatial_features: SpatialFeatures = field(default_factory=SpatialFeatures)
    color_features: ColorFeatures = field(default_factory=ColorFeatures)
    texture_features: TextureFeatures = field(default_factory=TextureFeatures)
    
    # 模板匹配结果
    template_matches: List[TemplateMatchResult] = field(default_factory=list)
    
    # OCR 文本
    ocr_text: str = ""
    
    # YOLO 检测结果
    yolo_classes: List[str] = field(default_factory=list)
    
    # 特征权重 (用于融合)
    feature_weights: Dict[str, float] = field(default_factory=dict)
    
    # 详细分析日志
    analysis_log: List[str] = field(default_factory=list)


class GameScreenAnalyzer:
    """多模态游戏画面分析器"""
    
    # 页面特征数据库 (通过样本学习得到)
    PAGE_PROFILES = {
        PageType.WORLD: {
            "golden_count": (18, 22),      # 金色元素范围
            "nav_bar_density": (0.3, 0.6), # 导航栏密度
            "edge_density": (0.15, 0.35),  # 边缘密度 (3D 场景较高)
            "has_person": True,            # 应有角色
        },
        PageType.QUEST_PANEL: {
            "golden_count": (22, 40),
            "nav_bar_density": (0.2, 0.5),
            "center_panel_density": (0.4, 0.8),  # 中央面板密度高
            "edge_density": (0.05, 0.15),        # 2D UI 边缘较少
            "has_person": False,
        },
        PageType.EXIT_DIALOG: {
            "golden_count": (12, 16),
            "nav_bar_density": (0.1, 0.3),       # 导航栏被遮挡
            "center_panel_density": (0.3, 0.6),  # 对话框在中央
            "edge_density": (0.05, 0.12),
            "has_person": False,
        },
        PageType.TITLE: {
            "golden_count": (5, 15),
            "brightness_mean": (50, 150),
            "edge_density": (0.05, 0.20),
            "has_person": False,
        },
        PageType.LOADING: {
            "brightness_mean": (0, 80),          # 通常较暗
            "edge_density": (0.02, 0.10),        # 边缘少
            "has_person": False,
        },
        PageType.MENU: {
            "golden_count": (15, 30),
            "nav_bar_density": (0.3, 0.6),
            "edge_density": (0.08, 0.20),
            "has_person": False,
        },
    }
    
    def __init__(self, image_width: int = 1280, image_height: int = 720):
        """
        初始化分析器
        
        Args:
            image_width: 图像宽度 (横屏)
            image_height: 图像高度 (横屏)
        """
        self.img_width = image_width
        self.img_height = image_height
        
    def analyze(self, image: np.ndarray, 
                ocr_text: str = "",
                yolo_classes: List[str] = None) -> PageAnalysisResult:
        """
        综合分析画面
        
        Args:
            image: BGR 图像 (已旋转到横屏 1280x720)
            ocr_text: OCR 识别的文本
            yolo_classes: YOLO 检测的物体类别列表
            
        Returns:
            PageAnalysisResult: 分析结果
        """
        if yolo_classes is None:
            yolo_classes = []
            
        result = PageAnalysisResult()
        result.ocr_text = ocr_text
        result.yolo_classes = yolo_classes
        
        # 1. 提取空间布局特征
        result.spatial_features = self._extract_spatial_features(image)
        result.analysis_log.append(f"[空间] 导航栏密度={result.spatial_features.nav_bar_density:.3f}, "
                                   f"中央密度={result.spatial_features.center_panel_density:.3f}")
        
        # 2. 提取颜色特征
        result.color_features = self._extract_color_features(image)
        result.analysis_log.append(f"[颜色] 金色元素={result.color_features.golden_count}个，"
                                   f"占比={result.color_features.golden_ratio:.3f}, "
                                   f"亮度={result.color_features.brightness_mean:.1f}")
        
        # 3. 提取纹理特征
        result.texture_features = self._extract_texture_features(image)
        result.analysis_log.append(f"[纹理] 边缘密度={result.texture_features.edge_density:.3f}, "
                                   f"高频能量={result.texture_features.high_freq_energy:.3f}")
        
        # 4. 模板匹配 (可选，需要预存模板)
        # result.template_matches = self._match_templates(image)
        
        # 5. 多特征融合判断
        predicted_type, confidence = self._fuse_features(result)
        result.predicted_type = predicted_type
        result.confidence = confidence
        
        result.analysis_log.append(f"[融合] 预测={predicted_type.value}, 置信度={confidence:.3f}")
        
        return result
    
    def _extract_spatial_features(self, image: np.ndarray) -> SpatialFeatures:
        """提取空间布局特征"""
        features = SpatialFeatures()
        
        # 转换为灰度并二值化 (检测 UI 元素)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 使用自适应阈值检测 UI 元素 (高对比度区域)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 11, 2)
        
        # 形态学操作连接相邻 UI 元素
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(thresh, kernel, iterations=2)
        eroded = cv2.erode(dilated, kernel, iterations=1)
        
        # 计算不同区域的 UI 密度
        h, w = eroded.shape
        
        # 导航栏区域 (顶部 10%)
        nav_region = eroded[0:int(h*0.10), :]
        features.nav_bar_density = cv2.countNonZero(nav_region) / nav_region.size
        
        # 中央面板区域 (中央 50%)
        center_y1, center_y2 = int(h*0.25), int(h*0.75)
        center_x1, center_x2 = int(w*0.25), int(w*0.75)
        center_region = eroded[center_y1:center_y2, center_x1:center_x2]
        features.center_panel_density = cv2.countNonZero(center_region) / center_region.size
        
        # 边缘区域 (四边 10%)
        edge_mask = np.zeros_like(eroded)
        edge_mask[0:int(h*0.10), :] = 255  # 上
        edge_mask[int(h*0.90):h, :] = 255  # 下
        edge_mask[:, 0:int(w*0.10)] = 255  # 左
        edge_mask[:, int(w*0.90):w] = 255  # 右
        edge_region = cv2.bitwise_and(eroded, eroded, mask=edge_mask)
        features.edge_density = cv2.countNonZero(edge_region) / edge_mask.sum() * 255
        
        # UI 元素聚类
        contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_contours = [c for c in contours if cv2.contourArea(c) > 100]
        features.ui_clusters = len(valid_contours)
        features.max_ui_area = max([cv2.contourArea(c) for c in valid_contours]) if valid_contours else 0
        
        return features
    
    def _extract_color_features(self, image: np.ndarray) -> ColorFeatures:
        """提取颜色特征"""
        features = ColorFeatures()
        
        # HSV 颜色空间
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # 金色元素检测
        lower_gold = np.array([25, 100, 100])
        upper_gold = np.array([35, 255, 255])
        gold_mask = cv2.inRange(hsv, lower_gold, upper_gold)
        
        # 形态学操作
        kernel = np.ones((3, 3), np.uint8)
        dilated_gold = cv2.dilate(gold_mask, kernel, iterations=2)
        eroded_gold = cv2.erode(dilated_gold, kernel, iterations=1)
        
        # 金色元素数量和面积
        contours, _ = cv2.findContours(eroded_gold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_gold = [c for c in contours if cv2.contourArea(c) > 50]
        features.golden_count = len(valid_gold)
        features.golden_ratio = cv2.countNonZero(eroded_gold) / eroded_gold.size
        
        # 金色元素空间分布熵
        if features.golden_count > 0:
            centroids = [cv2.moments(c) for c in valid_gold]
            centroids = [(m["M10"]/(m["M00"]+1e-6), m["M01"]/(m["M00"]+1e-6))
                        for m in centroids if m["M00"] > 0]
            if centroids:
                cx = np.mean([c[0] for c in centroids])
                cy = np.mean([c[1] for c in centroids])
                distances = [np.sqrt((c[0]-cx)**2 + (c[1]-cy)**2) for c in centroids]
                features.golden_entropy = np.std(distances) / (self.img_width / 2)
        
        # 颜色直方图
        h_hist = cv2.calcHist([hsv], [0], None, [32], [0, 180])
        features.hsv_histogram = h_hist.flatten() / (h_hist.sum() + 1e-6)
        
        # 亮度和饱和度
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        features.brightness_mean = np.mean(gray)
        features.brightness_std = np.std(gray)
        features.saturation_mean = np.mean(cv2.split(hsv)[1])
        
        return features
    
    def _extract_texture_features(self, image: np.ndarray) -> TextureFeatures:
        """提取纹理特征"""
        features = TextureFeatures()
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 边缘检测
        edges = cv2.Canny(gray, 50, 150)
        features.edge_density = cv2.countNonZero(edges) / edges.size
        
        # LBP 特征
        lbp = self._compute_lbp(gray)
        lbp_hist, _ = np.histogram(lbp.flatten(), bins=10, range=(0, 10))
        features.lbp_histogram = lbp_hist / (lbp_hist.sum() + 1e-6)
        
        # 频域特征 (FFT)
        f_transform = np.fft.fft2(gray)
        f_shift = np.fft.fftshift(f_transform)
        magnitude = np.abs(f_shift)
        
        # 高频能量 (中心区域外的能量)
        h, w = magnitude.shape
        center_h, center_w = h//4, w//4
        high_freq = magnitude[center_h:3*center_h, center_w:3*center_w]
        features.high_freq_energy = np.sum(high_freq) / (np.sum(magnitude) + 1e-6)
        
        # HOG 特征
        hog_hist = self._compute_hog(gray)
        features.hog_histogram = hog_hist / (hog_hist.sum() + 1e-6)
        
        return features
    
    def _compute_lbp(self, image: np.ndarray, radius: int = 1, points: int = 8) -> np.ndarray:
        """计算局部二值模式 (LBP)"""
        lbp = np.zeros_like(image, dtype=np.uint8)
        h, w = image.shape
        
        for y in range(radius, h-radius):
            for x in range(radius, w-radius):
                center = image[y, x]
                code = 0
                for i in range(points):
                    angle = 2 * np.pi * i / points
                    nx = int(x + radius * np.cos(angle))
                    ny = int(y + radius * np.sin(angle))
                    if image[ny, nx] >= center:
                        code |= (1 << i)
                lbp[y, x] = code
        
        # 统一 LBP (reduce to 10 patterns)
        uniform_lbp = np.zeros_like(lbp)
        for y in range(h):
            for x in range(w):
                bits = bin(lbp[y, x]).count('1')
                if bits <= 2 or bits >= points-1:
                    uniform_lbp[y, x] = bits
                else:
                    uniform_lbp[y, x] = points + 1
        
        return uniform_lbp
    
    def _compute_hog(self, image: np.ndarray, orientations: int = 9) -> np.ndarray:
        """计算梯度方向直方图 (简化版 HOG)"""
        grad_x = cv2.Sobel(image, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(image, cv2.CV_64F, 0, 1, ksize=3)
        
        magnitude, angle = cv2.cartToPolar(grad_x, grad_y)
        angle = angle * 180 / np.pi  # Convert to degrees
        
        # 直方图
        hist, _ = np.histogram(angle.flatten(), bins=orientations, range=(0, 180))
        return hist
    
    def _fuse_features(self, result: PageAnalysisResult) -> Tuple[PageType, float]:
        """多特征融合判断页面类型"""
        scores = {}  # page_type -> score
        
        # 1. 基于金色元素数量评分
        golden = result.color_features.golden_count
        for page_type, profile in self.PAGE_PROFILES.items():
            if "golden_count" in profile:
                min_g, max_g = profile["golden_count"]
                if min_g <= golden <= max_g:
                    scores[page_type] = scores.get(page_type, 0) + 0.3
                elif abs(golden - min_g) <= 3 or abs(golden - max_g) <= 3:
                    scores[page_type] = scores.get(page_type, 0) + 0.15
        
        # 2. 基于边缘密度评分
        edge_density = result.texture_features.edge_density
        for page_type, profile in self.PAGE_PROFILES.items():
            if "edge_density" in profile:
                min_e, max_e = profile["edge_density"]
                if min_e <= edge_density <= max_e:
                    scores[page_type] = scores.get(page_type, 0) + 0.2
                elif abs(edge_density - min_e) <= 0.05 or abs(edge_density - max_e) <= 0.05:
                    scores[page_type] = scores.get(page_type, 0) + 0.1
        
        # 3. 基于亮度评分
        brightness = result.color_features.brightness_mean
        for page_type, profile in self.PAGE_PROFILES.items():
            if "brightness_mean" in profile:
                min_b, max_b = profile["brightness_mean"]
                if min_b <= brightness <= max_b:
                    scores[page_type] = scores.get(page_type, 0) + 0.2
        
        # 4. 基于 YOLO 人物检测评分
        has_person = "person" in result.yolo_classes
        for page_type, profile in self.PAGE_PROFILES.items():
            if "has_person" in profile:
                if profile["has_person"] == has_person:
                    scores[page_type] = scores.get(page_type, 0) + 0.15
        
        # 5. 基于 OCR 关键词评分
        ocr_lower = result.ocr_text.lower()
        keyword_scores = {
            PageType.TITLE: ["点击进入", "进入游戏", "开始游戏", "适龄提示", "鹰角网络"],
            PageType.LOADING: ["加载中", "loading", "正在加载"],
            PageType.EXIT_DIALOG: ["退出", "确认退出", "自动登出", "长时间没有操作"],
            PageType.QUEST_PANEL: ["每日任务", "每周任务", "领取", "任务"],
            PageType.WORLD: ["探索", "工业", "基地"],
            PageType.SETTINGS: ["设置", "性能", "画面", "声音"],
        }
        
        for page_type, keywords in keyword_scores.items():
            if any(kw in ocr_lower for kw in keywords):
                scores[page_type] = scores.get(page_type, 0) + 0.3
        
        # 6. 基于空间布局评分
        nav_density = result.spatial_features.nav_bar_density
        center_density = result.spatial_features.center_panel_density
        
        if nav_density > 0.4 and center_density > 0.5:
            scores[PageType.QUEST_PANEL] = scores.get(PageType.QUEST_PANEL, 0) + 0.2
        elif nav_density > 0.3 and center_density < 0.3:
            scores[PageType.WORLD] = scores.get(PageType.WORLD, 0) + 0.15
        
        # 选择最高分
        if scores:
            best_type = max(scores, key=scores.get)
            best_score = scores[best_type]
            return best_type, min(best_score, 1.0)
        
        return PageType.UNKNOWN, 0.0


# 测试代码
if __name__ == "__main__":
    # 加载测试图像
    test_img = cv2.imread("test_screenshot.png")
    if test_img is not None:
        # 旋转到横屏并 resize
        test_img = cv2.rotate(test_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        test_img = cv2.resize(test_img, (1280, 720))
        
        # 分析
        analyzer = GameScreenAnalyzer()
        result = analyzer.analyze(test_img, ocr_text="测试文本", yolo_classes=["person"])
        
        print(f"预测页面：{result.predicted_type.value}")
        print(f"置信度：{result.confidence:.3f}")
        print("\n分析日志:")
        for log in result.analysis_log:
            print(f"  {log}")
