# 鹰角网络设计语言参考资料

> 本文件持续收集鹰角网络（Hypergryph）相关产品的设计思路，作为本项目 GUI/平面美术优化的参考来源。

## 1. 来源记录

### 1.1 游戏知识库提取（`game_knowledge_base.json`）
- **产品**：明日方舟：终末地
- **包名**：`com.hypergryph.endfield`
- **参考域名**：`ak.hypergryph.com`、`endfield.hypergryph.com`
- **核心视觉元素**：
  - 基地主界面为“多面板叠加”结构
  - 游戏场景以“蓝色主导”（93.9%）
  - 存在大量工业科幻风格按钮与面板（基础工业一期/二期/三期、原料开采、物流运输等）
  - UI 元素命名带有终端/工业感：`TerminalNotice`、`EnvironmentMonitoringButton`、`WorldMenuBaker` 等
- **当前已知交互模式**：
  - 顶部行：通知、信用点、任务领取
  - 左侧列：环境监测、好友列表、拍照
  - 右侧列：世界菜单、委托领取、背包
  - 底部行：进入按钮、任务领取、任务标签

### 1.2 鹰角产品设计共性（持续补充）
- **明日方舟（Arknights）**
  - 深色底 + 高对比信息色（黑/白/蓝/黄/红）
  - 等宽/终端风格字体用于系统信息，标题使用粗体无衬线
  - 卡片式布局，大量使用 1px 细线分割与微弱发光边框
  - 按钮状态极简：默认/悬停/按下/禁用，几乎无渐变，以透明度区分
  - 图标与文字严格对齐，间距遵循 4px/8px 网格

- **明日方舟：终末地（Endfield）**
  - 继承 Arknights 的深色工业科幻语言
  - 3D 场景 UI 叠加在游戏画面上，保持低侵入性
  - 面板采用半透明深色底 + 青色描边
  - 文字信息层级清晰：主标题 > 次级 > 辅助 > 禁用

## 2. 设计 token 清单

| Token | 用途 | 鹰角参考 |
|-------|------|----------|
| `primary` | 主按钮、选中态、高亮 | #18d1ff（终端青） |
| `success` | 成功状态、在线 | #00ffa2 |
| `danger` | 错误、停止、删除 | #ff3355 |
| `accent_gold` | 重要提示、稀有 | #fffa00 |
| `bg_primary` | 主背景 | #0a0a0f |
| `surface` | 卡片/面板底 | rgba(16,16,26,0.88) |
| `border` | 分割线/描边 | rgba(24,209,255,0.15) |
| `font_display` | 标题 | Microsoft YaHei UI Bold |
| `font_body` | 正文 | Microsoft YaHei UI Regular |

## 3. 待补充来源
- [ ] 官网截图存档（`assets/references/hypergryph/`）
- [ ] Arknights/Endfield 官方界面色值提取
- [ ] 鹰角动效规范（淡入淡出时长、缓动曲线）
- [ ] 跨端适配规则（PC/平板/手机）
