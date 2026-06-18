"""Calendar export tool — build an iCalendar (.ics) all-day VEVENT from a day's
itinerary. Pure text generation, no external API/key. The app can hand the
returned .ics to the phone calendar ("导出至日历").
"""

from __future__ import annotations

import datetime

from langchain_core.tools import tool


def _ics_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


@tool
def save_to_calendar(title: str, date: str, summary: str = "") -> str:
    """把某天的行程生成可导入手机日历的 .ics 日历事件（全天事件）。

    适合用户说"加入日历/导出日历"时调用，返回标准 iCalendar 文本，App 可直接保存。

    Args:
        title: 事件标题，如"成都 Day1 · 宽窄巷子"。
        date: 日期，格式 YYYY-MM-DD。
        summary: 当天行程要点（可多行），作为事件描述。
    """
    try:
        try:
            start = datetime.date.fromisoformat(date.strip())
        except ValueError:
            return "日期格式应为 YYYY-MM-DD，例如 2026-07-01。"

        end = start + datetime.timedelta(days=1)  # all-day DTEND is exclusive
        ymd = start.strftime("%Y%m%d")
        uid = f"{ymd}-{abs(hash(title)) % 10_000_000}@muststart"

        ics = "\r\n".join(
            [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//MustStart//Trip Agent//CN",
                "CALSCALE:GREGORIAN",
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTART;VALUE=DATE:{ymd}",
                f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
                f"SUMMARY:{_ics_escape(title)}",
                f"DESCRIPTION:{_ics_escape(summary)}",
                "END:VEVENT",
                "END:VCALENDAR",
            ]
        )
        return (
            f"已为「{title}」（{date}）生成日历事件，可保存到手机日历：\n\n"
            f"```ics\n{ics}\n```"
        )
    except Exception as exc:  # noqa: BLE001 - tool must return a string to the LLM
        return f"日历生成失败：{exc}"
