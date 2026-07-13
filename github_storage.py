"""GitHub 仓库文件存储模块：通过 GitHub Contents API 上传/删除文件，返回固定 raw URL。"""

import base64
import os
import uuid

import requests

# ---------- 配置（从环境变量读取） ----------

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "liuanlin0529")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "team-calendar-files")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_UPLOAD_DIR = os.environ.get("GITHUB_UPLOAD_DIR", "uploads")

API_BASE = "https://api.github.com"
RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}"


def is_configured() -> bool:
    """检查 GitHub 存储是否已配置（Token 非空）。"""
    return bool(GITHUB_TOKEN)


def _headers() -> dict:
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


def _api_url(path: str) -> str:
    """构造 Contents API URL。"""
    return f"{API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"


def _raw_url(path: str) -> str:
    """构造 raw 文件访问 URL（固定地址）。"""
    return f"{RAW_BASE}/{path}"


def upload_file(file_bytes: bytes, original_filename: str, subdir: str = "") -> dict:
    """
    上传文件到 GitHub 仓库。

    Args:
        file_bytes: 文件二进制内容
        original_filename: 原始文件名
        subdir: 子目录（可选，如按日期分目录）

    Returns:
        {"filename": "唯一文件名", "url": "GitHub raw URL", "original_name": "原始文件名"}

    Raises:
        RuntimeError: 上传失败时抛出
    """
    if not is_configured():
        raise RuntimeError("GitHub 存储未配置，请设置 GITHUB_TOKEN 环境变量")

    ext = os.path.splitext(original_filename)[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"

    if subdir:
        github_path = f"{GITHUB_UPLOAD_DIR}/{subdir}/{unique_name}"
    else:
        github_path = f"{GITHUB_UPLOAD_DIR}/{unique_name}"

    content_b64 = base64.b64encode(file_bytes).decode("utf-8")

    payload = {
        "message": f"upload: {original_filename}",
        "content": content_b64,
        "branch": GITHUB_BRANCH,
    }

    # 如果文件已存在，需要提供 sha 才能更新
    # 先检查文件是否存在
    resp_check = requests.get(
        _api_url(github_path),
        headers=_headers(),
        params={"ref": GITHUB_BRANCH},
        timeout=10,
    )
    if resp_check.status_code == 200:
        # 文件已存在（极小概率 uuid 冲突），更新它
        payload["sha"] = resp_check.json()["sha"]

    resp = requests.put(
        _api_url(github_path),
        headers=_headers(),
        json=payload,
        timeout=30,
    )

    if resp.status_code not in (200, 201):
        try:
            err_msg = resp.json().get("message", resp.text)
        except Exception:
            err_msg = resp.text
        raise RuntimeError(f"GitHub 上传失败 ({resp.status_code}): {err_msg}")

    return {
        "filename": unique_name,
        "url": _raw_url(github_path),
        "original_name": original_filename,
    }


def delete_file(filename: str, subdir: str = "") -> bool:
    """
    从 GitHub 仓库删除文件。

    Args:
        filename: 文件名（uuid 格式）
        subdir: 子目录

    Returns:
        是否删除成功
    """
    if not is_configured():
        return False

    if subdir:
        github_path = f"{GITHUB_UPLOAD_DIR}/{subdir}/{filename}"
    else:
        github_path = f"{GITHUB_UPLOAD_DIR}/{filename}"

    # 先获取文件的 sha
    resp_check = requests.get(
        _api_url(github_path),
        headers=_headers(),
        params={"ref": GITHUB_BRANCH},
        timeout=10,
    )
    if resp_check.status_code != 200:
        return False

    sha = resp_check.json()["sha"]

    resp = requests.delete(
        _api_url(github_path),
        headers=_headers(),
        json={
            "message": f"delete: {filename}",
            "sha": sha,
            "branch": GITHUB_BRANCH,
        },
        timeout=10,
    )

    return resp.status_code in (200, 204)


def create_repo() -> dict:
    """
    创建 GitHub 存储仓库（首次设置时调用）。

    Returns:
        API 响应 JSON

    Raises:
        RuntimeError: 创建失败时抛出
    """
    if not GITHUB_TOKEN:
        raise RuntimeError("请先设置 GITHUB_TOKEN 环境变量")

    resp = requests.post(
        f"{API_BASE}/user/repos",
        headers=_headers(),
        json={
            "name": GITHUB_REPO,
            "description": "团队共享日程 - 附件存储",
            "private": False,
            "auto_init": True,
        },
        timeout=15,
    )

    if resp.status_code == 201:
        return resp.json()
    elif resp.status_code == 422:
        # 仓库已存在
        raise RuntimeError(f"仓库 {GITHUB_OWNER}/{GITHUB_REPO} 已存在")
    else:
        try:
            err_msg = resp.json().get("message", resp.text)
        except Exception:
            err_msg = resp.text
        raise RuntimeError(f"创建仓库失败 ({resp.status_code}): {err_msg}")


# ========== 数据 CRUD（用于 Vercel serverless 替代 SQLite） ==========

DATA_DIR = "data"
EVENTS_FILE = f"{DATA_DIR}/events.json"
MEMBERS_FILE = f"{DATA_DIR}/members.json"

DEFAULT_MEMBERS = [
    {"id": 1, "name": "刘安林", "avatar_color": "#9fbcdb"},
    {"id": 2, "name": "曹天姿", "avatar_color": "#bbaecc"},
    {"id": 3, "name": "陈硕", "avatar_color": "#eecba8"},
    {"id": 4, "name": "张子怡", "avatar_color": "#a6cbb5"},
    {"id": 5, "name": "姚志锋", "avatar_color": "#ebd59a"},
    {"id": 6, "name": "陈肃磊", "avatar_color": "#e0a2a2"},
]

EVENT_TYPE_COLORS = {
    "卖方路演": "#9fbcdb",
    "基金经理需求": "#eecba8",
    "其他": "#a6cbb5",
}


def _read_json_file(github_path: str) -> list:
    """从 GitHub 仓库读取 JSON 文件，不存在返回空列表。"""
    if not is_configured():
        return []
    resp = requests.get(
        _api_url(github_path),
        headers=_headers(),
        params={"ref": GITHUB_BRANCH},
        timeout=15,
    )
    if resp.status_code == 404:
        return []
    if resp.status_code != 200:
        return []
    import base64 as _b64
    content_b64 = resp.json().get("content", "")
    try:
        import json
        return json.loads(_b64.b64decode(content_b64).decode("utf-8"))
    except Exception:
        return []


def _write_json_file(github_path: str, data: list, message: str = "update data") -> bool:
    """写入 JSON 数据到 GitHub 仓库文件。"""
    if not is_configured():
        return False
    import json, base64 as _b64
    content_b64 = _b64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")).decode("utf-8")

    payload = {
        "message": message,
        "content": content_b64,
        "branch": GITHUB_BRANCH,
    }

    # 检查文件是否已存在，获取 sha
    resp_check = requests.get(
        _api_url(github_path),
        headers=_headers(),
        params={"ref": GITHUB_BRANCH},
        timeout=10,
    )
    if resp_check.status_code == 200:
        payload["sha"] = resp_check.json()["sha"]

    resp = requests.put(
        _api_url(github_path),
        headers=_headers(),
        json=payload,
        timeout=30,
    )
    return resp.status_code in (200, 201)


# ---------- 成员 CRUD ----------

def get_all_members() -> list:
    members = _read_json_file(MEMBERS_FILE)
    if not members:
        # 首次运行，初始化默认成员
        _write_json_file(MEMBERS_FILE, DEFAULT_MEMBERS, "init: default members")
        return list(DEFAULT_MEMBERS)
    return members


# ---------- 事件 CRUD ----------

def get_all_events() -> list:
    return _read_json_file(EVENTS_FILE)


def _next_event_id(events: list) -> int:
    if not events:
        return 1
    return max(e.get("id", 0) for e in events) + 1


def create_event(event_data: dict) -> dict:
    events = get_all_events()
    event_data["id"] = _next_event_id(events)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    event_data.setdefault("created_at", now)
    event_data.setdefault("updated_at", now)
    # 设置颜色
    event_type = event_data.get("event_type", "其他")
    event_data["color"] = EVENT_TYPE_COLORS.get(event_type, "#a6cbb5")
    events.append(event_data)
    _write_json_file(EVENTS_FILE, events, f"create event: {event_data.get('title', '')}")
    return event_data


def update_event(event_id: int, update_data: dict) -> dict | None:
    events = get_all_events()
    for i, e in enumerate(events):
        if e["id"] == event_id:
            from datetime import datetime, timezone
            update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            if "event_type" in update_data:
                update_data["color"] = EVENT_TYPE_COLORS.get(update_data["event_type"], "#a6cbb5")
            e.update(update_data)
            events[i] = e
            _write_json_file(EVENTS_FILE, events, f"update event: {e.get('title', '')}")
            return e
    return None


def delete_event(event_id: int) -> bool:
    events = get_all_events()
    new_events = [e for e in events if e["id"] != event_id]
    if len(new_events) == len(events):
        return False
    _write_json_file(EVENTS_FILE, new_events, "delete event")
    return True
