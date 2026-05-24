"""
GitHub 存储一键配置脚本。

使用方法：
    python setup_github.py

脚本会引导你：
1. 输入 GitHub Personal Access Token
2. 自动创建存储仓库 team-calendar-files
3. 生成 .env 文件
4. 验证配置是否成功
"""

import os
import sys

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests  # noqa: E402
import github_storage  # noqa: E402

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def print_step(msg):
    print(f"\n{'='*50}")
    print(f"  {msg}")
    print(f"{'='*50}")


def get_token():
    print_step("第 1 步：获取 GitHub Personal Access Token")
    print("""
请按以下步骤创建 Token：

1. 打开 https://github.com/settings/tokens/new
2. Note（备注）填写：team-calendar-upload
3. Expiration（过期时间）建议选择：No expiration（永不过期）
4. 勾选权限：
   ☑ repo（完整的仓库访问权限）
5. 点击 "Generate token"
6. 复制生成的 Token（以 ghp_ 开头，只显示一次！）
""")
    token = input("请粘贴你的 GitHub Token：").strip()
    if not token:
        print("❌ Token 不能为空")
        sys.exit(1)
    return token


def verify_token(token):
    """验证 Token 是否有效。"""
    print("\n正在验证 Token...")
    resp = requests.get(
        "https://api.github.com/user",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
        timeout=10,
    )
    if resp.status_code == 200:
        user = resp.json()
        print(f"✅ Token 有效！登录用户：{user.get('login', '未知')}")
        return user.get("login", "YHfund1")
    else:
        print(f"❌ Token 无效 ({resp.status_code})")
        try:
            print(f"   错误信息：{resp.json().get('message', '')}")
        except Exception:
            pass
        sys.exit(1)


def create_repo(token, owner):
    """创建存储仓库。"""
    print_step("第 2 步：创建 GitHub 存储仓库")

    repo_name = "team-calendar-files"
    print(f"将在 {owner} 下创建仓库：{repo_name}")

    # 先检查仓库是否已存在
    resp = requests.get(
        f"https://api.github.com/repos/{owner}/{repo_name}",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
        timeout=10,
    )

    if resp.status_code == 200:
        print(f"✅ 仓库 {owner}/{repo_name} 已存在，跳过创建")
        return repo_name

    # 创建新仓库
    resp = requests.post(
        "https://api.github.com/user/repos",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
        json={
            "name": repo_name,
            "description": "团队共享日程 - 附件存储",
            "private": False,
            "auto_init": True,
        },
        timeout=15,
    )

    if resp.status_code == 201:
        print(f"✅ 仓库 {owner}/{repo_name} 创建成功！")
        print(f"   访问地址：https://github.com/{owner}/{repo_name}")
        return repo_name
    else:
        print(f"❌ 创建仓库失败 ({resp.status_code})")
        try:
            print(f"   错误信息：{resp.json().get('message', '')}")
        except Exception:
            pass
        sys.exit(1)


def save_env(token, owner, repo):
    """保存 .env 文件。"""
    print_step("第 3 步：保存配置到 .env 文件")

    content = f"""# GitHub 存储配置 - 团队共享日程附件
# 生成时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}

GITHUB_TOKEN={token}
GITHUB_OWNER={owner}
GITHUB_REPO={repo}
GITHUB_BRANCH=main
GITHUB_UPLOAD_DIR=uploads
"""
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ 配置已保存到 {ENV_FILE}")
    print("   ⚠ 请勿将 .env 文件提交到 Git 仓库！")


def verify_upload(token, owner, repo):
    """验证上传功能。"""
    print_step("第 4 步：验证上传功能")

    test_content = f"team-calendar 上传测试 - {__import__('datetime').datetime.now().isoformat()}"
    test_bytes = test_content.encode("utf-8")

    try:
        # 临时设置环境变量
        os.environ["GITHUB_TOKEN"] = token
        os.environ["GITHUB_OWNER"] = owner
        os.environ["GITHUB_REPO"] = repo

        # 重新加载模块配置
        import importlib
        importlib.reload(github_storage)

        result = github_storage.upload_file(test_bytes, "test_connection.txt")
        print(f"✅ 上传成功！")
        print(f"   文件 URL：{result['url']}")
        print(f"\n🎉 GitHub 云端存储配置完成！")
        print(f"\n附件将自动上传到 GitHub 仓库，通过以下固定格式访问：")
        print(f"   https://raw.githubusercontent.com/{owner}/{repo}/main/uploads/{{文件名}}")
        return True
    except Exception as e:
        print(f"❌ 上传测试失败：{e}")
        return False


def main():
    print("""
╔══════════════════════════════════════════╗
║    团队共享日程 - GitHub 云端存储配置    ║
╚══════════════════════════════════════════╝
""")

    # 第 1 步：获取 Token
    token = get_token()

    # 验证 Token
    owner = verify_token(token)

    # 第 2 步：创建仓库
    repo = create_repo(token, owner)

    # 第 3 步：保存配置
    save_env(token, owner, repo)

    # 第 4 步：验证
    verify_upload(token, owner, repo)

    print("""
═══════════════════════════════════════════
  配置完成后的使用方式：

  本地启动：
    1. 运行: python setup_github.py（已完成）
    2. 启动: python app.py
       （app.py 会自动读取 .env 文件）

  Render 部署：
    在 Render 后台设置环境变量：
    - GITHUB_TOKEN = 你的Token
    - GITHUB_OWNER = {owner}
    - GITHUB_REPO = {repo}

  如果不想使用 GitHub 存储，不设置 GITHUB_TOKEN 即可，
  系统会自动回退到本地文件存储。
═══════════════════════════════════════════
""".format(owner=owner, repo=repo))


if __name__ == "__main__":
    main()
