from datetime import date, timedelta

import click
from flask.cli import with_appcontext
from sqlalchemy import select

from .extensions import db
from .models import JoinRequest, Trip, User


@click.command("seed-demo")
@with_appcontext
def seed_demo():
    """Add a small, repeatable set of demonstration data."""
    if db.session.scalar(select(User.id).limit(1)):
        click.echo("数据库中已有用户；为避免覆盖，未写入演示数据。")
        return

    users = [
        User(username="lin", email="lin@example.com", bio="喜欢城市漫步与胶片摄影。"),
        User(username="maya", email="maya@example.com", bio="独立旅行者，美食与博物馆爱好者。"),
        User(username="chen", email="chen@example.com", bio="周末徒步，偶尔去远方。"),
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
        ),
    ]
    db.session.add_all(trips)
    db.session.flush()
    db.session.add(
        JoinRequest(
            trip_id=trips[0].id,
            applicant_id=users[1].id,
            message="时间刚好重合，我也喜欢看展和街头摄影。",
            status="ACCEPTED",
        )
    )
    db.session.add(
        JoinRequest(
            trip_id=trips[1].id,
            applicant_id=users[2].id,
            message="我有轻量徒步经验，希望一起环洱海。",
        )
    )
    db.session.commit()
    click.echo("已创建 3 个演示账号、3 条旅行计划和 2 条同行申请。")
    click.echo("演示密码统一为 Demo123!")

