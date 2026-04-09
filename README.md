# 面霸 — AI 简历面试教练

基于 **RAG + LangGraph Agent + 多模态语音** 的智能面试模拟系统。上传简历，AI 面试官根据你的真实项目经历进行个性化提问、追问和评分。

## 核心特性

- **简历驱动出题**：解析 PDF 简历，结合真题库 RAG 检索，生成与项目经历强相关的面试题
- **智能面试官**：像真人面试官一样追问、过渡、反问，支持跳题
- **实体级记忆**：每个项目/实习独立追踪，不串项目、不重复提问
- **多 LLM 支持**：DeepSeek / GPT / Gemini / Qwen / GLM / Kimi / SiliconFlow，一键切换
- **语音面试**：Qwen3-TTS 语音合成 + Qwen3-Omni 语音识别，可调语速
- **LeetCode 代码题**：完整题面 + Monaco 代码编辑器（Python3 / C++ / Java / Go / JS / TS / Rust）+ 本地样例测试
- **岗位智能过滤**：只对与目标岗位相关的经历出题
- **面试反馈报告**：多维度评分 + 改进建议 + 维度进度条
- **多对话管理**：历史面试保存/加载/删除，自动清理过期会话

## 架构

```
浏览器 (Next.js :3000) ──HTTP/SSE──▶ FastAPI (:8000) ──▶ Core (Agent / LLM / Voice)
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
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
```

**前端（Node.js）：**

```bash
cd frontend && npm install
```

### 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`，填写所选 Provider 的 API Key：

```bash
# 选择 LLM 提供商
LLM_PROVIDER=deepseek

# 对应的 API Key
DEEPSEEK_API_KEY=your-key

# 语音功能（可选，需阿里云 DashScope Key）
VOICE_API_KEY=your-dashscope-key
```

完整配置项参考 [.env.example](.env.example)。

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
│       ├── app/                    # 页面 (首页/面试/报告/历史)
│       ├── components/             # 组件 (聊天气泡/代码编辑器/语音/侧边栏)
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
│   ├── data/                       # 内置数据 (真题库 + LeetCode)
│   ├── code_runner.py              # Python 代码沙箱运行
│   ├── leetcode_manager.py         # LeetCode 题目管理
│   └── session_manager.py          # 会话持久化 + 自动清理
├── interfaces/                     # 交互接口
│   ├── text_interface.py           # 文本交互
│   └── voice_interface.py          # 语音交互 (TTS + STT)
├── config/
│   └── settings.py                 # pydantic-settings 配置
├── app.py                          # 旧 Streamlit 入口 (保留参考)
├── requirements.txt
└── .env.example
```

## 技术栈

| 模块 | 技术 |
|------|------|
| 前端 | Next.js 16 + shadcn/ui + Tailwind CSS + Monaco Editor |
| 后端 API | FastAPI + SSE (sse-starlette) + uvicorn |
| Agent | LangGraph (StateGraph 状态机, 手动调度节点) |
| LLM | LangChain + OpenAI 兼容接口 (多 Provider) |
| 简历解析 | pdfplumber + LLM 结构化提取 |
| RAG | sentence-transformers (`BAAI/bge-small-zh-v1.5`) + 本地真题库 |
| TTS | DashScope Qwen-TTS Realtime (qwen3-tts-instruct-flash-realtime) |
| STT | DashScope (qwen3-omni-flash) |
| 代码验证 | Python subprocess 沙箱 |

## API 端点

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/interview` | 上传简历 PDF, 创建会话 |
| POST | `/api/interview/{id}/select-job` | 选择目标岗位 |
| POST | `/api/interview/{id}/answer` | 提交回答 (SSE 流式返回) |
| GET | `/api/interview/{id}/status` | 获取面试状态 |
| GET | `/api/interview/{id}/report` | 获取反馈报告 |
| POST | `/api/interview/{id}/code/run` | 运行代码样例 |
| POST | `/api/voice/tts` | 文字转语音 |
| POST | `/api/voice/stt` | 语音转文字 |
| GET | `/api/sessions` | 历史会话列表 |
| DELETE | `/api/sessions/{id}` | 删除会话 |

## License

MIT
