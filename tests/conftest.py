"""
Shared pytest configuration.
Adds the project root to sys.path so that app/, core/, and mcp_local/ are importable.
"""

import sys
import os

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Project root on path: resolves app.*, core.*, mcp_local.*
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# app/ on path: allows `from main import app` (used in integration tests)
_APP = os.path.join(_ROOT, "app")
if _APP not in sys.path:
    sys.path.insert(0, _APP)