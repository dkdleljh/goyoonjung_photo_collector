# Goyoonjung Photo Collector (무료 API 기반)

배우 고윤정 사진을 무료 소스에서 수집하는 Python CLI 프로젝트입니다.

- 유료 API/유료 서비스 미사용
- Instagram 계정 전체 스크래핑 금지, seed URL만 처리
- 720p 이상만 저장
- 원본 바이트 그대로 저장(리사이즈/재인코딩/포맷변환 금지)
- SHA-256 + SQLite 기반 중복 제거
- 실행 요약 콘솔 출력 + 파일 저장

## 1) 요구 환경

- Python 3.11+
- 지원 OS: Windows, macOS, Linux (ChromeOS 제외)

## 2) 설치

```bash
cd /home/zenith/goyoonjung_photo_collector
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## 3) 환경변수 설정

`.env.example`를 복사해 `.env`를 만든 뒤 값 입력:

```bash
cp .env.example .env
```

`.env` 항목:

- `NAVER_CLIENT_ID` : NAVER 이미지 검색 Open API ID
- `NAVER_CLIENT_SECRET` : NAVER 이미지 검색 Open API SECRET
- `PHOTO_ROOT` (선택): 자동 Desktop 탐지가 어려운 환경에서 "Desktop처럼 간주할 경로"

저장 루트는 항상 다음 규칙을 따릅니다.

- 기본: `Desktop/Goyoonjung_Photos`
- `PHOTO_ROOT` 지정 시: `PHOTO_ROOT/Goyoonjung_Photos`

즉 바탕화면(또는 PHOTO_ROOT로 지정한 Desktop 대체 경로) 최상위에는 `Goyoonjung_Photos` 폴더 하나만 생성/사용합니다.

## 4) 실행

기본 실행:

```bash
python -m app.cli run
```

옵션 사용:

```bash
python -m app.cli run --providers "naver,wikimedia,instagram_seed" --keywords "고윤정,Go Yoon-jung"
```

- `--providers` 기본값(권장): `naver,wikimedia,instagram_seed,google`
- `twitter_rss`는 기본 비활성(실험적): 실패율이 높아 필요 시에만 직접 활성화
  - 재활성화 예시: `python -m app.cli run --providers "naver,wikimedia,instagram_seed,google,twitter_rss"`
- `--keywords` 미입력 시 기본 추천 키워드 자동 사용:
  - 고윤정
  - 고윤정 화보
  - 고윤정 프로필
  - 고윤정 인터뷰
  - Go Yoon-jung
  - Go Yoon-jung photoshoot
  - Go Yoon-jung profile
- `--dry-run`: 다운로드/저장 없이 후보 수집만 점검
- 상태 확인: `python -m app.cli status`

## 5) Instagram Seed 사용법

`seeds/instagram_urls.txt` 파일에 URL을 한 줄씩 입력합니다.

```txt
https://www.instagram.com/p/xxxxxxxxxxx/
https://instagram.fxxx-xx.fna.fbcdn.net/v/t51.2885-15/....jpg
```

동작 규칙:

- 직접 이미지 URL이면 바로 후보로 사용
- 게시물 URL이면 HTML에서 `og:image`를 추출 시도
- 로그인 필요/차단/og:image 없음이면 스킵하고 `meta/failed.jsonl`에 사유 기록

## 6) 저장 구조

실행 후 저장 구조 예시:

```text
Desktop/Goyoonjung_Photos/
  2026-02-08/
    naver/
    wikimedia/
    instagram_seed/
  meta/
    items.jsonl
    failed.jsonl
    dedup.sqlite
  logs/
    summary_2026-02-08.txt
```

- 날짜/제공자 하위 폴더에 원본 파일 저장
- `meta/items.jsonl`: 성공 메타데이터
- `meta/failed.jsonl`: 실패/스킵 + 사유
- `meta/dedup.sqlite`: SHA-256 중복 DB
- `logs/summary_YYYY-MM-DD.txt`: 실행 요약

## 7) 품질/필터 규칙

- 동시성: 4 workers
- 재시도: 3회 (지수 백오프)
- polite delay: 요청 간 0.8~1.6초 랜덤
- 이미지 판별: `Content-Type`이 `image/*`인지 확인
- 해상도 필터: 최소 한 변 `300px` 이상
- 중복 판별: `sha256(image_bytes)`
- 저장 방식: 다운로드 바이트 그대로 저장 (변환/재인코딩 없음)

## 8) 요약 출력 항목

매 실행 종료 시 다음 항목을 콘솔 및 summary 파일에 기록합니다.

- `candidates_total`
- `unique_urls`
- `OK`
- `RESOLUTION_TOO_SMALL`
- `DUPLICATE`
- `NOT_IMAGE`
- `IMAGE_DECODE_FAIL`
- `DOWNLOAD_FAIL`
- provider별 `OK` 건수
- `failures_by_reason` (사유별 실패 건수)

## 9) 스케줄러 등록 (매일 19:00, KST 기준)

### Windows Task Scheduler

1. 작업 스케줄러 열기 → 작업 만들기
2. 트리거: 매일, `19:00`
3. 동작:
   - 프로그램/스크립트: `C:\\path\\to\\project\\.venv\\Scripts\\python.exe`
   - 인수 추가: `-m app.cli run`
   - 시작 위치(Start in): `C:\\path\\to\\goyoonjung_photo_collector`

### macOS / Linux (cron)

```cron
0 19 * * * /path/to/goyoonjung_photo_collector/.venv/bin/python -m app.cli run >> /path/to/goyoonjung_photo_collector/cron.log 2>&1
```

중요:

- cron은 OS 로컬 타임존을 사용합니다.
- KST(Asia/Seoul) 19:00에 맞추려면 서버/PC 타임존 설정을 먼저 확인하세요.

## 10) 실패 처리 정책

접근 불가, 차단, 로그인 필요, 비이미지 등은 우회하지 않고 스킵하며 `meta/failed.jsonl`에 사유를 남깁니다.
