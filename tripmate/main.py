from datetime import UTC, date, datetime

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import JoinRequest, Trip
from .utils import clean_text, login_required, validate_csrf


bp = Blueprint("main", __name__)
TRAVEL_STYLES = ("城市探索", "自然户外", "美食体验", "摄影打卡", "文化历史", "轻松度假", "其他")


@bp.get("/")
def home():
    if g.user:
        return redirect(url_for("main.trips"))
    return render_template("index.html")


@bp.get("/trips")
@login_required
def trips():
    query = clean_text(request.args.get("q"))[:100]
    page = request.args.get("page", 1, type=int)
    statement = select(Trip).where(Trip.status == "OPEN")
    if query:
        statement = statement.where(Trip.destination.ilike(f"%{query}%"))
    statement = statement.order_by(Trip.start_date.asc(), Trip.created_at.desc())
    pagination = db.paginate(statement, page=max(page, 1), per_page=9, error_out=False)
    return render_template("trips/list.html", pagination=pagination, query=query)


@bp.route("/trips/new", methods=("GET", "POST"))
@login_required
def create_trip():
    form = _trip_form_values()
    if request.method == "POST":
        validate_csrf()
        error, parsed = _validate_trip_form(form)
        if error:
            flash(error, "error")
        else:
            trip = Trip(creator_id=g.user.id, **parsed)
            db.session.add(trip)
            db.session.commit()
            flash("旅行计划已发布，其他旅行者现在可以申请同行。", "success")
            return redirect(url_for("main.trip_detail", trip_id=trip.id))
    return render_template("trips/form.html", form=form, styles=TRAVEL_STYLES)


@bp.get("/trips/<int:trip_id>")
@login_required
def trip_detail(trip_id):
    trip = db.get_or_404(Trip, trip_id)
    own_request = db.session.scalar(
        select(JoinRequest).where(
            JoinRequest.trip_id == trip.id, JoinRequest.applicant_id == g.user.id
        )
    )
    return render_template("trips/detail.html", trip=trip, own_request=own_request)


@bp.post("/trips/<int:trip_id>/apply")
@login_required
def apply_to_trip(trip_id):
    validate_csrf()
    trip = db.get_or_404(Trip, trip_id)
    message = clean_text(request.form.get("message"))

    if trip.creator_id == g.user.id:
        flash("不能申请加入自己创建的旅行计划。", "error")
    elif trip.status != "OPEN" or trip.remaining_spots < 1:
        flash("该旅行计划已关闭或名额已满，暂时不能申请。", "error")
    elif len(message) > 500:
        flash("申请留言不能超过 500 个字符。", "error")
    else:
        existing = db.session.scalar(
            select(JoinRequest).where(
                JoinRequest.trip_id == trip.id, JoinRequest.applicant_id == g.user.id
            )
        )
        if existing:
            flash("你已经申请过该旅行计划，请在“我的旅行”查看状态。", "info")
        else:
            db.session.add(JoinRequest(trip_id=trip.id, applicant_id=g.user.id, message=message))
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("你已经申请过该旅行计划。", "info")
            else:
                flash("同行申请已发送，等待计划创建者处理。", "success")
    return redirect(url_for("main.trip_detail", trip_id=trip.id))


@bp.post("/trips/<int:trip_id>/close")
@login_required
def close_trip(trip_id):
    validate_csrf()
    trip = db.get_or_404(Trip, trip_id)
    if trip.creator_id != g.user.id:
        abort(403)
    if trip.status == "CLOSED":
        flash("该旅行计划已经关闭。", "info")
    else:
        trip.status = "CLOSED"
        db.session.commit()
        flash("旅行计划已关闭，不再接受新的同行申请。", "success")
    return redirect(url_for("main.trip_detail", trip_id=trip.id))


@bp.get("/me/trips")
@login_required
def my_trips():
    created = db.session.scalars(
        select(Trip).where(Trip.creator_id == g.user.id).order_by(Trip.created_at.desc())
    ).all()
    applications = db.session.scalars(
        select(JoinRequest)
        .where(JoinRequest.applicant_id == g.user.id)
        .order_by(JoinRequest.created_at.desc())
    ).all()
    return render_template("me/trips.html", created=created, applications=applications)


@bp.get("/requests")
@login_required
def manage_requests():
    items = db.session.scalars(
        select(JoinRequest)
        .join(Trip)
        .where(Trip.creator_id == g.user.id)
        .order_by(
            (JoinRequest.status == "PENDING").desc(),
            JoinRequest.created_at.desc(),
        )
    ).all()
    return render_template("requests/manage.html", items=items)


@bp.post("/requests/<int:request_id>/<action>")
@login_required
def handle_request(request_id, action):
    validate_csrf()
    if action not in {"accept", "reject"}:
        abort(404)

    item = db.get_or_404(JoinRequest, request_id)
    trip = item.trip
    if trip.creator_id != g.user.id:
        abort(403)
    if item.status != "PENDING":
        flash("该申请已经处理，不能重复操作。", "info")
        return redirect(url_for("main.manage_requests"))

    if action == "accept":
        if trip.status != "OPEN" or trip.remaining_spots < 1:
            flash("计划已关闭或名额已满，无法接受此申请。", "error")
            return redirect(url_for("main.manage_requests"))
        item.status = "ACCEPTED"
        item.handled_at = datetime.now(UTC)
        db.session.flush()
        accepted_count = db.session.scalar(
            select(func.count(JoinRequest.id)).where(
                JoinRequest.trip_id == trip.id, JoinRequest.status == "ACCEPTED"
            )
        )
        if accepted_count >= trip.expected_companions:
            trip.status = "CLOSED"
        flash(f"已接受 {item.applicant.username} 的同行申请。", "success")
    else:
        item.status = "REJECTED"
        item.handled_at = datetime.now(UTC)
        flash(f"已拒绝 {item.applicant.username} 的同行申请。", "info")

    db.session.commit()
    return redirect(url_for("main.manage_requests"))


def _trip_form_values():
    if request.method == "GET":
        return {
            "destination": "",
            "start_date": "",
            "end_date": "",
            "style": TRAVEL_STYLES[0],
            "description": "",
            "expected_companions": "1",
        }
    return {
        "destination": clean_text(request.form.get("destination")),
        "start_date": request.form.get("start_date", "").strip(),
        "end_date": request.form.get("end_date", "").strip(),
        "style": clean_text(request.form.get("style")),
        "description": clean_text(request.form.get("description")),
        "expected_companions": request.form.get("expected_companions", "").strip(),
    }


def _validate_trip_form(form):
    if not 2 <= len(form["destination"]) <= 100:
        return "目的地长度应为 2–100 个字符。", None
    if form["style"] not in TRAVEL_STYLES:
        return "请选择有效的旅行风格。", None
    if not 10 <= len(form["description"]) <= 1000:
        return "旅行简介长度应为 10–1000 个字符。", None

    try:
        start_date = date.fromisoformat(form["start_date"])
        end_date = date.fromisoformat(form["end_date"])
    except ValueError:
        return "请选择有效的开始和结束日期。", None
    if end_date < start_date:
        return "结束日期不能早于开始日期。", None

    try:
        expected = int(form["expected_companions"])
    except ValueError:
        return "期望同行人数必须是整数。", None
    if not 1 <= expected <= 20:
        return "期望同行人数应为 1–20 人。", None

    return None, {
        "destination": form["destination"],
        "start_date": start_date,
        "end_date": end_date,
        "style": form["style"],
        "description": form["description"],
        "expected_companions": expected,
    }
