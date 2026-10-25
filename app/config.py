import os
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")

if not LLM_API_KEY or not LLM_MODEL:
    raise RuntimeError("LLM_API_KEY or LLM_MODEL is missing. Check your .env file.")