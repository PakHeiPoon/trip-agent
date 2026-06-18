"""Traffic/routing tool — open-meteo geocoding + OSRM public router (free, no API key).

open-meteo geocoding resolves city/location names to coordinates.
OSRM (router.project-osrm.org) provides driving distance and duration.
"""

from __future__ import annotations

import httpx
from langchain_core.tools import tool

_GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
_OSRM_URL = "https://router.project-osrm.org/route/v1/driving"


def _geocode(name: str) -> tuple[float, float]:
    """Return (lat, lon) for a place name, or raise ValueError if not found."""
    geo = httpx.get(
        _GEO_URL, params={"name": name, "count": 1, "language": "zh"}, timeout=15
    ).json()
    results = geo.get("results")
    if not results:
        raise ValueError(f"未找到「{name}」的位置")
    r = results[0]
    return r["latitude"], r["longitude"]


def _format_duration(seconds: float) -> str:
    mins = int(seconds / 60)
    if mins < 60:
        return f"{mins} 分钟"
    hours, rem = divmod(mins, 60)
    return f"{hours} 小时 {rem} 分钟" if rem else f"{hours} 小时"


@tool
def get_traffic(origin: str, destination: str) -> str:
    """查询两地之间的驾车距离和预计时长。

    用于行程规划时估算路途耗时，辅助安排出发时间和交通方式。

    Args:
        origin: 出发地，如"成都"、"北京南站"。
        destination: 目的地，如"峨眉山"、"西安"。
    """
    try:
        olat, olon = _geocode(origin)
        dlat, dlon = _geocode(destination)

        resp = httpx.get(
            f"{_OSRM_URL}/{olon},{olat};{dlon},{dlat}",
            params={"overview": "false"},
            timeout=15,
        ).json()

        if resp.get("code") != "Ok" or not resp.get("routes"):
            return f"未能查到「{origin}」→「{destination}」的路线（OSRM：{resp.get('code', '未知错误')}）。"

        route = resp["routes"][0]
        distance_km = route["distance"] / 1000
        duration_str = _format_duration(route["duration"])

        return (
            f"「{origin}」→「{destination}」驾车路线：\n"
            f"- 距离：{distance_km:.1f} km\n"
            f"- 预计时长：{duration_str}\n"
            f"（数据来源：OSRM 开放路由，仅供参考）"
        )
    except Exception as exc:  # noqa: BLE001 - tool must return a string to the LLM
        return f"交通查询失败：{exc}"
