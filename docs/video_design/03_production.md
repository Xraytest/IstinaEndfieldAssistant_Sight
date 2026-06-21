# IEA 宣传视频制作工具链

## 软件清单

### 1. 录屏工具
| 工具 | 用途 | 配置 |
|------|------|------|
| OBS Studio | 游戏/界面录屏 | 60fps, 265 编码，CBR 20Mbps |
| ShareX | 快速截图 | PNG 无损，自动保存 |

**OBS 场景配置**:
- 场景 1: 游戏窗口捕获（1920x1080）
- 场景 2: IEA GUI 窗口捕获
- 场景 3: 浏览器（Hypergryph 素材参考）

### 2. 动画工具
| 工具 | 用途 | 适用场景 |
|------|------|----------|
| Manim | 数学动画库 | 数据流动、UI 元素高亮 |
| After Effects | 专业动画 | 复杂转场、特效 |
| Blender | 3D 动画 | Logo 动画（可选） |

**推荐**: Manim（开源，适合科技感动画）

### 3. 剪辑工具
| 工具 | 用途 | 优势 |
|------|------|------|
| DaVinci Resolve | 视频剪辑/调色 | 免费专业级 |
| Shotcut | 轻量剪辑 | 开源跨平台 |

**推荐**: DaVinci Resolve（调色强大，符合 Hypergryph 风格）

### 4. 音效工具
| 工具 | 用途 |
|------|------|
| Audacity | 音频编辑 |
| Freesound.org | 音效素材库 |
| YouTube Audio Library | 免版税音效 |

---

## Manim 动画脚本框架

### 安装
```bash
pip install manim
manim -pql scene_template.py TechIntroScene
```

### 核心动画场景

#### 场景 1: 数据流动效果
```python
from manim import *

class DataFlowScene(Scene):
    def construct(self):
        # 二进制数据流
        binary = Text("0101 1100 1010", font="Consolas", color=TEAL)
        self.play(Write(binary))
        self.wait(0.5)
        self.play(FadeOut(binary))
```

#### 场景 2: UI 元素高亮框
```python
class HighlightBoxScene(Scene):
    def construct(self):
        # 模拟游戏界面
        game_ui = ImageMobject("game_screenshot.png")
        self.add(game_ui)
        
        # 高亮框
        box = Rectangle(width=2, height=1, color=TEAL, stroke_width=3)
        box.move_to([1, 0, 0])
        self.play(Create(box))
        self.wait(1)
        self.play(FadeOut(box))
```

#### 场景 3: 进度条动画
```python
class ProgressBarScene(Scene):
    def construct(self):
        label = Text("Loading model...", font="Consolas", color=WHITE)
        bar_bg = Rectangle(width=6, height=0.2, color=GRAY)
        bar_fill = Rectangle(width=0, height=0.2, color=TEAL)
        
        self.play(Write(label))
        self.add(bar_bg, bar_fill)
        self.play(bar_fill.animate.set_width(6), run_time=2)
        self.wait(0.5)
```

---

## DaVinci Resolve 项目配置

### 时间线设置
- 分辨率：1920x1080
- 帧率：60fps
- 色彩空间：Rec.709
- 音频：48kHz, 24bit

### 调色预设（Hypergryph 风格）
```
Lift:   #0A0A0F (深黑背景)
Gamma:  #1A1A2E (冷色调)
Gain:   #E8E8EE (高光)
Saturation: -10 (降低饱和度)
Contrast: +15 (增强对比)
```

### 转场效果
- 硬切（90% 场景）
- 淡入淡出（场景切换）
- 滑入滑出（字幕）

---

## 素材清单

### 必需录屏
- [ ] Agent Terminal 界面操作（1 分钟）
- [ ] IEA Control Panel 界面（30 秒）
- [ ] 游戏实际操作录屏（2 分钟）
- [ ] Model Manager 界面（20 秒）
- [ ] 登录认证流程（30 秒）

### 必需截图
- [ ] 游戏界面（10 张，覆盖主要功能）
- [ ] IEA GUI 各页面（8 张）
- [ ] 数据面板/日志（5 张）

### 音效素材
- [ ] 科技感启动音效
- [ ] 数据流动音效
- [ ] 点击/滑动音效
- [ ] 成功/错误提示音
- [ ] 品牌音效

### 字体
- [ ] Consolas（代码/终端）
- [ ] 思源黑体（中文）

---

## 渲染输出配置

### 主视频
```
格式：MP4
编码：H.264
分辨率：1920x1080
帧率：60fps
比特率：20Mbps
音频：AAC 320kbps
```

### 社交媒体版本
- YouTube: 同上
- Bilibili: 同上
- Twitter: 1280x720, 30fps, 8Mbps
- TikTok: 1080x1920 (竖屏裁剪)

---

## 制作流程

1. **准备阶段** (1 天)
   - 安装工具链
   - 收集/录制素材
   - 准备音效

2. **动画制作** (2 天)
   - Manim 动画脚本编写
   - 渲染动画片段

3. **剪辑阶段** (2 天)
   - 粗剪（按分镜拼接）
   - 精剪（调整节奏）
   - 调色（Hypergryph 风格）

4. **音效阶段** (1 天)
   - 添加背景音乐
   - 添加音效
   - 音频混音

5. **输出阶段** (0.5 天)
   - 渲染主视频
   - 裁剪社交媒体版本
   - 质量检查

**总工期**: 6.5 天
