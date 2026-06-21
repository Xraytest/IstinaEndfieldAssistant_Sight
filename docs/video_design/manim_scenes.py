from manim import *

# 颜色定义（IEA 品牌色）
IEA_TEAL = "#18D1FF"
IEA_GREEN = "#00FFA2"
IEA_RED = "#FF3355"
IEA_BG = "#0A0A0F"


class DataFlowScene(Scene):
    """场景：数据流动效果（用于场景 4）"""
    
    def construct(self):
        self.camera.background_color = IEA_BG
        
        # 二进制数据流
        binary_text = Text(
            "0101 1100 1010 1111 0010",
            font="Consolas",
            color=IEA_TEAL,
            font_size=36
        )
        
        # 发光效果
        glow = Text(
            "0101 1100 1010 1111 0010",
            font="Consolas",
            color=IEA_TEAL,
            font_size=36
        ).set_opacity(0.3).blur(1)
        
        self.add(glow)
        self.play(Write(binary_text), run_time=1.5)
        self.wait(0.5)
        
        # 数据流动动画
        for i in range(3):
            self.play(
                binary_text.animate.shift(UP * 0.5),
                run_time=0.5
            )
            self.play(
                binary_text.animate.shift(DOWN * 0.5),
                run_time=0.5
            )
        
        self.play(FadeOut(binary_text), FadeOut(glow))


class HighlightBoxScene(Scene):
    """场景：UI 元素高亮框（用于场景 3）"""
    
    def construct(self):
        self.camera.background_color = IEA_BG
        
        # 模拟游戏界面（用矩形代替）
        game_ui = Rectangle(
            width=16, height=9,
            fill_color="#1A1A2E",
            fill_opacity=1,
            stroke_width=0
        )
        self.add(game_ui)
        
        # UI 元素标签
        labels = [
            Text("签到", font="Consolas", color=WHITE, font_size=24),
            Text("领取", font="Consolas", color=WHITE, font_size=24),
            Text("任务", font="Consolas", color=WHITE, font_size=24),
        ]
        labels[0].move_to([-3, 1, 0])
        labels[1].move_to([0, 1, 0])
        labels[2].move_to([3, 1, 0])
        
        for label in labels:
            self.add(label)
        
        # 高亮框动画
        for i, label in enumerate(labels):
            box = Rectangle(
                width=1.5, height=0.8,
                color=IEA_TEAL,
                stroke_width=4,
                fill_opacity=0.1
            ).move_to(label.get_center())
            
            # 发光效果
            glow = Rectangle(
                width=1.6, height=0.9,
                color=IEA_TEAL,
                stroke_width=2,
                fill_opacity=0.05
            ).move_to(label.get_center())
            
            self.play(Create(box), run_time=0.3)
            self.add(glow)
            self.wait(0.5)
            self.play(FadeOut(box), FadeOut(glow), run_time=0.3)


class ProgressBarScene(Scene):
    """场景：进度条动画（用于场景 4）"""
    
    def construct(self):
        self.camera.background_color = IEA_BG
        
        # 标签
        label = Text(
            "Loading: qwen3.5-35b-a3b",
            font="Consolas",
            color=IEA_TEAL,
            font_size=28
        )
        label.to_edge(UP, buff=2)
        
        # 进度条背景
        bar_bg = Rectangle(
            width=10, height=0.4,
            fill_color="#2A2A3E",
            fill_opacity=1,
            stroke_width=0
        )
        
        # 进度条填充
        bar_fill = Rectangle(
            width=0, height=0.4,
            fill_color=IEA_TEAL,
            fill_opacity=1,
            stroke_width=0
        ).next_to(bar_bg, LEFT, buff=0)
        
        # 百分比文字
        percent = Text(
            "0%", font="Consolas",
            color=IEA_GREEN, font_size=24
        ).next_to(bar_bg, RIGHT, buff=0.5)
        
        self.play(Write(label))
        self.add(bar_bg, bar_fill, percent)
        
        # 进度条增长动画
        for i in range(0, 101, 5):
            bar_fill.set_width(10 * i / 100, stretch=True)
            percent.become(Text(
                f"{i}%", font="Consolas",
                color=IEA_GREEN, font_size=24
            ).next_to(bar_bg, RIGHT, buff=0.5))
            self.wait(0.08)
        
        self.wait(0.5)
        self.play(FadeOut(label), FadeOut(bar_bg), 
                  FadeOut(bar_fill), FadeOut(percent))


