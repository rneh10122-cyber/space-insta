"""영어 원문을 한국어 인스타그램 게시물로 재구성합니다 (OpenAI)."""
import json

import requests

from . import config

SYSTEM = """너는 한국어 우주 인스타그램 계정의 에디터야.
NASA 원문(영어)을 읽고, 한국 독자가 끝까지 읽고 싶어지는 게시물로 다시 써.

규칙:
- 직역하지 말고 핵심을 골라 쉽게 풀어 써. 어려운 용어는 한 번 짧게 설명해.
- 숫자, 이름, 날짜 같은 사실은 원문 그대로 지키고 없는 내용은 지어내지 마.
- 가운뎃점(·)은 쓰지 마. 나열은 쉼표나 / 를 써.
- "AI", "번역" 같은 말이나 NASA 공식 계정처럼 보이는 표현은 쓰지 마.
- 이모지는 문단 앞에 1개 정도만, 과하지 않게.

JSON으로만 답해:
{
  "title": "이미지에 들어갈 제목, 띄어쓰기 포함 18자 이내, 호기심이 생기게",
  "subtitle": "제목 아래 한 줄 설명, 28자 이내",
  "caption": "본문, 3~5개 짧은 문단, 전체 700자 이내, 출처와 해시태그는 넣지 마",
  "hashtags": ["#주제에맞는", "#한국어해시태그", "최대 8개"]
}"""


def _style_examples() -> str:
    p = config.ROOT / "style_examples.txt"
    if p.exists():
        txt = p.read_text(encoding="utf-8").strip()
        if txt:
            return "\n\n참고: 아래는 이 계정이 예전에 올린 게시물이야. 말투와 길이를 비슷하게 맞춰.\n" + txt[:3000]
    return ""


def write_post(item) -> dict:
    if not config.OPENAI_API_KEY:
        raise SystemExit("[설정 오류] OPENAI_API_KEY 가 없습니다.")
    src = "NASA 오늘의 천문 사진(APOD)" if item.source == "apod" else "NASA 인스타그램 게시물"
    user = f"원문 출처: {src}\n\n원문:\n{item.text[:6000]}"
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        json={
            "model": config.OPENAI_MODEL,
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": SYSTEM + _style_examples()},
                {"role": "user", "content": user},
            ],
        },
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"OpenAI 오류: {r.status_code} {r.text[:300]}")
    data = json.loads(r.json()["choices"][0]["message"]["content"])
    return clean(data)


def clean(data: dict) -> dict:
    """모델이 규칙을 어겨도 결과가 안전하도록 한 번 더 다듬습니다."""
    fix = lambda s: (s or "").replace("·", ", ").replace("ㆍ", ", ").strip()
    tags = [t if t.startswith("#") else "#" + t for t in (data.get("hashtags") or []) if t]
    return {
        "title": fix(data.get("title"))[:24],
        "subtitle": fix(data.get("subtitle"))[:36],
        "caption": fix(data.get("caption")),
        "hashtags": [t.replace(" ", "") for t in tags][:8],
    }


def build_caption(post: dict, credit: str, permalink: str) -> str:
    extra = [t for t in config.HASHTAGS_EXTRA.split() if t not in post["hashtags"]]
    tags = " ".join((post["hashtags"] + extra)[:15])
    caption = f"{post['caption']}\n\n📷 Credit: {credit}\n원문: {permalink}\n\n{tags}"
    return caption[:2200]
