# 施工日志管理系统 · 后端

工程现场施工日志管理系统的后端服务，为 Flutter Web 前端提供 API、实时聊天、照片上传、PDF 导出与后台用户管理能力。

## 技术栈

- Python 3.8+
- Flask + Flask-SQLAlchemy + Flask-CORS + Flask-SocketIO
- 数据库：MariaDB / MySQL（生产）或 SQLite（开发）
- 实时聊天：Socket.IO（threading 模式，Web 端使用 polling 传输）
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

- 聊天在 Web 端使用 **polling** 传输（Werkzeug 开发服务器不支持 WebSocket），生产环境如需 WebSocket 可换用 eventlet / gevent。
- 账号由管理员在后台分配，无开放注册入口（注册接口预留）。
