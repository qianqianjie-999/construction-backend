from flask import Flask, session, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_construction.models import db
from flask_construction.config import config
import os

# 全局 SocketIO 实例（async_mode 由 config 决定：开发用 threading，生产用 eventlet）
socketio = SocketIO(cors_allowed_origins="*")


def _ensure_project_sort_column(app):
    """轻量迁移：projects 表补 sort_order 列。

    db.create_all() 不会给已存在的表加新列，生产库（MySQL）靠这里在启动时自动补列，
    幂等可重复执行。
    """
    from sqlalchemy import inspect, text
    with app.app_context():
        try:
            insp = inspect(db.engine)
            if not insp.has_table('projects'):
                return
            cols = [c['name'] for c in insp.get_columns('projects')]
            if 'sort_order' not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text(
                        'ALTER TABLE projects ADD COLUMN sort_order INT NOT NULL DEFAULT 0'
                    ))
                app.logger.info('projects 表已自动补充 sort_order 列')
        except Exception as e:
            app.logger.warning(f'检查/补充 projects.sort_order 列失败: {e}')


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

    # 初始化 SocketIO
    socketio.cors_allowed_origins = app.config.get('SOCKETIO_CORS_ORIGINS', '*')
    # async_mode=None 表示让 engineio 自动检测（gevent/eventlet/threading），
    # 显式传 None 新版会报 "Invalid async_mode"，所以只有有值时才传参数
    async_mode = app.config.get('SOCKETIO_ASYNC_MODE')
    if async_mode:
        socketio.init_app(app, async_mode=async_mode)
    else:
        socketio.init_app(app)

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

    # Jinja2 过滤器：把 naive UTC datetime 转北京时间（统一走 utils.timeutil）
    from flask_construction.utils.timeutil import fmt_beijing

    @app.template_filter('beijing_time')
    def beijing_time(dt, fmt='%Y-%m-%d %H:%M:%S'):
        return fmt_beijing(dt, fmt)

    # 根路径重定向到管理后台
    @app.route('/')
    def index():
        return redirect('/admin')

    # 启动时自动补列（幂等）
    _ensure_project_sort_column(app)

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
