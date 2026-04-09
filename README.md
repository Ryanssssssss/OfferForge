# 面霸 — AI 简历面试教练

基于 **RAG + LangGraph Agent + 多模态语音** 的智能面试模拟系统。上传简历，AI 面试官根据你的真实项目经历进行个性化提问、追问和评分。

## 核心特性

- **简历驱动出题**：解析 PDF 简历 + RAG 真题检索，按项目经历个性化出题
- **智能追问**：模拟真人面试官追问、过渡、反问，实体级记忆不串项目
- **多 LLM 切换**：DeepSeek / GPT / Gemini / Qwen / GLM / Kimi 等一键切换
- **语音 + 文本双模式**：Qwen3 TTS/STT 语音面试，可调语速，随时切换文本输入
- **LeetCode 代码题**：题面渲染 + Monaco 编辑器 + 本地样例测试 + 对话讨论
- **面试报告**：多维度评分 + 改进建议
- **简历复用**：已上传简历可直接复用，缓存解析结果跳过重复解析

## 架构

```
浏览器 (Next.js) ──HTTP/SSE──▶ FastAPI ──▶ Core (Agent / LLM / Voice)
```

前后端分离架构：Next.js + shadcn/ui 前端，FastAPI 后端，复用已有的面试核心逻辑。

## 快速开始

### 环境要求

- Python >= 3.10（推荐 3.12）
- Node.js >= 18
- [uv](https://docs.astral.sh/uv/)（推荐）或 pip

### 1. 安装依赖

**后端（Python）：**

```bash
uv sync
```

**前端（Node.js）：**

```bash
cd frontend && npm install
```

### 2. 配置

```bash
cp .env.example .env
```

有两种配置方式（任选其一）：

**方式 A：在 Web 界面配置（推荐）**

启动后点击侧边栏的「AI 模型配置」，选择提供商、填入 API Key，保存后自动写入 `.env`，无需手动编辑。

**方式 B：手动编辑 `.env`**

```bash
# LLM 提供商：deepseek / openai / gemini / qwen / zhipu / moonshot / siliconflow / custom
LLM_PROVIDER=你选的提供商

# 填写对应提供商的 API Key（只需填一个）
DEEPSEEK_API_KEY=
OPENAI_API_KEY=
QWEN_API_KEY=
# ... 其他 Key 见 .env.example

# 语音功能（可选）
# 使用阿里云 DashScope 的 Qwen3 系列语音模型
# 获取 Key: https://dashscope.console.aliyun.com/apiKey
VOICE_API_KEY=
```

> 在 Web 界面修改的配置会自动持久化到 `.env`，重启后依然生效。

### 3. 启动

```bash
# 终端 1：启动后端 (端口 8000)
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# 终端 2：启动前端 (端口 3000)
cd frontend && npm run dev
```

打开 `http://localhost:3000` 即可使用。

> 前端开发服务器会自动将 `/api/*` 请求代理到后端 `localhost:8000`。

## 支持的 LLM

| Provider | 默认模型 |
|----------|---------|
| DeepSeek | deepseek-chat |
| OpenAI (GPT) | gpt-4o-mini |
| Google Gemini | gemini-2.0-flash |
| 通义千问 | qwen-plus |
| 智谱 GLM | glm-4-flash |
| Moonshot (Kimi) | moonshot-v1-8k |
| SiliconFlow | DeepSeek-V3 |
| 自定义 | 任何 OpenAI 兼容 API |

> 所有 Provider 均通过 OpenAI 兼容接口调用，可在界面内"AI 模型配置"中实时切换。

## 语音服务

语音面试功能基于**阿里云 DashScope** 的 **Qwen3** 系列语音模型：

| 功能 | 模型 | 说明 |
|------|------|------|
| 语音合成 (TTS) | `qwen3-tts-instruct-flash-realtime` | WebSocket 实时流式合成，支持语速调节 |
| 语音识别 (STT) | `qwen3-omni-flash` | OpenAI 兼容接口，音频转文字 |

需要在 `.env` 中配置 `VOICE_API_KEY`（DashScope API Key）。未配置时语音功能自动禁用，不影响文本面试。

获取 Key：[dashscope.console.aliyun.com/apiKey](https://dashscope.console.aliyun.com/apiKey)

## 面试模式

| 模式 | 说明 |
|------|------|
| 技术岗面试 | 实习深入 + 项目 + 八股文 + LeetCode |
| 简历深度拷打 | 所有经历逐个深挖，不考八股 |

## 项目结构

```
SmartInterview/
├── backend/                        # FastAPI 后端 API 层
│   ├── main.py                     # FastAPI 入口, CORS, 路由挂载
│   ├── schemas.py                  # Pydantic request/response 模型
│   ├── session_store.py            # 内存 Session 池 (session_id → Agent)
│   └── api/
│       ├── interview.py            # 面试核心 API (上传/选岗/答题/报告)
│       ├── voice.py                # 语音 API (STT/TTS)
│       └── sessions.py             # 历史会话 CRUD
├── frontend/                       # Next.js 前端
│   └── src/
│       ├── app/                    # 页面 (首页/面试/报告)
│       ├── components/             # 组件 (聊天气泡/代码编辑器/语音/侧边栏/设置)
│       ├── hooks/                  # React Hooks (use-interview/use-voice)
│       ├── lib/api.ts              # API 客户端 + SSE 解析
│       └── types/                  # TypeScript 类型定义
├── core/                           # 面试核心逻辑 (不依赖 UI 框架)
│   ├── agent/                      # LangGraph Agent (状态机 + Memory)
│   │   ├── graph.py                # 手动调度的 StateGraph 流程编排
│   │   ├── nodes.py                # 节点 (出题/追问/评估/报告)
│   │   └── states.py               # Agent 状态 TypedDict
│   ├── llm/                        # LLM 接口层
│   │   ├── prompts.py              # Prompt 模板
│   │   ├── providers.py            # 多 Provider 注册表
│   │   └── thinker.py              # 统一 LLM 调用入口
│   ├── interview/                  # 面试核心
│   │   ├── question_gen.py         # 出题引擎
│   │   ├── evaluator.py            # 回答评估
│   │   └── reporter.py             # 面试报告生成
│   ├── rag/                        # 真题库语义检索
│   ├── resume/                     # 简历解析 (PDF → 结构化)
│   ├── data/                       # 内置数据 (真题库 + LeetCode Hot 100)
│   ├── code_runner.py              # Python 代码沙箱运行
│   ├── leetcode_manager.py         # LeetCode 题目管理
│   └── session_manager.py          # 会话持久化 + 自动清理
├── interfaces/                     # 交互接口
│   ├── text_interface.py           # 文本交互
│   └── voice_interface.py          # 语音交互 (Qwen3 TTS + STT)
├── config/
│   └── settings.py                 # pydantic-settings 配置
├── requirements.txt
└── .env.example
```

## License

MIT
