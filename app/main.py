"""실행 진입점.

  python -m app.main --source all            # 새 게시물 확인 후 자동 게시
  python -m app.main --source apod --dry-run # 게시하지 않고 out/ 에 이미지와 캡션만 저장
"""
import argparse
import json
import traceback
from datetime import datetime, timedelta, timezone

from . import config, figma, publish, render, rights, sources, writer

KST = timezone(timedelta(hours=9))


def load_state():
    if config.STATE_FILE.exists():
        return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    return {"seen": {}, "posts": [], "initialized": False}


def save_state(st):
    st["seen"] = dict(list(st["seen"].items())[-800:])
    st["posts"] = st["posts"][-300:]
    config.STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def posted_today(st):
    today = datetime.now(KST).strftime("%Y-%m-%d")
    return sum(1 for p in st["posts"] if p["at"].startswith(today))


def collect(source, st, backfill):
    items = []
    if source in ("apod", "all"):
        try:
            items.extend(sources.fetch_apod_all())  # 최신순, 저작권 있는 날은 건너뛰고 다음 것을 씀
        except Exception as e:
            print(f"[APOD] 가져오기 실패: {e}")
    if source in ("nasa", "all"):
        try:
            ig = sources.fetch_nasa_instagram()
            if not st.get("initialized") and not backfill:
                # 첫 실행 때 기존 게시물이 한꺼번에 올라가지 않도록 '이미 본 것'으로만 기록
                for it in ig:
                    st["seen"][it.id] = "첫 실행 시 기존 게시물로 기록"
                print(f"[NASA] 첫 실행: 기존 {len(ig)}개를 건너뛰고 다음 새 게시물부터 올립니다.")
                ig = []
            items.extend(reversed(ig))  # 오래된 것부터
        except Exception as e:
            print(f"[NASA] 가져오기 실패: {e}")
        st["initialized"] = True
    return [it for it in items if it.id not in st["seen"]]


def process(item, dry_run, st):
    ok, reason, credit = rights.check(item)
    if not ok:
        print(f"[건너뜀] {item.id}: {reason}")
        st["seen"][item.id] = f"건너뜀: {reason}"
        return False

    photo = sources.download(item.image_url)
    post = writer.write_post(item)
    jpeg = render.render(photo, post["title"], post["subtitle"], credit)
    caption = writer.build_caption(post, credit, item.permalink)

    config.OUT_DIR.mkdir(exist_ok=True)
    (config.OUT_DIR / f"{item.id}.jpg").write_bytes(jpeg)
    (config.OUT_DIR / f"{item.id}.txt").write_text(caption, encoding="utf-8")
    print(f"[생성] {item.id}: {post['title']}")

    if dry_run:
        print("  (dry-run: 게시하지 않음, out/ 폴더 확인)")
        return False

    url = publish.host_image(jpeg, f"{item.id}.jpg")
    media_id = publish.publish_image(url, caption)
    st["seen"][item.id] = "게시 완료"
    st["posts"].append({"id": item.id, "media_id": media_id, "title": post["title"],
                        "at": datetime.now(KST).isoformat(timespec="seconds")})
    print(f"[게시 완료] {item.id} → {media_id}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["apod", "nasa", "all"], default="all")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--backfill", action="store_true", help="첫 실행에도 NASA 기존 게시물을 올림")
    ap.add_argument("--url", default="", help="science.nasa.gov APOD 글 주소 하나만 처리")
    args = ap.parse_args()

    st = load_state()
    try:
        figma.sync()
    except Exception as e:
        print(f"[Figma] 동기화 실패, 기존 템플릿 사용: {e}")

    done = 0
    if args.url:
        one = sources.fetch_apod_article(args.url)
        targets = [one] if one else []
        if not one:
            print(f"[URL] 읽을 수 없는 주소입니다: {args.url}")
    else:
        targets = collect(args.source, st, args.backfill)
    for item in targets:
        if done >= config.MAX_POSTS_PER_RUN:
            break
        if not args.dry_run and posted_today(st) >= config.MAX_POSTS_PER_DAY:
            print(f"오늘 게시 한도({config.MAX_POSTS_PER_DAY}개)에 도달했습니다. 나머지는 다음 실행에서 올립니다.")
            break
        try:
            if process(item, args.dry_run, st):
                done += 1
        except Exception:
            traceback.print_exc()
            fails = st.setdefault("fails", {})
            fails[item.id] = fails.get(item.id, 0) + 1
            if fails[item.id] >= 3:
                st["seen"][item.id] = "3번 실패해서 포기"
                print(f"[오류] {item.id}: 3번 실패해서 이 게시물은 건너뜁니다.")
            else:
                print(f"[오류] {item.id}: 다음 실행에서 다시 시도합니다 ({fails[item.id]}/3).")
    if not args.dry_run:
        save_state(st)
    print(f"끝: 이번 실행에서 {done}개 게시")


if __name__ == "__main__":
    main()
