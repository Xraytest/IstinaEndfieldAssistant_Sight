# IEA 宣传视频音效素材清单

## 音效来源

### Freesound.org (免费音效库)
- 注册账号：https://freesound.org/
- 搜索关键词：tech, sci-fi, digital, data, interface

### YouTube Audio Library (免版税)
- 访问：YouTube Studio → Audio Library
- 分类：Electronic, Cinematic

### 自制音效 (Audacity)
- 使用合成器生成科技感音效
- 录制真实操作声（点击/滑动）

---

## 音效清单

### 1. 环境音效

| 文件名 | 描述 | 时长 | 来源 |
|--------|------|------|------|
| `ambient_tech_loop.wav` | 科技感背景音 | 60s 循环 | Freesound |
| `ambient_data_center.wav` | 数据中心环境音 | 60s 循环 | Freesound |

**用途**: 全程背景音乐，音量 -20dB

---

### 2. 界面音效

| 文件名 | 描述 | 时长 | 参数 |
|--------|------|------|------|
| `sfx_startup_tech.wav` | 系统启动音效 | 1.5s | 频率上升 200Hz→800Hz |
| `sfx_data_flow.wav` | 数据流动音效 | 2s | 白噪声 + 滤波 |
| `sfx_scan_ui.wav` | UI 扫描音效 | 1s | 高频脉冲 |
| `sfx_button_click.wav` | 按钮点击音效 | 0.1s | 短促电子音 |
| `sfx_button_hover.wav` | 按钮悬停音效 | 0.1s | 轻微提示音 |
| `sfx_notification.wav` | 通知音效 | 0.3s | 双音和弦 |

**用途**: 场景 2-4 的界面交互

---

### 3. 操作音效

| 文件名 | 描述 | 时长 | 录制方式 |
|--------|------|------|----------|
| `sfx_tap_01.wav` | 点击音效 1 | 0.05s | 真实鼠标录制 |
| `sfx_tap_02.wav` | 点击音效 2 | 0.05s | 真实鼠标录制 |
| `sfx_swipe_up.wav` | 上滑音效 | 0.3s | 滑动合成 |
| `sfx_swipe_down.wav` | 下滑音效 | 0.3s | 滑动合成 |
| `sfx_swipe_left.wav` | 左滑音效 | 0.3s | 滑动合成 |
| `sfx_swipe_right.wav` | 右滑音效 | 0.3s | 滑动合成 |

**用途**: 场景 3 的自动操作演示

---

### 4. 状态音效

| 文件名 | 描述 | 时长 | 参数 |
|--------|------|------|------|
| `sfx_success.wav` | 成功提示音 | 0.5s | 大三和弦 |
| `sfx_error.wav` | 错误提示音 | 0.5s | 不和谐音程 |
| `sfx_loading.wav` | 加载音效 | 1s | 循环脉冲 |
| `sfx_complete.wav` | 完成音效 | 1s | 上升音阶 |
| `sfx_confirm.wav` | 确认音效 | 0.3s | 单音 |

**用途**: 场景 3-4 的状态反馈

---

### 5. 技术音效

| 文件名 | 描述 | 时长 | 参数 |
|--------|------|------|------|
| `sfx_encryption.wav` | 加密音效 | 1s | 频率调制 |
| `sfx_decryption.wav` | 解密音效 | 1s | 反向调制 |
| `sfx_data_transmit.wav` | 数据传输音效 | 2s | 白噪声 + 滤波 |
| `sfx_data_receive.wav` | 数据接收音效 | 2s | 白噪声 + 滤波 |
| `sfx_model_load.wav` | 模型加载音效 | 2s | 渐进音阶 |
| `sfx_gpu_accelerate.wav` | GPU 加速音效 | 1s | 高频上升 |

**用途**: 场景 4 的技术优势展示

---

### 6. 品牌音效

| 文件名 | 描述 | 时长 | 设计 |
|--------|------|------|------|
| `sfx_brand_intro.wav` | 品牌开场音效 | 2s | 三音和弦 + 混响 |
| `sfx_brand_outro.wav` | 品牌收尾音效 | 3s | 渐弱和弦 |
| `sfx_logo_reveal.wav` | Logo 揭示音效 | 1.5s | 上升音阶 |

**用途**: 场景 6 的品牌展示

---

### 7. 转场音效

| 文件名 | 描述 | 时长 | 参数 |
|--------|------|------|------|
| `sfx_transition_whoosh.wav` | 快速转场 | 0.3s | 风声 + 低通 |
| `sfx_transition_glitch.wav` | 故障转场 | 0.2s | 数字失真 |
| `sfx_transition_fade.wav` | 淡入淡出 | 1s | 渐变白噪声 |

**用途**: 场景切换

---

## Audacity 音效制作指南

### 制作按钮点击音效

