from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from .utils.timeutil import fmt_beijing

db = SQLAlchemy()


def _to_beijing(dt):
    """将 UTC datetime 转为北京时间字符串（None 返回 None，兼容历史调用）"""
    return fmt_beijing(dt, default=None)

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nickname = db.Column(db.String(80))               # 昵称（显示名）
    avatar = db.Column(db.String(255))                # 头像文件名
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'nickname': self.nickname or self.username,
            'avatar': self.avatar,
            'role': self.role,
        }

class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)  # 项目名称
    location = db.Column(db.String(255))              # 工程地点/路段
    company = db.Column(db.String(255))               # 施工单位
    manager = db.Column(db.String(100))               # 项目经理
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 人工排序：值小者靠前；同为默认值 0 时按创建时间倒序（新项目排最上边）。
    # 快完工的项目可在后台用"下移"人工挪到后面。
    sort_order = db.Column(db.Integer, default=0, nullable=False, index=True)
    
    # 关联日志
    logs = db.relationship('ConstructionLog', backref='project', lazy=True, cascade='all, delete-orphan')
    # 关联消息
    messages = db.relationship('Message', backref='project', lazy=True, cascade='all, delete-orphan')

class ConstructionLog(db.Model):
    __tablename__ = 'construction_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True) # 日期
    weather = db.Column(db.String(50))                    # 天气情况
    temperature = db.Column(db.String(20))                # 气温
    wind_force = db.Column(db.String(20))                 # 风力
    wind_direction = db.Column(db.String(20))             # 风向
    construction_part = db.Column(db.Text)                # 当日工程施工部位
    work_content = db.Column(db.Text)                     # 施工内容
    progress = db.Column(db.Text)                         # 当日工程形象进度
    personnel = db.Column(db.Text)                        # 施工情况记录
    safety_notes = db.Column(db.Text)                     # 技术质量安全工作记录
    materials = db.Column(db.Text)                        # 材料记录
    project_manager = db.Column(db.String(100))           # 工程负责人
    recorder = db.Column(db.String(100))                  # 记录人
    remarks = db.Column(db.Text)                          # 备注
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联照片
    photos = db.relationship('LogPhoto', backref='log', lazy=True, cascade='all, delete-orphan')

class LogPhoto(db.Model):
    __tablename__ = 'log_photos'
    
    id = db.Column(db.Integer, primary_key=True)
    log_id = db.Column(db.Integer, db.ForeignKey('construction_logs.id'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)  # 文件在服务器上的存储名
    original_filename = db.Column(db.String(255))        # 原始文件名
    photo_type = db.Column(db.String(20), default='site') # 'site' 现场照片, 'certificate' 合格证
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Message(db.Model):
    """聊天消息"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content_type = db.Column(db.String(20), default='text')  # 'text', 'image', 'file', 'log_card'
    content = db.Column(db.Text)                              # 文本内容 / 图片文件名 / 文件元信息 JSON / ...
    log_id = db.Column(db.Integer, db.ForeignKey('construction_logs.id'))  # 转发日志卡片时引用
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    recalled = db.Column(db.Boolean, default=False, nullable=False)  # 是否已撤回
    
    user = db.relationship('User', backref='messages')
    log = db.relationship('ConstructionLog', backref='forwarded_in_messages')
    reads = db.relationship('MessageRead', backref='message', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self, current_user_id=None):
        d = {
            'id': self.id,
            'project_id': self.project_id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'nickname': (self.user.nickname or self.user.username) if self.user else None,
            'avatar': self.user.avatar if self.user else None,
            'content_type': self.content_type,
            # 已撤回消息不下发任何内容（文本/图片文件名/文件元信息/日志卡片引用），
            # 防止抓包/历史接口泄露；各端均不渲染占位，整条隐藏
            'content': None if self.recalled else self.content,
            'log_id': None if self.recalled else self.log_id,
            'created_at': _to_beijing(self.created_at),
            'recalled': self.recalled or False,
        }
        if current_user_id is not None:
            d['is_read_by_me'] = any(r.user_id == current_user_id for r in self.reads)
        return d


class MessageRead(db.Model):
    """消息已读记录"""
    __tablename__ = 'message_reads'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('message_id', 'user_id', name='_message_user_uc'),)


class LoginAttempt(db.Model):
    """登录失败计数（跨 gunicorn worker 共享，防暴力破解）

    同一 key（ip:username）在窗口内失败次数超限时拒绝登录。
    登录成功或窗口过期后记录自动清理。
    """
    __tablename__ = 'login_attempts'

    id = db.Column(db.Integer, primary_key=True)
    attempt_key = db.Column(db.String(128), nullable=False, index=True)
    failed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


class AppVersion(db.Model):
    """App 版本信息，供客户端检查更新使用"""
    __tablename__ = 'app_versions'

    id = db.Column(db.Integer, primary_key=True)
    # 数字版本号（pubspec.yaml 的 version: x.y.z+code 中的 code），用于比较大小
    version_code = db.Column(db.Integer, nullable=False, index=True)
    # 可读版本名，如 "1.2.0"
    version_name = db.Column(db.String(32), nullable=False)
    # APK 在服务器上的相对路径（相对于 UPLOAD_FOLDER/app/）
    apk_path = db.Column(db.String(255), nullable=False)
    # APK 文件大小（字节）
    apk_size = db.Column(db.BigInteger, default=0)
    # 更新说明（换行分隔）
    changelog = db.Column(db.Text, default='')
    # 是否强制更新（客户端低于 min_version_code 时必须更新）
    force_update = db.Column(db.Boolean, default=False)
    # 支持的最低版本号，低于此版本的客户端必须更新
    min_version_code = db.Column(db.Integer, default=1)
    # 是否为当前发布版本（同一时刻只有一个 is_published=True）
    is_published = db.Column(db.Boolean, default=False, index=True)
    # 发布时间
    published_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'version_code': self.version_code,
            'version_name': self.version_name,
            'apk_path': self.apk_path,
            'apk_size': self.apk_size or 0,
            'changelog': self.changelog or '',
            'force_update': self.force_update,
            'min_version_code': self.min_version_code,
            'is_published': self.is_published,
            'published_at': self.published_at.strftime('%Y-%m-%d %H:%M:%S') if self.published_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
        }
