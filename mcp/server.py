from config import LOG_FILE_PATH
from fastmcp import FastMCP
import os
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s\n-\n%(message)s",
)


mcp = FastMCP(
    name="Personal",
    instructions="""
        This server provides inner tools for personal use. The following tools are available:
        read_logs: Reads the latest logs from the system.
    """,
)


### All the tools ###
@mcp.tool
def tool_health_check() -> str:
    """Used to check if the server is running."""
    return "Server is healthy and running."


### All the resources ###
@mcp.resource(
    uri="data://logs",
    name="logs",
    description="Provides logs for all the past processes",
    tags={"monitoring", "status", "logs", "personal logs"},
)

def read_logs() -> str:
    """Read the latest logs from the system."""

    logging.info(f"Reading logs from: {LOG_FILE_PATH}")  # Debug statement to check the log file path

    try:
        os.makedirs(LOG_FILE_PATH.parent, exist_ok=True)
        if not os.path.exists(LOG_FILE_PATH):
            with open(LOG_FILE_PATH, "w"):
                pass
            logs = "No logs file found. A new log file has been created."
        else:
            logs = open(LOG_FILE_PATH, "r").read().splitlines()[-100:]  # Read the last 100 lines of logs
        logging.info(f"read_logs: successfully read logs")
    except OSError as e:
        logging.error(f"read_logs: Failed to read logs : {e}")
        logs = ["Something went wrong while reading logs. Please check the server logs for more details."]

    return str(logs)


### All the prompts ###
#@mcp.prompt


if __name__ == "__main__":
    # HTTP transport
    mcp.run(transport="http", host="0.0.0.0", port=9000)
