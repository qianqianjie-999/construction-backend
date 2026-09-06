# 更新日志

## v1.0.0 — 首个开源版本

### 核心能力
- Flask 3 REST API：项目、施工日志、用户、照片/文件上传
- Flask-SocketIO 实时群聊（WebSocket，gunicorn + gevent 承载）
- 消息全部落库**永久保存**，支持已读回执、消息撤回、聊天记录搜索
- 消息类型：文字 / 图片（服务端 Pillow 压缩）/ 文件 / GPS 点位 / 日志卡片
- 内置网页管理后台（`/admin`）：项目管理与排序、用户管理、日志审计、
  项目日志 PDF 导出（ReportLab 中文字体内嵌）、聊天图片 ZIP 打包

### 安全
- werkzeug 密码哈希、签名 token 鉴权、接口权限校验
- 上传文件白名单 + 图片魔数校验、上传大小限制（环境变量可调）
- 配置全部环境变量驱动（`.env`），生产密钥随机化

### 部署
- systemd（gunicorn + gevent）、Nginx 反代（含 WebSocket 头）配置模板
- frp 内网穿透配置模板（frps/frpc，TLS + token）
- 支持 MySQL/MariaDB（生产）与 SQLite（零配置体验）
- 详见 `docs/DEPLOY.md`（纯内网 / 云服务器 / frp 穿透三种方案）
