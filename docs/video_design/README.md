# IEA 宣传视频设计文档索引

## 文档概览

| 文档 | 内容 | 用途 |
|------|------|------|
| [01_concept.md](./01_concept.md) | 核心概念、品牌定位、目标受众 | 理解项目愿景 |
| [02_storyboard.md](./02_storyboard.md) | 详细分镜脚本（60 秒） | 指导视频制作 |
| [03_production.md](./03_production.md) | 工具链、制作流程、渲染配置 | 技术实施指南 |
| [04_recording_script.md](./04_recording_script.md) | 录屏步骤、截图清单、文件组织 | 素材采集指南 |
| [manim_scenes.py](./manim_scenes.py) | Manim 动画脚本 | 科技感动画生成 |

---

## 快速开始

### 1. 阅读核心概念
```bash
打开 01_concept.md
了解：核心主题、目标受众、品牌关键词
```

### 2. 查看详细分镜
```bash
打开 02_storyboard.md
了解：60 秒视频的时间轴、画面、字幕、音效
```

### 3. 准备工具链
```bash
# 安装 Manim（动画）
pip install manim

# 下载 OBS Studio（录屏）
# https://obsproject.com/

# 下载 DaVinci Resolve（剪辑）
# https://www.blackmagicdesign.com/products/davinciresolve/
```

### 4. 录制素材
```bash
# 按 04_recording_script.md 步骤录制
# 保存路径：assets/raw_recordings/
```

### 5. 生成动画
```bash
# 渲染 Manim 动画
manim -pql manim_scenes.py DataFlowScene
manim -pql manim_scenes.py HighlightBoxScene
manim -pql manim_scenes.py ProgressBarScene
manim -pql manim_scenes.py EncryptionScene
manim -pql manim_scenes.py LogoScene
manim -pql manim_scenes.py EfficiencyScene
```

### 6. 剪辑合成
```bash
# 使用 DaVinci Resolve
# 按 02_storyboard.md 拼接素材
# 添加音效和字幕
# 渲染输出
```

---

## 品牌规范

### 颜色
- **主色**: #18D1FF（青色）
- **辅助色**: #00FFA2（绿色）、#FF3355（红色）
- **背景**: #0A0A0F（深黑）
- **文字**: #E0E0E8（浅灰）

### 字体
- **英文/代码**: Consolas
- **中文**: 思源黑体

### 风格
- 极简主义
- 科技感
- 几何线条
- 数据流动

---

## 输出规格

| 版本 | 分辨率 | 帧率 | 用途 |
|------|--------|------|------|
| 主视频 | 1920x1080 | 60fps | YouTube/Bilibili |
| 标准版 | 1280x720 | 30fps | Twitter |
| 竖屏版 | 1080x1920 | 60fps | TikTok/Shorts |

---

## 联系方式

项目仓库：`C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant`

---

## 版本历史

- v1.0 (2026-05-31): 初始版本，完整设计文档
