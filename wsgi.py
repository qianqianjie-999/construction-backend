"""
WSGI 入口 —— 给 gunicorn 用

启动命令:
    gunicorn -c gunicorn.conf.py wsgi:app

关键:
    - gevent.monkey.patch_all() 必须在所有 import 之前！
    - 这样 Flask-SocketIO 的 engineio 才能正确检测 gevent 并启用 WebSocket
    - workers 必须为 1（gevent 协程模型，多 worker 会断 Socket.IO 长连接）
"""

# ===== 必须在任何 import 之前 patch！=====
import gevent.monkey
gevent.monkey.patch_all()
# =========================================

import os

os.environ.setdefault('FLASK_CONFIG', 'production')

from app import create_app, socketio
from flask_construction.models import db
from flask_construction.models import User

# 创建 Flask app
app = create_app()

# 确保表存在（幂等）
with app.app_context():
    db.create_all()
    # 轻量迁移：给 messages 表加 recalled 列（已存在则跳过）
    from sqlalchemy import text, inspect
    insp = inspect(db.engine)
    cols = [c['name'] for c in insp.get_columns('messages')]
    if 'recalled' not in cols:
        db.session.execute(text('ALTER TABLE messages ADD COLUMN recalled BOOLEAN NOT NULL DEFAULT 0'))
        db.session.commit()
        print('迁移：messages 表已添加 recalled 列')
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(username='admin', nickname='管理员', role='admin')
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
        print('默认管理员账户已创建：admin / admin123')
