# IEA 宣传视频录制脚本

## 录制前准备

### 环境配置
```bash
# 启动服务器
cd C:\Users\xray\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant
start_server.bat

# 启动 IEA GUI
python src/gui/pyqt6/main.py
```

### OBS 配置
- 分辨率：1920x1080
- 帧率：60fps
- 编码器：NVIDIA NVENC H.264 (或 x264)
- 比特率：20Mbps CBR
- 关键帧间隔：2s
- 音频：48kHz, AAC, 320kbps

---

## 录制清单

### 片段 1: Agent Terminal 操作 (60 秒)

**目标**: 展示自然语言指令到自动执行的完整流程

**步骤**:
1. 切换到 Agent Terminal 页面
2. 输入指令：`Go to the crafting menu`
3. 等待 AI 回复和动作执行
4. 观察 Chat 界面显示的执行结果
5. 再输入一条指令：`Check daily missions`
6. 记录完整交互过程

**录制时长**: 60 秒  
**保存路径**: `assets/raw_recordings/agent_terminal_01.mp4`

---

### 片段 2: IEA Control Panel (30 秒)

**目标**: 展示系统状态和数据统计

**步骤**:
1. 切换到 IEA Control Panel 页面
2. 点击 REFRESH 按钮
3. 等待数据加载完成
4. 展示 SERVER CONNECTION 状态（AUTHENTICATED）
5. 展示 AGENT ORCHESTRATOR 状态
6. 展示 STATE TEMPLATES 和 REFERENCE IMAGES
7. 展示 MODEL PROVIDERS 列表

**录制时长**: 30 秒  
**保存路径**: `assets/raw_recordings/control_panel_01.mp4`

---

### 片段 3: 游戏实际操作 (120 秒)

**目标**: 展示 Agent 自主探索游戏界面

**步骤**:
1. 在 IEA Control Panel 点击 PAGE EXPLORATION 的 START 按钮
2. 设置 Depth: 20, Verify: 3
3. 观察探索过程
4. 记录 Pages/Elements/Edges 统计数据增长
5. 查看 Exploration Log 输出
6. 等待 2-3 个页面探索完成
7. 点击 STOP 按钮

**录制时长**: 120 秒  
**保存路径**: `assets/raw_recordings/game_exploration_01.mp4`

---

### 片段 4: Model Manager (20 秒)

**目标**: 展示模型加载和管理

**步骤**:
1. 切换到 Model Manager 页面
2. 展示可用模型列表
3. 点击刷新模型列表
4. 展示模型选择过程
5. 展示本地/云端模式切换

**录制时长**: 20 秒  
**保存路径**: `assets/raw_recordings/model_manager_01.mp4`

---

### 片段 5: 登录认证流程 (30 秒)

**目标**: 展示安全认证机制

**步骤**:
1. 展示 Auth 页面
2. 输入 User ID 和 API Key
3. 点击 LOGIN 按钮
4. 等待认证成功
5. 展示 Session ID 和用户信息

**录制时长**: 30 秒  
**保存路径**: `assets/raw_recordings/auth_flow_01.mp4`

---

## 截图清单

### 游戏界面截图 (10 张)

使用 ShareX 或 OBS 截图功能，保存为 PNG 格式

1. `assets/screenshots/game_main_menu.png` - 游戏主菜单
2. `assets/screenshots/game_crafting.png` - 制造界面
3. `assets/screenshots/game_missions.png` - 任务界面
4. `assets/screenshots/game_inventory.png` - 背包界面
5. `assets/screenshots/game_settings.png` - 设置界面
6. `assets/screenshots/game_battle_prep.png` - 战斗准备
7. `assets/screenshots/game_daily_checkin.png` - 每日签到
8. `assets/screenshots/game_rewards.png` - 奖励领取
9. `assets/screenshots/game_world_map.png` - 世界地图
10. `assets/screenshots/game_dialog.png` - 对话框界面

**截图配置**:
- 分辨率：1920x1080
- 格式：PNG（无损）
- 命名：小写英文，下划线分隔

---

### IEA GUI 截图 (8 张)

1. `assets/screenshots/iea_agent_terminal.png` - Agent Terminal
2. `assets/screenshots/iea_control_panel.png` - Control Panel
3. `assets/screenshots/iea_model_manager.png` - Model Manager
4. `assets/screenshots/iea_auth_page.png` - 认证页面
5. `assets/screenshots/iea_cloud_page.png` - Cloud 页面
6. `assets/screenshots/iea_settings.png` - 设置页面
7. `assets/screenshots/iea_exploration_log.png` - 探索日志
8. `assets/screenshots/iea_data_panel.png` - 数据面板

---

### 数据面板/日志截图 (5 张)

1. `assets/screenshots/logs_exploration_stats.png` - 探索统计
2. `assets/screenshots/logs_agent_actions.png` - Agent 动作日志
3. `assets/screenshots/logs_communication.png` - 通信日志
4. `assets/screenshots/logs_performance.png` - 性能统计
5. `assets/screenshots/logs_errors.png` - 错误日志（可选）

---

## 录制后处理

### 视频剪辑（DaVinci Resolve）

1. 导入所有录制片段
2. 按分镜脚本拼接
3. 裁剪多余部分
4. 添加转场效果
5. 调色（Hypergryph 风格）

### 音频处理（Audacity）

1. 导入音效素材
2. 调整音量平衡
3. 添加背景音乐（可选）
4. 导出为 WAV 格式

### 合成输出

1. 视频 + 音频同步
2. 添加字幕
3. 渲染输出 MP4
4. 质量检查

---

## 质量检查清单

- [ ] 视频分辨率 1920x1080
- [ ] 帧率稳定 60fps
- [ ] 无明显卡顿/跳帧
- [ ] 音频无爆音/杂音
- [ ] 字幕准确无误
- [ ] 色彩符合品牌规范
- [ ] 文件大小合理（<500MB）

---

## 文件组织结构

```
IstinaEndfieldAssistant/
├── assets/
│   ├── raw_recordings/
│   │   ├── agent_terminal_01.mp4
│   │   ├── control_panel_01.mp4
│   │   ├── game_exploration_01.mp4
│   │   ├── model_manager_01.mp4
│   │   └── auth_flow_01.mp4
│   ├── screenshots/
│   │   ├── game_*.png (10 张)
│   │   ├── iea_*.png (8 张)
│   │   └── logs_*.png (5 张)
│   └── audio/
│       ├── sfx_*.wav
│       └── bgm_*.mp3
├── docs/
│   └── video_design/
│       ├── 01_concept.md
│       ├── 02_storyboard.md
│       ├── 03_production.md
│       ├── 04_recording_script.md
│       └── manim_scenes.py
└── output/
    ├── iea_promo_video_v1.mp4
    ├── iea_promo_video_720p.mp4
    └── iea_promo_video_vertical.mp4
```
