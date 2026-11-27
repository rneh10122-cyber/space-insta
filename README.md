# space-insta: NASA 우주 게시물 자동 발행

NASA 공식 인스타그램과 NASA 오늘의 천문 사진(APOD)에 새 사진이 올라오면
1. 사진과 영어 원문을 가져오고
2. 출처를 확인해 써도 되는 사진만 고르고 (개인 사진가, © 표시, 게티 등은 자동 제외)
3. GPT가 한국어 제목, 부제, 본문, 해시태그로 재구성하고
4. Figma 템플릿 모양대로 사진 위에 제목을 얹은 1080x1350 이미지를 만들고
5. 내 인스타그램에 게시합니다.

GitHub Actions에서 무료로 돌아가고, 서버를 따로 켜 둘 필요가 없습니다.

| 언제 | 무엇을 |
|---|---|
| 매일 21:07 | APOD 오늘의 사진 게시 |
| 2시간마다 | NASA 인스타에 새 사진이 있으면 게시 (한 번에 1개, 하루 최대 4개) |

시간과 개수는 `.github/workflows/post.yml` 의 cron, `MAX_POSTS_PER_RUN`, `MAX_POSTS_PER_DAY` 로 바꿉니다.

---

## 설정 순서 (처음 한 번, 30~40분)

### 1. 인스타그램 계정 준비
- 인스타 앱 > 설정 > 계정 유형 및 도구 > **프로페셔널 계정(비즈니스)** 으로 전환
- **페이스북 페이지와 연결** (NASA 게시물을 읽어오는 Business Discovery 기능이 페이스북 로그인 방식에서만 됩니다)

### 2. Meta 개발자 앱과 토큰
1. https://developers.facebook.com 에서 앱 만들기 (유형: 비즈니스)
2. 제품 추가에서 **Instagram (Facebook 로그인 방식)** 추가
3. 권한: `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`, `pages_show_list`, `business_management`
   - 내 계정에만 쓰는 거라면 앱 관리자 본인 계정으로 바로 쓸 수 있습니다.
4. **토큰은 만료 없는 시스템 사용자 토큰을 추천합니다**
   비즈니스 설정(business.facebook.com) > 사용자 > 시스템 사용자 > 추가 > 페이지와 인스타 계정 자산 할당 > 토큰 생성 (위 권한 체크)
   - 그래프 API 탐색기에서 받은 토큰은 60일 뒤 만료되니 테스트용으로만 쓰세요.
5. 내 인스타 계정 ID 찾기 (그래프 API 탐색기에서)
   `GET /me/accounts` → 페이지 id 확인 → `GET /{페이지id}?fields=instagram_business_account` → 나온 숫자가 `IG_USER_ID`

### 3. 나머지 키
- **NASA_API_KEY**: https://api.nasa.gov 에서 이메일만 넣으면 바로 발급 (무료)
- **OPENAI_API_KEY**: 쓰고 계신 키 그대로
- **워드프레스**: 인스타 API는 이미지를 공개 주소로만 받아서, 만든 이미지를 워드프레스 미디어에 먼저 올립니다.
  워드프레스 관리자 > 사용자 > 프로필 > **애플리케이션 비밀번호** 생성 → `WP_USER`(로그인 아이디), `WP_APP_PASSWORD`

### 4. GitHub에 올리기
1. GitHub에서 **Private** 저장소를 만들고 이 폴더 내용을 그대로 업로드
2. 저장소 Settings > Secrets and variables > Actions > **New repository secret** 으로 아래를 추가
   `NASA_API_KEY`, `IG_USER_ID`, `IG_ACCESS_TOKEN`, `OPENAI_API_KEY`, `WP_URL`, `WP_USER`, `WP_APP_PASSWORD`
   (Figma를 쓰면 `FIGMA_TOKEN`, `FIGMA_FILE_KEY`, `FIGMA_TEMPLATE_NODE` 도)
3. **Actions 탭 > space-insta 자동 게시 > Run workflow** 에서 `dry_run = true` 로 먼저 실행
   → 실행이 끝나면 화면 아래 Artifacts 의 `out` 을 받아 이미지와 캡션이 마음에 드는지 확인
