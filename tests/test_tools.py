"""Unit tests for the specialist tools (HTTP mocked — offline, hermetic)."""

from __future__ import annotations

import httpx
import agent.tools.traffic as traffic_mod
import agent.tools.vivo as vivo_mod
import agent.tools.weather as weather_mod
from agent.tools import get_traffic, get_weather, vivo_poi_search


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


# ---------------------------------------------------------------------------
# get_traffic tests
# ---------------------------------------------------------------------------

def _make_traffic_fake(distance_m: float, duration_s: float):
    """Return a monkeypatched httpx.get that simulates geocoding + OSRM responses."""

    call_count = {"n": 0}

    def fake_get(url, **kwargs):
        if "geocoding" in url:
            # Both origin and destination geocoding calls return plausible coords.
            call_count["n"] += 1
            coords = [
                {"latitude": 30.66, "longitude": 104.06},  # 成都
                {"latitude": 29.60, "longitude": 103.57},  # 峨眉山
            ]
            return _Resp({"results": [coords[min(call_count["n"] - 1, 1)]]})
        # OSRM route call
        return _Resp({
            "code": "Ok",
            "routes": [{"distance": distance_m, "duration": duration_s}],
        })

    return fake_get


def test_traffic_formats(monkeypatch):
    monkeypatch.setattr(traffic_mod.httpx, "get", _make_traffic_fake(152_000, 6_300))
    out = get_traffic.invoke({"origin": "成都", "destination": "峨眉山"})

    assert "成都" in out
    assert "峨眉山" in out
    assert "152.0 km" in out
    assert "1 小时 45 分钟" in out


def test_traffic_sub_hour(monkeypatch):
    monkeypatch.setattr(traffic_mod.httpx, "get", _make_traffic_fake(30_000, 1_800))
    out = get_traffic.invoke({"origin": "A", "destination": "B"})

    assert "30.0 km" in out
    assert "30 分钟" in out


def test_traffic_city_not_found(monkeypatch):
    def fake_get(url, **kwargs):
        if "geocoding" in url:
            return _Resp({"results": []})
        return _Resp({})

    monkeypatch.setattr(traffic_mod.httpx, "get", fake_get)
    out = get_traffic.invoke({"origin": "火星城市", "destination": "月球基地"})

    assert "交通查询失败" in out
    assert "火星城市" in out


def test_traffic_osrm_no_route(monkeypatch):
    call_count = {"n": 0}

    def fake_get(url, **kwargs):
        if "geocoding" in url:
            call_count["n"] += 1
            return _Resp({"results": [{"latitude": 0.0, "longitude": 0.0}]})
        return _Resp({"code": "NoRoute", "routes": []})

    monkeypatch.setattr(traffic_mod.httpx, "get", fake_get)
    out = get_traffic.invoke({"origin": "孤岛", "destination": "深海"})

    assert "未能查到" in out or "NoRoute" in out


def test_traffic_network_error(monkeypatch):
    def fake_get(url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(traffic_mod.httpx, "get", fake_get)
    out = get_traffic.invoke({"origin": "成都", "destination": "北京"})

    assert "交通查询失败" in out


def test_traffic_in_specialist_tools():
    from agent.tools import SPECIALIST_TOOLS, get_traffic as t
    assert t in SPECIALIST_TOOLS["planner"]
    assert t in SPECIALIST_TOOLS["pricing"]


# ---------------------------------------------------------------------------
# jump_ota tests — pure URL construction, no HTTP calls needed
# ---------------------------------------------------------------------------

from agent.tools.booking import jump_ota as jump_ota_fn  # noqa: E402


def test_jump_ota_flight():
    out = jump_ota_fn.invoke({"origin": "北京", "destination": "上海", "date": "2026-08-01", "kind": "flight"})
    assert "flights.ctrip.com" in out
    assert "fliggy.com" in out
    assert "北京" in out
    assert "上海" in out
    assert "2026-08-01" in out


def test_jump_ota_train():
    out = jump_ota_fn.invoke({"origin": "北京", "destination": "上海", "date": "2026-08-01", "kind": "train"})
    assert "trains.ctrip.com" in out
    assert "12306.cn" in out
    assert "北京" in out
    assert "上海" in out
    assert "2026-08-01" in out


def test_jump_ota_hotel():
    out = jump_ota_fn.invoke({"destination": "三亚", "date": "2026-08-01", "kind": "hotel"})
    assert "hotels.ctrip.com" in out
    assert "fliggy.com" in out
    assert "三亚" in out
    assert "2026-08-01" in out


def test_jump_ota_all():
    out = jump_ota_fn.invoke({"origin": "成都", "destination": "北京", "date": "2026-09-10"})
    assert "flights.ctrip.com" in out
    assert "trains.ctrip.com" in out
    assert "hotels.ctrip.com" in out
    assert "成都" in out
    assert "北京" in out
    assert "2026-09-10" in out


def test_jump_ota_no_destination():
    out = jump_ota_fn.invoke({"origin": "北京", "destination": ""})
    assert "目的地" in out


def test_jump_ota_invalid_kind():
    out = jump_ota_fn.invoke({"origin": "北京", "destination": "上海", "kind": "bus"})
    assert "无效" in out


def test_jump_ota_no_date():
    out = jump_ota_fn.invoke({"origin": "北京", "destination": "上海", "kind": "flight"})
    assert "flights.ctrip.com" in out
    assert "depdate=" not in out


def test_jump_ota_in_specialist_tools():
    from agent.tools import SPECIALIST_TOOLS, jump_ota as t
    assert t in SPECIALIST_TOOLS["planner"]
    assert t in SPECIALIST_TOOLS["pricing"]
