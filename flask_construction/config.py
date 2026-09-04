import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def _parse_bool(v, default=False):
    if isinstance(v, bool):
        return v
    return str(v).lower() in ('1', 'true', 'yes', 'on')


class Config:
    """基础配置"""
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or os.urandom(24)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 上传配置
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'uploads'
    # 请求总体积上限（字节），默认 100MB（聊天文件支持到 100MB，需同步调大 Nginx client_max_body_size）
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH') or 100 * 1024 * 1024)

    # 服务器配置
    HOST = os.environ.get('HOST') or '0.0.0.0'
    PORT = int(os.environ.get('PORT') or 5000)

    # 调试模式
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    # ---- CORS ----
    # 允许的 origin，多个用逗号分隔，* 表示全部允许（内网+frp 场景推荐 *）
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')

    # ---- Socket.IO ----
    # async_mode: threading(默认/开发) / eventlet(生产推荐) / gevent
    SOCKETIO_ASYNC_MODE = os.environ.get('SOCKETIO_ASYNC_MODE') or 'threading'
    SOCKETIO_CORS_ORIGINS = os.environ.get('SOCKETIO_CORS_ORIGINS') or CORS_ORIGINS


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    SOCKETIO_ASYNC_MODE = 'threading'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://construction_user:construction123@localhost/construction?charset=utf8mb4'


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    # gunicorn -k gevent 启动时 gevent 已 patch 所有标准库，
    # 硬编码 None 让 engineio 自动检测到 gevent（最稳妥，不读 .env 避免被 eventlet 等坑）
    SOCKETIO_ASYNC_MODE = None
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://construction_user:construction123@localhost/construction?charset=utf8mb4'

    @classmethod
    def init_app(cls, app):
        super().init_app(app)
        import logging
        from logging.handlers import RotatingFileHandler

        os.makedirs('logs', exist_ok=True)
        file_handler = RotatingFileHandler(
            'logs/construction.log',
            maxBytes=5 * 1024 * 1024,
            backupCount=10,
            encoding='utf-8',
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Construction Test (production) startup')


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
