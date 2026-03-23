"""
Configuration file for the application.
"""

import logging
from typing import Optional
from langchain_core.runnables import RunnableConfig
import os

# Configuration variables
LLM_MODEL = "gemini-3.1-flash-lite-preview"
EMBEDDING_MODEL = "models/gemini-embedding-2-preview"
LLM_TEMPERATURE = 0
REDIS_URL = "redis://localhost:6379/"
MESSAGES_BUFFER_LTM = 5  # messages to keep 
SUMMARISE_MESSAGE_THRESHOLD = 5

# Helper configuration definitions

# Get configuration for the graph checkpointer in short term memory to identify related threads 
def get_short_term_memory_config(thread_id: str) -> RunnableConfig:
    return {
        "configurable": {"thread_id": thread_id}
    }  # it is used to idenfify same messages duing graph runtime

# Get persistent storage location for vector DB
def get_persistent_storage():
    """Ensures the memory directory exists."""
    path = "/memory/data"
    try:
        os.makedirs(path, exist_ok=True)
        logging.info(f"Persistent storage directory created at: {path}")
        return path
    except OSError:
        logging.warning("Failed to create persistent storage directory. Check permissions config helper function")
        exit(1)