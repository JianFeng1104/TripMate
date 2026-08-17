from datetime import date, timedelta

from sqlalchemy import select

from tripmate.extensions import db
from tripmate.models import JoinRequest, Trip, User

from .conftest import create_trip, post_with_csrf


def test_complete_two_user_join_flow(app, client, auth):
    auth.register(username="owner", email="owner@example.com")
    response = create_trip(client, expected_companions="1")
    assert response.status_code == 302

    with app.app_context():
        trip = db.session.scalar(select(Trip))
        trip_id = trip.id

    auth.logout()
    auth.register(username="guest", email="guest@example.com")
    response = post_with_csrf(
        client, f"/trips/{trip_id}/apply", {"message": "我也喜欢摄影，日期完全合适。"}
    )
    assert "同行申请已发送" in client.get(response.headers["Location"]).get_data(as_text=True)

    with app.app_context():
        join_request = db.session.scalar(select(JoinRequest))
        request_id = join_request.id
        assert join_request.status == "PENDING"

    auth.logout()
    auth.login(identity="owner")
    inbox = client.get("/requests").get_data(as_text=True)
    assert "guest" in inbox and "等待处理" in inbox
    response = post_with_csrf(client, f"/requests/{request_id}/accept")
    assert response.status_code == 302

    with app.app_context():
        join_request = db.session.get(JoinRequest, request_id)
        trip = db.session.get(Trip, trip_id)
        assert join_request.status == "ACCEPTED"
        assert trip.status == "CLOSED"

    auth.logout()
    auth.login(identity="guest")
    my_page = client.get("/me/trips").get_data(as_text=True)
    detail = client.get(f"/trips/{trip_id}").get_data(as_text=True)
    assert "已接受" in my_page
    assert "@guest" in detail


def test_owner_cannot_apply_and_duplicate_is_prevented(app, client, auth):
    auth.register(username="owner", email="owner@example.com")
    create_trip(client)
    with app.app_context():
        trip_id = db.session.scalar(select(Trip.id))

    response = post_with_csrf(client, f"/trips/{trip_id}/apply")
    assert "不能申请加入自己" in client.get(response.headers["Location"]).get_data(as_text=True)

    auth.logout()
    auth.register(username="guest", email="guest@example.com")
    post_with_csrf(client, f"/trips/{trip_id}/apply")
    response = post_with_csrf(client, f"/trips/{trip_id}/apply")
    assert "已经申请过" in client.get(response.headers["Location"]).get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(db.func.count(JoinRequest.id))) == 1


def test_only_owner_can_handle_request(app, client, auth):
    auth.register(username="owner", email="owner@example.com")
    create_trip(client)
    auth.logout()
    auth.register(username="guest", email="guest@example.com")
    with app.app_context():
        trip_id = db.session.scalar(select(Trip.id))
    post_with_csrf(client, f"/trips/{trip_id}/apply")
    with app.app_context():
        request_id = db.session.scalar(select(JoinRequest.id))

    auth.logout()
    auth.register(username="outsider", email="outsider@example.com")
    response = post_with_csrf(client, f"/requests/{request_id}/accept")
    assert response.status_code == 403
    with app.app_context():
        assert db.session.get(JoinRequest, request_id).status == "PENDING"


def test_trip_date_and_field_validation(app, client, auth):
    auth.register()
    start_date = date.today() + timedelta(days=20)
    response = create_trip(
        client,
        start_date=start_date.isoformat(),
        end_date=(start_date - timedelta(days=1)).isoformat(),
    )
    assert response.status_code == 200
    assert "结束日期不能早于开始日期" in response.get_data(as_text=True)

    response = create_trip(client, description="太短")
    assert "旅行简介长度应为" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(db.func.count(Trip.id))) == 0


def test_past_start_date_is_rejected(app, client, auth):
    auth.register()
    response = create_trip(
        client,
        start_date=(date.today() - timedelta(days=1)).isoformat(),
        end_date=date.today().isoformat(),
    )
    assert response.status_code == 200
    assert "开始日期不能早于今天" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(db.func.count(Trip.id))) == 0


def test_today_start_date_is_allowed(app, client, auth):
    auth.register()
    response = create_trip(
        client,
        start_date=date.today().isoformat(),
        end_date=date.today().isoformat(),
    )
    assert response.status_code == 302
    with app.app_context():
        assert db.session.scalar(select(db.func.count(Trip.id))) == 1


def test_future_start_date_is_allowed(app, client, auth):
    auth.register()
    start_date = date.today() + timedelta(days=60)
    response = create_trip(
        client,
        start_date=start_date.isoformat(),
        end_date=(start_date + timedelta(days=3)).isoformat(),
    )
    assert response.status_code == 302
    with app.app_context():
        assert db.session.scalar(select(db.func.count(Trip.id))) == 1


def test_end_date_before_start_date_is_still_rejected(app, client, auth):
    auth.register()
    start_date = date.today() + timedelta(days=60)
    response = create_trip(
        client,
        start_date=start_date.isoformat(),
        end_date=(start_date - timedelta(days=1)).isoformat(),
    )
    assert response.status_code == 200
    assert "结束日期不能早于开始日期" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(db.func.count(Trip.id))) == 0


