"""Unit tests for the specialist tools (HTTP mocked — offline, hermetic)."""

from __future__ import annotations

import agent.tools.vivo as vivo_mod
import agent.tools.weather as weather_mod
from agent.tools import get_weather, vivo_poi_search


class _Resp:
    def __init__(self, data: dict) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._data


def test_poi_search_formats(monkeypatch):
    monkeypatch.setenv("VIVO_API_KEY", "test-key")

    def fake_get(url, **kwargs):
        return _Resp(
            {
                "pois": [
                    {
                        "name": "成都大熊猫繁育研究基地",
                        "typeName": "动物园",
                        "address": "外北熊猫大道1375号",
                        "phone": "028-83510033",
                        "location": "104.14,30.73",
                    }
                ]
            }
        )

    monkeypatch.setattr(vivo_mod.httpx, "get", fake_get)
    out = vivo_poi_search.invoke({"keywords": "熊猫基地", "city": "成都市"})

    assert "成都大熊猫繁育研究基地" in out
    assert "动物园" in out
    assert "104.14,30.73" in out


def test_poi_search_requires_key(monkeypatch):
    monkeypatch.delenv("VIVO_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    out = vivo_poi_search.invoke({"keywords": "x", "city": "成都市"})
    assert "未配置" in out


def test_weather_formats(monkeypatch):
    def fake_get(url, **kwargs):
        if "geocoding" in url:
            return _Resp({"results": [{"latitude": 30.66, "longitude": 104.06}]})
        return _Resp(
            {
                "daily": {
                    "time": ["2026-06-15"],
                    "weathercode": [61],
                    "temperature_2m_max": [28.0],
                    "temperature_2m_min": [20.0],
                    "precipitation_sum": [5.0],
                }
            }
        )

    monkeypatch.setattr(weather_mod.httpx, "get", fake_get)
    out = get_weather.invoke({"city": "成都", "days": 1})

    assert "成都" in out
    assert "小雨" in out
    assert "20.0~28.0" in out
