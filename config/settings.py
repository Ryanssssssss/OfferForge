"""全局配置管理，基于 pydantic-settings 从 .env 加载配置。

支持多 LLM Provider：DeepSeek / OpenAI / Qwen / 智谱 / Moonshot / SiliconFlow / 自定义
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM 多 Provider 配置 ──
    # 当前选中的 Provider（可在 UI 中切换）
    llm_provider: str = "deepseek"  # deepseek / openai / gemini / qwen / zhipu / moonshot / siliconflow / custom

    # 各 Provider 的 API Key（用户配哪个填哪个）
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    qwen_api_key: str = ""
    zhipu_api_key: str = ""
    moonshot_api_key: str = ""
    siliconflow_api_key: str = ""
    custom_api_key: str = ""
    custom_base_url: str = ""
    custom_model_name: str = ""

    # LLM 通用参数
    llm_model_name: str = ""  # 为空时使用 Provider 默认模型
    llm_temperature: float = 0.7

    # ── 语音模型配置 ──
    voice_api_key: str = ""
    voice_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    voice_model_name: str = "qwen3-omni-flash"
    voice_name: str = "Chelsie"

    # ── RAG ──
    local_embedding_model: str = "BAAI/bge-small-zh-v1.5"
    question_bank_path: str = "./core/data/question_bank.json"

    # ── 文件 ──
    upload_dir: str = "./data/uploads"

    # ── 面试配置 ──
    max_questions: int = 10
    max_follow_ups_per_question: int = 3

    # ── 岗位类别 ──
    job_categories: list[str] = [
        "简历深度拷打（不限岗位）",
        "纯算法题",
        "后端开发",
        "前端开发",
        "全栈开发",
        "数据工程师",
        "算法工程师",
        "产品经理",
        "运营",
        "设计师",
        "测试工程师",
        "DevOps",
    ]

    def get_llm_config(self) -> dict:
        """根据当前 Provider 返回 LLM 配置（api_key, base_url, model）。"""
        from core.llm.providers import get_provider

        provider = get_provider(self.llm_provider)
        if not provider:
            provider = get_provider("deepseek")

        # 确定 API Key
        key_map = {
            "deepseek": self.deepseek_api_key or self.openai_api_key,  # 兼容旧配置
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
            "qwen": self.qwen_api_key,
            "zhipu": self.zhipu_api_key,
            "moonshot": self.moonshot_api_key,
            "siliconflow": self.siliconflow_api_key,
            "custom": self.custom_api_key,
        }
        api_key = key_map.get(self.llm_provider, "")

        # 确定 base_url
        base_url = provider.base_url
        if self.llm_provider == "custom" and self.custom_base_url:
            base_url = self.custom_base_url

        # 确定 model
        model = self.llm_model_name or provider.default_model
        if self.llm_provider == "custom" and self.custom_model_name:
            model = self.custom_model_name

        return {
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "temperature": self.llm_temperature,
        }

    def ensure_dirs(self) -> None:
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)


settings = Settings()
