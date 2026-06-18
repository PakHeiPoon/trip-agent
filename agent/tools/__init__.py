"""Tool registry for the specialist Agents.

Maps each specialist id to the LangChain tools it may call. The graph wraps
tool-enabled specialists in ``create_react_agent`` so they can call these during
their reasoning; tool-less specialists fall back to a plain LLM call.
"""

from __future__ import annotations

from agent.tools.booking import jump_ota
from agent.tools.calendar import save_to_calendar
from agent.tools.traffic import get_traffic
from agent.tools.vivo import vivo_ocr, vivo_poi_search
from agent.tools.weather import get_weather

# specialist id -> tools it can use
SPECIALIST_TOOLS: dict[str, list] = {
    # 找真实景点/餐厅 + 看天气 + 交通距离 + 预订链接 + 导出日历
    "planner": [vivo_poi_search, get_weather, get_traffic, jump_ota, save_to_calendar],
    "contingency": [get_weather],                  # 天气驱动的应急调整
    "pricing": [get_traffic, jump_ota],            # 交通距离辅助费用估算 + 预订入口
}

# All tools (e.g. for a future screenshot intake flow that uses vivo_ocr).
ALL_TOOLS = [vivo_poi_search, get_weather, vivo_ocr, get_traffic, jump_ota, save_to_calendar]

__all__ = [
    "SPECIALIST_TOOLS", "ALL_TOOLS",
    "vivo_poi_search", "get_weather", "vivo_ocr",
    "get_traffic", "jump_ota", "save_to_calendar",
]
