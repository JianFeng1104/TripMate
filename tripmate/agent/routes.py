"""SSR route for the TripMate read-only assistant."""

from flask import Blueprint, current_app, g, render_template, request

from ..utils import login_required, validate_csrf
from .client import DeepSeekClient
from .exceptions import (
    AgentError,
    MaxToolRoundsExceeded,
    MissingDeepSeekConfiguration,
    ProviderTimeout,
)
from .runner import AgentRunner


bp = Blueprint("agent", __name__)


@bp.route("/travel-assistant", methods=("GET", "POST"))
@login_required
def travel_assistant():
    """Render one stateless, read-only TripMate assistant interaction."""

    question = ""
    answer = None
    error = None
    if request.method == "POST":
        validate_csrf()
        question = request.form.get("question", "").strip()
        if not question:
            error = "请输入你的旅行问题。"
        elif len(question) > 3000:
            error = "问题不能超过 3000 个字符。"
        else:
            try:
                client_factory = current_app.config.get("DEEPSEEK_CLIENT_FACTORY")
                client = (
                    client_factory()
                    if callable(client_factory)
                    else DeepSeekClient.from_config(current_app.config)
                )
                answer = AgentRunner(client).run(
                    question,
                    trusted_context={"authenticated_user_id": g.user.id},
                )
            except MissingDeepSeekConfiguration:
                current_app.logger.info(
                    "agent_provider service=TripMate success=false category=not_configured"
                )
                error = "DeepSeek Assistant is not configured."
            except ProviderTimeout:
                current_app.logger.warning(
                    "agent_provider service=TripMate success=false category=timeout"
                )
                error = "The AI assistant timed out. Please try again later."
            except MaxToolRoundsExceeded:
                current_app.logger.warning(
                    "agent_provider service=TripMate success=false category=max_tool_rounds"
                )
                error = "The assistant could not complete the request safely. Please try a simpler question."
            except (AgentError, ValueError) as agent_error:
                category = getattr(agent_error, "category", type(agent_error).__name__)
                current_app.logger.warning(
                    "agent_provider service=TripMate success=false category=%s",
                    category,
                )
                error = "The AI assistant is temporarily unavailable. Please try again later."
    return render_template(
        "agent/travel_assistant.html",
        question=question,
        answer=answer,
        error=error,
    )
