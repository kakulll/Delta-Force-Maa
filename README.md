# Delta-Force-Maa (三角洲行动 Maa)

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 的《三角洲行动》(Delta Force: Hawk Ops) **PC客户端** 自动化辅助工具。

## 🎯 核心功能

- **🚀 启动与弹窗处理 (`Startup`)**：
  - 自动检测游戏主窗口并进入游戏大厅。
  - 自动跳过每日公告、版本更新通知与各类活动弹窗。
- **🎁 每日日常福利 (`Daily`)**：
  - 邮件奖励一键领取与清理。
  - 战备手账/赛季通行证奖励一键获取。
- **🏭 特勤处基建运维 (`Shelter`)**：
  - 各工作台制造产物一键收获。
  - 发电机自动检测与燃料补充。
- **🛒 交易行自动捡漏与采购 (`Trading`)**：
  - 基于 MaaFramework 原生 ONNX OCR 动态定位与 Python 自定义价格评估器，实时监控并自动采购。
  - 支持 GUI 动态配置品类模式（收藏夹监控/消耗品/弹药）、最高购买限价（1w~20w/不限）、安全监控模式（DryRun，只报警不下单）及数量拉满。
- **🛠️ 扩展与 Maa 社区规范**：
  - 内置 Python Agent 自定义运行时，无缝扩展复杂物品识别。
  - 深度遵循 MaaHub 与 MaaFramework 协议规范，开箱即用。

---

## 💻 运行环境要求

1. **操作系统**：Windows 10 / 11 64位
2. **游戏客户端**：《三角洲行动》官方 PC 客户端
3. **分辨率支持**：原生适配 2560×1600 (16:10 黄金比例) 与 1920×1080 (16:9)，原生高 DPI 自适应缩放与 ONNX OCR 几何中心点击。
4. **运行工具**：
   - 方式 A（GUI 推荐）：使用 [MFA (MaaFramework Assistant)](https://github.com/MaaXYZ/MFA) 或 MaaX，直接载入本项目根目录。
   - 方式 B（命令行/Python）：运行 `python agent/bootstrap.py`。

---

## 📁 目录结构

```
Delta-Force-Maa/
├── .agents/skills/          # MaaHub AI Agent 技能辅助库
├── agent/                   # Python Agent 自定义扩展 (Action / Reco / Server)
├── resource/base/
│   ├── model/ocr/           # OCR 文字识别轻量化模型 (ONNX)
│   └── pipeline/            # MaaFramework 流水线配置
│       ├── common.json      # 公共弹窗与返回节点
│       ├── startup.json     # 启动与进入大厅
│       ├── daily.json       # 每日邮件与通行证
│       ├── shelter.json     # 特勤处基建收料
│       └── trading.json     # 交易行自动捡漏与采购
├── tasks/                   # GUI 任务入口配置 (Startup, Daily, Shelter, Trading)
├── interface.json           # MaaFramework GUI 接口定义 (仅启用 Win32 PC 端)
├── maa-project.json         # 项目元数据与构建配置
└── AGENTS.md                # 自动化开发与 Git 提交规范
```

---

## 🧪 验证与校验

项目遵循 MaaFramework v5+ 规范，运行以下命令验证 Schema：

```bash
node tools/validate-schema.mjs
```

---

## 📄 开源许可

本项目遵循 [MIT 许可证](LICENSE)。