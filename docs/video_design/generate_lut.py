"""IEA 品牌 LUT 生成脚本 — Hypergryph 风格调色"""
import struct
import os


LUT_SIZE = 33
LUT_NAME = "IEA_Hypergryph_Cine.cube"

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "output"
)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def srgb_to_linear(c):
    """sRGB to linear"""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    """Linear to sRGB"""
    if c <= 0.0031308:
        return c * 12.92
    return 1.055 * (c ** (1.0 / 2.4)) - 0.055


def apply_look(r, g, b):
    """应用 Hypergryph 风格调色"""
    # 1. 反差控制
    contrast = 1.15
    r = (r - 0.5) * contrast + 0.5
    g = (g - 0.5) * contrast + 0.5
    b = (b - 0.5) * contrast + 0.5

    # 2. 色调偏移 (冷色调)
    r *= 0.95      # 减少红色
    g *= 0.98      # 轻微减少绿色
    b *= 1.05      # 增加蓝色

    # 3. 阴影压缩 (深黑背景 #0A0A0F)
    shadow_lift = 0.04
    r = max(r, shadow_lift)
    g = max(g, shadow_lift)
    b = max(b, shadow_lift)

    # 4. 青色偏移 (高光区域偏青)
    highlight_threshold = 0.7
    if max(r, g, b) > highlight_threshold:
        cyan_strength = (max(r, g, b) - highlight_threshold) / (1.0 - highlight_threshold) * 0.08
        r -= cyan_strength * 0.3
        g -= cyan_strength * 0.1
        b += cyan_strength * 0.5

    # 5. 饱和度降低
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    desat = 0.10
    r = r * (1 - desat) + gray * desat
    g = g * (1 - desat) + gray * desat
    b = b * (1 - desat) + gray * desat

    return max(0.0, min(1.0, r)), max(0.0, min(1.0, g)), max(0.0, min(1.0, b))


def generate_lut(filename):
    """Generate .cube LUT file"""
    lines = []
    lines.append(f"TITLE \"IEA Hypergryph Style\"")
    lines.append(f"LUT_3D_SIZE {LUT_SIZE}")
    lines.append(f"DOMAIN_MIN 0.0 0.0 0.0")
    lines.append(f"DOMAIN_MAX 1.0 1.0 1.0")
    lines.append("")

    for b in range(LUT_SIZE):
        for g in range(LUT_SIZE):
            for r in range(LUT_SIZE):
                ri = r / (LUT_SIZE - 1)
                gi = g / (LUT_SIZE - 1)
                bi = b / (LUT_SIZE - 1)

                ri_lin = srgb_to_linear(ri)
                gi_lin = srgb_to_linear(gi)
                bi_lin = srgb_to_linear(bi)

                ro_lin, go_lin, bo_lin = apply_look(ri_lin, gi_lin, bi_lin)

                ro = linear_to_srgb(ro_lin)
                go = linear_to_srgb(go_lin)
                bo = linear_to_srgb(bo_lin)

                lines.append(f"{ro:.6f} {go:.6f} {bo:.6f}")

    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w") as f:
        f.write("\n".join(lines))

    print(f"LUT generated: {filepath} ({LUT_SIZE}x{LUT_SIZE}x{LUT_SIZE})")


def generate_3dl_lut(filename):
    """Generate .3dl LUT (for older NLE support)"""
    lines = []
    lines.append("# IEA Hypergryph Style 3DL")

    for b in range(LUT_SIZE):
        for g in range(LUT_SIZE):
            for r in range(LUT_SIZE):
                ri = r / (LUT_SIZE - 1)
                gi = g / (LUT_SIZE - 1)
                bi = b / (LUT_SIZE - 1)

                ri_lin = srgb_to_linear(ri)
                gi_lin = srgb_to_linear(gi)
                bi_lin = srgb_to_linear(bi)

                ro_lin, go_lin, bo_lin = apply_look(ri_lin, gi_lin, bi_lin)

                ro = int(linear_to_srgb(ro_lin) * 1023)
                go = int(linear_to_srgb(go_lin) * 1023)
                bo = int(linear_to_srgb(bo_lin) * 1023)

                lines.append(f"{ro} {go} {bo}")

    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w") as f:
        f.write("\n".join(lines))

    print(f"3DL LUT generated: {filepath}")


if __name__ == "__main__":
    generate_lut(LUT_NAME)
    generate_3dl_lut("IEA_Hypergryph_Cine.3dl")

    # 验证：测试几个关键颜色
    test_colors = [
        (0.04, 0.04, 0.06),   # 背景色 #0A0A0F
        (0.094, 0.82, 1.0),   # 青色 #18D1FF
        (0.0, 1.0, 0.635),    # 绿色 #00FFA2
        (1.0, 0.2, 0.333),    # 红色 #FF3355
        (0.878, 0.878, 0.933),# 浅灰 #E0E0E8
    ]

    print("\nLUT 验证:")
    print(f"{'输入 (sRGB)':<25} {'输出 (sRGB)':<25} {'输出 (Hex)':<15}")
    print("-" * 65)

    for cr, cg, cb in test_colors:
        cr_lin = srgb_to_linear(cr)
        cg_lin = srgb_to_linear(cg)
        cb_lin = srgb_to_linear(cb)
        r, g, b = apply_look(cr_lin, cg_lin, cb_lin)
        r_srgb = linear_to_srgb(r)
        g_srgb = linear_to_srgb(g)
        b_srgb = linear_to_srgb(b)
        hex_val = f"#{int(r_srgb*255):02X}{int(g_srgb*255):02X}{int(b_srgb*255):02X}"
        print(f"({cr:.3f}, {cg:.3f}, {cb:.3f})     ({r_srgb:.3f}, {g_srgb:.3f}, {b_srgb:.3f})   {hex_val}")