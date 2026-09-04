from flask import Blueprint, request, jsonify, current_app, send_from_directory, session, send_file
import os
from werkzeug.utils import secure_filename
from .models import db, Project, ConstructionLog, LogPhoto, User
from datetime import datetime
from .utils.pdf_generator import generate_pdf_for_project

# 创建一个蓝图 (blueprint)
api = Blueprint('api', __name__)

# 认证装饰器
from .auth import login_required

# 配置上传文件夹
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# 图片魔数签名（文件头字节），用于校验真实内容类型
IMAGE_SIGNATURES = {
    b'\xff\xd8\xff': 'jpg',          # JPEG
    b'\x89PNG\r\n\x1a\n': 'png',     # PNG
    b'GIF87a': 'gif',                # GIF87a
    b'GIF89a': 'gif',                # GIF89a
}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sniff_image_type(head):
    """根据文件头魔数判断真实图片类型，返回 'jpg'/'png'/'gif' 或 None"""
    for sig, typ in IMAGE_SIGNATURES.items():
        if head.startswith(sig):
            return typ
    return None


def validate_image(file_storage):
    """校验上传文件：扩展名 + 真实内容类型（魔数），防止伪装文件上传"""
    if not file_storage or not allowed_file(file_storage.filename):
        return False
    head = file_storage.stream.read(32)
    file_storage.stream.seek(0)  # 重置指针，便于后续 save
    return sniff_image_type(head) is not None


def save_uploaded_file(file_storage, prefix=''):
    """安全保存上传文件，返回唯一文件名；校验失败返回 None"""
    if not validate_image(file_storage):
        return None
    filename = secure_filename(file_storage.filename)
    unique_filename = f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{filename}"
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    file_storage.save(file_path)
    return unique_filename

@api.route('/projects', methods=['GET'])
@login_required
def get_projects():
    """获取所有项目列表"""
    projects = Project.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'location': p.location,
        'company': p.company,
        'manager': p.manager
    } for p in projects])

@api.route('/projects', methods=['POST'])
@login_required
def create_project():
    """创建新项目"""
    data = request.get_json()
    project = Project(
        name=data['name'],
        location=data.get('location', ''),
        company=data.get('company', ''),
        manager=data.get('manager', '')
    )
    db.session.add(project)
    db.session.commit()
    return jsonify({'id': project.id, 'message': 'Project created'}), 201

@api.route('/projects/<int:project_id>', methods=['DELETE'])
@login_required
def delete_project(project_id):
    """删除项目（级联删除关联的日志、照片、聊天消息及其磁盘文件）"""
    project = Project.query.get_or_404(project_id)

    # 1. 删除磁盘文件：日志照片 + 聊天图片 + 聊天文件（数据库由级联删除处理）
    from .utils.files import remove_project_files
    remove_project_files(project, current_app.config['UPLOAD_FOLDER'])

    # 2. 级联删除（SQLAlchemy relationship cascade 会处理）
    db.session.delete(project)
    db.session.commit()
    return jsonify({'message': '项目已删除'}), 200

@api.route('/logs', methods=['GET'])
@login_required
def get_logs():
    """获取指定项目的日志列表"""
    project_id = request.args.get('project_id')
    if project_id:
        logs = ConstructionLog.query.filter_by(project_id=int(project_id)).order_by(ConstructionLog.date.desc()).all()
    else:
        logs = ConstructionLog.query.order_by(ConstructionLog.date.desc()).all()

    result = []
    for log in logs:
        log_data = {
            'id': log.id,
            'project_id': log.project_id,
            'date': log.date.strftime('%Y-%m-%d'),
            'weather': log.weather or '',
            'temperature': log.temperature or '',
            'wind_force': log.wind_force or '',
            'wind_direction': log.wind_direction or '',
            'construction_part': log.construction_part or '',
            'construction_content': log.work_content or '',
            'progress': log.progress or '',
            'construction_record': log.personnel or '',
            'technical_safety_record': log.safety_notes or '',
            'material_record': log.materials or '',
            'project_manager': log.project_manager or '',
            'recorder': log.recorder or '',
            'photos': [{
                'id': photo.id,
                'filename': photo.filename,
                'original_filename': photo.original_filename,
                'photo_type': photo.photo_type,
                'url': f'/api/photos/{photo.filename}'
            } for photo in log.photos]
        }
        result.append(log_data)

    return jsonify(result)

