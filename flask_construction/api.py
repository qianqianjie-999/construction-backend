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

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@api.route('/projects', methods=['GET'])
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

@api.route('/logs', methods=['GET'])
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
def create_log():
    """创建新的施工日志，并处理照片上传"""
    # 1. 处理表单数据
    project_id = request.form['project_id']
    date_str = request.form['date']  # 格式: YYYY-MM-DD
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    
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
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # 为文件生成唯一名称，避免冲突
                unique_filename = f"{log.id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{filename}"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                
                photo = LogPhoto(
                    log_id=log.id,
                    filename=unique_filename,
                    original_filename=filename,
                    photo_type='site'  # 默认为现场照片
                )
                db.session.add(photo)
                photos.append(unique_filename)
    
    # 3. 处理合格证上传
    certificates = []
    if 'certificates' in request.files:
        files = request.files.getlist('certificates')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"cert_{log.id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{filename}"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                
                cert = LogPhoto(
                    log_id=log.id,
                    filename=unique_filename,
                    original_filename=filename,
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

@api.route('/photos/<filename>')
def uploaded_file(filename):
    """提供上传的照片访问"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@api.route('/export/logs', methods=['GET'])
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