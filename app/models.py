from pydantic import BaseModel
from typing import Any

# Model to validate agent task requests
class AgentTaskRequest(BaseModel):
    tool_name: str
    arguments: dict

# Model to validate agent task responses
class AgentTaskResponse(BaseModel):
    trace_id: str
    result: Any
