from pydantic import BaseModel
from typing import Any, Optional


# Model to validate agent task requests
class AgentTaskRequest(BaseModel):
    message: str
    trace_id: Optional[str] = None
# Model to validate agent task responses
class AgentTaskResponse(BaseModel):
    trace_id: str
    result: Any
