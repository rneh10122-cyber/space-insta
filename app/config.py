"""환경 변수에서 설정을 읽어옵니다. 값은 .env 파일이나 GitHub Secrets에 넣어 두세요."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv():
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = "" if re.match(r"\s+#", v) else re.sub(r"\s+#\s.*$", "", v)  # 줄 끝 설명 주석 제거
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def env(name, default=None, required=False):
    v = os.environ.get(name) or default  # Actions에서 비어 있는 Secret은 "" 로 들어옴
    if required and not v:
        raise SystemExit(f"[설정 오류] 환경 변수 {name} 이(가) 비어 있습니다. README의 설정 단계를 확인하세요.")
    return v


# NASA
NASA_API_KEY = env("NASA_API_KEY", "DEMO_KEY")
NASA_IG_USERNAME = env("NASA_IG_USERNAME", "nasa")

# Instagram (Facebook 로그인 방식, Business Discovery와 게시에 모두 사용)
IG_USER_ID = env("IG_USER_ID")
IG_ACCESS_TOKEN = env("IG_ACCESS_TOKEN")
GRAPH_VERSION = env("GRAPH_VERSION", "v25.0")

# OpenAI
OPENAI_API_KEY = env("OPENAI_API_KEY")
OPENAI_MODEL = env("OPENAI_MODEL", "gpt-4o-mini")

# 이미지 호스팅 (워드프레스 미디어 업로드)
WP_URL = env("WP_URL")  # 예: https://example.com
WP_USER = env("WP_USER")
WP_APP_PASSWORD = env("WP_APP_PASSWORD")

# Figma (선택)
FIGMA_TOKEN = env("FIGMA_TOKEN")
FIGMA_FILE_KEY = env("FIGMA_FILE_KEY")
FIGMA_TEMPLATE_NODE = env("FIGMA_TEMPLATE_NODE")  # 예: 12:34 (URL의 12-34도 됩니다)

# 폰트
FONT_BOLD = env("FONT_BOLD", "")
FONT_REGULAR = env("FONT_REGULAR", "")

# 운영
MAX_POSTS_PER_RUN = int(env("MAX_POSTS_PER_RUN", "1"))
MAX_POSTS_PER_DAY = int(env("MAX_POSTS_PER_DAY", "4"))
HASHTAGS_EXTRA = env("HASHTAGS_EXTRA", "#우주 #천문학 #NASA")

STATE_FILE = ROOT / "state.json"
OUT_DIR = ROOT / "out"
ASSETS = ROOT / "assets"
FONTS_DIR = ROOT / "fonts"
