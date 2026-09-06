# 生产部署指南

本文档介绍三种典型部署方式，按你的网络环境选择：

| 方案 | 适用场景 | 复杂度 |
| --- | --- | --- |
| **A. 纯内网直连** | 服务器和手机都在工地/公司局域网（或 Wi-Fi 同网段） | ⭐ 最简单 |
| **B. 云服务器直装** | 有公网云服务器（阿里云/腾讯云等），数据放云上 | ⭐⭐ |
| **C. 内网服务器 + frp 穿透**（推荐数据自主场景） | 数据必须放内网，但手机需要在外网（4G/5G）访问 | ⭐⭐⭐ |

> 生产环境建议 Linux（Rocky/CentOS/Ubuntu 均可），Python 3.9+。

---

## 一、服务器基础环境（三种方案通用）

### 1. 安装系统依赖

```bash
# Rocky / CentOS / RHEL
sudo dnf install -y python3 python3-pip python3-devel gcc mariadb-server nginx
sudo systemctl enable --now mariadb

# Ubuntu / Debian
sudo apt update && sudo apt install -y python3 python3-pip python3-venv python3-dev default-libmysqlclient-dev mariadb-server nginx
sudo systemctl enable --now mariadb
```

### 2. 初始化数据库

```bash
sudo mysql_secure_installation   # 设置 root 密码等（按提示操作）

sudo mysql -u root -p
```

```sql
CREATE DATABASE construction CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'construction_user'@'localhost' IDENTIFIED BY '改成你的强密码';
GRANT ALL PRIVILEGES ON construction.* TO 'construction_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3. 部署代码

```bash
sudo mkdir -p /opt/construction-app && sudo chown $USER /opt/construction-app
cd /opt/construction-app
git clone https://github.com/qianqianjie-999/construction-backend.git .

python3 -m venv venv
./venv/bin/pip install -r requirements.txt

cp .env.example .env
# 编辑 .env：至少修改 DATABASE_URL 密码、FLASK_SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"   # 生成密钥
```

`.env` 关键项：

```ini
FLASK_CONFIG=production
FLASK_SECRET_KEY=上一步生成的64位随机串
DATABASE_URL=mysql+pymysql://construction_user:你的密码@localhost/construction?charset=utf8mb4
```

### 4. 启动服务（gunicorn + systemd）

复制服务文件并修改其中的用户/路径（本示例假设部署在 `/opt/construction-app`）：

```bash
sudo cp deploy/flask.service /etc/systemd/system/construction-backend.service
sudo sed -i "s#/home/qianqianjie/flutter/construction_test#/opt/construction-app#g" /etc/systemd/system/construction-backend.service
sudo sed -i "s/User=qianqianjie/User=$USER/; s/Group=qianqianjie/Group=$USER/" /etc/systemd/system/construction-backend.service

sudo systemctl daemon-reload
sudo systemctl enable --now construction-backend
sudo systemctl status construction-backend     # 确认 active (running)
curl -I http://127.0.0.1:8082/                 # 200/308 即正常
```

服务监听 `0.0.0.0:8082`（gunicorn.conf.py），首次启动自动建表并创建默认管理员 **admin / admin123**，登录后台后请立即改密码。

---

## 方案 A：纯内网直连

手机和服务器连同一个 Wi-Fi/局域网即可：

- App 登录页"服务器地址"填 `http://服务器内网IP:8082`
- 管理后台：`http://服务器内网IP:8082/admin`
- 确认服务器防火墙放行 8082：`sudo firewall-cmd --add-port=8082/tcp --permanent && sudo firewall-cmd --reload`

> 无需 Nginx、无需证书，五分钟可用。

---

## 方案 B：云服务器直装 + HTTPS

在"基础环境"之上加 Nginx 反向代理与证书：

```bash
sudo cp deploy/nginx.conf /etc/nginx/conf.d/construction.conf
# 编辑该文件：listen 端口、证书路径按实际调整
sudo nginx -t && sudo systemctl reload nginx
```

证书二选一：