@api.route('/logs', methods=['POST'])
@login_required
def create_log():
    """创建新的施工日志，并处理照片上传"""
    # 1. 处理表单数据
    project_id = request.form.get('project_id')
    date_str = request.form.get('date')  # 格式: YYYY-MM-DD
    if not project_id or not date_str:
        return jsonify({'error': 'project_id and date are required'}), 400
    try:
        project_id = int(project_id)
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return jsonify({'error': 'invalid project_id or date format'}), 400
    
    log = ConstructionLog(
        project_id=project_id,
        date=date_obj,
        weather=request.form.get('weather', ''),
        temperature=request.form.get('temperature', ''),
        wind_force=request.form.get('wind_force', ''),
        wind_direction=request.form.get('wind_direction', ''),
        construction_part=request.form.get('construction_part', ''),
        work_content=request.form.get('construction_content', ''),
        progress=request.form.get('progress', ''),
        personnel=request.form.get('construction_record', ''),
        safety_notes=request.form.get('technical_safety_record', ''),
        materials=request.form.get('material_record', ''),
        project_manager=request.form.get('project_manager', ''),
        recorder=request.form.get('recorder', '')
    )
    db.session.add(log)
    db.session.flush()  # 获取临时ID以关联照片
    
    # 2. 处理照片上传
    photos = []
    if 'photos' in request.files:
        files = request.files.getlist('photos')
        for file in files:
            if file:
                unique_filename = save_uploaded_file(file, prefix=f"{log.id}_")
                if not unique_filename:
                    continue  # 校验失败的文件跳过
                original = secure_filename(file.filename)
                photo = LogPhoto(
                    log_id=log.id,
                    filename=unique_filename,
                    original_filename=original,
                    photo_type='site'  # 默认为现场照片
                )
                db.session.add(photo)
                photos.append(unique_filename)
    
    # 3. 处理合格证上传
    certificates = []
    if 'certificates' in request.files:
        files = request.files.getlist('certificates')
        for file in files:
            if file:
                unique_filename = save_uploaded_file(file, prefix=f"cert_{log.id}_")
                if not unique_filename:
                    continue
                original = secure_filename(file.filename)
                cert = LogPhoto(
                    log_id=log.id,
                    filename=unique_filename,
                    original_filename=original,
                    photo_type='certificate'
                )
                db.session.add(cert)
                certificates.append(unique_filename)
    
    db.session.commit()
    
    return jsonify({
        'log_id': log.id,
        'uploaded_photos': photos,
        'uploaded_certificates': certificates,
        'message': 'Log and photos uploaded successfully'
    }), 201


@api.route('/logs/<int:log_id>', methods=['PUT'])
@login_required
def update_log(log_id):
    """更新施工日志的文字字段（照片不在此接口处理）"""
    log = ConstructionLog.query.get_or_404(log_id)

    # 日期
    date_str = request.form.get('date')
    if date_str:
        try:
            log.date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'invalid date format'}), 400

    log.weather = request.form.get('weather', log.weather)
    log.temperature = request.form.get('temperature', log.temperature)
    log.wind_force = request.form.get('wind_force', log.wind_force)
    log.wind_direction = request.form.get('wind_direction', log.wind_direction)
    log.construction_part = request.form.get('construction_part', log.construction_part)
    log.work_content = request.form.get('construction_content', log.work_content)
    log.progress = request.form.get('progress', log.progress)
    log.personnel = request.form.get('construction_record', log.personnel)
    log.safety_notes = request.form.get('technical_safety_record', log.safety_notes)
    log.materials = request.form.get('material_record', log.materials)
    log.project_manager = request.form.get('project_manager', log.project_manager)
    log.recorder = request.form.get('recorder', log.recorder)

    db.session.commit()
    return jsonify({'message': 'Log updated successfully', 'log_id': log.id})


@api.route('/photos/<filename>')
def uploaded_file(filename):
    """提供上传的照片访问（公开访问，浏览器 img 标签不需要 token）"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@api.route('/export/logs', methods=['GET'])
@login_required
def export_logs():
    """导出施工日志为PDF格式"""
    project_id = request.args.get('project_id')
    format = request.args.get('format', 'pdf')
    
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400
    
    try:
        project = Project.query.get_or_404(int(project_id))
        
        if format.lower() == 'pdf':
            pdf_buffer = generate_pdf_for_project(project)
            if pdf_buffer is None:
                return jsonify({'error': 'PDF generation failed'}), 500
            
            pdf_buffer.seek(0)
            filename = f"{project.name}_施工日志.pdf"
            
            return send_file(
                pdf_buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )
        else:
            return jsonify({'error': f'Unsupported format: {format}'}), 400
            
    except Exception as e:
        print(f"Export error: {e}")
        return jsonify({'error': str(e)}), 500