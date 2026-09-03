from flask import Blueprint, render_template, request, send_file, current_app, redirect, url_for, session, flash
from .models import db, Project, ConstructionLog, Message, User
from .utils.pdf_generator import generate_pdf_for_project
from werkzeug.security import generate_password_hash
import os

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