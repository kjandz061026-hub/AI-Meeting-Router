# 🧠 AI Meeting Router

> 本地多智能体讨论平台 — 让多个 AI 像专家委员会一样协作讨论，得出更可靠的答案。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-3.0-orange.svg)](CHANGELOG.md)

---

## ✨ 这是什么？

AI Meeting Router 是一个运行在本地的 Web 应用。你可以配置多个 AI 模型（GPT-4、DeepSeek、Qwen 等任何兼容 OpenAI API 的模型），让它们围绕一个问题进行多轮辩论与协作，最终给出带有置信度评分的高质量答案。

**核心理念**：一个 AI 可能犯错或过于自信，但多个 AI 互相质疑、补充、校准后，结果会更可靠。

### 🎯 典型场景

- 💡 **复杂推理** — 数学题、逻辑题，多个 AI 从不同角度推敲
- 📋 **方案评估** — 让不同"专家"论证各自方案的优劣
- 🔍 **代码审查** — 多个 AI 逐行审查代码逻辑
- 🧪 **知识验证** — 交叉验证 AI 给出的事实是否准确

---

## 📸 界面预览

```
┌─────────────────────────────────────────────────────────┐
│  LOCAL MULTI-AGENT                                      │
│  AI Meeting Router        [讨论] [配置] [历史]           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─ 参与者 ──────────────────────────────────────────┐  │
│  │  GPT-4 分析师 · DeepSeek 工程师 · Qwen 数学家     │  │
│  └────────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─ 讨论区 ──────────────────────────────────────────┐  │
│  │  [第1轮] GPT-4 分析师 · 置信度 72                  │  │
│  │  我认为这个问题的关键在于...                        │  │
│  │                                                     │  │
│  │  [第1轮] DeepSeek 工程师 · 置信度 85 (校准+10=95)  │  │
│  │  上一个观点有遗漏，需要补充...                       │  │
│  │                                                     │  │
│  │  [第2轮] Qwen 数学家 · 置信度 98 ✨                 │  │
│  │  经过验证，最终答案是...                             │  │
│  └────────────────────────────────────────────────────┘  │
│                                                         │
│  ✅ 最终答案: 讨论已达成共识                             │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 环境要求

- Python **3.10+**
- 至少一个可用的 OpenAI 兼容 API Key（支持 OpenAI / DeepSeek / Qwen / Ollama 等）

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/AI-Meeting-Router.git
cd AI-Meeting-Router
# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动
python run.py
```

浏览器访问 **http://127.0.0.1:8000** 即可使用。

### 三步上手

1. **配置 AI** — 在「配置」页添加你的 AI 模型（名称、API Key、模型名）
2. **输入问题** — 在「讨论」页输入你想讨论的题目
3. **查看结果** — 观察 AI 多轮辩论，获得带有置信度评分的最终答案

---

## 🔥 核心特性

### 🗣️ 多智能体多轮讨论
- 支持任意数量的 AI 参与，按自定义顺序依次发言
- 每轮每位 AI 都能看到历史讨论，进行回应、质疑或补充
- 实时 SSE（Server-Sent Events）流式输出，打字机效果

### 🎯 置信度机制
- 每个 AI 发言末尾必须输出 `[CONFIDENCE:0-100]` 评分
- 当置信度 ≥ 用户设定阈值时，自动结束讨论并输出最终答案
- **v2.0**：置信度校准功能，可修正 AI 的过度自信或保守倾向
- **v3.0**：结构化校准提示词，要求 AI 执行 4 步自检后才输出置信度；自动惩罚空话和高频重复

### 🏆 动态信誉引擎（v3.0 新增）
- 每个 AI 初始信誉分 50，根据讨论中的客观行为自动更新
- 纯规则计算，无需额外 AI 调用
- 信誉分数影响最终答案排序权重

### 📦 上下文压缩
- 自动检测 token 用量，超限时用 AI 对早期轮次进行摘要压缩
- 可指定任意 AI 作为「压缩器」专门负责摘要
- 支持 tiktoken 精确计数 + 纯文本估算双模式

### 🎨 拖拽排序
- 在配置页拖拽 AI 卡片即可调整发言顺序，自动保存

### 💾 历史回溯
- 每次讨论自动保存为 JSON 记录
- 支持按时间倒序浏览历史，查看完整讨论过程

### ⚙️ 兼容性
- 兼容所有 OpenAI API 格式的服务商
- 支持 Azure OpenAI / 本地 Ollama / 自定义端点
- 可在 `app/llm.py` 中自定义请求参数

---

## 📁 项目结构

```
ai-meeting-router/
├── app.py                  # 入口（简洁版）
├── run.py                  # 入口（带启动横幅）
├── requirements.txt        # Python 依赖
├── CHANGELOG.md            # 开发日志
├── QUICKSTART.md           # 快速入门指南
├── 使用说明书.md            # 完整使用手册
│
├── app/
│   ├── main.py             # FastAPI 路由定义
│   ├── models.py           # Pydantic 数据模型
│   ├── llm.py              # LLM 客户端（HTTP 流式调用）
│   ├── storage.py          # JSON 文件持久化
│   └── services/
│       ├── discussion.py   # 讨论服务核心逻辑
│       └── reputation.py   # 动态信誉引擎（v3.0 新增）
│
├── app/templates/          # Jinja2 前端模板
│   ├── base.html
│   ├── discuss.html
│   ├── config.html
│   └── history.html
│
├── app/static/             # 静态资源
│   ├── css/app.css
│   └── js/
│       ├── config.js
│       ├── discuss.js
│       └── history.js
│
└── data/                   # 运行时数据（自动生成）
    ├── ais_config.json     # AI 配置
    └── discussions/        # 讨论历史
```

---

## 📊 技术栈

| 层次 | 技术 |
|------|------|
| 后端框架 | FastAPI |
| 前端模板 | Jinja2（原生 HTML/CSS/JS，无框架依赖） |
| 实时通信 | SSE（Server-Sent Events） |
| HTTP 客户端 | httpx（异步流式调用） |
| Token 计数 | tiktoken（可选，回退至估算） |
| 数据存储 | 本地 JSON 文件 |

---

## 🔄 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| **v3.0** | 2026-05 | 动态信誉引擎、增强置信度校准提示词、自动惩罚机制 |
| **v2.0** | 2026-05 | 置信度校准、校准后评分排序、前端校准展示 |
| **v1.0** | 2026-05 | 初始发布：多智能体讨论、置信度机制、上下文压缩 |

详见 [CHANGELOG.md](CHANGELOG.md)

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。

---

## 📄 许可

MIT License
