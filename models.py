from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class EventType:
    """日程类型常量集合（用字符串存储，PostgreSQL/SQLite 通用）。"""
    ROADSHOW = "卖方路演"
    FUND_MANAGER = "基金经理需求"
    OTHER = "其他"

    ALL = (ROADSHOW, FUND_MANAGER, OTHER)


EVENT_TYPE_COLORS = {
    EventType.ROADSHOW: "#9fbcdb",
    EventType.FUND_MANAGER: "#eecba8",
    EventType.OTHER: "#a6cbb5",
}


class Member(db.Model):
    __tablename__ = "members"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    avatar_color = db.Column(db.String(7), nullable=False, default="#9fbcdb")
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    events = db.relationship("CalendarEvent", backref="creator", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "avatar_color": self.avatar_color,
        }


class CalendarEvent(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, nullable=True, default="")
    event_type = db.Column(db.String(32), nullable=False, default=EventType.OTHER)
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)
    participant_name = db.Column(db.String(128), nullable=False, default="")
    participant_org = db.Column(db.String(128), nullable=False, default="")
    color = db.Column(db.String(7), nullable=False, default="#a6cbb5")
    notes = db.Column(db.Text, nullable=True, default="")
    attachment = db.Column(db.String(512), nullable=True, default="")
    created_by = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description or "",
            "event_type": self.event_type or "其他",
            "start_at": self.start_at.isoformat() if self.start_at else None,
            "end_at": self.end_at.isoformat() if self.end_at else None,
            "participant_name": self.participant_name or "",
            "participant_org": self.participant_org or "",
            "color": self.color,
            "notes": self.notes or "",
            "attachment": self.attachment or "",
            "created_by": self.created_by,
            "creator_name": self.creator.name if self.creator else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def color_for_type(event_type_str: str) -> str:
        if event_type_str not in EventType.ALL:
            event_type_str = EventType.OTHER
        return EVENT_TYPE_COLORS.get(event_type_str, "#a6cbb5")