4. 괜찮으면 그때부터는 정해진 시간에 자동으로 게시됩니다. 직접 바로 올리고 싶으면 `dry_run = false` 로 실행

> 처음 실행할 때는 NASA 인스타의 기존 게시물을 한꺼번에 올리지 않고, 그 다음에 새로 올라오는 것부터 게시합니다.

---

## Figma 템플릿 연결 (지금 쓰는 디자인 그대로)

Figma에서 디자인을 바꾸면 다음 실행부터 자동으로 반영됩니다.

1. 1080x1350 프레임을 하나 만들고 안에 아래 이름으로 레이어를 둡니다.
   | 레이어 이름 | 역할 |
   |---|---|
   | `TITLE` | 제목 텍스트 박스. 위치, 너비, 글자 크기, 색을 그대로 사용 |
   | `SUBTITLE` | 부제 텍스트 박스 |
   | `CREDIT` | 출처 텍스트 박스 |
   | `OVERLAY` | 로고, 계정명, 테두리, 그라데이션 등 사진 위에 얹을 장식을 묶은 그룹 (투명 PNG로 내보내짐) |
   - 사진 자리는 프레임 전체로 꽉 채웁니다. 텍스트 레이어 안의 글자는 아무거나 써도 됩니다.
2. Figma > 설정 > Security > **Personal access token** 생성 (File content 읽기 권한) → `FIGMA_TOKEN`
3. 프레임을 선택하고 링크 복사 → `figma.com/design/` 다음 부분이 `FIGMA_FILE_KEY`, `node-id=12-34` 의 `12-34` 가 `FIGMA_TEMPLATE_NODE`
4. Figma에서 쓰는 폰트 파일(예: Pretendard-Bold.otf, Pretendard-Regular.otf)을 `fonts/` 폴더에 넣습니다. 파일 이름에 Bold, Regular 가 들어가면 자동 인식합니다. (없으면 Noto Sans KR 사용)
5. OVERLAY 에 그라데이션을 이미 넣었다면 `assets/template.json` 에 `"gradient": {"enabled": false}` 를 적어 기본 그라데이션을 끕니다.

Figma 없이 쓸 때는 `assets/template.json` 에서 위치, 크기, 색을 직접 조정할 수 있습니다. (기본값은 `app/render.py` 맨 위)

## 말투 맞추기

`style_examples.txt` 에 지금까지 올린 게시물 본문을 3~5개 붙여 넣으면 GPT가 그 말투와 길이에 맞춰 씁니다.

---

## 사진 사용 기준 (자동 필터)

| 사용 | 제외 |
|---|---|
| NASA, JPL-Caltech, ESA, CSA, STScI 등 공공 우주기관 크레딧 | 개인 사진가 이름만 있는 크레딧 |
| `NASA/사진가 이름` (NASA 소속 사진가) | ©, Copyright, Getty, Reuters, AP, AFP |
| APOD 중 copyright 표시가 없는 사진 | APOD 중 copyright 표시가 있는 사진 (대부분 아마추어 천체사진가 작품) |
|  | 출처 표기가 없는 게시물, 영상과 릴스 |

- 게시물 캡션에는 원문 출처(Credit)와 원문 링크가 자동으로 붙습니다.
- 이미지에 NASA 로고(미트볼)를 넣거나 계정을 NASA 공식 계정처럼 보이게 하지 마세요. NASA 휘장과 로고는 별도로 보호됩니다.
- 왜 건너뛰었는지는 `state.json` 과 Actions 실행 로그에 남습니다.

## 파일 구성

```
app/sources.py   APOD, NASA 인스타 가져오기
app/rights.py    출처 판정
app/writer.py    GPT 한국어 재구성 (프롬프트 수정은 여기)
app/render.py    이미지 합성
app/figma.py     Figma 템플릿 동기화
app/publish.py   워드프레스 업로드, 인스타 게시
app/main.py      전체 실행
state.json       게시 기록 (중복 방지)
```

## 내 컴퓨터에서 테스트

```bash
pip install -r requirements.txt
cp .env.example .env   # 값 채우기
python -m app.main --source apod --dry-run   # out/ 폴더에 결과 저장, 게시는 안 함
```
