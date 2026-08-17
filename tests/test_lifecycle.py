from datetime import date, timedelta

import pytest
from sqlalchemy import select

from tripmate.extensions import db
from tripmate.models import JoinRequest, Trip, User

from .conftest import create_trip, post_with_csrf


def _edit_data(**overrides):
    start = date.today() + timedelta(days=40)
    data = {
        "destination": "韩国 · 首尔",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=4)).isoformat(),
        "style": "城市探索",
        "description": "更新后的旅行计划包含展览、美食和自由活动时间。",
        "expected_companions": "3",
    }
    data.update(overrides)
    return data


def _owner_trip(app, client, auth, expected="3"):
    auth.register(username="owner", email="owner@example.com")
    create_trip(client, expected_companions=expected)
    with app.app_context():
        return db.session.scalar(select(Trip.id))


def _pending_application(app, client, auth):
    trip_id = _owner_trip(app, client, auth)
    auth.logout()
    auth.register(username="applicant", email="applicant@example.com")
    post_with_csrf(client, f"/trips/{trip_id}/apply", {"message": "希望一起出发。"})
    with app.app_context():
        return trip_id, db.session.scalar(select(JoinRequest.id))


def test_creator_can_edit_trip_and_valid_edit_persists(app, client, auth):
    trip_id = _owner_trip(app, client, auth)
    assert client.get(f"/trips/{trip_id}/edit").status_code == 200

    response = post_with_csrf(client, f"/trips/{trip_id}/edit", _edit_data())
    assert response.status_code == 302
    with app.app_context():
        trip = db.session.get(Trip, trip_id)
        assert trip.destination == "韩国 · 首尔"
        assert trip.expected_companions == 3
        assert trip.status == "OPEN"


def test_non_creator_cannot_edit_trip(app, client, auth):
    trip_id = _owner_trip(app, client, auth)
    auth.logout()
    auth.register(username="outsider", email="outsider@example.com")

    assert client.get(f"/trips/{trip_id}/edit").status_code == 403
    assert post_with_csrf(client, f"/trips/{trip_id}/edit", _edit_data()).status_code == 403


def test_cancelled_trip_cannot_be_edited(app, client, auth):
    trip_id = _owner_trip(app, client, auth)
    post_with_csrf(client, f"/trips/{trip_id}/cancel")

    response = client.get(f"/trips/{trip_id}/edit")
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert response.status_code == 302
    assert "已取消的旅行计划不能继续编辑" in page


def test_past_date_is_rejected_during_edit(app, client, auth):
    trip_id = _owner_trip(app, client, auth)
    past = date.today() - timedelta(days=1)
    response = post_with_csrf(
        client,
        f"/trips/{trip_id}/edit",
        _edit_data(start_date=past.isoformat(), end_date=date.today().isoformat()),
    )
    assert response.status_code == 200
    assert "开始日期不能早于今天" in response.get_data(as_text=True)


def test_end_date_before_start_date_is_rejected_during_edit(app, client, auth):
    trip_id = _owner_trip(app, client, auth)
    start = date.today() + timedelta(days=10)
    response = post_with_csrf(
        client,
        f"/trips/{trip_id}/edit",
        _edit_data(
            start_date=start.isoformat(),
            end_date=(start - timedelta(days=1)).isoformat(),
        ),
    )
    assert response.status_code == 200
    assert "结束日期不能早于开始日期" in response.get_data(as_text=True)


def test_expected_companions_cannot_be_below_accepted_count(app, client, auth):
    trip_id = _owner_trip(app, client, auth, expected="3")
    with app.app_context():
        guests = []
        for index in range(2):
            user = User(
                username=f"accepted{index}",
                email=f"accepted{index}@example.com",
                bio="",
            )
            user.set_password("Pass1234")
            guests.append(user)
        db.session.add_all(guests)
        db.session.flush()
        db.session.add_all(
            JoinRequest(trip_id=trip_id, applicant_id=user.id, status="ACCEPTED")
            for user in guests
        )
        db.session.commit()

    response = post_with_csrf(
        client,
        f"/trips/{trip_id}/edit",
        _edit_data(expected_companions="1"),
    )
    assert "不能少于当前已接受的 2 人" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Trip, trip_id).expected_companions == 3


def test_closed_trip_can_edit_fields_without_reopening(app, client, auth):
    trip_id = _owner_trip(app, client, auth)
    post_with_csrf(client, f"/trips/{trip_id}/close")
    post_with_csrf(client, f"/trips/{trip_id}/edit", _edit_data(destination="中国 · 青岛"))

    with app.app_context():
        trip = db.session.get(Trip, trip_id)
        assert trip.destination == "中国 · 青岛"
        assert trip.status == "CLOSED"


