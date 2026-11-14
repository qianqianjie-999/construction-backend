# ============================================================
# gunicorn.conf.py —— 生产配置（gevent）
#
# 关键:
#   - wsgi.py 里必须在最前面 import gevent.monkey; gevent.monkey.patch_all()
#   - WebSocket 由 gevent 20+ 内置支持，勿再安装 gevent-websocket（会冲突，见 README 踩坑记录）
#   - workers = 1（gevent 协程模型，多 worker 会断 Socket.IO 长连接）
# ============================================================

import multiprocessing

# ---- 绑定 ----
bind = "0.0.0.0:8082"

# worker class 用 gevent（gevent 20+ 内置 WebSocket 支持）
worker_class = "gevent"

# worker 数量只能是 1（Socket.IO 长连接需要单进程）
workers = 1

# 按请求数滚动重启会卡死 gevent 单 worker + Socket.IO 长连接：
# 2026-11-13 21:44:41 触发 Autorestarting -> 21:46:41 WORKER TIMEOUT，
# master 假活、worker 僵尸，业务中断 11h+。故关闭，改由外部探活兜底。
max_requests = 0
max_requests_jitter = 0

# 超时（Socket.IO 长连接要长一点）
timeout = 120
graceful_timeout = 30

# 保持连接数
keepalive = 5

# ---- 日志 ----
accesslog = "logs/gunicorn_access.log"
errorlog  = "logs/gunicorn_error.log"
loglevel  = "info"

# ---- 进程名 ----
proc_name = "construction-gunicorn"

# ---- 预加载 ----
# 必须为 False：
# wsgi.py 顶层执行 gevent.monkey.patch_all()，preload=True 会让 patch 在 fork 之前
# 打进 master，把 Arbiter 自己的 waitpid/select 也换成 gevent 实现。worker 一旦
# WORKER TIMEOUT 被 kill，master 就收不到/处理不了 SIGCHLD，不再重建 worker，
# 表现为「进程在、8082 在监听、业务全挂、systemd 认为 active」。
# 2026-11-13 21:44 的 11 小时中断即此链路，preload 对 161MB 峰值无收益，改回 False。
preload_app = False
