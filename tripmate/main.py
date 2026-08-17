from datetime import UTC, date, datetime

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import JoinRequest, Trip
from .services import TRAVEL_STYLES, search_trips
from .utils import clean_text, login_required, validate_csrf


bp = Blueprint("main", __name__)


@bp.get("/")
def home():
    if g.user:
        return redirect(url_for("main.trips"))
    return render_template("index.html")


@bp.get("/trips")
@login_required
def trips():
    filters = {
        "destination": clean_text(request.args.get("q"))[:100],
        "style": clean_text(request.args.get("style")),
        "start_date": request.args.get("start_date", "").strip(),
        "end_date": request.args.get("end_date", "").strip(),
        "min_available_spots": request.args.get("min_available_spots", "").strip(),
    }
    page = request.args.get("page", 1, type=int) or 1
    try:
        result = search_trips(page=page, **filters)
    except ValueError:
        flash("筛选条件格式无效，请检查日期、旅行风格和剩余名额。", "error")
        result = search_trips(page=1)
    return render_template(
        "trips/list.html",
        result=result,
        filters=filters,
        styles=TRAVEL_STYLES,
    )


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
    return render_template("trips/form.html", form=form, styles=TRAVEL_STYLES, trip=None)


@bp.route("/trips/<int:trip_id>/edit", methods=("GET", "POST"))
@login_required
def edit_trip(trip_id):
    if request.method == "POST":
        validate_csrf()
    trip = db.get_or_404(Trip, trip_id)
    if trip.creator_id != g.user.id:
        abort(403)
    if trip.status == "CANCELLED":
        flash("已取消的旅行计划不能继续编辑。", "error")
        return redirect(url_for("main.trip_detail", trip_id=trip.id))

    form = _trip_form_values(trip)
    if request.method == "POST":
        error, parsed = _validate_trip_form(form)
        accepted_count = len(trip.accepted_requests)
        if not error and parsed["expected_companions"] < accepted_count:
            error = f"期望同行人数不能少于当前已接受的 {accepted_count} 人。"
        if error:
            flash(error, "error")
        else:
            for field, value in parsed.items():
                setattr(trip, field, value)
            if trip.status == "OPEN" and accepted_count >= trip.expected_companions:
                _close_trip(trip)
            db.session.commit()
            flash("旅行计划已更新。", "success")
            return redirect(url_for("main.trip_detail", trip_id=trip.id))

    return render_template("trips/form.html", form=form, styles=TRAVEL_STYLES, trip=trip)


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
    if trip.status == "CANCELLED":
        flash("已取消的旅行计划不能改为关闭状态。", "info")
        return redirect(url_for("main.trip_detail", trip_id=trip.id))
    was_closed = trip.status == "CLOSED"
    cancelled_count = _close_trip(trip)
    if was_closed and cancelled_count == 0:
        flash("该旅行计划已经关闭。", "info")
    else:
        db.session.commit()
        flash("旅行计划已关闭，不再接受新的同行申请。", "success")
    return redirect(url_for("main.trip_detail", trip_id=trip.id))


@bp.post("/trips/<int:trip_id>/cancel")
@login_required
def cancel_trip(trip_id):
    validate_csrf()
    trip = db.get_or_404(Trip, trip_id)
    if trip.creator_id != g.user.id:
        abort(403)
    if trip.status == "CANCELLED":
        flash("该旅行计划已经取消。", "info")
    else:
        trip.status = "CANCELLED"
        _cancel_pending_requests(trip)
        db.session.commit()
        flash("旅行计划已取消，待处理的同行申请已由系统结束。", "success")
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
            _close_trip(trip)
            db.session.commit()
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
            _close_trip(trip)
        flash(f"已接受 {item.applicant.username} 的同行申请。", "success")
    else:
        item.status = "REJECTED"
        item.handled_at = datetime.now(UTC)
        flash(f"已拒绝 {item.applicant.username} 的同行申请。", "info")

    db.session.commit()
    return redirect(url_for("main.manage_requests"))


@bp.post("/requests/<int:request_id>/withdraw")
@login_required
def withdraw_request(request_id):
    validate_csrf()
    item = db.get_or_404(JoinRequest, request_id)
    if item.applicant_id != g.user.id:
        abort(403)
    if item.status != "PENDING":
        flash("只有等待处理的同行申请可以撤回。", "info")
    else:
        item.status = "WITHDRAWN"
        item.handled_at = datetime.now(UTC)
        db.session.commit()
        flash("同行申请已撤回。", "success")
    return redirect(url_for("main.trip_detail", trip_id=item.trip_id))


def _close_trip(trip):
    """Close a trip and system-cancel only its still-pending requests."""
    trip.status = "CLOSED"
    return _cancel_pending_requests(trip)


def _cancel_pending_requests(trip):
    """System-cancel only pending requests for a no-longer-open trip."""
    result = db.session.execute(
        update(JoinRequest)
        .where(
            JoinRequest.trip_id == trip.id,
            JoinRequest.status == "PENDING",
        )
        .values(status="CANCELLED", handled_at=datetime.now(UTC))
    )
    return result.rowcount or 0


def _trip_form_values(trip=None):
    if request.method == "GET":
        if trip is not None:
            return {
                "destination": trip.destination,
                "start_date": trip.start_date.isoformat(),
                "end_date": trip.end_date.isoformat(),
                "style": trip.style,
                "description": trip.description,
                "expected_companions": str(trip.expected_companions),
            }
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
    if start_date < date.today():
        return "开始日期不能早于今天。", None

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
