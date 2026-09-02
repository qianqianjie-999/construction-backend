from functools import wraps
from flask import Blueprint, request, jsonify, session, current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from .models import User, db
import time
from collections import defaultdict

auth = Blueprint('auth', __name__)

# ===== 登录限流（防暴力破解）=====
# 内存计数：{ key: [时间戳, ...] }，key 为 ip:username
_login_attempts = defaultdict(list)
LOGIN_MAX_ATTEMPTS = 5       # 最大失败次数
LOGIN_WINDOW_SECONDS = 300   # 统计窗口（秒）


def _too_many_attempts(key):
    """判断该 key 在窗口内是否超过失败次数上限"""
    now = time.time()
    # 清理窗口外的旧记录
    attempts = [t for t in _login_attempts[key] if now - t < LOGIN_WINDOW_SECONDS]
    _login_attempts[key] = attempts
    return len(attempts) >= LOGIN_MAX_ATTEMPTS


def _record_attempt(key):
    _login_attempts[key].append(time.time())


def _serializer():
    """构建签名序列化器，密钥取自应用配置 SECRET_KEY"""
    secret = current_app.config.get('SECRET_KEY')
    return URLSafeTimedSerializer(secret, salt='auth-token')


def generate_token(user_id):
    """为用户生成签名 token（含过期时间，默认 30 天）"""
    s = _serializer()
    return s.dumps({'uid': user_id})


def _decode_token(token):
    """解析签名 token，返回 user_id；无效或过期返回 None"""
    s = _serializer()
    try:
        data = s.loads(token, max_age=3600 * 24 * 30)  # 30 天有效期
        return data.get('uid')
    except (BadSignature, SignatureExpired):
        return None


def get_current_user():
    """从 session 或 Bearer token 获取当前用户"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    token = request.headers.get('Authorization')
    if token and token.startswith('Bearer '):
        raw = token[7:].strip()
        # 仅接受签名 token，杜绝明文 user_id 伪造
        user_id = _decode_token(raw)
        if user_id is not None:
            return User.query.get(user_id)
    return None


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """管理员验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        if user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        request.current_user = user
        return f(*args, **kwargs)
    return decorated_function


@auth.route('/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    # 暴力破解防护：按 IP+用户名限流
    client_ip = request.remote_addr or 'unknown'
    attempt_key = f"{client_ip}:{username}"
    if _too_many_attempts(attempt_key):
        return jsonify({'error': 'Too many login attempts. Please try again later.'}), 429

    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        # 登录成功，清空该 key 的失败计数
        _login_attempts.pop(attempt_key, None)
        session['user_id'] = user.id
        session['username'] = user.username
        return jsonify({
            'id': user.id,
            'username': user.username,
            'nickname': user.nickname or user.username,
            'avatar': user.avatar,
            'role': user.role,
            'token': generate_token(user.id)  # 签名 token，防伪造
        })

    # 登录失败，记录一次
    _record_attempt(attempt_key)
    return jsonify({'error': 'Invalid credentials'}), 401


@auth.route('/logout', methods=['POST'])
def logout():
    """用户登出"""
    session.clear()
    return jsonify({'message': 'Logged out successfully'})


@auth.route('/me', methods=['GET'])
@login_required
def get_current_user_info():
    """获取当前用户信息"""
    return jsonify(request.current_user.to_dict())


@auth.route('/register', methods=['POST'])
@admin_required
def register():
    """创建新用户（仅管理员可调用，用于人工分配账号）"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    nickname = data.get('nickname', '').strip() or username
    role = data.get('role', 'user')  # 默认普通用户

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password too short (min 6)'}), 400
    if role not in ('admin', 'user'):
        return jsonify({'error': 'Invalid role'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 409

    user = User(username=username, nickname=nickname, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        'id': user.id,
        'username': user.username,
        'nickname': user.nickname,
        'role': user.role,
    }), 201


@auth.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """更新用户信息（重置密码、修改昵称/角色）"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    if 'password' in data:
        new_password = data['password']
        if len(new_password) < 6:
            return jsonify({'error': 'Password too short (min 6)'}), 400
        user.set_password(new_password)

    if 'nickname' in data:
        user.nickname = data['nickname'].strip() or user.username

    if 'role' in data:
        if data['role'] not in ('admin', 'user'):
            return jsonify({'error': 'Invalid role'}), 400
        user.role = data['role']

    db.session.commit()
    return jsonify(user.to_dict())


@auth.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """删除用户"""
    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        return jsonify({'error': 'Cannot delete the admin account'}), 400
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'User deleted'})


@auth.route('/users', methods=['GET'])
@login_required
def list_users():
    """获取用户列表"""
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])

