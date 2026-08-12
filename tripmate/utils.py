import hmac
import secrets
from functools import wraps
from urllib.parse import urlsplit

from flask import abort, g, redirect, request, session, url_for


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def validate_csrf():
    expected = session.get("_csrf_token", "")
    supplied = request.form.get("_csrf_token", "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        abort(400, description="表单已过期或来源无效，请返回上一页后重试。")


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.full_path))
        return view(**kwargs)

    return wrapped_view


def safe_next_url(value):
    if not value:
        return None
    target = urlsplit(value)
    if target.scheme or target.netloc or not target.path.startswith("/"):
        return None
    return value


def clean_text(value):
    return " ".join((value or "").split())

