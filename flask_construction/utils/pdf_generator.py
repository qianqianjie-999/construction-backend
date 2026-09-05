from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from xml.sax.saxutils import escape
from io import BytesIO
import os
from flask import current_app

# 注册中文字体
def register_chinese_fonts():
    """注册中文字体，优先用系统字体，fallback 到 reportlab 内置 CID 字体"""
    # 1. 尝试系统字体（效果更好）
    font_paths = [
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc',
        '/usr/share/fonts/chinese/STHeiti.ttf',
        '/System/Library/Fonts/PingFang.ttc',
        'C:\\Windows\\Fonts\\simhei.ttf',
        'C:\\Windows\\Fonts\\simsun.ttc',
    ]
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('Chinese', font_path))
                return 'Chinese'
            except:
                pass

    # 2. Fallback: reportlab 内置 CID 字体（STSong-Light，无需系统装任何字体）
    try:
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        return 'STSong-Light'
    except:
        pass
    return None

def generate_pdf_for_project(project):
    """
    为给定的项目生成施工日志 PDF，按照标准格式输出。
    不包含照片，内容铺满A4纸。
    一个项目有多条日志时，每条日志占一页，全部输出在同一个 PDF 里。
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=25, rightMargin=25, topMargin=30, bottomMargin=30)
    story = []

    # 注册中文字体
    cn_font = register_chinese_fonts() or 'Helvetica'

    styles = getSampleStyleSheet()

    # 创建中文字体样式
    if cn_font != 'Helvetica':
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=cn_font,
            fontSize=24,
            spaceAfter=25,
            alignment=1  # Center
        )
        normal_style = ParagraphStyle(
            'ChineseNormal',
            parent=styles['Normal'],
            fontName=cn_font,
            fontSize=11,
            leading=18,
        )
    else:
        title_style = styles['Heading1']
        normal_style = styles['Normal']

    # 单元格文本样式：自动换行，不溢出框
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontName=cn_font,
        fontSize=11,
        leading=16,
        alignment=0,  # LEFT
    )

    def _para(text):
        """把长文本转成可自动换行的 Paragraph，处理特殊字符与换行符"""
        t = escape(text if text else '-')
        t = t.replace('\n', '<br/>')
        return Paragraph(t, cell_style)

    # 遍历项目下的所有日志，按日期升序排列
    sorted_logs = sorted(project.logs, key=lambda x: x.date)

    for i, log in enumerate(sorted_logs):
        # 标题：施工日志
        title = Paragraph("施工日志", title_style)
        story.append(title)
        story.append(Spacer(1, 12))

        # 日期和天气信息表格 - 总宽度540，与下面内容区等宽
        weekday_map = {0: '星期一', 1: '星期二', 2: '星期三', 3: '星期四', 4: '星期五', 5: '星期六', 6: '星期日'}
        weekday = weekday_map.get(log.date.weekday(), '')

        date_info_data = [
            ['日期', log.date.strftime('%Y 年 %m 月 %d 日'), '星期', weekday, '天气', log.weather or '-'],
            ['气温', log.temperature or '-', '风力', log.wind_force or '-', '风向', log.wind_direction or '-'],
        ]

        date_info_table = Table(date_info_data, colWidths=[70, 140, 70, 90, 70, 100])  # 总宽度540
        date_info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), cn_font),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (0, 1), colors.lightgrey),
            ('BACKGROUND', (2, 0), (2, 1), colors.lightgrey),
            ('BACKGROUND', (4, 0), (4, 1), colors.lightgrey),
        ]))
        story.append(date_info_table)
        story.append(Spacer(1, 8))

        # 当日工程信息表格 - 总宽度540，与下面内容区等宽
        work_info_data = [
            ['当日工程施工部位', '当日工程施工内容', '当日工程形象进度'],
            [_para(log.construction_part), _para(log.work_content), _para(log.progress)],
        ]

        work_info_table = Table(work_info_data, colWidths=[180, 180, 180])  # 总宽度540
        work_info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), cn_font),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('VALIGN', (0, 1), (-1, 1), 'TOP'),
        ]))
        story.append(work_info_table)
        story.append(Spacer(1, 8))

        # 施工情况记录 - 增加高度填充页面
        construction_record_data = [
            ['施工情况记录（部位项目、机械作业、班组工作、施工存在问题等）：'],
            [_para(log.personnel)],
            [''],
            [''],
            [''],
        ]

        construction_record_table = Table(construction_record_data, colWidths=[540])
        construction_record_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), cn_font),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(construction_record_table)
        story.append(Spacer(1, 6))

        # 技术质量安全工作记录 - 增加高度填充页面
        tech_safety_data = [
            ['技术质量安全工作记录（技术质量安全活动、技术质量安全问题、检查评定验收等）：'],
            [_para(log.safety_notes)],
            [''],
            [''],
            [''],
        ]

        tech_safety_table = Table(tech_safety_data, colWidths=[540])
        tech_safety_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), cn_font),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(tech_safety_table)
        story.append(Spacer(1, 6))

        # 今日材料进场记录 - 增加高度填充页面
        material_data = [
            ['今日材料、构配件进场、检（试）验情况记录'],
            [_para(log.materials)],
            [''],
            [''],
            [''],
        ]

        material_table = Table(material_data, colWidths=[540])
        material_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), cn_font),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(material_table)
        story.append(Spacer(1, 6))

        # 工程负责人和记录人 - 总宽度540，与上面内容区等宽
        sign_data = [
            ['工程负责人', log.project_manager or '-', '记录人', log.recorder or '-'],
        ]

        sign_table = Table(sign_data, colWidths=[100, 170, 100, 170])  # 总宽度540
        sign_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), cn_font),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            # 只保留外边框
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (0, 0), colors.lightgrey),
            ('BACKGROUND', (2, 0), (2, 0), colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(sign_table)

        # 每个日志之间分页（最后一条日志后不分页）
        if i < len(sorted_logs) - 1:
            story.append(PageBreak())

    try:
        doc.build(story)
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"PDF generation error: {e}")
        return None
