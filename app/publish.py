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


def upload_to_github(jpeg: bytes, filename: str) -> str:
    """공개 GitHub 저장소의 posted/ 폴더에 이미지를 올리고 공개 주소를 돌려줍니다 (Actions 안에서 실행)."""
    import os
    import subprocess
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise SystemExit("[설정 오류] GITHUB_REPOSITORY 가 없습니다. GitHub Actions 안에서 실행하거나 IMAGE_HOST=wordpress 를 쓰세요.")
    branch = os.environ.get("GITHUB_REF_NAME") or "main"
    folder = config.ROOT / "posted"
    folder.mkdir(exist_ok=True)
    (folder / filename).write_bytes(jpeg)
    git = lambda *a: subprocess.run(["git", *a], cwd=config.ROOT, check=True, capture_output=True, text=True)
    git("config", "user.name", "space-insta-bot")
    git("config", "user.email", "bot@users.noreply.github.com")
    git("add", f"posted/{filename}")
    git("commit", "-m", f"게시 이미지 {filename}")
    git("push", "origin", f"HEAD:{branch}")
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/posted/{filename}"
    for _ in range(20):  # 공개 주소에서 열릴 때까지 최대 1분 대기
        if requests.head(url, timeout=15).status_code == 200:
            return url
        time.sleep(3)
    raise RuntimeError(f"이미지 공개 주소가 열리지 않습니다: {url} (저장소가 공개인지 확인하세요)")


def host_image(jpeg: bytes, filename: str) -> str:
    if config.IMAGE_HOST == "wordpress":
        return upload_to_wordpress(jpeg, filename)
    return upload_to_github(jpeg, filename)


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
