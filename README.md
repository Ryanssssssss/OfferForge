# 🎯 面霸 — AI 简历面试教练

基于 **RAG + LangGraph Agent + 多模态语音** 的智能面试模拟系统。上传简历，AI 面试官根据你的真实项目经历进行个性化提问、追问和评分。

## 核心特性

- **简历驱动出题**：解析 PDF 简历，结合真题库 RAG 检索，生成与项目经历强相关的面试题
- **智能面试官**：像真人面试官一样追问、过渡、反问，支持跳题
- **实体级记忆**：每个项目/实习独立追踪，不串项目、不重复提问
- **多 LLM 支持**：DeepSeek / GPT / Gemini / Qwen / GLM / Kimi / SiliconFlow，一键切换
- **语音面试**：Qwen3-TTS 语音合成 + Qwen3-Omni 语音识别，可调语速
- **LeetCode 代码题**：完整题面 + 代码编辑器 + 本地样例测试 + LeetCode 链接
- **岗位智能过滤**：只对与目标岗位相关的经历出题
- **面试反馈报告**：多维度评分 + 改进建议
- **多对话管理**：历史面试保存/加载/删除，自动清理

## 快速开始

### 1. 安装依赖

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`：

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-key

# 语音功能（可选）
VOICE_API_KEY=your-dashscope-key
```

### 3. 启动

```bash
streamlit run app.py
```

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
├── app.py                          # Streamlit 主入口
├── config/
│   └── settings.py                 # 全局配置 + 多 Provider
├── core/
│   ├── agent/                      # LangGraph Agent（状态机 + Memory）
│   ├── llm/                        # LLM 接口 + Prompt + Provider 注册表
│   ├── interview/                  # 出题 + 评估 + 报告
│   ├── rag/                        # 真题库语义检索
│   ├── resume/                     # PDF 简历解析
│   ├── data/                       # 真题库 + LeetCode Hot 100
│   ├── code_runner.py              # 代码沙箱运行
│   ├── leetcode_manager.py         # LeetCode 题目管理
│   └── session_manager.py          # 会话持久化 + 自动清理
├── interfaces/
│   ├── text_interface.py           # 文本交互
│   └── voice_interface.py          # 语音交互（TTS + STT）
├── requirements.txt
└── .env.example
```

## 技术栈

| 模块 | 技术 |
|------|------|
| 前端 | Streamlit |
| Agent | LangGraph |
| LLM | OpenAI 兼容（多 Provider） |
| 简历解析 | pdfplumber + LLM |
| RAG | sentence-transformers + 本地真题库 |
| TTS | DashScope qwen3-tts-instruct-flash-realtime |
| STT | DashScope qwen3-omni-flash |
| 代码验证 | Python subprocess |

## License

MIT
