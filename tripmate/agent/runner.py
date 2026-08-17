"""Bounded DeepSeek tool-calling loop for TripMate."""

import json
from collections.abc import Mapping
from typing import Any, Protocol

from .exceptions import MalformedProviderResponse, MaxToolRoundsExceeded
from .instructions import SYSTEM_INSTRUCTION
from .tools import TRIP_TOOLS, execute_tool_call


MAX_TOOL_ROUNDS = 5


class ChatClient(Protocol):
    """Minimal injectable client contract used by the Agent runner."""

    def chat(self, messages, tools=None) -> dict[str, Any]: ...


class AgentRunner:
    """Run a single read-only TripMate conversation with a hard loop limit."""

    def __init__(self, client: ChatClient, max_tool_rounds: int = MAX_TOOL_ROUNDS):
        if not 1 <= max_tool_rounds <= MAX_TOOL_ROUNDS:
            raise ValueError(f"max_tool_rounds must be between 1 and {MAX_TOOL_ROUNDS}")
        self.client = client
        self.max_tool_rounds = max_tool_rounds

    def run(
        self,
        user_message: str,
        trusted_context: Mapping[str, Any] | None = None,
    ) -> str:
        """Return the final assistant answer after zero or more read-only tools."""

        user_message = (user_message or "").strip()
        if not user_message or len(user_message) > 3000:
            raise ValueError("User message must contain 1 to 3000 characters.")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": user_message},
        ]
        for _ in range(self.max_tool_rounds):
            assistant_message = self.client.chat(messages, tools=TRIP_TOOLS)
            normalized = _normalize_assistant_message(assistant_message)
            messages.append(normalized)
            tool_calls = normalized.get("tool_calls") or []
            if not tool_calls:
                content = normalized.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise MalformedProviderResponse("DeepSeek returned an empty answer")
                return content.strip()
            for tool_call in tool_calls:
                tool_call_id, name, arguments = _parse_tool_call(tool_call)
                result = execute_tool_call(name, arguments, trusted_context)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                    }
                )
        raise MaxToolRoundsExceeded("Maximum tool rounds reached")


def _normalize_assistant_message(message: Any) -> dict[str, Any]:
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise MalformedProviderResponse("Invalid assistant message")
    normalized: dict[str, Any] = {
        "role": "assistant",
        "content": message.get("content"),
    }
    if message.get("tool_calls") is not None:
        if not isinstance(message["tool_calls"], list):
            raise MalformedProviderResponse("Invalid tool_calls")
        normalized["tool_calls"] = message["tool_calls"]
    return normalized


def _parse_tool_call(tool_call: Any) -> tuple[str, str, str]:
    try:
        tool_call_id = tool_call["id"]
        function = tool_call["function"]
        name = function["name"]
        arguments = function["arguments"]
    except (KeyError, TypeError) as error:
        raise MalformedProviderResponse("Invalid tool call") from error
    if not all(isinstance(value, str) and value for value in (tool_call_id, name)):
        raise MalformedProviderResponse("Invalid tool identity")
    if not isinstance(arguments, str):
        raise MalformedProviderResponse("Invalid tool arguments")
    return tool_call_id, name, arguments
