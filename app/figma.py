"""Figma 템플릿 프레임에서 레이아웃과 장식 레이어(OVERLAY)를 가져옵니다.

Figma 프레임 안에 아래 이름의 레이어를 만들어 두면 됩니다 (대소문자 무관).
  TITLE     제목 텍스트 박스 (위치, 너비, 글자 크기, 색을 사용)
  SUBTITLE  부제 텍스트 박스
  CREDIT    출처 텍스트 박스
  OVERLAY   로고, 테두리, 그라데이션 등 사진 위에 얹을 장식을 묶은 그룹/프레임 (PNG로 내보냄)
글꼴 파일 자체는 Figma에서 받아올 수 없으니 fonts/ 폴더에 같은 폰트를 넣어 두세요.
"""
import json

import requests

from . import config

API = "https://api.figma.com/v1"


def _hdr():
    return {"X-Figma-Token": config.FIGMA_TOKEN}


def _hex(fills):
    for f in fills or []:
        if f.get("type") == "SOLID" and f.get("visible", True):
            c = f["color"]
            return "#{:02X}{:02X}{:02X}".format(*(round(c[k] * 255) for k in "rgb"))
    return None


def _find(node, name):
    if node.get("name", "").strip().upper() == name:
        return node
    for ch in node.get("children", []):
        hit = _find(ch, name)
        if hit:
            return hit
    return None


def sync() -> bool:
    """Figma가 설정돼 있으면 assets/figma_template.json, assets/overlay.png 를 갱신합니다."""
    if not (config.FIGMA_TOKEN and config.FIGMA_FILE_KEY and config.FIGMA_TEMPLATE_NODE):
        return False
    node_id = config.FIGMA_TEMPLATE_NODE.replace("-", ":")
    r = requests.get(f"{API}/files/{config.FIGMA_FILE_KEY}/nodes", params={"ids": node_id},
                     headers=_hdr(), timeout=30)
    r.raise_for_status()
    frame = r.json()["nodes"][node_id]["document"]
    fb = frame["absoluteBoundingBox"]
    s = 1080 / fb["width"]
    W, H = 1080, round(fb["height"] * s)

    def box(n):
        b = n["absoluteBoundingBox"]
        return {"x": round((b["x"] - fb["x"]) * s), "y": round((b["y"] - fb["y"]) * s),
                "w": round(b["width"] * s), "h": round(b["height"] * s)}

    tpl = {"width": W, "height": H}
    title, sub, cred, ov = (_find(frame, n) for n in ("TITLE", "SUBTITLE", "CREDIT", "OVERLAY"))

    def text_spec(n, bold):
        b, st = box(n), n.get("style", {})
        spec = {"x": b["x"], "w": b["w"], "bold": bold}
        if st.get("fontSize"):
            spec["size"] = round(st["fontSize"] * s)
            spec["min_size"] = round(spec["size"] * 0.72)
        if st.get("lineHeightPx") and st.get("fontSize"):
            spec["line_height"] = round(st["lineHeightPx"] / st["fontSize"], 3)
        col = _hex(n.get("fills"))
        if col:
            spec["color"] = col
        return spec, b

    if title:
        tpl["title"], tb = text_spec(title, (title.get("style", {}).get("fontWeight", 700) >= 600))
        tpl["block_bottom"] = tb["y"] + tb["h"]
    if sub:
        tpl["subtitle"], sb = text_spec(sub, sub.get("style", {}).get("fontWeight", 400) >= 600)
        tpl["block_bottom"] = sb["y"] + sb["h"]
        if title:
            tpl["gap"] = max(0, sb["y"] - (tb["y"] + tb["h"]))
    if cred:
        tpl["credit"], cb = text_spec(cred, False)
        tpl["credit"]["y"] = cb["y"]

    if ov:
        b = box(ov)
        img = requests.get(f"{API}/images/{config.FIGMA_FILE_KEY}",
                           params={"ids": ov["id"], "format": "png", "scale": s},
                           headers=_hdr(), timeout=60).json()
        url = (img.get("images") or {}).get(ov["id"])
        if url:
            (config.ASSETS / "overlay.png").write_bytes(requests.get(url, timeout=60).content)
            tpl["overlay"] = {"path": "assets/overlay.png", **b}

    (config.ASSETS / "figma_template.json").write_text(json.dumps(tpl, ensure_ascii=False, indent=2),
                                                      encoding="utf-8")
    print(f"[Figma] 템플릿 동기화 완료 ({W}x{H})")
    return True
