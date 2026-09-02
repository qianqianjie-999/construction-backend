from flask import Flask, session, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_construction.models import db
from flask_construction.config import config
import os

# 全局 SocketIO 实例（async_mode 由 config 决定：开发用 threading，生产用 eventlet）
socketio = SocketIO(cors_allowed_origins="*")


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')

    app = Flask(__name__)

    # 加载配置
    app.config.from_object(config[config_name])

    # 解析 CORS origins（支持逗号分隔）
    raw_origins = app.config.get('CORS_ORIGINS', '*')
    if raw_origins == '*':
        cors_origins = '*'
    else:
        cors_origins = [o.strip() for o in raw_origins.split(',') if o.strip()]

    # 配置 CORS
    CORS(app, resources={r"/api/*": {"origins": cors_origins}}, supports_credentials=True)
    # 管理后台（/admin）和 Socket.IO 也允许跨域
    CORS(app, resources={r"/admin*": {"origins": cors_origins}}, supports_credentials=True)

    # 确保上传文件夹存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # 初始化数据库
    db.init_app(app)

    # 初始化 SocketIO（async_mode 和 cors 从配置来）
    socketio.cors_allowed_origins = app.config.get('SOCKETIO_CORS_ORIGINS', '*')
    socketio.init_app(app, async_mode=app.config.get('SOCKETIO_ASYNC_MODE'))

    # 注册蓝图
    from flask_construction.api import api
    from flask_construction.admin_views import admin
    from flask_construction.auth import auth
    from flask_construction.chat import chat, register_socketio

    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(admin, url_prefix='')
    app.register_blueprint(auth, url_prefix='/api')
    app.register_blueprint(chat, url_prefix='/api/chat')

    # 注册 SocketIO 事件
    register_socketio(socketio)

    # Jinja2 过滤器：把 naive UTC datetime 转北京时间
    from datetime import timezone, timedelta
    CST = timezone(timedelta(hours=8))

    @app.template_filter('beijing_time')
    def beijing_time(dt, fmt='%Y-%m-%d %H:%M:%S'):
        if dt is None:
            return '-'
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(CST).strftime(fmt)

    # 根路径重定向到管理后台
    @app.route('/')
    def index():
        return redirect('/admin')

    return app


if __name__ == '__main__':
    env = os.environ.get('FLASK_CONFIG', 'development')
    app = create_app(env)

    # 创建数据库表
    with app.app_context():
        db.create_all()

        # 创建默认管理员账户（如果不存在）
        from flask_construction.models import User
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(username='admin', nickname='管理员', role='admin')
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            print('默认管理员账户已创建：admin / admin123')

    # 启动应用（socketio.run 会自动用 eventlet/gevent，如果不可用则 fallback 到 threading）
    socketio.run(
        app,
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG'],
        allow_unsafe_werkzeug=True,
    )
