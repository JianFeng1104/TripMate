r"""Manually exercise the real TripMate DeepSeek agent.

Run from the project root only when you intentionally want to spend API tokens:
    .\.venv\Scripts\python.exe scripts\deepseek_agent_smoke.py
"""

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tripmate import create_app  # noqa: E402
from tripmate.agent import AgentRunner, DeepSeekClient  # noqa: E402
from tripmate.agent.exceptions import AgentError  # noqa: E402
from tripmate.services import search_trips  # noqa: E402


PROJECT_NAME = "TripMate"
PROVIDER_NAME = "DeepSeek"
TEST_PROMPT = "帮我找去东京、目前可以参加的旅行，并根据真实数据说明为什么适合。"


def main() -> int:
    configured_model = os.environ.get("DEEPSEEK_MODEL") or "deepseek-v4-flash"
    print(f"Project: {PROJECT_NAME}")
    print(f"Provider: {PROVIDER_NAME}")
    print(f"Model: {configured_model}")
    print(f"Test prompt: {TEST_PROMPT}")
    if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        print("Status: FAILURE")
        print("Reason: DEEPSEEK_API_KEY is not configured; no API request was made.")
        return 2

    app = create_app()
    try:
        with app.app_context():
            available = search_trips(destination="东京", page=1, per_page=1)
            if not available["items"]:
                raise ValueError(
                    "The current database has no OPEN Tokyo trip; no API request was made."
                )
            client = DeepSeekClient.from_config(app.config)
            answer = AgentRunner(client).run(TEST_PROMPT)
    except AgentError as error:
        print("Status: FAILURE")
        print(f"Reason: {type(error).__name__}")
        return 1
    except ValueError as error:
        print("Status: FAILURE")
        print(f"Reason: {error}")
        return 1

    print("Final assistant response:")
    print(answer)
    print("Status: SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
