"""IEA 宣传视频完整生成脚本
生成 60 秒 1920x1080 宣传视频"""

import os
import sys
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from datetime import datetime

# ── 配置 ──
FPS = 24
W, H = 1920, 1080
TOTAL_SECONDS = 60
TOTAL_FRAMES = FPS * TOTAL_SECONDS

FFMPEG_PATH = r"C:\Users\xray\Documents\ffmpeg\ffmpeg.exe"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_VIDEO = os.path.join(PROJECT_ROOT, "output", "iea_promo_video_v1.mp4")
FRAME_DIR = os.path.join(PROJECT_ROOT, "output", "_frames")

# ── 品牌色 ──
C_TEAL = (24, 209, 255)
C_GREEN = (0, 255, 162)
C_RED = (255, 51, 85)
C_BG = (10, 10, 15)
C_TEXT = (224, 224, 232)
C_MUTED = (144, 144, 168)
C_DIM = (64, 64, 88)
C_CARD_BG = (16, 16, 26)

# ── 字体路径（若缺失则用默认） ──
FONT_CONSOLAS = None
FONT_SANS = None
for fp in [
    r"C:\Windows\Fonts\consola.ttf",
    r"C:\Windows\Fonts\CONSOLA.TTF",
]:
    if os.path.exists(fp):
        FONT_CONSOLAS = fp
        break

for fp in [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\SIMHEI.TTF",
]:
    if os.path.exists(fp):
        FONT_SANS = fp
        break


def get_font(size, bold=False):
    """加载 Consolas 字体"""
    if FONT_CONSOLAS:
        return ImageFont.truetype(FONT_CONSOLAS, size)
    return ImageFont.load_default()


def get_sans_font(size):
    """加载中文字体"""
    if FONT_SANS:
        return ImageFont.truetype(FONT_SANS, size)
    return ImageFont.load_default()


def new_frame():
    img = Image.new("RGB", (W, H), C_BG)
    draw = ImageDraw.Draw(img)
    return img, draw


def draw_grid(draw, opacity=15):
    """装饰网格线"""
    step_x = W // 5
    step_y = H // 5
    for x in range(0, W + 1, step_x):
        alpha = opacity
        draw.line([(x, 0), (x, H)], fill=(*C_TEAL, alpha), width=1)
    for y in range(0, H + 1, step_y):
        alpha = opacity
        draw.line([(0, y), (W, y)], fill=(*C_TEAL, alpha), width=1)


def draw_horizontal_bar(draw, x, y, w, h, color, opacity=255, corner=0):
    """半透明矩形条"""
    r, g, b = color
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rounded_rectangle([x, y, x + w, y + h], radius=corner, fill=(r, g, b, opacity))
    return overlay


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ── 场景生成函数 ──

def scene_1_pain_point(frame_idx, sec):
    """0-8s: 痛点引入"""
    img, draw = new_frame()
    draw_grid(draw, 8)

    progress = sec / 8  # 0->1

    # 快速点击动画（多个点击波纹）
    click_positions = [(800, 400), (1100, 500), (600, 600), (1200, 350), (700, 550)]
    for i, (cx, cy) in enumerate(click_positions):
        phase = (sec * 3 + i * 1.2) % 1
        if phase < 0.5:
            rad = int(phase * 2 * 30)
            alpha = int((1 - phase * 2) * 100)
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.ellipse([cx - rad, cy - rad, cx + rad, cy + rad],
                       outline=(*C_TEAL, alpha), width=2)
            img = Image.alpha_composite(img.convert("RGBA"), overlay)

    # 文字：日常任务 · 重复操作 · 时间消耗
    texts = ["日常任务", "重复操作", "时间消耗"]
    for i, t in enumerate(texts):
        alpha = max(0, int(255 * (1 - abs(progress * 3 - i * 0.33 - 0.15) * 4)))
        f = get_sans_font(40)
        draw.text((960, 400 + i * 70), t, fill=(*C_TEXT, alpha), font=f, anchor="mm")

    # 底部状态栏
    bar = draw_horizontal_bar(draw, 0, H - 60, W, 60, C_CARD_BG, 180, 4)
    img = Image.alpha_composite(img.convert("RGBA"), bar)
    d = ImageDraw.Draw(img)
    f_small = get_font(14)
    d.text((30, H - 40), "STATUS: MANUAL OPERATION", fill=(*C_RED, 200), font=f_small)
    d.text((W - 30, H - 40), "EFFICIENCY: 1x", fill=(*C_MUTED, 200), font=f_small, anchor="rm")

    return img.convert("RGB")