class EncryptionScene(Scene):
    """场景：加密通信动画（用于场景 4）"""
    
    def construct(self):
        self.camera.background_color = IEA_BG
        
        # TCP 协议标识
        tcp_label = Text(
            "TCP // ARKS",
            font="Consolas",
            color=IEA_TEAL,
            font_size=32
        ).to_edge(LEFT, buff=2)
        
        # Fernet 加密标识
        fernet_label = Text(
            "Fernet Encrypted",
            font="Consolas",
            color=IEA_GREEN,
            font_size=28
        ).to_edge(RIGHT, buff=2)
        
        # 十六进制数据流
        hex_data = Text(
            "4A 7B 9C 2E F1 3D",
            font="Consolas",
            color=WHITE,
            font_size=24
        )
        
        # 锁图标（用矩形模拟）
        lock = Square(
            side_length=0.5,
            color=IEA_GREEN,
            stroke_width=3,
            fill_color=IEA_GREEN,
            fill_opacity=0.3
        )
        
        self.play(Write(tcp_label), Write(fernet_label))
        self.add(lock)
        
        # 数据流动
        for i in range(5):
            new_hex = Text(
                f"{random.randint(0, 255):02X} {random.randint(0, 255):02X} "
                f"{random.randint(0, 255):02X} {random.randint(0, 255):02X} "
                f"{random.randint(0, 255):02X} {random.randint(0, 255):02X}",
                font="Consolas",
                color=WHITE,
                font_size=24
            )
            self.play(Transform(hex_data, new_hex), run_time=0.5)
        
        self.play(FadeOut(tcp_label), FadeOut(fernet_label),
                  FadeOut(hex_data), FadeOut(lock))


class LogoScene(Scene):
    """场景：IEA Logo 动画（用于场景 6）"""
    
    def construct(self):
        self.camera.background_color = IEA_BG
        
        # IEA 字母（几何风格）
        i_rect = Rectangle(
            width=0.3, height=2,
            fill_color=IEA_TEAL,
            fill_opacity=1,
            stroke_width=0
        )
        
        e_rects = VGroup(
            Rectangle(width=1.2, height=0.3, fill_color=IEA_TEAL, fill_opacity=1, stroke_width=0),
            Rectangle(width=0.8, height=0.3, fill_color=IEA_TEAL, fill_opacity=1, stroke_width=0),
            Rectangle(width=1.0, height=0.3, fill_color=IEA_TEAL, fill_opacity=1, stroke_width=0),
        ).arrange(DOWN, center=False, aligned_edge=LEFT)
        e_rects.next_to(i_rect, RIGHT, buff=0.3)
        
        a_tri = Polygon(
            [-0.8, 1, 0], [0.8, 1, 0], [0, -1, 0],
            fill_color=IEA_TEAL,
            fill_opacity=1,
            stroke_width=0
        )
        a_rect = Rectangle(
            width=0.6, height=0.6,
            fill_color=IEA_BG,
            fill_opacity=1,
            stroke_width=0
        )
        a_group = VGroup(a_tri, a_rect).move_to([2.5, 0, 0])
        
        logo = VGroup(i_rect, e_rects, a_group)
        
        # 发光效果
        logo_glow = VGroup(i_rect, e_rects, a_group).copy().set_opacity(0.3).blur(1)
        
        self.add(logo_glow)
        self.play(Create(i_rect), run_time=0.5)
        self.play(Create(e_rects), run_time=0.5)
        self.play(Create(a_tri), Create(a_rect), run_time=0.5)
        self.wait(1)
        
        # Slogan
        slogan = Text(
            "完全智能 · 解放双手",
            font="思源黑体",
            color=WHITE,
            font_size=48
        ).to_edge(DOWN, buff=2)
        
        self.play(Write(slogan), run_time=2)
        self.wait(2)
        self.play(FadeOut(logo), FadeOut(logo_glow), FadeOut(slogan))


class EfficiencyScene(Scene):
    """场景：效率提升数据（用于场景 3）"""
    
    def construct(self):
        self.camera.background_color = IEA_BG
        
        # 标题
        title = Text(
            "Efficiency Boost",
            font="Consolas",
            color=IEA_TEAL,
            font_size=36
        ).to_edge(UP, buff=2)
        
        # 数据
        data_items = [
            (Text("Manual", font="Consolas", color=GRAY, font_size=28), "100%"),
            (Text("IEA Auto", font="Consolas", color=IEA_TEAL, font_size=28), "300%"),
        ]
        
        # 进度条
        bars = []
        for i, (label, _) in enumerate(data_items):
            bar_bg = Rectangle(
                width=8, height=0.4,
                fill_color="#2A2A3E",
                fill_opacity=1,
                stroke_width=0
            ).next_to(label, RIGHT, buff=1)
            
            width = 4 if i == 0 else 12
            bar_fill = Rectangle(
                width=0, height=0.4,
                fill_color=IEA_GREEN if i == 1 else IEA_TEAL,
                fill_opacity=1,
                stroke_width=0
            ).next_to(bar_bg, LEFT, buff=0)
            
            bars.append((bar_bg, bar_fill))
            self.add(bar_bg, bar_fill)
        
        percent_texts = []
        for i, (_, percent) in enumerate(data_items):
            pt = Text(
                percent, font="Consolas",
                color=IEA_GREEN, font_size=28
            ).next_to(bars[i][0], RIGHT, buff=0.5)
            percent_texts.append(pt)
            self.add(pt)
        
        self.play(Write(title))
        
        for i, (label, _) in enumerate(data_items):
            self.play(Write(label))
            self.play(
                bars[i][1].animate.set_width(4 if i == 0 else 12, stretch=True),
                run_time=1
            )
        
        self.wait(2)
        self.play(FadeOut(title))
        for label, _ in data_items:
            self.play(FadeOut(label))
        for bar_bg, bar_fill in bars:
            self.play(FadeOut(bar_bg), FadeOut(bar_fill))
        for pt in percent_texts:
            self.play(FadeOut(pt))
