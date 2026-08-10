"""Current local date/time tool."""

from __future__ import annotations

from datetime import datetime


_WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def get_current_time() -> str:
    now = datetime.now().astimezone()
    weekday = _WEEKDAYS[now.weekday()]
    return (
        f"本地时间: {now.strftime('%Y-%m-%d %H:%M:%S')} "
        f"({weekday}, tz={now.tzname() or now.strftime('%z')})"
    )
