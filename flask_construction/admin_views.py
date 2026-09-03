from flask import Blueprint, render_template, request, send_file, current_app, redirect, url_for, session, flash
from .models import db, Project, ConstructionLog, Message, User
from .utils.pdf_generator import generate_pdf_for_project
from werkzeug.security import generate_password_hash
import os
import io
import zipfile
from datetime import datetime

# 创建管理后台蓝图
admin = Blueprint('admin', __name__, template_folder='templates')


def admin_login_required(f):
    """管理后台登录验证装饰器（用 session 验证）"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('admin.admin_login'))
        user = User.query.get(session['user_id'])
        if not user:
            session.clear()
            return redirect(url_for('admin.admin_login'))
        if user.role != 'admin':
            return "Forbidden: Admin access required", 403
        return f(*args, **kwargs)
    return decorated


@admin.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """管理后台登录"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password) and user.role == 'admin':
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('admin.admin_dashboard'))
        return render_template('admin/login.html', error='用户名或密码错误，或非管理员账户')
    return render_template('admin/login.html')


@admin.route('/admin/logout')
def admin_logout():
    """管理后台登出"""
    session.clear()
    return redirect(url_for('admin.admin_login'))


@admin.route('/admin')
@admin_login_required
def admin_dashboard():
    """管理后台首页，显示项目列表"""
    projects = Project.query.all()
    return render_template('admin/dashboard.html', projects=projects)

@admin.route('/admin/project/create', methods=['GET', 'POST'])
@admin_login_required
def create_project():
    """创建新项目"""
    if request.method == 'POST':
        name = request.form.get('name')
        location = request.form.get('location')
        company = request.form.get('company')
        manager = request.form.get('manager')

        if not name:
            return render_template('admin/create_project.html', error='项目名称不能为空')

        project = Project(
            name=name,
            location=location or '',
            company=company or '',
            manager=manager or ''
        )
        db.session.add(project)
        db.session.commit()

        return render_template('admin/create_project.html', success='项目创建成功！')

    return render_template('admin/create_project.html')

@admin.route('/admin/project/<int:project_id>')
@admin_login_required
def project_detail(project_id):
    """查看项目详情和所有日志"""
    project = Project.query.get_or_404(project_id)
    logs = ConstructionLog.query.filter_by(project_id=project_id).order_by(ConstructionLog.date.desc()).all()
    return render_template('admin/project_detail.html', project=project, logs=logs)

@admin.route('/admin/project/<int:project_id>/chat')
@admin_login_required
def project_chat(project_id):
    """查看项目群的聊天记录"""
    project = Project.query.get_or_404(project_id)
    messages = (
        Message.query
        .filter_by(project_id=project_id)
        .order_by(Message.id.asc())
        .all()
    )
    # 预加载用户信息
    users = {u.id: u for u in User.query.all()}
    return render_template('admin/chat.html', project=project, messages=messages, users=users)


@admin.route('/admin/project/<int:project_id>/chat/images/zip')
@admin_login_required
def download_chat_images(project_id):
    """一键下载项目所有聊天图片（打包 ZIP）"""
    project = Project.query.get_or_404(project_id)

    # 查出所有图片类型的消息
    image_msgs = (
        Message.query
        .filter_by(project_id=project_id, content_type='image')
        .order_by(Message.id.asc())
        .all()
    )

    if not image_msgs:
        flash('该项目没有聊天图片', 'warning')
        return redirect(url_for('admin.project_chat', project_id=project_id))

    upload_folder = current_app.config['UPLOAD_FOLDER']
    buffer = io.BytesIO()

    # 收集有效文件，处理重名
    file_map = {}  # zip内文件名 -> 磁盘路径
    missing = 0

    for msg in image_msgs:
        filename = msg.content
        if not filename:
            missing += 1
            continue
        disk_path = os.path.join(upload_folder, filename)
        if not os.path.exists(disk_path):
            missing += 1
            continue

        # 用 "序号_原文件名" 避免重名
        if filename not in file_map.values():
            # 找一个唯一的名字
            base = filename
            counter = 1
            zip_name = f"{len(file_map)+1:03d}_{base}"
            while zip_name in file_map:
                counter += 1
                zip_name = f"{len(file_map)+1:03d}_{counter}_{base}"
            file_map[zip_name] = disk_path

    if not file_map:
        flash(f'图片记录 {len(image_msgs)} 条，但文件都不存在了', 'error')
        return redirect(url_for('admin.project_chat', project_id=project_id))

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for zip_name, disk_path in file_map.items():
            zf.write(disk_path, zip_name)

    buffer.seek(0)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_filename = f"{project.name}_聊天图片_{ts}.zip"

    return send_file(
        buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_filename,
    )

