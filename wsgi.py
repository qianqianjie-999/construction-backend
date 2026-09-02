"""
WSGI 入口 —— 给 gunicorn 用

启动命令:
    gunicorn -k gevent -w 1 -b 0.0.0.0:5000 -c gunicorn.conf.py wsgi:app

关键:
    - 导出 Flask app（不是 socketio.wsgi_app！）
    - gevent worker 内置支持，不需要额外插件
    - workers 必须为 1（gevent/eventlet 协程模型，多 worker 会断 Socket.IO 长连接）
"""
import os

# 生产环境默认 production
os.environ.setdefault('FLASK_CONFIG', 'production')

from app import create_app, socketio
from flask_construction.models import db
from flask_construction.models import User

# 创建 Flask app（init_app 内部会把 Socket.IO 注入到 app 里）
app = create_app()

# 确保表存在（幂等）
with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(username='admin', nickname='管理员', role='admin')
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
        print('默认管理员账户已创建：admin / admin123')
