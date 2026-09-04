# 施工日志管理系统 · 后端

工程现场施工日志管理系统的后端服务，为 Flutter APP + 管理后台网页提供 API、实时聊天、照片上传、PDF 导出与用户管理能力。

## 技术栈

- Python 3.9+（Rocky 9.6 系统版本）
- Flask + Flask-SQLAlchemy + Flask-CORS + Flask-SocketIO
- 数据库：MariaDB / MySQL（生产）或 SQLite（开发）
- 实时聊天：Socket.IO + gevent（gunicorn worker），WebSocket 传输
- PDF 导出：ReportLab

## 目录结构

```
.
├── app.py                      # 应用入口（含默认管理员创建、SocketIO 启动）
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量示例
├── flask_construction/
│   ├── config.py               # 配置（开发/生产）
│   ├── models.py               # 数据模型
│   ├── api.py                  # 施工日志/项目 CRUD 接口
│   ├── auth.py                 # 登录鉴权
│   ├── chat.py                 # 聊天 REST + SocketIO 事件
│   ├── admin_views.py          # 管理后台
│   ├── utils/                  # 工具（水印、PDF 导出等）
│   └── templates/              # 后台模板
└── uploads/                    # 照片/附件上传目录
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，按需修改：

```bash
cp .env.example .env
```

关键配置项：

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `FLASK_SECRET_KEY` | 会话密钥，生产环境务必改成随机字符串 | 随机 |
| `DATABASE_URL` | 数据库连接串 | SQLite 或 MariaDB |
| `HOST` | 监听地址（`0.0.0.0` 允许局域网访问） | `0.0.0.0` |
| `PORT` | 监听端口 | `5000` |
| `FLASK_DEBUG` | 调试模式 | `false` |
| `UPLOAD_FOLDER` | 照片上传目录 | `uploads` |

数据库连接串示例：

```bash
# MariaDB / MySQL
DATABASE_URL=mysql+pymysql://construction_user:construction123@localhost/construction?charset=utf8mb4

# 快速开发用 SQLite
DATABASE_URL=sqlite:///construction.db
```

### 3. 启动服务

```bash
python app.py
```

首次启动会自动建表，并创建默认管理员账户：

- 用户名：`admin`
- 密码：`admin123`

> ⚠️ 生产环境请登录后台后立即修改默认密码。

启动成功后，后端监听 `http://0.0.0.0:5000`，局域网内其他设备可通过 `http://<服务器IP>:5000` 访问。

## 前端对接

- API 前缀统一为 `/api`（如 `/api/login`、`/api/projects`、`/api/logs`）
- 已开启 CORS，允许跨域访问（前端可在登录页配置任意服务器地址）
- 聊天走 Socket.IO，与 HTTP 同端口同地址

## 说明

- 生产环境通过 Nginx + rust_frp 暴露，Socket.IO 使用 WebSocket 传输（gevent worker 支持）。
- 账号由管理员在后台分配，无开放注册入口（注册接口预留）。

## 生产部署架构

```
[手机 APP / 管理后台网页]
        │
   HTTPS:9304
        │
┌───────────────────────┐
│  阿里云 ECS 123.57.86.80  │
│  Nginx (SSL 终止)       │
│  rust_fps (bind 9300)   │
└─────────┬─────────────┘
  frp TCP 隧道 (port 19304)
          │
┌─────────▼─────────────┐
│  内网 Rocky 9.6         │
│  rust_frpc             │
│  gunicorn -k gevent    │
│  Flask :8082           │
│  MariaDB               │
└───────────────────────┘
```

### Rocky 9.6 部署步骤

```bash
# 1. 克隆项目
cd /data/sata_1T/www_project
git clone https://github.com/qianqianjie-999/construction-backend.git

# 2. 创建 venv 并装依赖
cd construction-backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 3. 配置 .env
cat > .env << EOF
FLASK_SECRET_KEY=随机字符串
FLASK_CONFIG=production
DATABASE_URL=mysql+pymysql://construction_user:construction123@localhost/construction?charset=utf8mb4
EOF

# 4. 启动 gunicorn（root 用户可避免端口权限问题）
sudo pkill -f gunicorn; sleep 1
FLASK_CONFIG=production venv/bin/gunicorn -c gunicorn.conf.py wsgi:app &
```

