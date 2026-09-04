# -*- coding: utf-8 -*-
"""
项目删除时清理磁盘文件（日志照片 + 聊天图片 + 聊天文件）。

供 api.py 与 admin_views.py 的 delete_project 复用，避免两处重复且
漏掉聊天文件（聊天磁盘文件此前会变孤儿）。只负责删文件，不碰数据库。
"""
import json
import os


def _safe_remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass  # 文件已被删/无权限都忽略，删除流程不因此中断


def remove_project_files(project, upload_folder):
    """删除一个项目所有关联的磁盘文件：日志照片、聊天图片、聊天文件"""
    # 1) 施工日志照片（site + certificate）
    for log in project.logs:
        for photo in log.photos:
            _safe_remove(os.path.join(upload_folder, photo.filename))

    # 2) 聊天消息引用的图片/文件
    for msg in project.messages:
        if msg.content_type == 'image':
            if msg.content:
                _safe_remove(os.path.join(upload_folder, msg.content))
        elif msg.content_type == 'file':
            path = None
            if msg.content:
                try:
                    meta = json.loads(msg.content)
                    path = meta.get('path') if isinstance(meta, dict) else None
                except (ValueError, AttributeError):
                    path = None
            if path:
                _safe_remove(os.path.join(upload_folder, os.path.basename(str(path))))
