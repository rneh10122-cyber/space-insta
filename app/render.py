"""사진 위에 제목/부제/출처를 얹어 1080x1350 인스타 이미지를 만듭니다.

레이아웃은 assets/template.json 에서 바꿀 수 있고, Figma를 연결하면 Figma 템플릿 프레임의
TITLE / SUBTITLE / CREDIT / OVERLAY 레이어 위치와 크기, 색을 그대로 따라갑니다.
"""
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import config

DEFAULT_TEMPLATE = {
    "width": 1080,
    "height": 1350,
    "gradient": {"enabled": True, "start": 0.48, "max_alpha": 225},
    "block_bottom": 1222,       # 제목+부제 묶음의 아래 끝 y
    "gap": 22,                  # 제목과 부제 사이 간격
    "title": {"x": 72, "w": 936, "size": 78, "min_size": 56, "max_lines": 2,
              "line_height": 1.22, "color": "#FFFFFF", "bold": True},
    "subtitle": {"x": 72, "w": 936, "size": 36, "line_height": 1.35, "max_lines": 2,
                 "color": "#D5DBE7", "bold": False},
    "credit": {"x": 72, "y": 1272, "w": 936, "size": 22, "color": "#98A2B6", "bold": False},
    "overlay": {"path": "assets/overlay.png", "x": 0, "y": 0},
}

_SYSTEM_FONTS = {
    True: ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
           "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"],
    False: ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"],
}


def load_template() -> dict:
    tpl = json.loads(json.dumps(DEFAULT_TEMPLATE))
    for name in ("figma_template.json", "template.json"):  # 직접 적은 template.json 이 마지막에 덮어씀
        p = config.ASSETS / name
        if p.exists():
            _deep_update(tpl, json.loads(p.read_text(encoding="utf-8")))
    return tpl


def _deep_update(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            _deep_update(a[k], v)
        else:
            a[k] = v


def _font_path(bold: bool) -> str:
    env_path = config.FONT_BOLD if bold else config.FONT_REGULAR
    if env_path and Path(env_path).exists():
        return env_path
    key = "bold" if bold else "regular"
    for f in sorted(config.FONTS_DIR.glob("*")):
        n = f.name.lower()
        if f.suffix.lower() in (".ttf", ".otf", ".ttc") and (key in n or (not bold and "medium" in n)):
            return str(f)
    for p in _SYSTEM_FONTS[bold]:
        if Path(p).exists():
            return p
    raise SystemExit("한글 폰트를 찾지 못했습니다. fonts/ 폴더에 Bold, Regular 폰트 파일을 넣어 주세요.")


def font(size: int, bold: bool) -> ImageFont.FreeTypeFont:
    path = _font_path(bold)
    if path.endswith(".ttc"):  # 한국어(KR) 서체를 찾아서 사용
        for i in range(10):
            try:
                f = ImageFont.truetype(path, size, index=i)
            except OSError:
                break
            if "KR" in " ".join(f.getname()):
                return f
    return ImageFont.truetype(path, size)


def _wrap(draw, text, fnt, width):
    lines, cur = [], ""
    for word in text.split(" "):
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=fnt) <= width:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        cur = ""
        for ch in word:  # 한 단어가 너무 길면 글자 단위로 자름
            if draw.textlength(cur + ch, font=fnt) <= width:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
    if cur:
        lines.append(cur)
    return lines


def _fit(draw, text, spec):
    size = spec["size"]
    while True:
        fnt = font(size, spec.get("bold", False))
        lines = _wrap(draw, text, fnt, spec["w"])
        if len(lines) <= spec.get("max_lines", 2) or size <= spec.get("min_size", size):
            return fnt, lines[: spec.get("max_lines", 2)], size
        size -= 4


def _cover(img, w, h):
    return ImageOps.fit(img.convert("RGB"), (w, h), method=Image.LANCZOS, centering=(0.5, 0.45))


def render(photo_bytes: bytes, title: str, subtitle: str, credit: str) -> bytes:
    tpl = load_template()
    W, H = tpl["width"], tpl["height"]
    base = _cover(Image.open(io.BytesIO(photo_bytes)), W, H).convert("RGBA")

    g = tpl["gradient"]
    if g.get("enabled", True):
        grad = Image.new("L", (1, H), 0)
        start = int(H * g["start"])
        for y in range(start, H):
            t = (y - start) / max(1, H - start)
            grad.putpixel((0, y), int(g["max_alpha"] * (t ** 1.3)))
        shade = Image.new("RGBA", (W, H), (4, 6, 14, 255))
        shade.putalpha(grad.resize((W, H)))
        base = Image.alpha_composite(base, shade)

    ov = tpl.get("overlay") or {}
    ov_path = config.ROOT / ov.get("path", "")
    if ov.get("path") and ov_path.is_file():
        overlay = Image.open(ov_path).convert("RGBA")
        if ov.get("w") and ov.get("h"):
            overlay = overlay.resize((int(ov["w"]), int(ov["h"])), Image.LANCZOS)
        elif overlay.size != (W, H) and ov.get("x", 0) == 0 and ov.get("y", 0) == 0:
            overlay = overlay.resize((W, H), Image.LANCZOS)
        base.alpha_composite(overlay, (int(ov.get("x", 0)), int(ov.get("y", 0))))

    draw = ImageDraw.Draw(base)
    ts, ss = tpl["title"], tpl["subtitle"]
    tf, tlines, tsize = _fit(draw, title, ts)
    sf, slines, ssize = _fit(draw, subtitle, ss) if subtitle else (None, [], 0)
    t_lh = int(tsize * ts["line_height"])
    s_lh = int(ssize * ss["line_height"]) if slines else 0
    block_h = t_lh * len(tlines) + (tpl["gap"] + s_lh * len(slines) if slines else 0)
    y = tpl["block_bottom"] - block_h

    for line in tlines:
        draw.text((ts["x"], y), line, font=tf, fill=ts["color"])
        y += t_lh
    if slines:
        y += tpl["gap"]
        for line in slines:
            draw.text((ss["x"], y), line, font=sf, fill=ss["color"])
            y += s_lh

    cs = tpl["credit"]
    if credit and cs.get("size"):
        cf = font(cs["size"], cs.get("bold", False))
        label = f"Credit: {credit}"
        while draw.textlength(label, font=cf) > cs["w"] and len(label) > 10:
            label = label[:-2]
        draw.text((cs["x"], cs["y"]), label, font=cf, fill=cs["color"])

    out = io.BytesIO()
    base.convert("RGB").save(out, "JPEG", quality=92, optimize=True)
    return out.getvalue()