def scene_2_solution(frame_idx, sec):
    """8-15s: 解决方案"""
    img, draw = new_frame()
    draw_grid(draw, 8)
    progress = (sec - 8) / 7

    # 终端界面效果
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # 终端边框
    od.rounded_rectangle([200, 200, W - 200, H - 200], radius=8,
                         outline=(*C_TEAL, 60), width=1)
    od.rounded_rectangle([200, 200, W - 200, 245], radius=0,
                         fill=(*C_TEAL, 8))
    od.rounded_rectangle([200, 200, W - 200, 245], radius=0,
                         outline=(*C_TEAL, 30), width=1)

    # 标题栏
    od.text((240, 218), "AGENT TERMINAL", fill=(*C_TEAL, 200),
            font=get_font(18))
    od.text((W - 260, 218), "● ONLINE", fill=(*C_GREEN, 200),
            font=get_font(14))

    # 输入框效果
    box_y = H - 170
    od.rounded_rectangle([220, box_y, W - 220, box_y + 55], radius=4,
                         fill=(*C_BG, 200), outline=(*C_TEAL, 40), width=1)
    od.text((240, box_y + 14), ">>> 输入指令...", fill=(*C_MUTED, 150),
            font=get_font(16))

    # 聊天记录效果（渐显）
    chat_lines = [
        "> 自动探索游戏界面",
        "> 识别 UI 元素 · 分析布局",
        "> 执行点击/滑动操作",
    ]
    for i, line in enumerate(chat_lines):
        alpha = max(0, int(255 * min(1, (progress - 0.1 - i * 0.2) * 5)))
        od.text((240, 280 + i * 45), line, fill=(*C_TEXT, alpha),
                font=get_font(15))

    # 大标题
    title_alpha = int(255 * min(1, progress * 3))
    f_big = get_sans_font(60)
    od.text((960, 380), "I E A", fill=(*C_TEAL, title_alpha),
            font=f_big, anchor="mm")
    f_sub = get_sans_font(28)
    od.text((960, 445), "智能自动化助手", fill=(*C_TEXT, title_alpha),
            font=f_sub, anchor="mm")

    # 底部绿色横线
    line_alpha = int(80 * min(1, progress * 2))
    od.line([600, 500, 1320, 500], fill=(*C_GREEN, line_alpha), width=2)

    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    return img.convert("RGB")


def scene_3_features(frame_idx, sec):
    """15-35s: 核心功能展示"""
    img, draw = new_frame()
    draw_grid(draw, 8)

    subsec = sec - 15
    phase = subsec / 20  # 0->1

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # 游戏界面模拟框
    od.rounded_rectangle([150, 140, W - 150, 680], radius=4,
                         fill=(*C_CARD_BG, 230), outline=(*C_TEAL, 30), width=1)

    # UI 元素高亮框（模拟 VLM 识别）
    elements = [
        (300, 250, 400, 310, "签到", C_GREEN),
        (500, 250, 600, 310, "领取", C_GREEN),
        (700, 250, 800, 310, "任务", C_GREEN),
        (400, 400, 520, 470, "战斗", C_TEAL),
        (600, 500, 720, 570, "制造", C_TEAL),
    ]
    for i, (ex1, ey1, ex2, ey2, label, color) in enumerate(elements):
        el_phase = (phase * 2 + i * 0.15) % 1
        if el_phase < 0.4:
            a = int(200 * (1 - el_phase / 0.4))
            od.rectangle([ex1, ey1, ex2, ey2], outline=(*color, a), width=3)
            od.text((ex1 + 10, ey1 - 25), label, fill=(*color, a),
                    font=get_font(12))

    # 左侧聊天面板
    chat_x = 80
    od.rounded_rectangle([chat_x, 140, chat_x + 300, 680], radius=4,
                         fill=(*C_BG, 200), outline=(*C_TEAL, 20), width=1)
    od.text((chat_x + 15, 160), "<<< Go to crafting", fill=(*C_TEAL, 200),
            font=get_font(13))
    od.text((chat_x + 15, 195), ">>> tap(450, 320)", fill=(*C_GREEN, 180),
            font=get_font(13))
    od.text((chat_x + 15, 230), "   ✓ swipe(450, 320, 450, 600)", fill=(*C_GREEN, 160),
            font=get_font(12))
    od.text((chat_x + 15, 265), ">>> wait(2.0)", fill=(*C_GREEN, 160),
            font=get_font(13))

    # 右侧统计面板
    stats_x = W - 400
    od.rounded_rectangle([stats_x, 140, stats_x + 320, 300], radius=4,
                         fill=(*C_BG, 200), outline=(*C_GREEN, 30), width=1)
    od.text((stats_x + 15, 160), "STATISTICS", fill=(*C_GREEN, 200),
            font=get_font(14))
    od.text((stats_x + 15, 195), f"Pages:     {int(12 + phase * 30)}",
            fill=(*C_TEXT, 200), font=get_font(13))
    od.text((stats_x + 15, 225), f"Elements:  {int(45 + phase * 80)}",
            fill=(*C_TEXT, 200), font=get_font(13))
    od.text((stats_x + 15, 255), f"VLM Calls: {int(30 + phase * 120)}",
            fill=(*C_TEXT, 200), font=get_font(13))
    od.text((stats_x + 15, 285), f"Taps:      {int(50 + phase * 200)}",
            fill=(*C_TEXT, 200), font=get_font(13))

    # 效率对比条
    bar_y = 730
    od.text((300, bar_y), "Manual", fill=(*C_MUTED, 200), font=get_font(16))
    od.text((300, bar_y + 50), "IEA Auto", fill=(*C_TEAL, 200), font=get_font(16))

    # Manual 条
    od.rounded_rectangle([500, bar_y, 500 + 300, bar_y + 30], radius=4,
                         fill=(*C_DIM, 200))
    od.rounded_rectangle([500, bar_y + 50, 500 + min(900, int(300 + phase * 600)), bar_y + 80],
                         radius=4, fill=(*C_TEAL, 200))
    od.text((820, bar_y + 55), f"{int(100 + phase * 200)}%",
            fill=(*C_GREEN, 200), font=get_font(14))

    # 底部状态
    od.text((30, H - 40), "STATUS: AGENT ACTIVE",
            fill=(*C_GREEN, 200), font=get_font(13))
    od.text((W - 30, H - 40), f"SCENE 3/6  ({int(subsec + 16)}s)",
            fill=(*C_MUTED, 200), font=get_font(12), anchor="rm")

    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    return img.convert("RGB")


