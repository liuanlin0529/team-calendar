"""初始化数据库：创建表并预置6名团队成员。"""

import os
from flask import Flask
from models import db, Member

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "team_calendar.db")

DEFAULT_MEMBERS = [
    {"name": "刘安林", "avatar_color": "#9fbcdb"},
    {"name": "曹天姿", "avatar_color": "#bbaecc"},
    {"name": "陈硕", "avatar_color": "#eecba8"},
    {"name": "张子怡", "avatar_color": "#a6cbb5"},
    {"name": "姚志锋", "avatar_color": "#ebd59a"},
    {"name": "陈肃磊", "avatar_color": "#e0a2a2"},
]


def init_db():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

        # 仅在成员表为空时插入预置数据
        if Member.query.count() == 0:
            for m in DEFAULT_MEMBERS:
                member = Member(name=m["name"], avatar_color=m["avatar_color"])
                db.session.add(member)
            db.session.commit()
            print(f"已创建 {len(DEFAULT_MEMBERS)} 名团队成员")
        else:
            print("成员已存在，跳过预置")

        print(f"数据库初始化完成: {DB_PATH}")


if __name__ == "__main__":
    init_db()
