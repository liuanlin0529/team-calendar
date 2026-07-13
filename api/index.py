"""Vercel Serverless 入口：Flask 应用，数据存储在 GitHub 仓库。"""

import os
import sys
import uuid
from datetime import datetime, timezone

# 确保项目根目录在 sys.path 中
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from flask import Flask, render_template, request, jsonify, send_from_directory
import github_storage

app = Flask(
    __name__,
    template_folder=os.path.join(ROOT_DIR, "templates"),
    static_folder=os.path.join(ROOT_DIR, "static"),
)

UPLOAD_FOLDER = os.path.join(ROOT_DIR, "uploads")

EVENT_TYPE_COLORS = {
    "卖方路演": "#9fbcdb",
    "基金经理需求": "#eecba8",
    "其他": "#a6cbb5",
}


# ---------- 页面路由 ----------

@app.route("/")
def index():
    return render_template("index.html")


# ---------- 成员 API ----------

@app.route("/api/members", methods=["GET"])
def get_members():
    members = github_storage.get_all_members()
    return jsonify(members)


# ---------- 事件 API ----------

@app.route("/api/events", methods=["GET"])
def get_events():
    events = github_storage.get_all_events()
    # 按 start_at 排序
    events.sort(key=lambda e: e.get("start_at", ""))
    return jsonify(events)


@app.route("/api/events", methods=["POST"])
def create_event():
    data = request.get_json(force=True)

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

    event_data = {
        "title": title,
        "description": data.get("description", ""),
        "event_type": data.get("event_type", "其他"),
        "start_at": data.get("start_at", ""),
        "end_at": data.get("end_at", ""),
        "participant_name": data.get("participant_name", ""),
        "participant_org": data.get("participant_org", ""),
        "notes": data.get("notes", ""),
        "attachment": data.get("attachment", ""),
        "created_by": data.get("created_by"),
    }

    # 查找创建者名称
    members = github_storage.get_all_members()
    creator = next((m for m in members if m.get("id") == event_data["created_by"]), None)
    event_data["creator_name"] = creator["name"] if creator else None

    result = github_storage.create_event(event_data)
    return jsonify(result), 201


@app.route("/api/events/<int:event_id>", methods=["PUT"])
def update_event(event_id):
    data = request.get_json(force=True)
    result = github_storage.update_event(event_id, data)
    if result is None:
        return jsonify({"error": "事件不存在"}), 404
    return jsonify(result)


@app.route("/api/events/<int:event_id>", methods=["DELETE"])
def delete_event(event_id):
    ok = github_storage.delete_event(event_id)
    if not ok:
        return jsonify({"error": "事件不存在"}), 404
    return jsonify({"ok": True})


# ---------- 文件上传 ----------

@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "未选择文件"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "未选择文件"}), 400

    if github_storage.is_configured():
        try:
            file_bytes = file.read()
            result = github_storage.upload_file(file_bytes, file.filename)
            return jsonify({
                "filename": result["filename"],
                "url": result["url"],
                "original_name": result["original_name"],
            })
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 500

    # Fallback：本地存储
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    return jsonify({"filename": filename, "url": f"/uploads/{filename}", "original_name": file.filename})


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/api/github_status")
def github_status():
    return jsonify({
        "configured": github_storage.is_configured(),
        "owner": github_storage.GITHUB_OWNER,
        "repo": github_storage.GITHUB_REPO,
    })


# Vercel serverless handler
# Vercel 会自动调用这个 Flask app 对象
