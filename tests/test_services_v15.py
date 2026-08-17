from datetime import date, timedelta

from tripmate.extensions import db
from tripmate.models import JoinRequest, Trip, User
from tripmate.services import (
    TripSearchCriteria,
    calculate_trip_compatibility,
    get_public_trip_details,
    get_public_user_profile,
    search_trips,
)


def _add_user(username="owner"):
    user = User(username=username, email=f"{username}@example.com", bio=f"{username} bio")
    user.set_password("Pass1234")
    db.session.add(user)
    db.session.flush()
    return user


def _add_trip(
    owner,
    *,
    destination="日本 · 东京",
    style="摄影打卡",
    start_offset=30,
    duration=5,
    expected=3,
    status="OPEN",
):
    start = date.today() + timedelta(days=start_offset)
    trip = Trip(
        creator_id=owner.id,
        destination=destination,
        start_date=start,
        end_date=start + timedelta(days=duration),
        style=style,
        description="用于 V1.5 服务层测试的完整旅行简介。",
        expected_companions=expected,
        status=status,
    )
    db.session.add(trip)
    db.session.flush()
    return trip


def test_destination_filter_works(app):
    with app.app_context():
        owner = _add_user()
        _add_trip(owner, destination="日本 · 东京")
        _add_trip(owner, destination="中国 · 大理")
        db.session.commit()

        result = search_trips(destination="东京")

        assert [item["destination"] for item in result["items"]] == ["日本 · 东京"]


def test_style_filter_works(app):
    with app.app_context():
        owner = _add_user()
        _add_trip(owner, style="摄影打卡")
        _add_trip(owner, destination="韩国 · 首尔", style="美食体验")
        db.session.commit()

        result = search_trips(style="美食体验")

        assert [item["style"] for item in result["items"]] == ["美食体验"]


def test_date_overlap_filter_works(app):
    with app.app_context():
        owner = _add_user()
        matching = _add_trip(owner, destination="法国 · 巴黎", start_offset=20, duration=8)
        _add_trip(owner, destination="日本 · 东京", start_offset=60, duration=3)
        db.session.commit()

        result = search_trips(
            start_date=date.today() + timedelta(days=25),
            end_date=date.today() + timedelta(days=28),
        )

        assert [item["trip_id"] for item in result["items"]] == [matching.id]


def test_minimum_available_spots_filter_works(app):
    with app.app_context():
        owner = _add_user()
        roomy = _add_trip(owner, destination="中国 · 大理", expected=3)
        full = _add_trip(owner, destination="日本 · 东京", expected=1)
        applicant = _add_user("guest")
        db.session.add(
            JoinRequest(trip_id=full.id, applicant_id=applicant.id, status="ACCEPTED")
        )
        db.session.commit()

        result = search_trips(min_available_spots=2)

        assert [item["trip_id"] for item in result["items"]] == [roomy.id]


def test_combined_trip_filters_work(app):
    with app.app_context():
        owner = _add_user()
        match = _add_trip(owner, destination="日本 · 东京", style="摄影打卡", expected=3)
        _add_trip(owner, destination="日本 · 京都", style="文化历史", expected=3)
        _add_trip(owner, destination="中国 · 上海", style="摄影打卡", expected=3)
        db.session.commit()

        result = search_trips(
            destination="日本",
            style="摄影打卡",
            start_date=date.today() + timedelta(days=28),
            end_date=date.today() + timedelta(days=40),
            min_available_spots=2,
        )

        assert [item["trip_id"] for item in result["items"]] == [match.id]
        assert result["items"][0]["compatibility"]["score"] == 100


def test_closed_and_cancelled_trips_are_excluded(app):
    with app.app_context():
        owner = _add_user()
        open_trip = _add_trip(owner, destination="开放旅程")
        _add_trip(owner, destination="关闭旅程", status="CLOSED")
        _add_trip(owner, destination="取消旅程", status="CANCELLED")
        db.session.commit()

        result = search_trips()

        assert [item["trip_id"] for item in result["items"]] == [open_trip.id]


def test_trip_search_pagination_still_works(app):
    with app.app_context():
        owner = _add_user()
        for index in range(5):
            _add_trip(owner, destination=f"目的地 {index}", start_offset=20 + index)
        db.session.commit()

        first = search_trips(page=1, per_page=2)
        second = search_trips(page=2, per_page=2)

        assert len(first["items"]) == 2
        assert len(second["items"]) == 2
        assert {item["trip_id"] for item in first["items"]}.isdisjoint(
            {item["trip_id"] for item in second["items"]}
        )
        assert first["pagination"]["pages"] == 3


