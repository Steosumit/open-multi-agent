"""
Configuration file for the application.
"""

from langchain_core.runnables import RunnableConfig

# Configuration variables
LLM_MODEL = "gemini-3-flash-preview"
LLM_TEMPERATURE = 0
REDIS_URL = "redis://localhost:6379/"


# Helper configuration definitions
def get_short_term_memory_config(thread_id: str) -> RunnableConfig:
    return {
        "configurable": {"thread_id": thread_id}
    }  # it is used to idenfify same messages duing graph runtime