def scene_4_tech(frame_idx, sec):
    """35-48s: 技术优势"""
    img, draw = new_frame()
    draw_grid(draw, 8)
    subsec = sec - 35
    phase = subsec / 13

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # 三栏布局
    col_w = 520
    gap = 60
    start_x = (W - col_w * 3 - gap * 2) // 2

    titles = ["本地推理", "云端模式", "加密通信"]
    icons = ["GGUF", "API", "Fernet"]
    descs = [
        ["llama-cpp-python", "qwen3.5-35b-a3b", "GPU 加速 CUDA 12.4"],
        ["模型路由", "自动负载均衡", "API Key 认证"],
        ["TLS 传输", "AES-256 加密", "会话安全"],
    ]

    cols_phase = phase * 3
    for col in range(3):
        x = start_x + col * (col_w + gap)
        cp = max(0, min(1, cols_phase - col * 0.3) * 3)

        # 卡片背景
        od.rounded_rectangle([x, 250, x + col_w, 700], radius=8,
                             fill=(*C_CARD_BG, int(180 * cp)),
                             outline=(*C_TEAL, int(30 * cp)), width=1)

        # 标题
        f_t = get_font(24)
        od.text((x + col_w // 2, 280), titles[col],
                fill=(*C_TEAL, int(255 * cp)), font=f_t, anchor="mm")

        # 图标框
        od.rounded_rectangle([x + col_w // 2 - 50, 320, x + col_w // 2 + 50, 380],
                             radius=6, fill=(*C_TEAL, int(20 * cp)),
                             outline=(*C_TEAL, int(40 * cp)), width=1)
        od.text((x + col_w // 2, 350), icons[col],
                fill=(*C_GREEN, int(230 * cp)), font=get_font(14), anchor="mm")

        # 描述列表
        for j, desc in enumerate(descs[col]):
            da = int(255 * cp * max(0, min(1, (cols_phase - col * 0.3 - j * 0.1) * 4)))
            od.text((x + 30, 420 + j * 45), f"▸ {desc}",
                    fill=(*C_TEXT, da), font=get_font(14))

    # 底部进度指示条
    loading_w = int(800 * phase)
    od.rounded_rectangle([560, 850, 560 + 800, 870], radius=4,
                         fill=(*C_DIM, 150))
    od.rounded_rectangle([560, 850, 560 + loading_w, 870], radius=4,
                         fill=(*C_TEAL, 200))
    od.text((960, 890), f"系统初始化完成 {int(phase * 100)}%",
            fill=(*C_MUTED, 200), font=get_font(13), anchor="mm")

    od.text((30, H - 40), "STATUS: INFERENCE READY",
            fill=(*C_GREEN, 200), font=get_font(13))

    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    return img.convert("RGB")


def scene_5_usecase(frame_idx, sec):
    """48-55s: 使用场景"""
    img, draw = new_frame()
    draw_grid(draw, 8)
    subsec = sec - 48
    phase = subsec / 7

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # 电脑屏幕效果（左侧大框）
    od.rounded_rectangle([200, 200, 900, 750], radius=8,
                         fill=(*C_CARD_BG, 230), outline=(*C_TEAL, 30), width=1)

    # 屏幕内的小终端
    od.rounded_rectangle([220, 220, 880, 730], radius=4,
                         fill=(*C_BG, 200))
    od.text((240, 240), "AGENT TERMINAL — RUNNING",
            fill=(*C_GREEN, 200), font=get_font(14))
    od.text((240, 280), ">>> Checking daily missions...",
            fill=(*C_TEXT, 180), font=get_font(13))
    od.text((240, 315), ">>> Mission 1/5 complete",
            fill=(*C_GREEN, 160), font=get_font(13))
    od.text((240, 350), ">>> Mission 2/5 complete",
            fill=(*C_GREEN, 160), font=get_font(13))
    od.text((240, 385), ">>> Mission 3/5 in progress",
            fill=(*C_MUTED, 150), font=get_font(13))

    # 右侧手机效果
    phone_x = 1100
    phone_y = 300
    od.rounded_rectangle([phone_x, phone_y, phone_x + 200, phone_y + 400],
                         radius=20, fill=(*C_CARD_BG, 200),
                         outline=(*C_TEAL, 40), width=2)
    # 手机屏幕
    od.rounded_rectangle([phone_x + 10, phone_y + 25, phone_x + 190, phone_y + 380],
                         radius=4, fill=(*C_BG, 200))
    od.text((phone_x + 100, phone_y + 60), "IEA Remote",
            fill=(*C_TEAL, 200), font=get_font(12), anchor="mm")
    od.text((phone_x + 100, phone_y + 100), "STATUS: ONLINE",
            fill=(*C_GREEN, 200), font=get_font(11), anchor="mm")
    od.text((phone_x + 100, phone_y + 140), "Pages: 15",
            fill=(*C_MUTED, 180), font=get_font(10), anchor="mm")
    od.text((phone_x + 100, phone_y + 165), "Taps: 234",
            fill=(*C_MUTED, 180), font=get_font(10), anchor="mm")
    od.text((phone_x + 100, phone_y + 190), "Runtime: 2h",
            fill=(*C_MUTED, 180), font=get_font(10), anchor="mm")

    # 箭头连接线
    od.line([900, 480, 1100, 480], fill=(*C_TEAL, 60), width=2)

    # 主文字
    title_alpha = int(255 * min(1, phase * 3))
    f_big = get_sans_font(48)
    od.text((960, 120), "解放双手", fill=(*C_TEXT, title_alpha),
            font=f_big, anchor="mm")
    f_sub = get_sans_font(28)
    od.text((960, 170), "智能托管 · 全天候运行", fill=(*C_MUTED, title_alpha),
            font=f_sub, anchor="mm")

    # 底部状态
    od.text((30, H - 40), "STATUS: AUTOMATION ACTIVE",
            fill=(*C_GREEN, 200), font=get_font(13))

    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    return img.convert("RGB")


def scene_6_brand(frame_idx, sec):
    """55-60s: 品牌收尾"""
    img, draw = new_frame()
    draw_grid(draw, 8)
    subsec = sec - 55
    phase = subsec / 5  # 0->1

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # IEA Logo（几何风格）
    logo_alpha = int(255 * min(1, phase * 2))
    glow_alpha = int(60 * min(1, phase * 2))

    # IEA 发光背景
    od.ellipse([680, 280, 1240, 840], fill=(*C_TEAL, glow_alpha))

    # I - 竖线
    lx = 780
    od.rectangle([lx, 400, lx + 20, 700], fill=(*C_TEAL, logo_alpha))
    od.rectangle([lx - 20, 400, lx + 40, 420], fill=(*C_TEAL, logo_alpha))
    od.rectangle([lx - 20, 680, lx + 40, 700], fill=(*C_TEAL, logo_alpha))

    # E
    ex = 860
    od.rectangle([ex, 400, ex + 16, 700], fill=(*C_TEAL, logo_alpha))
    od.rectangle([ex, 400, ex + 90, 420], fill=(*C_TEAL, logo_alpha))
    od.rectangle([ex, 540, ex + 65, 560], fill=(*C_TEAL, logo_alpha))
    od.rectangle([ex, 680, ex + 90, 700], fill=(*C_TEAL, logo_alpha))

    # A
    ax = 1000
    poly_a = [(ax, 400), (ax + 80, 700), (ax - 80, 700)]
    od.polygon(poly_a, fill=(*C_TEAL, logo_alpha))
    od.rectangle([ax - 15, 555, ax + 15, 580], fill=(*C_BG, logo_alpha))

    # Slogan
    slogan_alpha = int(255 * min(1, max(0, (phase - 0.3) * 2)))
    f_slogan = get_font(18) if FONT_SANS is None else ImageFont.truetype(FONT_SANS, 36)
    od.text((960, 780), "完全智能 · 解放双手",
            fill=(*C_TEXT, slogan_alpha), font=f_slogan, anchor="mm")

    # 副标题
    od.text((960, 830), "IstinaEndfieldAssistant",
            fill=(*C_MUTED, slogan_alpha), font=get_font(16), anchor="mm")

    # 底部装饰
    od.line([760, 860, 1160, 860], fill=(*C_TEAL, int(40 * slogan_alpha / 255)),
            width=1)

    # 底部文字
    od.text((30, H - 40), "STATUS: MISSION COMPLETE",
            fill=(*C_GREEN, 200), font=get_font(13))
    od.text((W - 30, H - 40), "iea_promo_v1 // 2026",
            fill=(*C_MUTED, 150), font=get_font(11), anchor="rm")

    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    return img.convert("RGB")


# ── 帧生成分发 ──

def generate_frame(frame_idx):
    sec = frame_idx / FPS

    if sec < 8:
        return scene_1_pain_point(frame_idx, sec)
    elif sec < 15:
        return scene_2_solution(frame_idx, sec)
    elif sec < 35:
        return scene_3_features(frame_idx, sec)
    elif sec < 48:
        return scene_4_tech(frame_idx, sec)
    elif sec < 55:
        return scene_5_usecase(frame_idx, sec)
    else:
        return scene_6_brand(frame_idx, sec)


# ── 主流程 ──

def main():
    print("=" * 60)
    print("IEA 宣传视频生成器")
    print(f"分辨率: {W}x{H}")
    print(f"帧率: {FPS}fps")
    print(f"时长: {TOTAL_SECONDS}s")
    print(f"总帧数: {TOTAL_FRAMES}")
    print("=" * 60)

    os.makedirs(FRAME_DIR, exist_ok=True)

    # 生成帧
    frame_files = []
    print(f"\n生成 {TOTAL_FRAMES} 帧...")
    batch_size = 60
    for i in range(0, TOTAL_FRAMES, batch_size):
        end = min(i + batch_size, TOTAL_FRAMES)
        for fi in range(i, end):
            fname = f"frame_{fi:06d}.png"
            fpath = os.path.join(FRAME_DIR, fname)
            img = generate_frame(fi)
            img.save(fpath, "PNG")
            frame_files.append(fpath)

        pct = (end / TOTAL_FRAMES) * 100
        eta_sec = (TOTAL_FRAMES - end) / (batch_size / max(1, (datetime.now().timestamp() - __import__('time').time() if False else 0.5)))
        print(f"  [{pct:5.1f}%] {end}/{TOTAL_FRAMES} 帧", end="\r")

    print(f"\n\n帧生成完成: {len(frame_files)} 文件")

    # ffmpeg 合成视频
    print("\n合成视频...")
    pattern = os.path.join(FRAME_DIR, "frame_%06d.png").replace("\\", "/")

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-framerate", str(FPS),
        "-i", pattern,
        "-c:v", "h264_mf",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}",
        "-movflags", "+faststart",
        OUTPUT_VIDEO,
    ]

    import subprocess
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
        print(f"视频输出: {OUTPUT_VIDEO}")
        print(f"文件大小: {size_mb:.1f} MB")
    else:
        print(f"FFmpeg 错误:\n{result.stderr}")
        return

    # 清理临时帧
    print("\n清理临时帧文件...")
    for f in frame_files:
        os.remove(f)
    os.rmdir(FRAME_DIR)

    print("\n✓ 完成!")
    print(f"  {OUTPUT_VIDEO}")


if __name__ == "__main__":
    main()