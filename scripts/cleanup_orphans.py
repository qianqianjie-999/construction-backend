#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
孤儿文件清理脚本（施工日志系统）

背景：删除项目/日志时只清理了日志照片与数据库记录，聊天图片/文件的
磁盘文件、以及上传中断产生的残留文件不会自动删除。本脚本对比数据库
引用（日志照片 + 聊天图片 + 聊天文件 path），找出 uploads/ 里没有被
任何记录引用的文件。

安全设计：
  - 默认 dry-run，只列出不删除；确认无误后加 --apply 才会真正删除
  - --min-age-days 默认 1 天：只清理 mtime 超过该时长的文件，
    避免误删"正在上传/刚写入"的文件

用法：
  # 1) 先看会删什么（连接数据库，只读扫描）
  python3 scripts/cleanup_orphans.py --uploads /srv/construction-backend/uploads

  # 2) 确认列表无误后真正删除
  python3 scripts/cleanup_orphans.py --uploads /srv/construction-backend/uploads --apply

  # 3) 配合备份脚本放进 crontab（每周一次 + --apply）：
  #    15 3 * * 1 cd /srv/construction-backend && python3 scripts/cleanup_orphans.py --apply >> logs/cleanup.log 2>&1
"""
import argparse
import json
import os
import sys
import time

# 让脚本可以从项目根目录或 scripts/ 下执行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from flask_construction.models import LogPhoto, Message  # noqa: E402


def collect_referenced(app):
    """收集所有被数据库记录引用的文件名集合"""
    referenced = set()
    with app.app_context():
        # 1) 施工日志照片
        for row in LogPhoto.query.with_entities(LogPhoto.filename).all():
            if row[0]:
                referenced.add(row[0])

        # 2) 聊天图片（content 即文件名）
        for row in (
            Message.query.with_entities(Message.content)
            .filter(Message.content_type == 'image')
            .all()
        ):
            if row[0]:
                referenced.add(row[0])

        # 3) 聊天文件（content 为 JSON：{"name":…, "path":服务器文件名, …}）
        for row in (
            Message.query.with_entities(Message.content)
            .filter(Message.content_type == 'file')
            .all()
        ):
            if not row[0]:
                continue
            try:
                meta = json.loads(row[0])
                path = meta.get('path') if isinstance(meta, dict) else None
            except (ValueError, AttributeError):
                path = None
            if path:
                referenced.add(os.path.basename(str(path)))
    return referenced


def main():
    parser = argparse.ArgumentParser(description='清理 uploads 目录中的孤儿文件')
    parser.add_argument('--uploads', default=os.environ.get('UPLOAD_FOLDER', 'uploads'),
                        help='uploads 目录路径（默认取 UPLOAD_FOLDER 环境变量或 ./uploads）')
    parser.add_argument('--apply', action='store_true',
                        help='真正删除（不加则只 dry-run 列出）')
    parser.add_argument('--min-age-days', type=int, default=1,
                        help='只清理 mtime 早于该天数的文件（默认 1 天，防误删上传中文件）')
    args = parser.parse_args()

    uploads = os.path.abspath(args.uploads)
    if not os.path.isdir(uploads):
        print(f'[错误] uploads 目录不存在: {uploads}')
        sys.exit(1)

    app = create_app(os.environ.get('FLASK_CONFIG', 'production'))
    referenced = collect_referenced(app)
    print(f'数据库引用文件数: {len(referenced)}')

    cutoff = time.time() - args.min_age_days * 86400
    orphans = []
    total_bytes = 0
    for entry in os.scandir(uploads):
        if not entry.is_file():
            continue
        name = entry.name
        if name in referenced:
            continue
        # 跳过近期文件（可能是刚上传、事务未落库）
        if entry.stat().st_mtime > cutoff:
            continue
        orphans.append(entry)
        total_bytes += entry.stat().st_size

    if not orphans:
        print('没有发现孤儿文件 ✓')
        return

    print(f'发现 {len(orphans)} 个孤儿文件，共 {total_bytes / 1048576:.1f} MB：')
    for entry in sorted(orphans, key=lambda e: e.name):
        print(f'  - {entry.name} ({entry.stat().st_size / 1024:.1f} KB)')

    if not args.apply:
        print('\n[dry-run] 未删除任何文件。确认无误后加 --apply 执行。')
        return

    removed = 0
    for entry in orphans:
        try:
            os.remove(entry.path)
            removed += 1
        except OSError as e:
            print(f'  [失败] {entry.name}: {e}')
    print(f'已删除 {removed}/{len(orphans)} 个孤儿文件')


if __name__ == '__main__':
    main()
