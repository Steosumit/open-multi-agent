# Gateway TUI

Terminal chat client for the FastAPI gateway endpoint `/agent-task`.

## Requirements

- Python 3.13+
- Gateway running at `GATEWAY_URL` (default expected from `.env`)

## Configuration

Configuration is loaded from `.env` in the project root.

- `GATEWAY_URL` (example: `http://localhost:8001`)
- `GATEWAY_UI_TIMEOUT` in seconds (optional, defaults to `60`)

## Run

1. Start the gateway:

```powershell
just gateway
```

2. In another terminal, run the TUI:

```powershell
python -m UI.tui
```

## Usage

- Type a message and press Enter.
- Use `/clear` to reset the chat window.
- Use `/quit` or `Ctrl+C` to exit.