def test_creator_cancel_trip_updates_only_pending_requests(app, client, auth):
    trip_id = _owner_trip(app, client, auth, expected="4")
    with app.app_context():
        states = ("PENDING", "ACCEPTED", "REJECTED", "CANCELLED", "WITHDRAWN")
        for index, status in enumerate(states):
            user = User(username=f"guest{index}", email=f"guest{index}@example.com", bio="")
            user.set_password("Pass1234")
            db.session.add(user)
            db.session.flush()
            db.session.add(JoinRequest(trip_id=trip_id, applicant_id=user.id, status=status))
        db.session.commit()

    response = post_with_csrf(client, f"/trips/{trip_id}/cancel")
    assert response.status_code == 302
    with app.app_context():
        trip = db.session.get(Trip, trip_id)
        statuses = db.session.scalars(
            select(JoinRequest.status).where(JoinRequest.trip_id == trip_id).order_by(JoinRequest.id)
        ).all()
        assert trip.status == "CANCELLED"
        assert statuses == ["CANCELLED", "ACCEPTED", "REJECTED", "CANCELLED", "WITHDRAWN"]


def test_non_creator_cannot_cancel_trip(app, client, auth):
    trip_id = _owner_trip(app, client, auth)
    auth.logout()
    auth.register(username="outsider", email="outsider@example.com")

    assert post_with_csrf(client, f"/trips/{trip_id}/cancel").status_code == 403
    with app.app_context():
        assert db.session.get(Trip, trip_id).status == "OPEN"


def test_cancelled_trip_rejects_new_application(app, client, auth):
    trip_id = _owner_trip(app, client, auth)
    post_with_csrf(client, f"/trips/{trip_id}/cancel")
    auth.logout()
    auth.register(username="guest", email="guest@example.com")

    response = post_with_csrf(client, f"/trips/{trip_id}/apply")
    assert "已关闭或名额已满" in client.get(response.headers["Location"]).get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(db.func.count(JoinRequest.id))) == 0


def test_applicant_can_withdraw_pending_request(app, client, auth):
    trip_id, request_id = _pending_application(app, client, auth)

    response = post_with_csrf(client, f"/requests/{request_id}/withdraw")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/trips/{trip_id}")
    with app.app_context():
        item = db.session.get(JoinRequest, request_id)
        assert item.status == "WITHDRAWN"
        assert item.handled_at is not None


def test_non_applicant_cannot_withdraw_request(app, client, auth):
    _, request_id = _pending_application(app, client, auth)
    auth.logout()
    auth.register(username="outsider", email="outsider@example.com")

    assert post_with_csrf(client, f"/requests/{request_id}/withdraw").status_code == 403
    with app.app_context():
        assert db.session.get(JoinRequest, request_id).status == "PENDING"


@pytest.mark.parametrize("status", ["ACCEPTED", "REJECTED", "CANCELLED", "WITHDRAWN"])
def test_only_pending_request_can_be_withdrawn(app, client, auth, status):
    _, request_id = _pending_application(app, client, auth)
    with app.app_context():
        item = db.session.get(JoinRequest, request_id)
        item.status = status
        db.session.commit()

    response = post_with_csrf(client, f"/requests/{request_id}/withdraw")
    assert "只有等待处理的同行申请可以撤回" in client.get(
        response.headers["Location"]
    ).get_data(as_text=True)
    with app.app_context():
        assert db.session.get(JoinRequest, request_id).status == status


def test_withdrawn_request_cannot_be_accepted_or_rejected(app, client, auth):
    _, request_id = _pending_application(app, client, auth)
    post_with_csrf(client, f"/requests/{request_id}/withdraw")
    auth.logout()
    auth.login(identity="owner")

    for action in ("accept", "reject"):
        response = post_with_csrf(client, f"/requests/{request_id}/{action}")
        assert "已经处理" in client.get(response.headers["Location"]).get_data(as_text=True)
    with app.app_context():
        assert db.session.get(JoinRequest, request_id).status == "WITHDRAWN"


def test_cancel_and_withdraw_routes_require_post(app, client, auth):
    trip_id, request_id = _pending_application(app, client, auth)
    assert client.get(f"/trips/{trip_id}/cancel").status_code == 405
    assert client.get(f"/requests/{request_id}/withdraw").status_code == 405
