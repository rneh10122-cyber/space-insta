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


MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
UA = {"User-Agent": "Mozilla/5.0 (space-insta)"}


def _meta(html, prop):
    import html as h
    import re
    m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']*)' % re.escape(prop), html, re.I) \
        or re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']%s["\']' % re.escape(prop), html, re.I)
    return h.unescape(m.group(1)).strip() if m else ""


def _plain(html):
    import html as h
    import re
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", html)
    txt = h.unescape(re.sub(r"<[^>]+>", " ", html))
    return re.sub(r"[ \t\xa0]+", " ", re.sub(r"\n\s*\n+", "\n", txt)).strip()


def parse_apod_article(url: str, html: str) -> Item | None:
    """science.nasa.gov 의 APOD 상세 페이지에서 제목, 이미지, 출처, 설명을 뽑습니다."""
    import re
    m = re.search(r"/apod-(\d{4})-([a-z]+)-(\d{1,2})-", url)
    if not m or m.group(2) not in MONTHS:
        return None
    day = f"{m.group(1)}-{MONTHS[m.group(2)]:02d}-{int(m.group(3)):02d}"
    image = _meta(html, "og:image")
    if not image:
        im = re.search(r'https://assets\.science\.nasa\.gov/[^"\'\s>]+?\.(?:jpe?g|png)', html, re.I)
        image = im.group(0) if im else ""
    if not image or re.search(r"youtube|vimeo|\.mp4", image, re.I):
        return None
    image = image.split("?")[0]  # 원본 크기로
    title = re.sub(r"\s*[-|]\s*NASA Science\s*$", "", _meta(html, "og:title")).strip()
    text = _plain(html)
    expl = ""
    em = re.search(r"Explanation:?\s*(.+?)(?:\n\s*(?:Tomorrow|Authors?|Editors?|Share|Keep Exploring)\b|$)", text, re.S)
    if em:
        expl = em.group(1).strip()
    expl = expl or _meta(html, "og:description") or _meta(html, "description")
    cm = re.search(r"((?:Image|Video|Illustration)?\s*Credits?(?:\s*(?:&|and)\s*Copyright)?|Copyright)\s*:?\s*([^\n]{2,200})", text, re.I)
    if not cm:
        # 출처를 확인할 수 없으면 쓰지 않도록 제3자 저작물로 취급
        return Item(id=f"apod-{day}", source="apod", image_url=image, text=title, permalink=url,
                    copyright="출처 확인 불가", credit_raw="", timestamp=day)
    label, credit = cm.group(1), re.sub(r"\s+,", ",", cm.group(2)).strip()
    head = text[: (em.end() if em else len(text))]  # 설명까지의 본문 영역
    copyrighted = bool(re.search(r"copyright|©", label + " " + credit + " " + head, re.I))
    return Item(
        id=f"apod-{day}", source="apod", image_url=image,
        text=f"{title}\n\n{expl}", permalink=url,
        copyright=credit if copyrighted else "",
        credit_raw=credit, timestamp=day, extra={"title_en": title},
    )


def fetch_apod_web(limit: int = 5) -> list[Item]:
    """APOD가 science.nasa.gov/apod 로 옮겨져서, API가 안 될 때 웹 페이지에서 최근 게시물을 읽습니다."""
    import re
    r = requests.get("https://science.nasa.gov/apod/", headers=UA, timeout=30)
    r.raise_for_status()
    links = []
    for u in re.findall(r'https://science\.nasa\.gov/image-article/apod-\d{4}-[a-z]+-\d{1,2}-[^"\'\s<>#?]+', r.text):
        u = u.rstrip("/") + "/"
        if u not in links:
            links.append(u)
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
    items = []
    for u in links[:limit]:
        it = fetch_apod_article(u)
        if it and it.timestamp >= cutoff:  # 열흘 넘은 옛날 게시물은 쓰지 않음
            items.append(it)
    return items


def fetch_apod_article(u: str) -> Item | None:
    try:
        a = requests.get(u, headers=UA, timeout=30)
        a.raise_for_status()
        return parse_apod_article(u, a.text)
    except Exception as e:
        print(f"[APOD] {u} 읽기 실패: {e}")
        return None


def fetch_apod_all() -> list[Item]:
    """API(오늘 것) + 웹(최근 며칠)을 합쳐 최신순으로 돌려줍니다."""
    items = {}
    for attempt in range(2):
        try:
            it = fetch_apod()
            if it:
                items[it.id] = it
            break
        except Exception as e:
            print(f"[APOD] API 실패({attempt + 1}/2): {e}")
    try:
        for it in fetch_apod_web():
            items.setdefault(it.id, it)
    except Exception as e:
        print(f"[APOD] 웹 페이지 읽기 실패: {e}")
    return sorted(items.values(), key=lambda x: x.timestamp, reverse=True)


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
