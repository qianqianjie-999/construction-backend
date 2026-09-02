# ============================================================
# gunicorn.conf.py —— 生产配置
# worker 只能 1 个！eventlet 协程模型，多 worker 会断 Socket.IO 长连接
# ============================================================

import multiprocessing

# ---- 绑定 ----
bind = "0.0.0.0:8082"

# worker class 用 gevent（内置 ggevent，支持协程 + WebSocket）
# eventlet 已废弃（engineio 警告），gevent 是现在推荐的
worker_class = "gevent"

# worker 数量只能是 1（eventlet 自己处理并发）
workers = 1

# 每个 worker 最大请求数（防内存泄漏）
max_requests = 10000
max_requests_jitter = 500

# 超时（Socket.IO 长连接要长一点）
timeout = 120
graceful_timeout = 30

# ---- 日志 ----
accesslog = "logs/gunicorn_access.log"
errorlog  = "logs/gunicorn_error.log"
loglevel  = "info"

# ---- 进程名 ----
proc_name = "construction-gunicorn"

# ---- 预加载 ----
preload_app = True
