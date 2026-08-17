"""Minimal DeepSeek Chat Completions HTTP client using the Python standard library."""

import json
import socket
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .exceptions import (
    MalformedProviderResponse,
    MissingDeepSeekConfiguration,
    ProviderError,
    ProviderTimeout,
)


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_TIMEOUT_SECONDS = 25


class DeepSeekClient:
    """Send non-streaming, non-thinking Chat Completion requests to DeepSeek."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ):
        api_key = (api_key or "").strip()
        if not api_key:
            raise MissingDeepSeekConfiguration("DEEPSEEK_API_KEY is missing")
        parsed_url = urlparse(base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise MissingDeepSeekConfiguration("DEEPSEEK_BASE_URL is invalid")
        if not model.strip():
            raise MissingDeepSeekConfiguration("DEEPSEEK_MODEL is invalid")
        if not 1 <= int(timeout) <= 120:
            raise MissingDeepSeekConfiguration("DeepSeek timeout is invalid")
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model.strip()
        self.timeout = int(timeout)

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "DeepSeekClient":
        """Build a client from Flask configuration without requiring a request context."""

        return cls(
            api_key=str(config.get("DEEPSEEK_API_KEY") or ""),
            base_url=str(config.get("DEEPSEEK_BASE_URL") or DEFAULT_BASE_URL),
            model=str(config.get("DEEPSEEK_MODEL") or DEFAULT_MODEL),
            timeout=int(config.get("DEEPSEEK_TIMEOUT") or DEFAULT_TIMEOUT_SECONDS),
        )

    def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Return one validated assistant message from DeepSeek."""

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "stream": False,
            "thinking": {"type": "disabled"},
            "max_tokens": 1200,
        }
        if tools:
            payload["tools"] = list(tools)
            payload["tool_choice"] = "auto"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base_url}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw_response = response.read()
        except HTTPError as error:
            raise ProviderError(_http_error_category(error.code), error.code) from error
        except (TimeoutError, socket.timeout) as error:
            raise ProviderTimeout() from error
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise ProviderTimeout() from error
            raise ProviderError("network") from error
        except OSError as error:
            raise ProviderError("network") from error

        try:
            response_data = json.loads(raw_response.decode("utf-8"))
            message = response_data["choices"][0]["message"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise MalformedProviderResponse("DeepSeek returned malformed JSON") from error
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise MalformedProviderResponse("DeepSeek returned no assistant message")
        if message.get("content") is not None and not isinstance(message.get("content"), str):
            raise MalformedProviderResponse("DeepSeek returned invalid content")
        if "tool_calls" in message and not isinstance(message["tool_calls"], list):
            raise MalformedProviderResponse("DeepSeek returned invalid tool calls")
        return message


def _http_error_category(status_code: int) -> str:
    return {
        400: "invalid_request",
        401: "authentication",
        402: "insufficient_balance",
        422: "invalid_parameters",
        429: "rate_limit",
        500: "server_error",
        503: "server_overloaded",
    }.get(status_code, "provider_error")
