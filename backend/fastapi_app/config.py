import os

APP_ID = os.environ.get("APP_ID", "")
APP_SECRET = os.environ.get("APP_SECRET", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
DB_URL = os.environ.get("DB_URL", "sqlite:///./clothing.db")

# agent LLM(国产模型,OpenAI 兼容端点)
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen-plus")
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "120"))

AGENT_MAX_STEPS = int(os.environ.get("AGENT_MAX_STEPS", "1000"))  # 纯防死循环兜底,非成本护栏
