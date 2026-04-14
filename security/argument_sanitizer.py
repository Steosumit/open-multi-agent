import re
import inspect
import logging
from functools import wraps


class InvalidToolArguments(Exception):
    pass


class ArgumentSanitizer:
    """Analyzes tool parameters and sanitizes them."""

    # Strict tool rules
    RULES = {
        "tool_health_check": {
            "required": [],
            "types": {},
        },
        "file_read": {
            "required": ["file_path"],
            "types": {"file_path": str},
            "min_len": {"file_path": 1},
            "max_len": {"file_path": 1024},
        },
        "file_create": {
            "required": ["file_path"],
            "types": {"file_path": str},
            "min_len": {"file_path": 1},
            "max_len": {"file_path": 1024},
        },
        "file_write": {
            "required": ["file_path", "content"],
            "types": {"file_path": str, "content": str},
            "min_len": {"file_path": 1},
            "max_len": {"file_path": 1024, "content": 1_000_000},
        },
        # g-search tools
        "search": {
            "required": ["queries"],
            "types": {"queries": list, "limit": int, "timeout": int, "noSaveState": bool, "debug": bool, "locale": str},
            "min": {"limit": 1, "timeout": 1000},
            "max": {"limit": 100, "timeout": 300000},
            "max_len": {"locale": 10},
        },
        # playwright tools
        "browser_navigate": {
            "required": ["url"],
            "types": {"url": str},
            "max_len": {"url": 2048},
            "regex": {"url": r"^https?://.+"},
        },
        "browser_screenshot": {
            "required": ["name"],
            "types": {"name": str, "selector": str, "fullPage": bool},
            "max_len": {"name": 256},
        },
        "browser_click": {
            "required": ["selector"],
            "types": {"selector": str},
            "max_len": {"selector": 512},
        },
        "browser_click_text": {
            "required": ["text"],
            "types": {"text": str},
            "max_len": {"text": 512},
        },
        "browser_fill": {
            "required": ["selector", "value"],
            "types": {"selector": str, "value": str},
            "max_len": {"selector": 512, "value": 100000},
        },
        "browser_select": {
            "required": ["selector", "value"],
            "types": {"selector": str, "value": str},
            "max_len": {"selector": 512, "value": 512},
        },
        "browser_select_text": {
            "required": ["text", "value"],
            "types": {"text": str, "value": str},
            "max_len": {"text": 512, "value": 512},
        },
        "browser_hover": {
            "required": ["selector"],
            "types": {"selector": str},
            "max_len": {"selector": 512},
        },
        "browser_hover_text": {
            "required": ["text"],
            "types": {"text": str},
            "max_len": {"text": 512},
        },
        "browser_evaluate": {
            "required": ["script"],
            "types": {"script": str},
            "max_len": {"script": 50000},
        },
    }

    @classmethod
    def sanitize(cls, function_name: str, arguments: dict) -> dict:
        if not isinstance(arguments, dict):
            raise InvalidToolArguments("arguments must be a JSON object")

        rules = cls.RULES.get(function_name)
        if rules is None:
            raise InvalidToolArguments(f"Unknown tool: {function_name}")

        required_fields = set(rules.get("required", []))
        typed_fields = set(rules.get("types", {}).keys())
        allowed_fields = required_fields | typed_fields

        # Unknown field checks (strict mode)
        unknown_fields = set(arguments.keys()) - allowed_fields
        if unknown_fields:
            fields = ", ".join(sorted(unknown_fields))
            raise InvalidToolArguments(f"Unknown field(s): {fields}")

        # Required fields
        for field in required_fields:
            if field not in arguments:
                raise InvalidToolArguments(f"Missing field: {field}")

        # Type checks
        for field, expected_type in rules.get("types", {}).items():
            if field in arguments and not isinstance(arguments[field], expected_type):
                raise InvalidToolArguments(f"{field} must be {expected_type.__name__}")

        # Min checks
        for field, min_val in rules.get("min", {}).items():
            if field in arguments and arguments[field] < min_val:
                raise InvalidToolArguments(f"{field} must be >= {min_val}")

        # Max checks
        for field, max_val in rules.get("max", {}).items():
            if field in arguments and arguments[field] > max_val:
                raise InvalidToolArguments(f"{field} must be <= {max_val}")

        # String length checks
        for field, min_len in rules.get("min_len", {}).items():
            if field in arguments and isinstance(arguments[field], str):
                if len(arguments[field].strip()) < min_len:
                    raise InvalidToolArguments(f"{field} length must be >= {min_len}")

        for field, max_len in rules.get("max_len", {}).items():
            if field in arguments and isinstance(arguments[field], str):
                if len(arguments[field]) > max_len:
                    raise InvalidToolArguments(f"{field} length must be <= {max_len}")

        # Regex checks (Future Extension)
        for field, pattern in rules.get("regex", {}).items():
            if field in arguments and isinstance(arguments[field], str):
                if re.fullmatch(pattern, arguments[field]) is None:
                    raise InvalidToolArguments(f"{field} has invalid format")

        return arguments


def sanitize_args(tool_name: str):
    """Decorator to sanitize MCP tool arguments from request context."""

    def decorator(func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            logging.debug(
                f"[sanitize_args] tool={tool_name} ctx_type={type(ctx).__name__}"
            )

            # Extract the arguments as per the ctx
            request_ctx = getattr(ctx, "request_context", None)
            request = getattr(request_ctx, "request", None)
            params = getattr(request, "params", None)
            raw_args = getattr(params, "arguments", {}) if params else {}

            try:
                clean_args = ArgumentSanitizer.sanitize(tool_name, raw_args or {})
                merged_kwargs = {**kwargs, **clean_args}
                result = func(ctx, *args, **merged_kwargs)
                if inspect.isawaitable(result):
                    return await result
                return result

            except InvalidToolArguments as e:
                error_msg = str(e)
                logging.warning(
                    f"[sanitize_args] Argument validation failed for {tool_name}: {error_msg}"
                )
                return {
                    "status": "error",
                    "message": error_msg,
                }

        return wrapper

    return decorator