def test_each_trip_compatibility_component_contributes(app):
    with app.app_context():
        owner = _add_user()
        trip = _add_trip(owner)
        db.session.commit()
        criteria = TripSearchCriteria(
            destination="东京",
            style="摄影打卡",
            start_date=trip.start_date,
            end_date=trip.end_date,
            min_available_spots=2,
        )

        score = calculate_trip_compatibility(trip.id, criteria)

        assert score["destination_score"] == 30
        assert score["date_score"] == 30
        assert score["style_score"] == 20
        assert score["availability_score"] == 20
        assert score["score"] == 100


def test_missing_criteria_do_not_reduce_normalized_score(app):
    with app.app_context():
        owner = _add_user()
        trip = _add_trip(owner)
        db.session.commit()

        score = calculate_trip_compatibility(
            trip.id, TripSearchCriteria(destination="东京")
        )

        assert score["score"] == 100
        assert score["earned_score"] == score["possible_score"] == 30


def test_score_is_normalized_and_never_exceeds_one_hundred(app):
    with app.app_context():
        owner = _add_user()
        trip = _add_trip(owner)
        db.session.commit()

        partial = calculate_trip_compatibility(
            trip.id,
            TripSearchCriteria(
                destination="不匹配",
                style="摄影打卡",
                min_available_spots=20,
            ),
        )

        assert partial["score"] == 29
        assert 0 <= partial["score"] <= 100


def test_no_criteria_does_not_invent_compatibility(app):
    with app.app_context():
        owner = _add_user()
        trip = _add_trip(owner)
        db.session.commit()

        score = calculate_trip_compatibility(trip.id, TripSearchCriteria())
        search_result = search_trips()

        assert score["score"] == 0
        assert score["scored"] is False
        assert score["reasons"] == []
        assert search_result["items"][0]["compatibility"] is None


def test_compatibility_reasons_only_describe_actual_matches(app):
    with app.app_context():
        owner = _add_user()
        trip = _add_trip(owner)
        db.session.commit()

        score = calculate_trip_compatibility(
            trip.id,
            TripSearchCriteria(destination="东京", style="美食体验"),
        )

        assert score["reasons"] == ["目的地与 日本 · 东京 匹配"]


def test_higher_compatibility_ranks_first_for_preference_search(app):
    with app.app_context():
        owner = _add_user()
        _add_trip(owner, destination="中国 · 大理", style="自然户外")
        best = _add_trip(owner, destination="日本 · 东京", style="摄影打卡")
        db.session.commit()

        result = search_trips(
            destination="东京",
            style="摄影打卡",
            strict_filters=False,
        )

        assert result["items"][0]["trip_id"] == best.id
        assert result["items"][0]["compatibility"]["score"] == 100


def test_same_compatibility_score_has_stable_id_descending_order(app):
    with app.app_context():
        owner = _add_user()
        first = _add_trip(owner, destination="日本 · 东京")
        second = _add_trip(owner, destination="日本 · 东京")
        db.session.commit()

        result = search_trips(destination="东京")

        assert [item["trip_id"] for item in result["items"]] == [second.id, first.id]


def test_public_trip_service_returns_only_expected_public_fields(app):
    with app.app_context():
        owner = _add_user()
        trip = _add_trip(owner)
        db.session.commit()

        result = get_public_trip_details(trip.id)

        assert {
            "trip_id",
            "destination",
            "start_date",
            "end_date",
            "style",
            "description",
            "expected_companions",
            "accepted_count",
            "remaining_spots",
            "status",
            "creator",
        } == set(result)
        assert set(result["creator"]) == {"user_id", "username", "bio"}
        assert "email" not in result["creator"]
        assert "password_hash" not in result["creator"]


def test_public_user_profile_excludes_private_credentials(app):
    with app.app_context():
        owner = _add_user()
        db.session.commit()

        result = get_public_user_profile(owner.id)

        assert result == {"user_id": owner.id, "username": "owner", "bio": "owner bio"}
        assert "email" not in result
        assert "password_hash" not in result


def test_public_trip_service_represents_closed_and_cancelled_statuses(app):
    with app.app_context():
        owner = _add_user()
        closed = _add_trip(owner, destination="关闭", status="CLOSED")
        cancelled = _add_trip(owner, destination="取消", status="CANCELLED")
        db.session.commit()

        assert get_public_trip_details(closed.id)["status"] == "CLOSED"
        assert get_public_trip_details(cancelled.id)["status"] == "CANCELLED"
