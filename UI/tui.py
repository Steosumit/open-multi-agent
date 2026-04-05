import asyncio

import httpx
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    RichLog,
)

from UI.client import GatewayClient


class ResponseMessage(Message):
    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__()


class ErrorMessage(Message):
    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__()


class GatewayTUI(App[None]):
    CSS = """
    Screen {
        background: #11151a;
        color: #ecf3fb;
    }

    #root {
        height: 1fr;
        padding: 1 2;
    }

    #status-bar {
        height: auto;
        padding: 0 1;
        color: #8fa6bc;
    }

    #chat-log {
        height: 1fr;
        border: round #2e3a46;
        background: #171d24;
        padding: 0 1;
    }

    #controls {
        height: auto;
        padding-top: 1;
    }

    #prompt {
        width: 1fr;
    }

    #send-btn {
        width: 14;
        content-align: center middle;
        border: round #4278a8;
        background: #22384d;
        color: #d6e9fc;
        padding: 0 1;
    }

    #send-btn.-active {
        background: #2b4a66;
    }

    #loading {
        width: auto;
        height: auto;
        margin-left: 1;
    }
    """

    TITLE = "Agent TUI"
    BINDINGS = [
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._client = GatewayClient()
        self._busy = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="root"):
            yield Label(
                f"Connected endpoint: {self._client.base_url}/agent-task | timeout: {int(self._client.timeout_seconds)}s",
                id="status-bar",
            )
            yield RichLog(id="chat-log", wrap=True, markup=False, highlight=False)
            with Horizontal(id="controls"):
                yield Input(placeholder="Type a message. /clear or /quit", id="prompt")
                yield Button("Send", id="send-btn")
                yield LoadingIndicator(id="loading")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#loading", LoadingIndicator).display = False
        self._log_system(
            "Ready. Enter a message and press Enter. Commands: /clear, /quit"
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text == "/quit":
            self.exit()
            return
        if text == "/clear":
            self.action_clear_chat()
            return
        if self._busy:
            self._log_system("Please wait for the current request to finish.")
            return

        self._log_user(text)
        self._set_busy(True)
        self._send_message(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "send-btn":
            return
        prompt = self.query_one("#prompt", Input)
        text = prompt.value.strip()
        if not text:
            return
        prompt.value = ""
        if self._busy:
            self._log_system("Please wait for the current request to finish.")
            return
        self._log_user(text)
        self._set_busy(True)
        self._send_message(text)

    @work(exclusive=False)
    async def _send_message(self, text: str) -> None:
        try:
            task = asyncio.create_task(self._client.send_message(text))
            response = await task
            assistant_text = f"Assistant: {response.result}"
            trace_line = (
                f"trace_id: {response.trace_id}"
                if response.trace_id
                else "trace_id: missing"
            )
            self.post_message(ResponseMessage(f"{assistant_text}\n{trace_line}"))
        except httpx.TimeoutException:
            self.post_message(ErrorMessage("Request timed out. Try again."))
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            body = exc.response.text.strip()
            details = body[:300] if body else "No response body"
            self.post_message(
                ErrorMessage(f"Gateway returned HTTP {code}. Details: {details}")
            )
        except httpx.RequestError as exc:
            self.post_message(
                ErrorMessage(f"Cannot reach gateway at {self._client.base_url}. {exc}")
            )
        except Exception as exc:
            self.post_message(ErrorMessage(f"Unexpected error: {exc}"))

    def on_response_message(self, message: ResponseMessage) -> None:
        self._log_assistant(message.text)
        self._set_busy(False)

    def on_error_message(self, message: ErrorMessage) -> None:
        self._log_error(message.text)
        self._set_busy(False)

    def action_clear_chat(self) -> None:
        self.query_one("#chat-log", RichLog).clear()
        self._log_system("Chat cleared.")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        prompt = self.query_one("#prompt", Input)
        loading = self.query_one("#loading", LoadingIndicator)
        send_btn = self.query_one("#send-btn", Button)
        prompt.disabled = busy
        loading.display = busy
        send_btn.set_class(busy, "-active")

    def _log_user(self, text: str) -> None:
        self.query_one("#chat-log", RichLog).write(f"You: {text}")

    def _log_assistant(self, text: str) -> None:
        self.query_one("#chat-log", RichLog).write(text)

    def _log_system(self, text: str) -> None:
        self.query_one("#chat-log", RichLog).write(f"System: {text}")

    def _log_error(self, text: str) -> None:
        self.query_one("#chat-log", RichLog).write(f"Error: {text}")


if __name__ == "__main__":
    GatewayTUI().run()
