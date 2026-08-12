import re

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import or_, select

from .extensions import db
from .models import User
from .utils import clean_text, safe_next_url, validate_csrf


bp = Blueprint("auth", __name__, url_prefix="/auth")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = db.session.get(User, user_id) if user_id else None


@bp.route("/register", methods=("GET", "POST"))
def register():
    if g.user:
        return redirect(url_for("main.trips"))

    if request.method == "POST":
        validate_csrf()
        username = clean_text(request.form.get("username"))
        email = clean_text(request.form.get("email")).lower()
        password = request.form.get("password", "")
        bio = clean_text(request.form.get("bio"))
        error = _registration_error(username, email, password, bio)

        existing = db.session.scalar(
            select(User).where(or_(User.username == username, User.email == email))
        )
        if not error and existing:
            error = "用户名或邮箱已被使用，请更换后重试。"

        if error:
            flash(error, "error")
        else:
            user = User(username=username, email=email, bio=bio)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            session.clear()
            session["user_id"] = user.id
            flash("账号创建成功，欢迎加入 TripMate！", "success")
            return redirect(url_for("main.trips"))

    return render_template("auth/register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("main.trips"))

    if request.method == "POST":
        validate_csrf()
        identity = clean_text(request.form.get("identity"))
        password = request.form.get("password", "")
        user = db.session.scalar(
            select(User).where(or_(User.username == identity, User.email == identity.lower()))
        )

        if user is None or not user.check_password(password):
            flash("用户名、邮箱或密码不正确。", "error")
        else:
            session.clear()
            session["user_id"] = user.id
            flash(f"欢迎回来，{user.username}！", "success")
            target = safe_next_url(request.args.get("next"))
            return redirect(target or url_for("main.trips"))

    return render_template("auth/login.html")


@bp.post("/logout")
def logout():
    validate_csrf()
    session.clear()
    flash("你已安全退出登录。", "info")
    return redirect(url_for("main.home"))


def _registration_error(username, email, password, bio):
    if not 3 <= len(username) <= 30:
        return "用户名长度应为 3–30 个字符。"
    if not re.fullmatch(r"[\w\u4e00-\u9fff.-]+", username):
        return "用户名只能包含中英文、数字、点、短横线和下划线。"
    if len(email) > 120 or not EMAIL_PATTERN.fullmatch(email):
        return "请输入有效的邮箱地址。"
    if len(password) < 8 or not any(char.isalpha() for char in password) or not any(
        char.isdigit() for char in password
    ):
        return "密码至少 8 位，并同时包含字母和数字。"
    if len(bio) > 500:
        return "个人简介不能超过 500 个字符。"
    return None

