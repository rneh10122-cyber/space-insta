"""이미지를 공개 URL로 올리고(워드프레스), 인스타그램에 게시합니다."""
import time

import requests

from . import config


def upload_to_wordpress(jpeg: bytes, filename: str) -> str:
    """인스타그램 API는 이미지를 '공개 URL'로만 받기 때문에 워드프레스 미디어에 먼저 올립니다."""
    for k in ("WP_URL", "WP_USER", "WP_APP_PASSWORD"):
        if not getattr(config, k):
            raise SystemExit(f"[설정 오류] {k} 가 없습니다.")
    r = requests.post(
        f"{config.WP_URL.rstrip('/')}/wp-json/wp/v2/media",
        auth=(config.WP_USER, config.WP_APP_PASSWORD),
        headers={"Content-Disposition": f'attachment; filename="{filename}"',
                 "Content-Type": "image/jpeg"},
        data=jpeg,
        timeout=120,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"워드프레스 업로드 실패: {r.status_code} {r.text[:300]}")
    return r.json()["source_url"]


def _graph(path):
    return f"https://graph.facebook.com/{config.GRAPH_VERSION}/{path}"


def publish_image(image_url: str, caption: str) -> str:
    tok = config.IG_ACCESS_TOKEN
    r = requests.post(_graph(f"{config.IG_USER_ID}/media"),
                      data={"image_url": image_url, "caption": caption, "access_token": tok}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"컨테이너 생성 실패: {r.status_code} {r.text[:300]}")
    cid = r.json()["id"]

    for _ in range(30):  # 최대 약 90초 대기
        s = requests.get(_graph(cid), params={"fields": "status_code,status", "access_token": tok},
                         timeout=30).json()
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"컨테이너 처리 실패: {s}")
        time.sleep(3)

    r = requests.post(_graph(f"{config.IG_USER_ID}/media_publish"),
                      data={"creation_id": cid, "access_token": tok}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"게시 실패: {r.status_code} {r.text[:300]}")
    return r.json()["id"]
