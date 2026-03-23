import asyncio
import logging
import sys
import os
# Ensure we can import app modules
sys.path.append(os.getcwd())
from app.orchestrator import run_agent
# Configure logging to see the "Triggering summarization" and "Stored long-term memory" logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
async def main():
    trace_id = "verify-memory-trace-001"
    print(f"--- Starting Memory Load Test (Trace ID: {trace_id}) ---")
    # 1. Send 20 messages to fill up Short Term Memory
    print("\n[1/2] Sending 20 messages to trigger summarization...")
    for i in range(20):
        msg = f"This is fact number {i}. I am teaching you about numbers."
        print(f"User: {msg}")
        # We don't print every agent response to keep output clean, 
        # but we await it to ensure sequential processing
        await run_agent(msg, trace_id)
        # Small delay to ensure logs print in order (optional)
        await asyncio.sleep(0.1)
    print("\n[2/2] Asking for a summary (should trigger LTM retrieval)...")
    # 2. Ask a question that requires the summary
    query = "What have we been talking about? Summarize the facts."
    print(f"User: {query}")
    response = await run_agent(query, trace_id)
    print(f"\nAgent: {response}")
if __name__ == "__main__":
    asyncio.run(main())