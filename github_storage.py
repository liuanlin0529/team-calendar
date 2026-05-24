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
