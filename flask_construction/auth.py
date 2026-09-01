from functools import wraps
from flask import Blueprint, request, jsonify, session
from .models import User, db

auth = Blueprint('auth', __name__)


def get_current_user():
    """从 session 或 Bearer token 获取当前用户"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    token = request.headers.get('Authorization')
    if token and token.startswith('Bearer '):
        try:
            user_id = int(token[7:])
            return User.query.get(user_id)
        except (ValueError, TypeError):
            return None
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

    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        session['user_id'] = user.id
        session['username'] = user.username
        return jsonify({
            'id': user.id,
            'username': user.username,
            'nickname': user.nickname or user.username,
            'avatar': user.avatar,
            'role': user.role,
            'token': str(user.id)  # 使用 user_id 作为简单 token（与 SocketIO 配合）
        })

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

