# Overview

This file contains the situations I faced and the learnings
I gained in the process

The format is :

```
## Situation
...
## Learnings
...
```


## Implementing a payload builder to handle multiple requests

We use a single MCPClient class to handle multiple tool, resource, prompt requests. This makes every request we make to 
the server consistent and structured.

```python
class MCPClient:
    
    def __init__(self, base_url: str) -> None:
        self._client = Client(base_url)
        
    @staticmethod
    def _build_tool_payload(trace_id: str, tool_name: str, arguments: dict) -> tuple[str, dict]:
        """Build and log tool call payload with tracing.

        Args:
            trace_id: Trace identifier for logging.
            tool_name: Registered MCP tool name.
            arguments: Flexible input arguments.

        Returns:
            Tuple of (tool_name, arguments).
        """
        logging.info(f"[{trace_id}] Building payload for tool: {tool_name}")
        return tool_name, arguments
```

Every transaction is logged using a trace_id assigned with each run_tool, run_resource, run_prompt call.


## Separating the concerns of MCP client and fastAPI gateway

The MCP client is not directly executed instead it is implemented in the FastAPI gateway. It helps in filtering the information being 
exposed to the outside gateway and the inside functioning.


## Adding a LLM orchestrator to the FastAPI gateway

What changes it makes? Current the tool call is purely based on the input schemas and the internal hardcoded logic. But adding a LLM orchestrator can help making tool, resource, prompt calling dynamic — power of agentic workflow.
It would help us automatically execute tasks till we arrive at a situation.


## How generic tools are replaced by tool nodes in MCP integrated langgraph orchestrator?

We do not directly bind the tools to the LLM. Instead we call the mcp client to handle the tool calling for us.

```python
  result = mcp_client.run_client(
    trace_id=state["trace_id"],
    name=state["selected_tool"],
    args=state["input"]
)
```


## Conversion from MCP tools received from the MCP server to LangcChain

- bind_tools() expects LangChain schema — it needs objects with .name, .description, and a Pydantic args_schema, not raw FastMCP Tool objects.
- LLM tool-calling format — bind_tools() serializes tools into the LLM's function-calling API format (OpenAI/Gemini spec). FastMCP Tool objects don't implement the BaseTool interface needed for this serialization.
- Type mismatch — FastMCP Tool is a Pydantic model describing a tool schema; StructuredTool is a LangChain runtime object that the framework knows how to invoke and serialize.

```python
# Convert the MCP tool to LangChain StructuredTool
        async with self._client:
            try:
                session = self._client.session
                lc_tools = await load_mcp_tools(session)
                return lc_tools
            except Exception as e:
                logging.error(f"list_tools_output_by_session failed: {e}")
                raise
```


## Functions of tools, resources and prompts and the integration with MCP

MCP provides with tools, resources and prompts. But, only tools are called by the LLM, rest are orchestrated.
Advantage is that the tools, resouces and prompts can by updated and changed in real time.

Here is the distinction:
1. Tools: Model-Controlled (The "Hands")

The LLM is aware of the tools' schemas and decides to call them when it needs to perform an action or fetch dynamic data it doesn't have.

    Orchestration Role: These are the decision points. Your orchestrator simply "binds" the tools to the LLM. The LLM then autonomously loops: Think -> Call Tool -> Observe Result -> Repeat.

2. Resources: Application-Controlled (The "Library")

The LLM cannot "call" a resource URI on its own. It is the job of the Orchestrator (the client application) to read the resource and inject its content into the context window.

    Orchestration Role: You use resources to manage the Context Window. Instead of dumping 50MB of documentation into every prompt (which is expensive and slows down the model), your orchestrator can:

    See that the user asked about "Project X."

    await client.read_resource("project://x/spec").

    Attach that specific content to the message sent to the LLM.

    Advantage: This prevents "context bloat." You only give the LLM the data relevant to the current step of your orchestration flow.

3. Prompts: User/Orchestrator-Controlled (The "Blueprint")

