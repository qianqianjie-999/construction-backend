import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def _parse_bool(v, default=False):
    if isinstance(v, bool):
        return v
    return str(v).lower() in ('1', 'true', 'yes', 'on')


def _get_secret_key():
    """获取稳定的 SECRET_KEY。

    优先级：环境变量 FLASK_SECRET_KEY > instance/.secret_key 持久化文件 > 随机生成并持久化。
    避免每次重启生成新密钥导致所有已登录用户的签名 token 失效。
    """
    key = os.environ.get('FLASK_SECRET_KEY')
    if key:
        return key
    key_file = os.path.join('instance', '.secret_key')
    if os.path.exists(key_file):
        with open(key_file, 'r') as f:
            key = f.read().strip()
        if key:
            return key
    import secrets
    key = secrets.token_hex(32)
    os.makedirs('instance', exist_ok=True)
    with open(key_file, 'w') as f:
        f.write(key)
    return key


def _get_database_url(default_for_dev=None):
    """获取数据库连接串。

    生产环境必须通过 DATABASE_URL 环境变量注入；未设置则启动失败，
    杜绝把明文密码硬编码在仓库里。
    开发环境允许回退到 default_for_dev（仅本机调试用）。
    """
    url = os.environ.get('DATABASE_URL')
    if url:
        return url
    if default_for_dev:
        return default_for_dev
    sys.stderr.write(
        '[FATAL] 未设置 DATABASE_URL 环境变量。\n'
        '        请在 .env 或环境变量中配置数据库连接串，例如：\n'
        '        DATABASE_URL=mysql+pymysql://user:password@localhost/db?charset=utf8mb4\n'
    )
    sys.exit(1)


class Config:
    """基础配置"""
    SECRET_KEY = _get_secret_key()
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
    # 开发环境允许回退到本机默认库（仅本机调试，不含真实密码）
    SQLALCHEMY_DATABASE_URI = _get_database_url(
        default_for_dev='sqlite:///construction_dev.db'
    )


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    # gunicorn -k gevent 启动时 gevent 已 patch 所有标准库，
    # 硬编码 None 让 engineio 自动检测到 gevent（最稳妥，不读 .env 避免被 eventlet 等坑）
    SOCKETIO_ASYNC_MODE = None
    # 生产环境强制从环境变量读取，不提供任何默认密码
    SQLALCHEMY_DATABASE_URI = _get_database_url()

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
