"""
Configuration file for the application.
"""

import logging
import os
from typing import Optional

from langchain_core.runnables import RunnableConfig

# Configuration variables
OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4317"
OTEL_DEPLOYMENT_ENV = "dev"

# LLM Model
#LLM_MODEL = "gemini-3.1-flash-lite-preview"
LLM_MODEL = "mistral-large-2512"

# Embedding Model
#EMBEDDING_MODEL = "models/gemini-embedding-2-preview"
EMBEDDING_MODEL = "mistral-embed"

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
        logging.warning(
            "Failed to create persistent storage directory. Check permissions config helper function"
        )
        exit(1)