The LLM does not "call" a prompt. A prompt is a template that the Orchestrator fetches from the server to structure the conversation.

    Orchestration Role: Use prompts to standardize how your agents behave across different steps.

    Example: You have a research_orchestrator.py. It first fetches a search_strategy prompt to tell the LLM how to use the search tools. Once data is gathered, it fetches a summarization_report prompt to tell the LLM how to format the final output.

    Advantage: You can update the "instructions" for your agent on the MCP server side without touching the orchestration code in your main app.

## Why we cannot localise llm_node for all the llm invokation tasks

You must call the LLM (invoke or ainvoke) directly inside the summarization_node. You cannot easily direct it to the llm_node for this specific task.

### Why?
The llm_node and summarization_node have completely different jobs:
1.  llm_node: Is bound with Tools, uses the System Prompt for acting, and maintains the persona.
2.  summarization_node: Is a background "maintenance" task. It needs a specific instruction ("Compress this text") and should not have access to tools or the main persona prompts.

## How merging works in memory management?

```python
class MessageState(TypeDict):
    message: Annotated[str, add_messages]
    summary: str
```
This two variables are handled differently. When we update the MessageState of `message`, it merges the contents safely. But in case of summary, it overwrites it. Annotated is used to do pre-operation.

*   If you return {"messages": [NewMessage]} -> It appends to the existing messages list (because of operator.add).
*   If you return {"summary": "New text"} -> It overwrites the summary (because it has no reducer).

## The looping issue in summarization_node to llm_node

I was sending the summarization_node result to the llm_node. What it was doing? It was taking it as if a assitant message and should
generate something out of it uselessly. After making the entry in DB and the necessary changes in the State variable, there is no 
need to do anything but END.

```python
# From
agent_builder.add_edge("summarize_node", "llm_node")
# To
agent_builder.add_edge("summarize_node", END) 
```

## Mapping conflict in observability docker compose between jaeger and OTel Collector

We need to send the intrumented data to Collector through gRPC that sends it to Jaeger which helps in visualizing the traces.

In Docker Compose, ports means:
HOST_PORT:CONTAINER_PORT
So:
- "4317:4317"
means: expose container’s 4317 on host 4317.
What was wrong
- Jaeger had:
  - 4317:4317
  - 4318:4318
- Collector also had:
  - 4317:4317
  - 4318:4318
That is a host port conflict. Even if startup appears okay at times, routing/ownership is wrong or unstable.

*Host ports connects to docker ports and should not conflict with the collector and jaeger exposed ports.*

## Implementing Argument Sanitization in an efficient manner
Understand that each function has a request data as :

```python
ctx = {
    "request_context": {
        "request": {
            "params": {
                "name": "usage_analyzer",
                "arguments": {
                    "days": 5
                }
            }
        }
    }
}
```

We make a decorator that act as a layer through which the function parameters are sanitized on run

```python
# security/sanitizer.py

def sanitize(tool_name, args):

    if tool_name == "usage_analyzer":
        if "days" not in args:
            raise Exception("Missing days")

        if not isinstance(args["days"], int):
            raise Exception("days must be int")

        if args["days"] < 1 or args["days"] > 30:
            raise Exception("days must be between 1 and 30")

    return args
    
# security/decorator.py

def sanitize_args(tool_name):
    def decorator(func):
        def wrapper(ctx):

            # extract args from request
            params = getattr(ctx.request_context.request, "params", None)
            args = getattr(params, "arguments", {}) if params else {}

            try:
                clean_args = sanitize(tool_name, args)
            except Exception as e:
                return {"status": "error", "message": str(e)}

            return func(ctx, clean_args)

        return wrapper
    return decorator

# Use
from security.decorator import sanitize_args

@mcp.tool(name="usage_analyzer")
@sanitize_args("usage_analyzer")
def usage_analyzer(ctx, args):

    days = args["days"]

    return {
        "days": days,
        "total_usage": days * 2
    }
```
