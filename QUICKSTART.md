# 🚀 快速开始

## 环境要求
- Python 3.10+
- 可访问的 OpenAI 兼容 API（如 OpenAI、Azure、本地 Ollama 等）

## 安装步骤

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动应用
```bash
python run.py
# 或者
python app.py
```

### 3. 打开浏览器
访问 http://127.0.0.1:8000

---

## 首次使用

### 步骤 1: 配置 AI（/config）

点击"配置"选项卡，填写 AI 信息：

- **名称**: AI 的显示名称（如"GPT-4分析师"）
- **API 地址**: OpenAI 兼容 API 的基础 URL
  - OpenAI: `https://api.openai.com/v1`
  - Azure: `https://{your-resource}.openai.azure.com/v1`
  - 本地: `http://localhost:8000/v1` (如 Ollama)
- **API Key**: 对应服务的密钥
- **模型**: 模型名称（如 `gpt-4o`, `gpt-4-turbo` 等）
- **系统角色** (可选): 定制 AI 的行为
- **上下文窗口**: 模型支持的最大 token 数（默认 8192）
- **作为压缩器模型**: 勾选此项让该 AI 专门用于摘要

> **💡 提示**: 首次添加 AI 时，系统会自动生成自我介绍。如果生成失败，可手动补充。

### 步骤 2: 启动讨论（/discuss）

1. 输入想要讨论的问题
2. 调整参数：
   - **置信度阈值** (0-100): 当某个 AI 的置信度≥阈值时，讨论停止
   - **最大轮数**: 每个 AI 最多回复的轮数
3. 点击"开始讨论"

### 步骤 3: 观看实时讨论

- 左侧显示参与者简介
- 中间显示实时讨论流（每个 AI 一个气泡）
- 右下显示最终答案

---

## 配置示例

### 示例 1: 使用 OpenAI

```
名称: GPT-4 分析师
API 地址: https://api.openai.com/v1
API Key: sk-proj-xxxxxxxxxx
模型: gpt-4o
系统角色: 你是一位资深的商业分析师，专长于战略规划和市场分析。
上下文窗口: 8192
```

### 示例 2: 使用本地 Ollama

```
名称: Mistral 本地分析
API 地址: http://localhost:11434/v1
API Key: ollama  (任意值，Ollama 不验证)
模型: mistral
上下文窗口: 4096
```

### 示例 3: 压缩器模型

```
名称: 摘要专家
API 地址: https://api.openai.com/v1
API Key: sk-proj-xxxxxxxxxx
模型: gpt-4o-mini
系统角色: 你是文本摘要专家，善于提炼核心内容。
✓ 作为压缩器模型
```

---

## 常见问题

### Q: 如何添加多个 AI？
A: 在配置页面重复添加即可，最多支持任意数量。讨论时会按配置顺序轮流发言。

### Q: 如何改变 AI 的发言顺序？
A: 在配置页面，拖拽 AI 卡片调整顺序，会自动保存。

### Q: 什么是"置信度阈值"？
A: 当 AI 给出的回复置信度达到或超过此值时，系统认为已有充分答案，停止讨论。

### Q: 讨论记录保存在哪？
A: 自动保存到 `data/discussions/` 目录，以时间戳命名的 JSON 文件。

### Q: 如何清空所有配置？
A: 删除 `data/ais_config.json` 文件，重启应用。

### Q: 如何处理超出上下文窗口的讨论？
A: 系统自动压缩较早的轮次讨论（称为"二次摘要"），同时保留原始问题和参与者简介。

### Q: 压缩器模型有什么用？
A: 如果配置了压缩器模型，系统会使用它来生成摘要，而不是简单的文字截断。这样摘要质量更高。

---

## 高级特性

### 1. 二次摘要
当讨论历史过长时：
- 第一次压缩：第 1 轮讨论 → 摘要 1
- 第二次压缩：摘要 1 + 第 2 轮讨论 → 摘要 2
- 以此类推...

这允许讨论无限延续而不会因为 token 限制而中断。

### 2. 系统提示
如果某个 AI 试图给出最终答案但置信度不足，系统会在下一个 AI 的提示中告知，促使其深入讨论。

### 3. Token 计数
系统智能检测：
- 如果安装了 `tiktoken`，精确计数
- 否则用字符估算（ASCII 1/4 token，中文 1 token）

---

## API 文档

FastAPI 自动生成的 API 文档可访问：http://127.0.0.1:8000/docs

主要端点：
- `GET /` - 讨论页面
- `GET /config` - 配置页面
- `GET /api/ais` - 列表所有 AI
- `POST /api/ais` - 创建新 AI
- `PUT /api/ais/{id}` - 更新 AI
- `DELETE /api/ais/{id}` - 删除 AI
- `POST /api/discussions` - 启动讨论（SSE）
- `POST /api/discussions/stop` - 停止讨论

---

## 故障排查

### 问题: 启动失败 - ModuleNotFoundError
**解决**: 确保已运行 `pip install -r requirements.txt`

### 问题: API 连接失败
**检查**:
- API 地址格式是否正确
- API Key 是否有效
- 网络连接是否正常
- 防火墙是否允许访问

### 问题: Token 数超过限制
**解决**: 
- 增加模型的上下文窗口配置
- 配置压缩器 AI 以提高摘要质量
- 减少最大轮数

### 问题: 讨论卡住
**解决**: 点击"停止"按钮，或刷新页面重试

---

## 进阶配置

### 修改监听地址
编辑 `run.py`：
```python
uvicorn.run(app, host="0.0.0.0", port=8000)  # 允许外部访问
```

### 修改数据目录
编辑 `app/storage.py`：
```python
DATA_DIR = Path("/custom/path/to/data")
```

### 自定义系统提示
编辑 `app/services/discussion.py` 中的相关字符串。

---

## 性能建议

1. **生产环境**:
   - 使用 Gunicorn: `gunicorn -w 4 app:app`
   - 使用反向代理（Nginx）
   - 考虑使用数据库替代 JSON

2. **优化讨论**:
   - 使用较小的模型进行讨论（如 gpt-4o-mini）
   - 使用较大的模型作为压缩器（如 gpt-4o）
   - 合理设置上下文窗口

---

## 贡献与反馈

如有建议或问题，欢迎反馈！

---

**最后更新**: 2026年5月1日  
**版本**: 1.0.0
