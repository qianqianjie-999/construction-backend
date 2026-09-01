from flask import Blueprint, request, jsonify, session, current_app, send_from_directory
from werkzeug.utils import secure_filename
from .models import db, User, Project, Message, MessageRead, ConstructionLog
from datetime import datetime
import os
from functools import wraps

chat = Blueprint('chat', __name__)

ALLOWED_IMG_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMG_EXTENSIONS


def get_current_user():
    """从 session 或 token 获取当前用户"""
    # 1) session
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    # 2) Authorization: Bearer <user_id>  (简单 token，与 auth.py 保持一致)
    token = request.headers.get('Authorization')
    if token and token.startswith('Bearer '):
        try:
            user_id = int(token[7:])
            return User.query.get(user_id)
        except (ValueError, TypeError):
            return None
    return None


def chat_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


@chat.route('/messages', methods=['GET'])
@chat_login_required
def get_messages():
    """获取项目群历史消息，支持分页"""
    project_id = request.args.get('project_id', type=int)
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400

    before_id = request.args.get('before_id', type=int)
    limit = min(request.args.get('limit', default=30, type=int), 100)

    q = Message.query.filter_by(project_id=project_id)
    if before_id:
        q = q.filter(Message.id < before_id)
    q = q.order_by(Message.id.desc()).limit(limit)
    msgs = q.all()
    msgs.reverse()

    user_id = request.current_user.id
    return jsonify([m.to_dict(current_user_id=user_id) for m in msgs])


@chat.route('/messages/<int:message_id>/read', methods=['POST'])
@chat_login_required
def mark_message_read(message_id):
    """标记消息已读"""
    msg = Message.query.get_or_404(message_id)
    user = request.current_user
    existing = MessageRead.query.filter_by(message_id=msg.id, user_id=user.id).first()
    if not existing:
        read = MessageRead(message_id=msg.id, user_id=user.id)
        db.session.add(read)
        db.session.commit()
    return jsonify({'message': 'marked as read'})


@chat.route('/messages/unread_count', methods=['GET'])
@chat_login_required
def unread_count():
    """获取用户在所有项目群的未读消息数"""
    user = request.current_user
    counts = (
        db.session.query(Message.project_id, db.func.count(Message.id))
        .outerjoin(MessageRead, db.and_(MessageRead.message_id == Message.id, MessageRead.user_id == user.id))
        .filter(MessageRead.id.is_(None))
        .filter(Message.user_id != user.id)
        .group_by(Message.project_id)
        .all()
    )
    return jsonify({pid: cnt for pid, cnt in counts})


@chat.route('/upload_image', methods=['POST'])
@chat_login_required
def upload_image():
    """上传聊天图片，返回文件名，前端通过 socket 推送 image 消息"""
    if 'image' not in request.files:
        return jsonify({'error': 'image is required'}), 400
    file = request.files['image']
    if not (file.filename and allowed_image(file.filename)):
        return jsonify({'error': 'invalid image file'}), 400

    filename = secure_filename(file.filename)
    unique_filename = f"chat_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{filename}"
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(file_path)

    return jsonify({
        'filename': unique_filename,
        'url': f'/api/chat/images/{unique_filename}'
    }), 201


@chat.route('/images/<filename>')
def get_chat_image(filename):
    """访问聊天图片"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@chat.route('/logs/<int:log_id>/card', methods=['GET'])
@chat_login_required
def get_log_card(log_id):
    """获取日志卡片信息（用于聊天中的日志卡片点击展开）"""
    log = ConstructionLog.query.get_or_404(log_id)
    return jsonify({
        'id': log.id,
        'project_id': log.project_id,
        'date': log.date.strftime('%Y-%m-%d'),
        'weather': log.weather or '',
        'construction_part': log.construction_part or '',
        'work_content': log.work_content or '',
        'progress': log.progress or '',
        'project_manager': log.project_manager or '',
        'recorder': log.recorder or '',
    })


def register_socketio(socketio):
    """注册 SocketIO 事件处理"""
    from flask_socketio import join_room, leave_room, emit

    @socketio.on('connect')
    def on_connect():
        user = get_current_user()
        if not user:
            return False  # 拒绝连接
        # 把连接加入"用户私有房间"，便于推送私信
        from flask import request as sio_request
        join_room(f'user_{user.id}')
        emit('connected', {'user_id': user.id, 'username': user.username})

    @socketio.on('disconnect')
    def on_disconnect():
        pass

    @socketio.on('join_project')
    def on_join_project(data):
        user = get_current_user()
        if not user:
            return
        project_id = data.get('project_id')
        if not project_id:
            return
        # 验证项目存在
        project = Project.query.get(project_id)
        if not project:
            emit('error', {'message': 'project not found'})
            return
        join_room(f'project_{project_id}')
        emit('joined', {'project_id': project_id, 'user': user.to_dict()})

    @socketio.on('leave_project')
    def on_leave_project(data):
        project_id = data.get('project_id')
        if project_id:
            leave_room(f'project_{project_id}')

    @socketio.on('send_message')
    def on_send_message(data):
        """发送消息事件"""
        user = get_current_user()
        if not user:
            emit('error', {'message': 'not authenticated'})
            return

        project_id = data.get('project_id')
        content_type = data.get('content_type', 'text')
        content = data.get('content', '').strip()
        log_id = data.get('log_id')

        # 校验
        if not project_id:
            emit('error', {'message': 'project_id required'})
            return
        project = Project.query.get(project_id)
        if not project:
            emit('error', {'message': 'project not found'})
            return
        if content_type == 'text' and not content:
            emit('error', {'message': 'empty message'})
            return
        if content_type == 'image' and not content:
            emit('error', {'message': 'image filename required'})
            return
        if content_type == 'log_card' and not log_id:
            emit('error', {'message': 'log_id required'})
            return

        # 创建消息
        msg = Message(
            project_id=project_id,
            user_id=user.id,
            content_type=content_type,
            content=content,
            log_id=log_id if content_type == 'log_card' else None,
        )
        db.session.add(msg)
        db.session.commit()

        # 广播到项目群
        msg_data = msg.to_dict()
        emit('receive_message', msg_data, room=f'project_{project_id}')

    @socketio.on('mark_read')
    def on_mark_read(data):
        """标记消息已读（批量）"""
        user = get_current_user()
        if not user:
            return
        message_ids = data.get('message_ids', [])
        for mid in message_ids:
            existing = MessageRead.query.filter_by(message_id=mid, user_id=user.id).first()
            if not existing:
                db.session.add(MessageRead(message_id=mid, user_id=user.id))
        db.session.commit()
