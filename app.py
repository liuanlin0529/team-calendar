"""Flask主应用：路由 + SocketIO事件 + 初始化。"""

import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

# 启动时自动加载 .env 文件（本地开发用）
load_dotenv()

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from models import db, Member, CalendarEvent, EventType
import github_storage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "team_calendar.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

app = Flask(__name__)

# 优先使用环境变量 DATABASE_URL（Render 上接 Neon PostgreSQL）。
# 本地调试默认 fallback 到 SQLite。
database_url = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ---------- 页面路由 ----------

@app.route("/")
def index():
    return render_template("index.html")


# ---------- REST API ----------

@app.route("/api/members", methods=["GET"])
def get_members():
    members = Member.query.order_by(Member.id).all()
    return jsonify([m.to_dict() for m in members])


@app.route("/api/events", methods=["GET"])
def get_events():
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    query = CalendarEvent.query
    if start_str:
        try:
            start_dt = datetime.fromisoformat(start_str)
            query = query.filter(CalendarEvent.start_at >= start_dt)
        except ValueError:
            pass
    if end_str:
        try:
            end_dt = datetime.fromisoformat(end_str)
            query = query.filter(CalendarEvent.end_at <= end_dt)
        except ValueError:
            pass

    events = query.order_by(CalendarEvent.start_at).all()
    return jsonify([e.to_dict() for e in events])


@app.route("/api/events", methods=["POST"])
def create_event():
    data = request.get_json(force=True)

    # 标题为空时自动由机构+姓名生成
    title = (data.get("title") or "").strip()
    if not title:
        org = (data.get("participant_org") or "").strip()
        name = (data.get("participant_name") or "").strip()
        if org and name:
            title = f"{org}·{name}"
        elif org:
            title = org
        elif name:
            title = name
        else:
            return jsonify({"error": "请填写所属机构或参与人姓名"}), 400

    event_type_str = data.get("event_type", "其他")
    color = CalendarEvent.color_for_type(event_type_str)

    try:
        start_at = datetime.fromisoformat(data["start_at"])
        end_at = datetime.fromisoformat(data["end_at"])
    except (KeyError, ValueError):
        return jsonify({"error": "时间格式无效"}), 400

    event = CalendarEvent(
        title=title,
        description=data.get("description", ""),
        event_type=event_type_str,
        start_at=start_at,
        end_at=end_at,
        participant_name=data.get("participant_name", ""),
        participant_org=data.get("participant_org", ""),
        color=color,
        notes=data.get("notes", ""),
        attachment=data.get("attachment", ""),
        created_by=data.get("created_by"),
    )
    db.session.add(event)
    db.session.commit()

    event_data = event.to_dict()
    socketio.emit("event_created", event_data)
    return jsonify(event_data), 201


@app.route("/api/events/<int:event_id>", methods=["PUT"])
def update_event(event_id):
    event = db.session.get(CalendarEvent, event_id)
    if not event:
        return jsonify({"error": "事件不存在"}), 404

    data = request.get_json(force=True)

    if "title" in data:
        event.title = data["title"]
    if "description" in data:
        event.description = data["description"]
    if "event_type" in data:
        event.event_type = data["event_type"]
        event.color = CalendarEvent.color_for_type(data["event_type"])
    if "start_at" in data:
        event.start_at = datetime.fromisoformat(data["start_at"])
    if "end_at" in data:
        event.end_at = datetime.fromisoformat(data["end_at"])
    if "participant_name" in data:
        event.participant_name = data["participant_name"]
    if "participant_org" in data:
        event.participant_org = data["participant_org"]
    if "notes" in data:
        event.notes = data["notes"]
    if "attachment" in data:
        event.attachment = data["attachment"]
    if "color" in data:
        event.color = data["color"]

    event.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    event_data = event.to_dict()
    socketio.emit("event_updated", event_data)
    return jsonify(event_data)


@app.route("/api/events/<int:event_id>", methods=["DELETE"])
def delete_event(event_id):
    event = db.session.get(CalendarEvent, event_id)
    if not event:
        return jsonify({"error": "事件不存在"}), 404

    db.session.delete(event)
    db.session.commit()
    socketio.emit("event_deleted", {"id": event_id})
    return jsonify({"ok": True})


@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "未选择文件"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "未选择文件"}), 400

    # 优先使用 GitHub 云端存储
    if github_storage.is_configured():
        try:
            file_bytes = file.read()
            result = github_storage.upload_file(file_bytes, file.filename)
            # attachment 字段存储完整 GitHub raw URL
            return jsonify({
                "filename": result["filename"],
                "url": result["url"],
                "original_name": result["original_name"],
            })
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 500

    # Fallback：未配置 GitHub Token 时使用本地存储
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    return jsonify({"filename": filename, "url": f"/uploads/{filename}", "original_name": file.filename})


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    """本地文件 fallback（未配置 GitHub 时使用）。"""
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/api/github_status")
def github_status():
    """返回 GitHub 存储配置状态。"""
    return jsonify({
        "configured": github_storage.is_configured(),
        "owner": github_storage.GITHUB_OWNER,
        "repo": github_storage.GITHUB_REPO,
    })


# ---------- 初始化 ----------

def init_app():
    """首次运行时自动初始化数据库。"""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    with app.app_context():
        db.create_all()
        if Member.query.count() == 0:
            from init_db import DEFAULT_MEMBERS
            for m in DEFAULT_MEMBERS:
                member = Member(name=m["name"], avatar_color=m["avatar_color"])
                db.session.add(member)
            db.session.commit()


if __name__ == "__main__":
    init_app()
    port = int(os.environ.get("PORT", 5000))
    print(f"共享日程管理应用已启动: http://localhost:{port}")
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
else:
    # 被 gunicorn 加载时（Render 生产环境）自动初始化
    init_app()
