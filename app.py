from flask import Flask, session, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_construction.models import db
from flask_construction.config import config
import os

# 全局 SocketIO 实例（使用 threading 模式，避免 eventlet 兼容性问题）
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')

    app = Flask(__name__)

    # 加载配置
    app.config.from_object(config[config_name])

    # 配置 CORS，允许 Flutter Web 访问
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # 确保上传文件夹存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # 初始化数据库
    db.init_app(app)

    # 初始化 SocketIO
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

    # 根路径重定向到管理后台
    @app.route('/')
    def index():
        return redirect('/admin')

    return app


if __name__ == '__main__':
    app = create_app(os.environ.get('FLASK_CONFIG', 'development'))

    # 创建数据库表
    with app.app_context():
        db.create_all()

        # 创建默认管理员账户（如果不存在）
        from flask_construction.models import User
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(username='admin', nickname='管理员', role='admin')
            admin_user.set_password('admin123')  # 默认密码
            db.session.add(admin_user)
            db.session.commit()
            print('默认管理员账户已创建：admin / admin123')

    # 启动应用（使用 socketio.run 启用 WebSocket）
    socketio.run(
        app,
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG'],
        allow_unsafe_werkzeug=True,
    )
