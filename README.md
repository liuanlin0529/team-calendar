# 团队共享日程管理系统

基金团队共享日程管理网页应用，基于 Flask + SQLAlchemy + Flask-SocketIO。

## 功能
- 6人团队共享日程
- 月/周/日视图切换
- 日程类型：卖方路演、基金经理需求、其他
- 实时同步（WebSocket）
- 标题自动由"机构·姓名"生成
- 登录身份持久化（localStorage）

## 部署
- 平台：Render.com
- 数据库：Neon PostgreSQL（免费）
- 启动命令：`gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT app:app`

## 环境变量
- `DATABASE_URL`：PostgreSQL 连接字符串（Render 上配置）
- `PORT`：服务端口（Render 自动注入）