1. **有域名**：`sudo dnf install -y certbot python3-certbot-nginx && sudo certbot --nginx -d 你的域名`（Let's Encrypt 免费证书）
2. **只有 IP / 自签证书**：App 已内置信任用户证书（忽略自签校验），可直接用自签证书：

```bash
sudo openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
  -keyout /etc/nginx/construction.key -out /etc/nginx/construction.crt \
  -subj "/CN=你的服务器IP"
# 然后在 nginx 配置中填写这两个路径
```

云服务器**安全组/防火墙**放行对外端口（如 9304）。

---

## 方案 C：内网服务器 + frp 内网穿透（数据不出内网）

拓扑：

```
手机 App ──HTTPS──▶ 云服务器 Nginx:9304(SSL)
                      │ 127.0.0.1:19304
                      ▼
                    frps（云，TLS 加密隧道）
                      │
        ══════════════╪══════════════  公网边界
                      ▼
                    frpc（内网客户端）
                      │ 127.0.0.1:8082
                      ▼
              内网 gunicorn 服务 + 数据库 + uploads
```

数据存储全部在内网；云服务器只做加密转发，不落业务数据。

**云服务器侧（frps）**：

```bash
# 安装 frp（或 rust_frp），把 deploy/frps.toml 放到 /etc/frp/frps.toml
# 务必修改 token：openssl rand -hex 32
# 放行安全组端口：bind_port(9300)、work_conn_port(10300)、对外 9304
sudo systemctl enable --now frps
```

**内网服务器侧（frpc）**：

```bash
# deploy/frpc.toml 放到 /etc/frp/frpc.toml
# 修改：server_addr = 云服务器公网IP；token 与 frps 完全一致
sudo cp deploy/frpc.service /etc/systemd/system/frpc.service   # 如有需要
sudo systemctl enable --now frpc
```

**云服务器 Nginx**：使用 `deploy/nginx.conf`（`proxy_pass http://127.0.0.1:19304`），证书同方案 B。

完成后 App 地址填 `https://云服务器IP:9304`。

> ⚠️ **token 是隧道的唯一凭证，务必使用随机值并定期轮换**；仓库 `deploy/` 中的 token 全部是占位符。

---

## 二、数据备份

业务数据 = 数据库 + `uploads/` 附件目录。示例每日备份脚本 `/opt/construction-app/backup.sh`：

```bash
#!/bin/bash
BK=/data/backup/construction
mkdir -p "$BK"
DATE=$(date +%F)
mysqldump -u construction_user -p'你的密码' construction | gzip > "$BK/db_$DATE.sql.gz"
tar czf "$BK/uploads_$DATE.tar.gz" -C /opt/construction-app uploads
# 保留 30 天
find "$BK" -name "*.gz" -mtime +30 -delete
```

```bash
chmod +x /opt/construction-app/backup.sh
echo "30 2 * * * /opt/construction-app/backup.sh" | sudo crontab -
```

建议备份文件定期拷贝到另一台机器/对象存储。

---

## 三、升级流程

```bash
cd /opt/construction-app
git pull
./venv/bin/pip install -r requirements.txt   # 依赖有变化时
sudo systemctl restart construction-backend
```

数据库表结构变更会在启动时自动建表/补列（如无）；大版本升级请先看 Release 说明并备份。

---

## 四、常见问题

| 现象 | 排查 |
| --- | --- |
| App 提示连接失败 | 手机能否 ping/浏览器访问服务器地址；防火墙/安全组端口；`systemctl status construction-backend` |
| 聊天消息不实时 | Nginx 必须带 `Upgrade`/`Connection` 头且 `proxy_read_timeout` 加长（见 deploy/nginx.conf） |
| 上传大文件失败 | 同时调大 Nginx `client_max_body_size` 与 `.env` 的 `MAX_CONTENT_LENGTH` |
| 重启后所有人掉线需重登 | `.env` 未设置固定 `FLASK_SECRET_KEY` |
| 后台忘记管理员密码 | 服务器执行：`./venv/bin/python -c "from app import app; ..."` 或直接在数据库中重置（见用户手册） |
