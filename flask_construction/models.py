from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# 北京时间（UTC+8）
CST = timezone(timedelta(hours=8))


def _to_beijing(dt):
    """将 UTC datetime 转为北京时间字符串"""
    if dt is None:
        return None
    # 数据库存的是 naive UTC（datetime.utcnow），先标记为 UTC 再转北京时间
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CST).strftime('%Y-%m-%d %H:%M:%S')

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
            'content': self.content,
            'log_id': self.log_id,
            'created_at': _to_beijing(self.created_at),
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
