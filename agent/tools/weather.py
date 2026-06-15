"""Weather tool — open-meteo (free, no API key).

Weather is not a vivo capability (per the 觅途 PPT it is a 第三方/系统能力), so we
use open-meteo's free geocoding + forecast APIs. Real data, no key required.
"""

from __future__ import annotations

import httpx
from langchain_core.tools import tool

_GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes -> 中文描述
_WMO: dict[int, str] = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "米雪",
    80: "小阵雨", 81: "阵雨", 82: "强阵雨",
    85: "小阵雪", 86: "大阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "强雷阵雨伴冰雹",
}


@tool
def get_weather(city: str, days: int = 3) -> str:
    """查询某城市未来几天的天气预报（天气状况/气温/降水）。

    用于天气敏感的行程规划与应急调整（如下雨改室内行程）。

    Args:
        city: 城市名，如"成都"、"杭州"。
        days: 预报天数，1-7，默认 3。
    """
    days = max(1, min(7, days))
    try:
        geo = httpx.get(
            _GEO_URL, params={"name": city, "count": 1, "language": "zh"}, timeout=15
        ).json()
        results = geo.get("results")
        if not results:
            return f"未找到城市「{city}」的位置。"
        lat, lon = results[0]["latitude"], results[0]["longitude"]

        data = httpx.get(
            _FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum",
                "forecast_days": days,
                "timezone": "auto",
            },
            timeout=15,
        ).json()["daily"]
    except Exception as exc:  # noqa: BLE001 - tool must return a string to the LLM
        return f"天气查询失败：{exc}"

    lines = [f"{city}未来{days}天天气预报："]
    for i, date in enumerate(data["time"]):
        desc = _WMO.get(data["weathercode"][i], "未知")
        tmin = data["temperature_2m_min"][i]
        tmax = data["temperature_2m_max"][i]
        precip = data["precipitation_sum"][i]
        lines.append(f"- {date}：{desc}，{tmin}~{tmax}°C，降水 {precip}mm")
    return "\n".join(lines)
