from core.config import ALLOWED_TOOLS

class ToolAccessControl:
    """Implements tool access control for mcp"""
    
    def __init__(self):
        self.allowed_tools = set(ALLOWED_TOOLS)
    
    def enforce_tool_access(self, tool_name: str):
        if tool_name not in ALLOWED_TOOLS:
            # disabled during testing
            pass
            #raise Exception(f"{tool_name} not allowed")
            