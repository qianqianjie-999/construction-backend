<div align="center">

# 🏗️ 工程现场施工管理系统

### 自部署 · 数据完全自主的施工日志 + 项目群聊一体化平台

**施工日志规范记录 ｜ 现场照片水印取证 ｜ 项目群聊消息永久保存 ｜ 内网/私有云部署**

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask)
![Flutter](https://img.shields.io/badge/Flutter-APP-02569B?logo=flutter)
![Socket.IO](https://img.shields.io/badge/Socket.IO-WebSocket-010101?logo=socketdotio)
![License](https://img.shields.io/badge/license-MIT-green)
![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen)

</div>

---

> 面向中小型施工企业、市政/公路/房建项目部的**轻量化现场管理工具**。
> 一台内网服务器即可运行：工人用手机 App 记日志、发照片、群聊沟通；管理者在网页后台查看、导出、归档。
> **数据全部保存在你自己的服务器上**——不依赖任何 SaaS 平台，消息、照片、日志永久留存、随时可审计。

## 📸 功能截图

> 截图文件放在 `docs/screenshots/` 目录，首次使用请按 [截图清单](docs/screenshots/README.md) 替换为你自己系统的截图。

<div align="center">

**📱 手机 App**

<img src="docs/screenshots/01_login.png" width="150"> <img src="docs/screenshots/02_projects.png" width="150"> <img src="docs/screenshots/03_log_list.png" width="150"> <img src="docs/screenshots/04_log_edit.png" width="150"> <img src="docs/screenshots/05_chat.png" width="150">

登录 ｜ 项目列表 ｜ 施工日志 ｜ 日志填报（水印照片） ｜ 项目群聊

<img src="docs/screenshots/06_chat_location.png" width="150"> <img src="docs/screenshots/07_forward.png" width="150">

点位共享导航 ｜ 多选转发微信/QQ

**🖥️ 管理后台（网页）**

<img src="docs/screenshots/08_admin_web.png" width="520">

项目总览 · 用户管理 · 日志审计 · PDF 导出

<img src="docs/screenshots/09_pdf.png" width="520">

施工日志 PDF（含水印照片，可直接归档竣工资料）

> 上图为展示占位图，替换为真实截图见 [docs/screenshots/README.md](docs/screenshots/README.md)。

</div>

## ⭐ 三大核心优势

### 🔒 1. 完全本地部署，数据 100% 自主可控

- 整套系统（App 接口 + 网页后台 + 数据库 + 文件存储）**全部部署在你自己的服务器**上
- 支持**纯内网/离线环境**运行；也可选配 frp 内网穿透 + 云服务器 SSL 入口，让外网手机安全访问
- 数据库用 MySQL/MariaDB（生产）或 SQLite（体验），照片文件存本地磁盘，**一键备份、一键迁移**
- 无任何第三方数据上报，无用户数/消息条数收费，适合对数据安全敏感的工程项目

### 📋 2. 专业施工日志，规范到每一天

- 标准日志字段：**天气气温、施工部位、出勤人数、机械台班、施工内容、质量安全情况**
- 现场照片**自动加水印**（项目名、日期时间、GPS 定位地址、经纬度），杜绝补拍、替拍
- 日志按项目分组、按日期归档，漏填/补填清晰可查
- 网页后台可**一键导出项目日志 PDF**（含照片、水印信息），直接用于竣工资料归档
- 支持日志编辑、删除、图片打包下载（ZIP）

### 💬 3. 项目群聊，消息永久保存不丢失

- 每个项目一个独立群聊：**文字、图片、文件（PDF/CAD/Excel…）、GPS 点位共享**
- 消息全部落库永久存储，换机、重装 App 后历史记录完整同步，可按关键词**搜索聊天记录**
- Socket.IO + WebSocket 实时推送，已读状态、消息撤回、施工日志卡片转发一应俱全
- 支持**多选消息转发/分享到微信、QQ**（文字+点位自动生成高德导航链接，图片文件原样发出），方便和外部协作方沟通
- 网页后台可直接查看项目全部聊天记录并批量导出图片，**纠纷追责有据可查**

## 🧩 功能全览

**📱 移动端（Flutter App，Android / iOS）**

- 账号登录，支持登录页自定义服务器地址（一套 App 可连多个自建服务器）
- 项目列表（按排序/置顶）、角色权限区分（管理员 / 普通用户）
- 施工日志：新建/编辑、拍照/相册多选、水印自动叠加、GPS 定位
- 项目群聊：实时消息、图片预览与保存、文件收发、点位地图、撤回、已读、搜索、多选转发微信
- 消息通知与连接状态指示，弱网自动重连

**🖥️ 管理后台（响应式网页，服务器自带，无需额外部署）**

- 管理员登录、项目创建/编辑/排序/删除
- 用户管理：创建账号、重置密码、角色分配
- 项目日志浏览、编辑、删除、**PDF 导出**、聊天图片 ZIP 打包
- 项目群聊记录在线查看（只读审计视角）

## 🏗️ 技术架构

```
┌────────────────────────────────────────────────────────────┐
│  移动端 Flutter App (Android/iOS)          管理后台网页(浏览器) │
│  dio + Socket.IO client                    自带 Flask 模板    │
└──────────────┬───────────────────────────────┬─────────────┘
               │ HTTPS / WSS (自签证书也支持)    │
               ▼                               ▼
┌────────────────────────────────────────────────────────────┐
│  云服务器（可选）：Nginx 9304 SSL 卸载 + frps 内网穿透        │
└──────────────┬─────────────────────────────────────────────┘
               ▼ frp TLS 隧道（纯内网部署可省略此层）
┌────────────────────────────────────────────────────────────┐
│  内网应用服务器（Linux，systemd 守护）                        │
│  gunicorn (gevent worker) :8082                            │
│  ├─ Flask REST API        日志/项目/用户/上传/PDF            │
│  ├─ Flask-SocketIO        WebSocket 实时群聊                │
│  ├─ 内置管理后台           /admin（账号密码登录）            │
│  └─ 本地文件存储           uploads/（照片、聊天图片、附件）   │
└──────────────┬─────────────────────────────────────────────┘
               ▼
┌────────────────────────────────────────────────────────────┐
│  MySQL / MariaDB（生产） 或 SQLite（零配置体验）             │
│  users · projects · construction_logs · log_photos         │
│  messages · message_reads（消息/已读回执，永久保存）         │
└────────────────────────────────────────────────────────────┘
```

**后端技术栈**

| 层 | 技术 |
| --- | --- |
| Web 框架 | Flask 3 + Flask-SQLAlchemy + Flask-CORS |
| 实时通信 | Flask-SocketIO（WebSocket，gunicorn + gevent 承载） |
| 数据库 | MySQL/MariaDB（PyMySQL 驱动），开发可用 SQLite |
| 图片处理 | Pillow（聊天图服务端压缩）、上传魔数校验 |
| PDF 导出 | ReportLab（中文字体内嵌） |
| 进程管理 | gunicorn(gevent) + systemd |
| 安全 | werkzeug 密码哈希、签名 token 鉴权、接口权限校验、上传白名单 |

**前端（App）技术栈**：Flutter、dio（HTTP）、socket_io_client、image_picker、share_plus、高德地图 URI 导航，详见 [App 仓库](https://github.com/qianqianjie-999/construction-frontend)。

## 📂 项目结构

```
.
├── app.py                    # 应用入口（默认管理员初始化、SocketIO 启动）
├── wsgi.py                   # gunicorn 入口（生产）
├── requirements.txt          # Python 依赖
├── .env.example              # 环境变量示例
├── flask_construction/
│   ├── config.py             # 开发/生产配置（环境变量驱动）
│   ├── models.py             # 数据模型（用户/项目/日志/照片/消息/已读）
│   ├── api.py                # 施工日志、项目 REST 接口
│   ├── auth.py               # 登录鉴权（签名 token）
│   ├── chat.py               # 聊天 REST + SocketIO 事件
│   ├── admin_views.py        # 网页管理后台
│   ├── utils/                # 水印、PDF 导出等工具
│   └── templates/            # 后台页面模板
├── deploy/                   # 生产部署配置示例（systemd / nginx / frp）
└── docs/                     # 部署文档、截图
```

## 🚀 快速开始（本地体验）

```bash
# 1. 获取代码
git clone https://github.com/qianqianjie-999/construction-backend.git
cd construction-backend

# 2. 安装依赖（建议虚拟环境）
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. 零配置启动（默认 SQLite，首次运行自动建库）
python app.py
```

启动后：

- App 接口服务：`http://服务器IP:5000`
- 管理后台：浏览器打开 `http://服务器IP:5000/admin`
- **默认管理员**：`admin / admin123`（首次启动自动创建，**登录后请立即修改密码**）

使用 MySQL/MariaDB：复制 `.env.example` 为 `.env`，配置 `DATABASE_URL`：

```bash
DATABASE_URL=mysql+pymysql://construction_user:你的密码@localhost/construction?charset=utf8mb4
FLASK_CONFIG=production
FLASK_SECRET_KEY=用 openssl rand -hex 32 生成
```

## 🧑‍🔧 生产部署（推荐）

单机一键式部署（gunicorn + systemd + Nginx），详见 **[docs/DEPLOY.md](docs/DEPLOY.md)**，内含：

- Linux 服务器初始化（Python、MySQL 建库建用户）
- gunicorn + gevent 服务（systemd 开机自启、自动重启）
- Nginx 反向代理 + HTTPS 证书（含 WebSocket 长连接配置）
- **frp 内网穿透方案**（服务器在内网、手机在外网时的标准拓扑，配置模板在 `deploy/`）
- 数据备份脚本（数据库 + uploads 附件定时备份）

部署配置模板：[`deploy/flask.service`](deploy/flask.service)、[`deploy/nginx.conf`](deploy/nginx.conf)、[`deploy/frpc.toml`](deploy/frpc.toml)、[`deploy/frps.toml`](deploy/frps.toml)。

## 📱 App 构建

App 为独立仓库：[construction-frontend](https://github.com/qianqianjie-999/construction-frontend)（Flutter）。

```bash
git clone https://github.com/qianqianjie-999/construction-frontend.git
cd construction-frontend
flutter pub get
# 打包时指定你的服务器地址（也可在 App 登录页"服务器地址"里填写）
flutter build apk --release --dart-define=API_BASE_URL=https://你的服务器IP:9304
```

## 👷 适用场景 / 用户案例

- **市政道路、公路养护、房建施工项目部**：工人现场填报日志，照片带水印不可伪造，月底 PDF 直接归档竣工资料
- **监理 / 甲方单位**：要求施工方群聊记录可追溯，点位共享直接导航到现场核查
- **内网/涉密环境**：数据不能出工地/公司内网的项目，纯局域网部署即可全功能运行
- **多点位分散项目**：公司一台中心服务器管多个项目，按项目隔离群聊与日志

> 欢迎在 [Discussions](https://github.com/qianqianjie-999/construction-backend/discussions) 分享你的使用场景与部署方式。

## 🤝 贡献指南

欢迎提交 Issue 与 PR！

1. Fork 本仓库并创建特性分支：`git checkout -b feature/你的功能`
2. 代码风格遵循现有约定（Python 遵循 PEP 8，中文注释）
3. 提交信息建议使用中文，格式：`feat: 新功能` / `fix: 修复` / `docs: 文档`
4. 确保 `python -m compileall flask_construction` 通过；涉及接口变更请同步更新文档
5. 提交 Pull Request 并说明改动内容与测试方式

**安全问题**：请勿直接提 Issue 公开漏洞，可通过仓库 Security 或邮件私下联系维护者。

## 🗺️ Roadmap

- [ ] Docker / docker-compose 一键部署
- [ ] App 消息推送（离线通知）
- [ ] 日志审批流程（填报 → 项目经理审核）
- [ ] 更多导出格式（Excel 汇总表）
- [ ] iOS 打包与上架指引

## 📄 License

[MIT License](LICENSE)

---

<div align="center">

如果这个项目对你的项目管理有帮助，欢迎点一个 ⭐ Star 支持！

</div>
