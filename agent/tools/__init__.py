"""Tool registry for the specialist Agents.

Maps each specialist id to the LangChain tools it may call. The graph wraps
tool-enabled specialists in ``create_react_agent`` so they can call these during
their reasoning; tool-less specialists fall back to a plain LLM call.
"""

from __future__ import annotations

from agent.tools.vivo import vivo_ocr, vivo_poi_search
from agent.tools.weather import get_weather

# specialist id -> tools it can use
SPECIALIST_TOOLS: dict[str, list] = {
    "planner": [vivo_poi_search, get_weather],   # 找真实景点/餐厅 + 看天气
    "contingency": [get_weather],                # 天气驱动的应急调整
    "pricing": [],                               # 预算估算暂不接工具
}

# All tools (e.g. for a future screenshot intake flow that uses vivo_ocr).
ALL_TOOLS = [vivo_poi_search, get_weather, vivo_ocr]

__all__ = ["SPECIALIST_TOOLS", "ALL_TOOLS", "vivo_poi_search", "get_weather", "vivo_ocr"]
