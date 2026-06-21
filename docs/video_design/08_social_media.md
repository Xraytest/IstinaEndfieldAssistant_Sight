# IEA 宣传视频社交媒体适配指南

## 各平台规格

| 平台 | 分辨率 | 帧率 | 时长 | 格式 |
|------|--------|------|------|------|
| YouTube | 1920x1080 | 60fps | 60s | MP4 H.264 |
| Bilibili | 1920x1080 | 60fps | 60s | MP4 H.265 |
| Twitter/X | 1280x720 | 30fps | 60s | MP4 H.264 |
| TikTok | 1080x1920 | 60fps | 15-60s | MP4 H.264 |
| Instagram Reels | 1080x1920 | 30fps | 15-30s | MP4 H.264 |
| 微信视频号 | 1080x1260 | 30fps | 60s | MP4 H.264 |

---

## YouTube / Bilibili 版本 (60s, 1920x1080)

### 配置
- 分辨率：1920x1080
- 帧率：60fps
- 比特率：H.264 20Mbps / H.265 12Mbps
- 音频：AAC 320kbps
- 色彩：Rec.709 + LUT

### 缩略图设计
- 尺寸：1280x720
- IEA Logo 居中
- 背景色 #0A0A0F
- 文字：AGENT TERMINAL / 完全智能 · 解放双手
- 使用 `assets/iea_logo.svg` 导出 PNG

### 视频描述模板
```
IEA (IstinaEndfieldAssistant) — 《明日方舟：终末地》智能自动化助手

完全智能 · 解放双手
- VLM 视觉理解，自主决策
- 本地/云端双模式推理
- Fernet 加密通信
- PyQt6 专业 GUI

GitHub: [项目链接]
教程: [教程链接]
```

---

## Twitter/X 版本 (60s, 1280x720)

### 配置
- 分辨率：1280x720
- 帧率：30fps
- 比特率：H.264 8Mbps
- 音频：AAC 192kbps
- 文件大小限制：< 512MB

### 修改
1. 字幕字号放大至 28px
2. 文字间距增加 2px
3. 去除过于精细的装饰线

---

## TikTok / Reels 版本 (15-30s, 1080x1920)

### 配置
- 分辨率：1080x1920（竖屏）
- 帧率：60fps
- 比特率：H.264 12Mbps
- 音频：AAC 256kbps

### 重新剪辑要求

**超精简版 (15s)**：
| 时间 | 内容 | 字幕 |
|------|------|------|
| 0-3s | 痛点快剪（手动点击×3） | 手动操作太累了？ |
| 3-6s | IEA 界面展示 | IEA 智能自动化 |
| 6-10s | Agent 执行任务 | 一句话，自动完成 |
| 10-13s | 本地/云端切换 | 免费本地推理 |
| 13-15s | Logo + Slogan | 解放双手 |

**标准版 (30s)**：
| 时间 | 内容 |
|------|------|
| 0-4s | 痛点引入 |
| 4-8s | 解决方案展示 |
| 8-18s | 核心功能（快速切换 4 个分镜） |
| 18-25s | 技术优势（双模式 / 加密） |
| 25-30s | Use case + Logo |

### 竖屏适配规则
1. **画面裁剪**：从 1920x1080 中心裁剪 1080x1920（保留 60% 宽）
2. **文字位置**：上 20% 和 下 20% 区域避免放置关键视觉元素
3. **字幕位置**：安全区域（y: 1400-1800px）
4. **高亮元素**：放大 150%，确保在小屏可见

---

## 微信视频号版本 (60s, 1080x1260)

### 配置
- 分辨率：1080x1260（1:1.17 竖屏）
- 帧率：30fps
- 比特率：H.264 8Mbps
- 文件大小限制：< 200MB

### 适配规则
1. 从 1920x1080 → 1080x1260：上下各加 90px 黑边
2. 关键信息居中布局
3. 字幕放大至 32px

---

## 渲染批处理脚本

```bash
# ==================== 渲染命令 ====================

# YouTube / Bilibili (1920x1080, 60fps, H.264)
ffmpeg -i timeline_final.mov \\
  -c:v libx264 -preset slow -crf 18 \\
  -vf "fps=60,scale=1920:1080" \\
  -c:a aac -b:a 320k \\
  -pix_fmt yuv420p \\
  output/iea_promo_youtube.mp4

# YouTube / Bilibili (H.265 版)
ffmpeg -i timeline_final.mov \\
  -c:v libx265 -preset slow -crf 22 \\
  -vf "fps=60,scale=1920:1080" \\
  -c:a aac -b:a 320k \\
  -pix_fmt yuv420p10le \\
  output/iea_promo_bilibili.mp4

# Twitter (1280x720, 30fps)
ffmpeg -i timeline_final.mov \\
  -c:v libx264 -preset medium -crf 22 \\
  -vf "fps=30,scale=1280:720" \\
  -c:a aac -b:a 192k \\
  -pix_fmt yuv420p \\
  output/iea_promo_twitter.mp4

# TikTok (1080x1920, 60fps, 30s 裁剪)
ffmpeg -i timeline_final.mov \\
  -c:v libx264 -preset medium -crf 22 \\
  -vf "fps=60,crop=1080:1920:420:0,scale=1080:1920" \\
  -c:a aac -b:a 256k \\
  -pix_fmt yuv420p \\
  -t 30 \\
  output/iea_promo_tiktok.mp4

# 微信视频号 (1080x1260, 30fps)
ffmpeg -i timeline_final.mov \\
  -c:v libx264 -preset medium -crf 22 \\
  -vf "fps=30,scale=1080:1260:force_original_aspect_ratio=decrease,pad=1080:1260:(ow-iw)/2:(oh-ih)/2:color=#0A0A0F" \\
  -c:a aac -b:a 192k \\
  -pix_fmt yuv420p \\
  output/iea_promo_wechat.mp4
```

---

## 发布计划

| 日期 | 平台 | 版本 | 备注 |
|------|------|------|------|
| Day 1 | YouTube | 完整版 60s | 主发布 |
| Day 1 | Bilibili | 完整版 60s | 同步发布 |
| Day 2 | Twitter | 完整版 60s | 简中+英文双版本 |
| Day 3 | TikTok | 精简版 30s | 剪辑版本 |
| Day 3 | Instagram | 精简版 30s | Reels |
| Day 4 | 微信视频号 | 完整版 60s | 公众号关联 |