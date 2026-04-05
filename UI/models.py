from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AgentTaskResult:
    trace_id: str
    result: Any
