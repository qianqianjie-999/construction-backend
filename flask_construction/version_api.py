"""App 版本管理：公开查询接口 + APK 下载路由"""
import os
from datetime import datetime

from flask import Blueprint, jsonify, request, current_app, send_from_directory, abort
from .models import db, AppVersion

version_api = Blueprint('version_api', __name__)

# APK 文件存放目录（UPLOAD_FOLDER/app/）
APK_SUBDIR = 'app'


def _apk_dir():
    d = os.path.join(current_app.config['UPLOAD_FOLDER'], APK_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d


@version_api.route('/app/version', methods=['GET'])
def get_latest_version():
    """客户端检查更新：返回当前已发布的最新版本信息。

    无需鉴权。客户端传入 ?version_code=12 可由后端判断是否需要更新，
    但为简化，直接返回最新发布版本，客户端自行比较。
    """
    latest = (AppVersion.query
              .filter_by(is_published=True)
              .order_by(AppVersion.version_code.desc())
              .first())
    if not latest:
        return jsonify({'has_update': False}), 200

    # 客户端当前版本号（可选，用于后端判断 force_update）
    try:
        current_code = int(request.args.get('version_code', 0))
    except (TypeError, ValueError):
        current_code = 0

    # 是否需要强制更新：当前版本低于 min_version_code
    need_force = current_code > 0 and current_code < latest.min_version_code

    return jsonify({
        'has_update': True,
        'version_code': latest.version_code,
        'version_name': latest.version_name,
        'changelog': latest.changelog or '',
        'apk_size': latest.apk_size or 0,
        'force_update': latest.force_update or need_force,
        'min_version_code': latest.min_version_code,
        'apk_url': f'/api/app/download/{latest.apk_path}',
        'published_at': latest.published_at.strftime('%Y-%m-%d %H:%M:%S') if latest.published_at else None,
    }), 200


@version_api.route('/app/download/<path:filename>', methods=['GET'])
def download_apk(filename):
    """下载 APK 文件。

    直接返回文件流，供客户端下载安装。
    安全：只允许下载 APK 后缀文件，防止路径穿越读取其它文件。
    """
    # 防止路径穿越：只取文件名部分
    safe_name = os.path.basename(filename)
    if not safe_name.lower().endswith('.apk'):
        abort(404)

    apk_dir = _apk_dir()
    full_path = os.path.join(apk_dir, safe_name)
    if not os.path.isfile(full_path):
        abort(404)

    return send_from_directory(
        apk_dir,
        safe_name,
        as_attachment=True,
        download_name=safe_name,
        mimetype='application/vnd.android.package-archive',
    )