def test_closed_trip_blocks_new_application(app, client, auth):
    auth.register(username="owner", email="owner@example.com")
    create_trip(client)
    with app.app_context():
        trip_id = db.session.scalar(select(Trip.id))
    post_with_csrf(client, f"/trips/{trip_id}/close")

    auth.logout()
    auth.register(username="guest", email="guest@example.com")
    response = post_with_csrf(client, f"/trips/{trip_id}/apply")
    assert "已关闭或名额已满" in client.get(response.headers["Location"]).get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(db.func.count(JoinRequest.id))) == 0


def test_destination_filter_only_returns_matches(client, auth):
    auth.register()
    create_trip(client, destination="日本 · 东京")
    create_trip(client, destination="中国 · 大理")
    page = client.get("/trips?q=东京").get_data(as_text=True)
    assert "日本 · 东京" in page
    assert "中国 · 大理" not in page


def test_owner_can_reject_once(app, client, auth):
    auth.register(username="owner", email="owner@example.com")
    create_trip(client)
    auth.logout()
    auth.register(username="guest", email="guest@example.com")
    with app.app_context():
        trip_id = db.session.scalar(select(Trip.id))
    post_with_csrf(client, f"/trips/{trip_id}/apply")
    with app.app_context():
        request_id = db.session.scalar(select(JoinRequest.id))
    auth.logout()
    auth.login(identity="owner")
    post_with_csrf(client, f"/requests/{request_id}/reject")
    response = post_with_csrf(client, f"/requests/{request_id}/accept")
    assert "已经处理" in client.get(response.headers["Location"]).get_data(as_text=True)
    with app.app_context():
        assert db.session.get(JoinRequest, request_id).status == "REJECTED"


def test_manual_close_cancels_only_pending_requests(app, client, auth):
    auth.register(username="owner", email="owner@example.com")
    create_trip(client, expected_companions="3")
    with app.app_context():
        trip = db.session.scalar(select(Trip))
        users = []
        for username in ("accepted", "rejected", "pending_a", "pending_b"):
            user = User(username=username, email=f"{username}@example.com", bio="")
            user.set_password("Pass1234")
            users.append(user)
        db.session.add_all(users)
        db.session.flush()
        db.session.add_all(
            [
                JoinRequest(trip_id=trip.id, applicant_id=users[0].id, status="ACCEPTED"),
                JoinRequest(trip_id=trip.id, applicant_id=users[1].id, status="REJECTED"),
                JoinRequest(trip_id=trip.id, applicant_id=users[2].id, status="PENDING"),
                JoinRequest(trip_id=trip.id, applicant_id=users[3].id, status="PENDING"),
            ]
        )
        db.session.commit()
        trip_id = trip.id

    response = post_with_csrf(client, f"/trips/{trip_id}/close")
    assert response.status_code == 302
    assert "已取消" in client.get("/requests").get_data(as_text=True)
    with app.app_context():
        items = db.session.scalars(select(JoinRequest).order_by(JoinRequest.id)).all()
        assert [item.status for item in items] == [
            "ACCEPTED",
            "REJECTED",
            "CANCELLED",
            "CANCELLED",
        ]
        assert all(item.handled_at is not None for item in items[2:])
        assert db.session.get(Trip, trip_id).status == "CLOSED"


def test_accepting_last_spot_cancels_other_pending_requests(app, client, auth):
    auth.register(username="owner", email="owner@example.com")
    create_trip(client, expected_companions="1")
    with app.app_context():
        trip = db.session.scalar(select(Trip))
        guests = []
        for username in ("guest_a", "guest_b"):
            user = User(username=username, email=f"{username}@example.com", bio="")
            user.set_password("Pass1234")
            guests.append(user)
        db.session.add_all(guests)
        db.session.flush()
        requests = [
            JoinRequest(trip_id=trip.id, applicant_id=user.id, status="PENDING")
            for user in guests
        ]
        db.session.add_all(requests)
        db.session.commit()
        trip_id = trip.id
        accepted_request_id = requests[0].id

    response = post_with_csrf(client, f"/requests/{accepted_request_id}/accept")
    assert response.status_code == 302
    assert "已取消" in client.get("/requests").get_data(as_text=True)
    with app.app_context():
        trip = db.session.get(Trip, trip_id)
        items = db.session.scalars(select(JoinRequest).order_by(JoinRequest.id)).all()
        assert trip.status == "CLOSED"
        assert [item.status for item in items] == ["ACCEPTED", "CANCELLED"]
        assert items[1].handled_at is not None

    auth.logout()
    auth.register(username="guest_c", email="guest_c@example.com")
    response = post_with_csrf(client, f"/trips/{trip_id}/apply")
    assert "已关闭或名额已满" in client.get(response.headers["Location"]).get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(db.func.count(JoinRequest.id))) == 2
        assert db.session.scalar(
            select(db.func.count(JoinRequest.id)).where(JoinRequest.status == "PENDING")
        ) == 0


def test_seed_demo_command_is_repeatable(app, runner):
    first = runner.invoke(args=["seed-demo"])
    assert first.exit_code == 0
    assert "已创建 3 个演示账号" in first.output
    second = runner.invoke(args=["seed-demo"])
    assert second.exit_code == 0
    assert "已有用户" in second.output
    with app.app_context():
        assert db.session.scalar(select(db.func.count(User.id))) == 3
        assert db.session.scalar(select(db.func.count(Trip.id))) == 4
        assert db.session.scalar(select(db.func.count(JoinRequest.id))) == 6
