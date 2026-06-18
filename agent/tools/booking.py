"""Booking deep-link tool — pure URL construction, no external API key required.

Generates clickable search/booking URLs for Ctrip (携程), 12306, and Fliggy (飞猪).
URL formats may change; the tool degrades gracefully when exact deep-links are
unavailable.
"""

from __future__ import annotations

from urllib.parse import quote

from langchain_core.tools import tool

# Ctrip 3-letter domestic city codes used in flight search URLs.
# Source: flights.ctrip.com/online/list/oneway-{dep}-{arr}?depdate={YYYY-MM-DD}
# Unknown cities fall back to URL-encoded city name (less precise but usually opens search).
_CITY_CODES: dict[str, str] = {
    "北京": "bjs", "上海": "sha", "成都": "ctu", "广州": "can",
    "深圳": "szx", "杭州": "hgh", "重庆": "ckg", "西安": "xiy",
    "武汉": "wuh", "南京": "nkj", "厦门": "xmn", "三亚": "syx",
    "昆明": "kmg", "青岛": "tao", "哈尔滨": "hrb", "沈阳": "she",
    "大连": "dlc", "郑州": "cgo", "天津": "tsn", "长沙": "csx",
    "贵阳": "kwe", "南宁": "nng", "乌鲁木齐": "urc", "拉萨": "lxa",
    "呼和浩特": "hld", "海口": "hak", "福州": "foc", "南昌": "khn",
    "合肥": "hfe", "太原": "tyn", "石家庄": "sjw", "长春": "cgq",
    "兰州": "lhw", "银川": "inc", "西宁": "xnn",
}


def _city_code(city: str) -> str:
    """Return Ctrip flight city code if known, else URL-encode the raw city name."""
    return _CITY_CODES.get(city, quote(city))


def _flight_links(origin: str, destination: str, date: str) -> list[str]:
    dep = _city_code(origin)
    arr = _city_code(destination)
    # Ctrip oneway: flights.ctrip.com/online/list/oneway-{dep}-{arr}?depdate={YYYY-MM-DD}
    ctrip_url = f"https://flights.ctrip.com/online/list/oneway-{dep}-{arr}"
    if date:
        ctrip_url += f"?depdate={date}"
    # Fliggy: fliggy.com/channel/flight.htm?from={city}&to={city}&date={YYYY-MM-DD}&type=OW
    fliggy_url = (
        f"https://www.fliggy.com/channel/flight.htm"
        f"?from={quote(origin)}&to={quote(destination)}&type=OW"
    )
    if date:
        fliggy_url += f"&date={date}"
    return [
        f"[携程机票：{origin}→{destination}]({ctrip_url})",
        f"[飞猪机票：{origin}→{destination}]({fliggy_url})",
    ]


def _train_links(origin: str, destination: str, date: str) -> list[str]:
    # Ctrip train: trains.ctrip.com/webapp/train/list
    # ?fromStationName={city}&toStationName={city}&depDate={YYYY-MM-DD}
    ctrip_params = (
        f"fromStationName={quote(origin)}&toStationName={quote(destination)}"
    )
    if date:
        ctrip_params += f"&depDate={date}"
    ctrip_url = f"https://trains.ctrip.com/webapp/train/list?{ctrip_params}"
    # 12306: kyfw.12306.cn/otn/leftTicket/init pre-fills the search form.
    # Users must be logged in to purchase; this link opens the query page.
    params_12306 = (
        f"linktypeid=dc"
        f"&fromStationName={quote(origin)}&toStationName={quote(destination)}"
        f"&purpose_codes=ADULT"
    )
    if date:
        params_12306 += f"&depart_date={date}"
    url_12306 = f"https://kyfw.12306.cn/otn/leftTicket/init?{params_12306}"
    return [
        f"[携程火车票：{origin}→{destination}]({ctrip_url})",
        f"[12306：{origin}→{destination}]({url_12306})",
    ]


def _hotel_links(destination: str, date: str) -> list[str]:
    # Ctrip hotel: hotels.ctrip.com/hotel/?city={city}&checkin={YYYY-MM-DD}
    ctrip_url = f"https://hotels.ctrip.com/hotel/?city={quote(destination)}"
    if date:
        ctrip_url += f"&checkin={date}"
    # Fliggy hotel: hotels.fliggy.com/hotel/search?city={city}&checkin={YYYY-MM-DD}
    fliggy_url = f"https://hotels.fliggy.com/hotel/search?city={quote(destination)}"
    if date:
        fliggy_url += f"&checkin={date}"
    return [
        f"[携程酒店：{destination}]({ctrip_url})",
        f"[飞猪酒店：{destination}]({fliggy_url})",
    ]


@tool
def jump_ota(origin: str = "", destination: str = "", date: str = "", kind: str = "all") -> str:
    """生成携程/12306/飞猪 搜索/预订跳转链接（Markdown 格式，可直接点击）。

    纯 URL 构造，不需要任何 API Key。适合在攻略末尾给用户提供「去预订」的快捷入口。
    URL 参数说明：
    - 携程机票 flights.ctrip.com/online/list/oneway-{dep}-{arr}：dep/arr 为携程城市代码
    - 携程火车票 trains.ctrip.com/webapp/train/list：fromStationName/toStationName 为城市名
    - 12306 kyfw.12306.cn/otn/leftTicket/init：预填车票搜索表单，用户登录后可直接购票
    - 携程酒店 hotels.ctrip.com/hotel/：city 参数为城市名，checkin 为入住日期
    - 飞猪 fliggy.com：备选平台，参数含义同携程

    Args:
        origin: 出发城市，如"北京"、"成都"。hotel 类型可留空。
        destination: 目的地城市，如"上海"、"三亚"。必填。
        date: 出行/入住日期，格式 YYYY-MM-DD，可选。传入后嵌入搜索 URL。
        kind: 预订类型，取值 flight / train / hotel / all，默认 all。
    """
    if not destination:
        return "请提供目的地城市名称。"

    kind = kind.lower().strip()
    if kind not in ("flight", "train", "hotel", "all"):
        return f"kind 参数无效（{kind!r}），请使用 flight / train / hotel / all。"

    try:
        sections: list[str] = []

        if kind in ("flight", "all"):
            if not origin:
                sections.append("**机票**：请提供出发城市（origin 参数）。")
            else:
                links = _flight_links(origin, destination, date)
                sections.append("**机票预订**\n" + "\n".join(f"- {lnk}" for lnk in links))

        if kind in ("train", "all"):
            if not origin:
                sections.append("**火车票**：请提供出发城市（origin 参数）。")
            else:
                links = _train_links(origin, destination, date)
                sections.append("**火车票预订**\n" + "\n".join(f"- {lnk}" for lnk in links))

        if kind in ("hotel", "all"):
            links = _hotel_links(destination, date)
            sections.append("**酒店预订**\n" + "\n".join(f"- {lnk}" for lnk in links))

        header = f"### 前往「{destination}」预订链接"
        if date:
            header += f"（{date}）"

        return header + "\n\n" + "\n\n".join(sections)

    except Exception as exc:  # noqa: BLE001 - tool must return a string to the LLM
        return f"预订链接生成失败：{exc}"