@admin.route('/admin/export/<int:project_id>')
@admin_login_required
def export_project(project_id):
    """导出指定项目的竣工资料为PDF"""
    project = Project.query.get_or_404(project_id)
    pdf_buffer = generate_pdf_for_project(project)

    if pdf_buffer:
        filename = f"{project.name}_竣工资料.pdf"
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    else:
        return "PDF generation failed", 500


@admin.route('/admin/project/<int:project_id>/delete', methods=['POST'])
@admin_login_required
def delete_project(project_id):
    """删除项目及其所有关联数据（日志、照片、聊天消息、磁盘文件）"""
    project = Project.query.get_or_404(project_id)
    project_name = project.name

    # 1. 删除关联的日志照片文件
    for log in project.logs:
        for photo in log.photos:
            try:
                os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], photo.filename))
            except OSError:
                pass  # 文件已不存在就忽略

    # 2. 级联删除（SQLAlchemy relationship cascade 会处理 logs/photos/messages）
    db.session.delete(project)
    db.session.commit()

    flash(f'项目「{project_name}」已删除', 'success')
    return redirect(url_for('admin.admin_dashboard'))


@admin.route('/admin/log/<int:log_id>/delete', methods=['POST'])
@admin_login_required
def delete_log(log_id):
    """删除单条施工日志（级联删除关联照片文件）"""
    log = ConstructionLog.query.get_or_404(log_id)
    project_id = log.project_id

    # 删除磁盘上的照片文件
    for photo in log.photos:
        try:
            os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], photo.filename))
        except OSError:
            pass

    db.session.delete(log)
    db.session.commit()

    flash(f'日志（{log.date.strftime("%Y年%m月%d日")}）已删除', 'success')
    return redirect(url_for('admin.project_detail', project_id=project_id))


@admin.route('/admin/log/<int:log_id>/edit', methods=['GET', 'POST'])
@admin_login_required
def edit_log(log_id):
    """编辑施工日志"""
    log = ConstructionLog.query.get_or_404(log_id)
    project = Project.query.get_or_404(log.project_id)

    if request.method == 'POST':
        try:
            date_str = request.form.get('date', '')
            if date_str:
                log.date = datetime.strptime(date_str, '%Y-%m-%d').date()
            log.weather = request.form.get('weather', '')
            log.temperature = request.form.get('temperature', '')
            log.wind_force = request.form.get('wind_force', '')
            log.wind_direction = request.form.get('wind_direction', '')
            log.construction_part = request.form.get('construction_part', '')
            log.work_content = request.form.get('construction_content', '')
            log.progress = request.form.get('progress', '')
            log.personnel = request.form.get('construction_record', '')
            log.safety_notes = request.form.get('technical_safety_record', '')
            log.materials = request.form.get('material_record', '')
            log.project_manager = request.form.get('project_manager', '')
            log.recorder = request.form.get('recorder', '')

            db.session.commit()
            flash(f'日志（{log.date.strftime("%Y年%m月%d日")}）已更新', 'success')
            return redirect(url_for('admin.project_detail', project_id=project.id))
        except Exception as e:
            db.session.rollback()
            flash(f'保存失败：{e}', 'error')

    return render_template('admin/log_edit.html', log=log, project=project)


# ============ 用户管理（人工分配账号） ============

@admin.route('/admin/users')
@admin_login_required
def user_list():
    """用户列表"""
    users = User.query.order_by(User.id.asc()).all()
    return render_template('admin/users.html', users=users)


@admin.route('/admin/users/create', methods=['GET', 'POST'])
@admin_login_required
def create_user():
    """创建新用户（人工分配账号）"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        nickname = request.form.get('nickname', '').strip() or username
        role = request.form.get('role', 'user')

        if not username or not password:
            return render_template('admin/user_form.html', error='用户名和密码不能为空')
        if len(password) < 6:
            return render_template('admin/user_form.html', error='密码至少 6 位')
        if role not in ('admin', 'user'):
            role = 'user'
        if User.query.filter_by(username=username).first():
            return render_template('admin/user_form.html', error='用户名已存在')

        user = User(username=username, nickname=nickname, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('admin.user_list'))

    return render_template('admin/user_form.html', user=None)


@admin.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_login_required
def edit_user(user_id):
    """编辑用户（重置密码、修改昵称/角色）"""
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip() or user.username
        role = request.form.get('role', user.role)
        new_password = request.form.get('password', '').strip()

        if role not in ('admin', 'user'):
            role = user.role
        user.nickname = nickname
        user.role = role
        if new_password:
            if len(new_password) < 6:
                return render_template('admin/user_form.html', user=user, error='密码至少 6 位')
            user.set_password(new_password)
        db.session.commit()
        return redirect(url_for('admin.user_list'))

    return render_template('admin/user_form.html', user=user)


@admin.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_login_required
def delete_user(user_id):
    """删除用户"""
    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        flash('不能删除默认管理员账户', 'error')
        return redirect(url_for('admin.user_list'))
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin.user_list'))