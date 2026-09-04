# -*- coding: utf-8 -*-
"""
时间工具：数据库统一存 naive UTC（datetime.utcnow），展示层统一转北京时间。

原先 models.py 与 app.py 各自实现了一份转换逻辑，容易不一致；
现在统一从这里取，模型/API/模板过滤器共用。
"""
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))


def to_cst(dt):
    """把 naive UTC 或带时区的 datetime 统一转成北京时间（CST, UTC+8）；None 返回 None"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)  # 数据库存的是 naive UTC
    return dt.astimezone(CST)


def fmt_beijing(dt, fmt='%Y-%m-%d %H:%M:%S', default='-'):
    """格式化北京时间字符串；dt 为 None 时返回 default"""
    cst = to_cst(dt)
    if cst is None:
        return default
    return cst.strftime(fmt)