### gunicorn.conf.py

```python
worker_class = "gevent"
workers = 1
bind = "0.0.0.0:8082"
```

### wsgi.py 关键配置（gevent 必须最前面 patch）

```python
from gevent import monkey
monkey.patch_all()

import os
from app import create_app
app = create_app(os.environ.get('FLASK_CONFIG', 'production'))
```

### frps.toml（阿里云）

```toml
bindPort = 9300
auth.method = "token"
auth.token = "你的token"
allowPorts = [
  { start = 19304, end = 19304 },
]
```

### frpc.toml（Rocky）

```toml
serverAddr = "123.57.86.80"
serverPort = 9300
auth.method = "token"
auth.token = "你的token"

[[proxies]]
name = "web_app"
type = "tcp"
local_ip = "127.0.0.1"
local_port = 8082
remote_port = 19304
```

### Nginx（阿里云）

```nginx
server {
    listen 9304 ssl;
    server_name 123.57.86.80;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # API + Socket.IO (HTTP 反代)
    location / {
        proxy_pass http://127.0.0.1:19304;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

## 踩坑记录

| 坑 | 根因 | 修复 |
|---|---|---|
| `Invalid async_mode specified` | 新版 python-socketio(>=5.16) 不支持硬编码 'gevent' | ProductionConfig 硬编码 `SOCKETIO_ASYNC_MODE=None`，app.py 里只有 async_mode 有值才传参 |
| gevent-websocket 和 gevent 26.x 冲突 | 新版 gevent 20+ 已内置 WebSocket，旧包反而搞破坏 | **卸掉 gevent-websocket** |
| gunicorn worker 崩了 | wsgi.py 没有在最前面 `gevent.monkey.patch_all()` | patch 必须在所有 import 之前 |
| frpc remote_port=None | frpc.toml 写错成 `remote = 9304` 不是 `remote_port` | 改 `remote_port = 19304` |
| frps 端口冲突 | frpc remote_port 和 Nginx 监听同端口冲突 | frps allow_ports 用 19304，frpc remote_port=19304，Nginx 反代 127.0.0.1:19304 |
| Nginx WebSocket 不升级 | 缺 Upgrade/Connection 头 | Nginx 加 `proxy_set_header Upgrade $http_upgrade;` |

## 运维日常

### 备份（数据库 + uploads）

项目内置 `scripts/backup.sh`：mysqldump 数据库 + tar 打包上传目录，保留最近 7 天。

```bash
# 手动试跑
bash scripts/backup.sh

# 加入 crontab（凌晨 2 点，需自行配置 DB_PASS 或写进脚本）
# 0 2 * * * cd /data/sata_1T/www_project/construction-backend && bash scripts/backup.sh >> logs/backup.log 2>&1
```

备份产物默认在 `/var/backups/construction/`，可用 `BACKUP_ROOT` 变量修改。建议把备份目录放到与项目不同的磁盘/挂载点。

### 孤儿文件清理（磁盘瘦身）

删除项目/日志只清理数据库与日志照片，聊天图片/文件会残留磁盘。`scripts/cleanup_orphans.py` 对比数据库引用找出孤儿：

```bash
# dry-run 先看列表
python3 scripts/cleanup_orphans.py --uploads /data/sata_1T/www_project/construction-backend/uploads

# 确认后真正删除（可加 --min-age-days 调整保护期，默认 1 天）
python3 scripts/cleanup_orphans.py --uploads <uploads 绝对路径> --apply
```

### 上线 checklist

- [ ] `FLASK_SECRET_KEY` 设为随机长字符串（`python -c "import secrets; print(secrets.token_hex(32))"`）
- [ ] 后台默认密码 `admin/admin123` 首次登录后立即修改
- [ ] Nginx `client_max_body_size 100m;`（聊天大文件，否则 413）
- [ ] 上传下载：图片公开可读（供 `<img>` 标签），**聊天文件接口已加登录鉴权**（APP 走 Bearer token、后台同源 cookie）
- [ ] 依赖锁定：`pip freeze > requirements.lock.txt` 并提交，之后新环境用它安装