1. 打开 Audacity
2. 生成 → 音调 → 频率：800Hz, 时长：0.05s, 波形：正弦波
3. 效果 → 包络 → 衰减：0.03s
4. 效果 → 混响 → 预设：Small Room
5. 导出为 WAV

### 制作数据流动音效

1. 生成 → 噪声 → 白噪声，时长：2s
2. 效果 → 滤波器 → 低通滤波器：截止频率 2000Hz
3. 效果 → 调制 → 颤音：深度 50%, 频率 5Hz
4. 包络工具：淡入 0.2s, 淡出 0.5s
5. 导出为 WAV

### 制作科技感启动音效

1. 生成 → 音调 → 频率：200Hz→800Hz 滑音，时长：1.5s
2. 效果 → 延迟 → 延迟时间：0.1s, 反馈：30%
3. 效果 → 混响 → 预设：Large Hall
4. 导出为 WAV

---

## 音频混音参数

### 音量平衡 (DaVinci Resolve)

| 音轨 | 音量 | 说明 |
|------|------|------|
| 背景音乐 | -20dB | 环境音效 |
| 音效 | -6dB | 界面/操作音效 |
| 旁白 (如有) | 0dB | 主音量 |
| 品牌音效 | -3dB | 开场/收尾 |

### 音频处理链

```
原始音频 → 降噪 → 均衡器 → 压缩器 → 限幅器 → 输出
```

**均衡器设置**:
- 低频 (60Hz): -3dB (减少低频轰鸣)
- 中频 (1kHz): 0dB
- 高频 (8kHz): +2dB (增加清晰度)

**压缩器设置**:
- 阈值：-18dB
- 比率：3:1
- 攻击：10ms
- 释放：100ms

**限幅器设置**:
- 阈值：-1dB
- 释放：50ms

---

## 背景音乐推荐

### 选项 1: 科技感电子乐
- 艺术家：Scott Buckley
- 曲目：Technology, Digital World
- 来源：https://www.scottbuckley.com.au/

### 选项 2: 极简氛围音乐
- 艺术家：Kevin MacLeod
- 曲目：Digital, Technology
- 来源：https://incompetech.com/

### 选项 3: 自制环境音
- 使用 Audacity 合成
- 白噪声 + 低通滤波 + 混响

---

## 音效文件组织

```
assets/audio/
├── ambient/
│   ├── ambient_tech_loop.wav
│   └── ambient_data_center.wav
├── interface/
│   ├── sfx_startup_tech.wav
│   ├── sfx_data_flow.wav
│   ├── sfx_scan_ui.wav
│   ├── sfx_button_click.wav
│   ├── sfx_button_hover.wav
│   └── sfx_notification.wav
├── interaction/
│   ├── sfx_tap_01.wav
│   ├── sfx_tap_02.wav
│   ├── sfx_swipe_up.wav
│   ├── sfx_swipe_down.wav
│   ├── sfx_swipe_left.wav
│   └── sfx_swipe_right.wav
├── status/
│   ├── sfx_success.wav
│   ├── sfx_error.wav
│   ├── sfx_loading.wav
│   ├── sfx_complete.wav
│   └── sfx_confirm.wav
├── tech/
│   ├── sfx_encryption.wav
│   ├── sfx_decryption.wav
│   ├── sfx_data_transmit.wav
│   ├── sfx_data_receive.wav
│   ├── sfx_model_load.wav
│   └── sfx_gpu_accelerate.wav
├── brand/
│   ├── sfx_brand_intro.wav
│   ├── sfx_brand_outro.wav
│   └── sfx_logo_reveal.wav
├── transition/
│   ├── sfx_transition_whoosh.wav
│   ├── sfx_transition_glitch.wav
│   └── sfx_transition_fade.wav
└── bgm/
    └── bgm_tech_ambient.mp3
```

---

## 音效使用时间表

| 时间 | 音效 | 音量 |
|------|------|------|
| 0:00-0:08 | ambient_tech_loop, sfx_button_click (×10) | -20dB, -6dB |
| 0:08-0:15 | sfx_startup_tech, sfx_data_flow | -6dB |
| 0:15-0:20 | sfx_scan_ui, sfx_data_transmit | -6dB |
| 0:20-0:25 | sfx_button_click, sfx_notification | -6dB |
| 0:25-0:30 | sfx_tap_01, sfx_swipe_up | -6dB |
| 0:30-0:35 | sfx_success, sfx_complete | -6dB |
| 0:35-0:38 | sfx_transition_whoosh | -6dB |
| 0:38-0:42 | sfx_model_load, sfx_gpu_accelerate | -6dB |
| 0:42-0:48 | sfx_encryption, sfx_data_transmit | -6dB |
| 0:48-0:55 | sfx_transition_fade | -6dB |
| 0:55-1:00 | sfx_brand_intro, sfx_logo_reveal, sfx_brand_outro | -3dB |
