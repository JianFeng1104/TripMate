from datetime import UTC, date, datetime, timedelta

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import select

from .extensions import db
from .models import JoinRequest, Trip, User


@click.command("seed-demo")
@with_appcontext
def seed_demo():
    """Add a DEV/DEMO-only, repeatable portfolio dataset."""
    if current_app.config["APP_ENV"] == "production":
        raise click.ClickException("seed-demo is disabled in production.")
    if db.session.scalar(select(User.id).limit(1)):
        click.echo("数据库中已有用户；为避免覆盖，未写入演示数据。")
        return

    users = [
        User(username="lin", email="lin@example.test", bio="喜欢城市漫步与胶片摄影。"),
        User(username="maya", email="maya@example.test", bio="独立旅行者，美食与博物馆爱好者。"),
        User(username="chen", email="chen@example.test", bio="周末徒步，偶尔去远方。"),
    ]
    for user in users:
        user.set_password("Demo123!")
        db.session.add(user)
    db.session.flush()

    today = date.today()
    trips = [
        Trip(
            creator_id=users[0].id,
            destination="日本 · 东京",
            start_date=today + timedelta(days=30),
            end_date=today + timedelta(days=35),
            style="城市探索",
            description="计划慢节奏逛街、看展和拍照，希望找到尊重彼此安排的同行者。",
            expected_companions=2,
        ),
        Trip(
            creator_id=users[1].id,
            destination="中国 · 云南大理",
            start_date=today + timedelta(days=45),
            end_date=today + timedelta(days=51),
            style="自然户外",
            description="环洱海、走古城，也留一些自由活动时间；期待作息相近的旅伴。",
            expected_companions=3,
        ),
        Trip(
            creator_id=users[2].id,
            destination="马来西亚 · 槟城",
            start_date=today + timedelta(days=18),
            end_date=today + timedelta(days=21),
            style="美食体验",
            description="以街头美食和老城建筑为主，不赶景点，适合轻松随性的短途同行。",
            expected_companions=1,
            status="CLOSED",
        ),
        Trip(
            creator_id=users[0].id,
            destination="韩国 · 首尔",
            start_date=today + timedelta(days=60),
            end_date=today + timedelta(days=64),
            style="文化历史",
            description="原计划参观宫殿和博物馆，因行程变化已取消，保留用于展示完整状态生命周期。",
            expected_companions=2,
            status="CANCELLED",
        ),
    ]
    db.session.add_all(trips)
    db.session.flush()
    handled_at = datetime.now(UTC)
    db.session.add_all([
        JoinRequest(
            trip_id=trips[0].id,
            applicant_id=users[1].id,
            message="时间刚好重合，我也喜欢看展和街头摄影。",
            status="ACCEPTED",
            handled_at=handled_at,
        ),
        JoinRequest(
            trip_id=trips[0].id,
            applicant_id=users[2].id,
            message="日期合适，但旅行节奏暂时不一致。",
            status="REJECTED",
            handled_at=handled_at,
        ),
        JoinRequest(
            trip_id=trips[1].id,
            applicant_id=users[2].id,
            message="我有轻量徒步经验，希望一起环洱海。",
        ),
        JoinRequest(
            trip_id=trips[1].id,
            applicant_id=users[0].id,
            message="原本想加入，后来时间安排发生变化。",
            status="WITHDRAWN",
            handled_at=handled_at,
        ),
        JoinRequest(
            trip_id=trips[2].id,
            applicant_id=users[0].id,
            message="想一起探索槟城老城和街头美食。",
            status="ACCEPTED",
            handled_at=handled_at,
        ),
        JoinRequest(
            trip_id=trips[3].id,
            applicant_id=users[1].id,
            message="对历史街区与博物馆路线感兴趣。",
            status="CANCELLED",
            handled_at=handled_at,
        ),
    ])
    db.session.commit()
    click.echo("已创建 3 个演示账号、4 条旅行计划和 6 条同行申请。")
    click.echo("DEMO ONLY：演示密码统一为 Demo123!")
