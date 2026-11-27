"""NASA 오늘의 천문 사진(APOD)과 NASA 공식 인스타그램에서 새 게시물을 가져옵니다."""
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

from . import config


@dataclass
class Item:
    id: str                 # 중복 방지용 고유 ID
    source: str             # "apod" | "nasa_ig"
    image_url: str
    text: str               # 원문(영어) 제목 + 설명/캡션
    permalink: str
    credit_raw: str = ""    # 원문에 적힌 출처 표기
    copyright: str = ""     # APOD copyright 필드 (있으면 제3자 저작물)
    timestamp: str = ""
    extra: dict = field(default_factory=dict)


def fetch_apod(date: str | None = None) -> Item | None:
    params = {"api_key": config.NASA_API_KEY, "thumbs": "false"}
    if date:
        params["date"] = date
    r = requests.get("https://api.nasa.gov/planetary/apod", params=params, timeout=30)
    r.raise_for_status()
    d = r.json()
    if d.get("media_type") != "image":
        print(f"[APOD] {d.get('date')} 은(는) 이미지가 아닌 {d.get('media_type')} 라서 건너뜁니다.")
        return None
    day = d["date"]  # YYYY-MM-DD
    yymmdd = day[2:4] + day[5:7] + day[8:10]
    return Item(
        id=f"apod-{day}",
        source="apod",
        image_url=d.get("hdurl") or d["url"],
        text=f"{d.get('title', '')}\n\n{d.get('explanation', '')}",
        permalink=f"https://apod.nasa.gov/apod/ap{yymmdd}.html",
        copyright=(d.get("copyright") or "").strip(),
        credit_raw=(d.get("copyright") or "NASA").strip(),
        timestamp=day,
        extra={"title_en": d.get("title", "")},
    )


def fetch_nasa_instagram(limit: int = 8) -> list[Item]:
    """Business Discovery API로 NASA 계정의 최근 게시물을 가져옵니다. 이미지(또는 캐러셀 첫 이미지)만 사용합니다."""
    fields = (
        f"business_discovery.username({config.NASA_IG_USERNAME})"
        f"{{media.limit({limit}){{id,caption,media_type,media_url,permalink,timestamp,"
        f"children{{media_type,media_url}}}}}}"
    )
    url = f"https://graph.facebook.com/{config.GRAPH_VERSION}/{config.IG_USER_ID}"
    r = requests.get(url, params={"fields": fields, "access_token": config.IG_ACCESS_TOKEN}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Business Discovery 실패: {r.status_code} {r.text[:300]}")
    media = r.json().get("business_discovery", {}).get("media", {}).get("data", [])
    items = []
    for m in media:
        image_url = None
        if m.get("media_type") == "IMAGE":
            image_url = m.get("media_url")
        elif m.get("media_type") == "CAROUSEL_ALBUM":
            for c in m.get("children", {}).get("data", []):
                if c.get("media_type") == "IMAGE" and c.get("media_url"):
                    image_url = c["media_url"]
                    break
        if not image_url:
            continue  # 영상/릴스는 1차 버전에서 제외
        caption = m.get("caption") or ""
        items.append(Item(
            id=f"nasaig-{m['id']}",
            source="nasa_ig",
            image_url=image_url,
            text=caption,
            permalink=m.get("permalink", ""),
            credit_raw=extract_credit(caption),
            timestamp=m.get("timestamp", ""),
        ))
    return items


def extract_credit(caption: str) -> str:
    """캡션에서 'Image credit: ...' 같은 줄을 찾아 출처 부분만 돌려줍니다."""
    import re
    m = re.search(r"(?im)^\W*(?:image|photo|video)?\s*credits?\s*[:\-]\s*(.+)$", caption)
    return m.group(1).strip() if m else ""


def download(url: str) -> bytes:
    r = requests.get(url, timeout=60, headers={"User-Agent": "space-insta/1.0"})
    r.raise_for_status()
    return r.content


def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
