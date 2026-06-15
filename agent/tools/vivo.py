"""vivo native tools — POI(LBS) search and OCR.

Verified against the vivo AIGC platform (2026-06):
    POI : GET  https://api-ai.vivo.com.cn/search/geo
          query: keywords, city, page_size, requestId   | Bearer auth
    OCR : POST https://api-ai.vivo.com.cn/ocr/general_recognition
          form: image(base64), pos, businessid="aigc"+AppId | Bearer auth | query requestId

Config (Backend/.env):
    VIVO_API_KEY   the AppKey (Bearer)
    VIVO_APP_ID    the numeric AppId (used to build the OCR businessid)
"""

from __future__ import annotations

import os
import uuid

import httpx
from langchain_core.tools import tool

VIVO_BASE = "https://api-ai.vivo.com.cn"


def _api_key() -> str:
    return os.getenv("VIVO_API_KEY") or os.getenv("LLM_API_KEY", "")


@tool
def vivo_poi_search(keywords: str, city: str) -> str:
    """搜索某城市的地点（POI），返回名称/地址/类型/坐标/电话。

    用于查找景点、餐厅、酒店、车站等真实地点信息以辅助行程规划。

    Args:
        keywords: 关键字，如"熊猫基地"、"火锅"、"地铁站"。
        city: 城市名或行政区划编码，如"成都市"或"510100"。
    """
    key = _api_key()
    if not key:
        return "POI 搜索不可用：未配置 VIVO_API_KEY。"

    try:
        resp = httpx.get(
            f"{VIVO_BASE}/search/geo",
            params={
                "keywords": keywords,
                "city": city,
                "page_size": 5,
                "requestId": str(uuid.uuid4()),
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            timeout=15,
        )
        resp.raise_for_status()
        pois = resp.json().get("pois", [])[:5]
    except Exception as exc:  # noqa: BLE001 - tool must return a string to the LLM
        return f"POI 搜索失败：{exc}"

    if not pois:
        return f"未找到与「{keywords}」相关的地点。"

    lines = [f"「{keywords}」在{city}的相关地点："]
    for p in pois:
        seg = f"- {p.get('name', '')}（{p.get('typeName', '未知类型')}）地址：{p.get('address', '')}"
        if p.get("phone"):
            seg += f"，电话：{p['phone']}"
        if p.get("location"):
            seg += f"，坐标：{p['location']}"
        lines.append(seg)
    return "\n".join(lines)


@tool
def vivo_ocr(image_base64: str) -> str:
    """识别图片中的文字（OCR）。输入图片的 base64 编码（jpg/png/bmp），返回识别出的文本。

    用于解析用户上传的攻略截图、票据等图文内容。

    Args:
        image_base64: 图片的 base64 编码字符串（不含 data: 前缀）。
    """
    key = _api_key()
    if not key:
        return "OCR 不可用：未配置 VIVO_API_KEY。"

    business_id = "aigc" + os.getenv("VIVO_APP_ID", "")
    try:
        resp = httpx.post(
            f"{VIVO_BASE}/ocr/general_recognition",
            params={"requestId": str(uuid.uuid4())},
            data={"image": image_base64, "pos": 2, "businessid": business_id},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Bearer {key}",
            },
            timeout=20,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001 - tool must return a string to the LLM
        return f"OCR 失败：{exc}"

    if str(payload.get("error_code", "0")) not in {"0", "None"}:
        return f"OCR 识别失败：{payload.get('error_msg', '未知错误')}"

    return _extract_ocr_text(payload.get("result", {})) or "未识别到文字。"


def _extract_ocr_text(result: dict) -> str:
    """Pull plain text out of an OCR result (pos=2 returns 'OCR'/'words' lists)."""
    items = result.get("OCR") or result.get("words") or []
    words = [it.get("words", "") for it in items if isinstance(it, dict)]
    return "\n".join(w for w in words if w)
