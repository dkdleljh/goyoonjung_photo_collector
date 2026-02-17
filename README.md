# goyoonjung_photo_collector

무료로 접근 가능한 공개 소스(검색/오픈 데이터/seed URL 등)에서 **배우 고윤정** 관련 이미지를 수집해 로컬에 저장하는 Python CLI/배치 수집기입니다.

- 유료 API/유료 서비스 **미사용**
- 수집 결과는 **로컬 파일로만 저장**(S3/DB 업로드 같은 자동 외부 전송 없음)
- 원본 바이트를 **그대로 저장**(리사이즈/재인코딩/포맷 변환 없음)
- **중복 제거(sha256 + SQLite)**
- 실패/스킵 사유를 JSONL로 남겨서 **재현/디버깅 가능**

> 이 프로젝트는 “공개적으로 접근 가능한 리소스”만을 대상으로 합니다.
> 로그인 우회, 차단 우회, 비공개 콘텐츠 접근을 목표로 하지 않습니다.

---

## 목차

- [1. 빠른 시작(Quickstart)](#1-빠른-시작quickstart)
- [2. 요구사항](#2-요구사항)
- [3. 설치](#3-설치)
- [4. 설정(.env)](#4-설정env)
- [5. 실행 방법](#5-실행-방법)
  - [5.1 1회 실행(run --once)](#51-1회-실행run---once)
  - [5.2 상태 확인(status)](#52-상태-확인status)
  - [5.3 주기 실행(run_loop.py)](#53-주기-실행run_looppy)
- [6. Providers(수집 소스)](#6-providers수집-소스)
- [7. 저장 구조](#7-저장-구조)
- [8. 필터/정책](#8-필터정책)
- [9. 종료 코드(Exit code)](#9-종료-코드exit-code)
- [10. 트러블슈팅](#10-트러블슈팅)
- [11. 보안 체크리스트(중요)](#11-보안-체크리스트중요)

---

## 1. 빠른 시작(Quickstart)

```bash
# 1) 클론
git clone https://github.com/dkdleljh/goyoonjung_photo_collector.git
cd goyoonjung_photo_collector

# 2) 가상환경(프로젝트는 venv/를 기본으로 사용)
python3 -m venv venv
source venv/bin/activate

# 3) 의존성 설치
pip install -r requirements.txt

# 4) 환경변수 파일 준비
cp .env.example .env
# .env를 열어 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET / PHOTO_ROOT 등을 세팅

# 5) 1회 실행
python -m app.cli run --once

# 6) 상태 확인
python -m app.cli status
```

---

## 2. 요구사항

- Python **3.11+**
- OS: Linux / macOS / Windows

---

## 3. 설치

### 3.1 가상환경 생성(권장)

이 저장소는 `run_loop.py`에서 기본 파이썬 경로로 `./venv/bin/python`을 사용합니다.
따라서 가상환경 폴더 이름을 **venv/** 로 맞추는 것을 권장합니다.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows:

```powershell
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## 4. 설정(.env)

`.env.example`를 복사해서 `.env`를 만들고 값을 채우세요.

```bash
cp .env.example .env
```

### 4.1 .env 항목

- `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET`
  - 네이버 이미지 검색 Open API 사용 시 필요
- `PHOTO_ROOT` (선택)
  - “바탕화면(Desktop)” 자동 탐지가 어려운 환경에서 저장 루트를 강제로 지정

### 4.2 저장 루트 규칙

저장 루트는 항상 다음 규칙을 따릅니다.

- 기본: `Desktop/Goyoonjung_Photos`
- `PHOTO_ROOT` 지정 시: `${PHOTO_ROOT}/Goyoonjung_Photos`

즉 `Desktop`(또는 `PHOTO_ROOT`) 아래에 `Goyoonjung_Photos` 폴더 하나만 생성/사용합니다.

---

## 5. 실행 방법

### 5.0 실제 실행 예시(출력 샘플)

드라이런 예시(다운로드/저장 없이 후보 수집만 점검):

```bash
python -m app.cli run --once --dry-run --providers "wikimedia" --keywords "Go Yoon-jung"
```

출력 예시(요약):

```text
[Collector] Starting batch...
--- Batch Summary [YYYY-MM-DDTHH:MM:SS+09:00] ---
dry_run: True
providers: wikimedia
candidates_total: 65
unique_urls: 40
OK: 0
DUPLICATE: 0
DOWNLOAD_FAIL: 0
...
[Collector] Batch finished with exit=0.
```

상태 확인 예시:

```bash
python -m app.cli status
```

```text
last_run_kst: YYYY-MM-DDTHH:MM:SS.ssssss+09:00
last_ok_count: 0
last_exit_code: 0
failures_by_reason:
  (있으면 출력됨)
```

> `--dry-run`은 OK가 0이어도 정상입니다(저장 자체를 안 하므로).


### 5.1 1회 실행(run --once)

기본 실행:

```bash
python -m app.cli run --once
```

Providers/키워드 지정:

```bash
python -m app.cli run --once \
  --providers "naver,wikimedia,instagram_seed,google" \
  --keywords "고윤정,Go Yoon-jung,고윤정 화보"
```

드라이런(다운로드/저장 없이 후보 수집만 점검):

```bash
python -m app.cli run --once --dry-run
```

### 5.2 상태 확인(status)

```bash
python -m app.cli status
```

`PHOTO_ROOT/.../meta/status.json`(내부 구현) 기반으로 최근 실행 결과를 보여줍니다.

### 5.3 주기 실행(run_loop.py)

`run_loop.py`는 다음을 수행하는 “서비스형 루프”입니다.

- 실행 전 **smoke test** 수행(빠른 사전 점검)
- `python -m app.cli run --once` 실행
- (성공 시) `reorganize.py` 실행(정리)
- 설정된 시간(기본 4시간) sleep 후 반복

1회만 돌리고 종료:

```bash
python run_loop.py --once
```

주기 실행(기본 4시간):

```bash
python run_loop.py
```

옵션 예시:

```bash
python run_loop.py \
  --interval-hours 6 \
  --providers "naver,wikimedia,instagram_seed" \
  --keywords "고윤정,Go Yoon-jung" \
  --timeout-seconds 3600
```

---

## 6. Providers(수집 소스)

프로바이더는 `--providers`로 콤마 구분 문자열로 지정합니다.

기본 권장 조합 예시:

- `naver` (API 키 필요)
- `wikimedia` (키 불필요)
- `instagram_seed` (키 불필요, seed URL만)
- `google` (키 불필요, 공개 RSS/HTML 기반 best-effort)

실험적/환경 의존:

- `twitter_rss`, `twitter_rsshub`, `twitter_snscrape`
  - 실패율이 높거나, 추가 구성(RSSHub/docker 등)이 필요할 수 있어 기본 비권장

### 6.1 Instagram Seed 사용법

`seeds/instagram_urls.txt`에 URL을 한 줄에 하나씩 넣습니다.

- 이미지 직링크면 그대로 후보로 사용
- 게시물 URL이면 HTML에서 `og:image` 추출을 시도
- 로그인 필요/차단/`og:image` 없음이면 스킵하고 `meta/failed.jsonl`에 사유 기록

예시:

```text
https://www.instagram.com/p/xxxxxxxxxxx/
https://instagram.fxxx-xx.fna.fbcdn.net/v/t51.2885-15/....jpg
```

### 6.2 RSSHub(선택)

`docker-compose.rsshub.yml`은 RSSHub 기반 수집을 실험할 때 사용합니다.

> 운영 환경에 따라 RSSHub는 외부 서비스에 부하를 줄 수 있으니 사용 시 주의하세요.

---

## 7. 저장 구조

실행 후 예시:

```text
Desktop/Goyoonjung_Photos/
  2026-02-17/
    naver/
    wikimedia/
    instagram_seed/
    google/
  Organized/
    Best_Cuts/
    Desktop_Wallpapers/
    Mobile_Wallpapers/
    General_HQ/
    Archive_LowRes/
  meta/
    items.jsonl
    failed.jsonl
    dedup.sqlite
    status.json
  logs/
    summary_2026-02-17.txt
```

- 날짜/프로바이더 하위 폴더: 원본 파일 저장
- `meta/items.jsonl`: 성공 메타데이터(저장 경로, 해상도, sha256 등)
- `meta/failed.jsonl`: 실패/스킵 + 사유(DOWNLOAD_FAIL, NOT_IMAGE 등)
- `meta/dedup.sqlite`: sha256 중복 제거 DB
- `logs/summary_YYYY-MM-DD.txt`: 실행 요약
- `Organized/*`: 해상도/용량 기준으로 “복사본”을 분류 저장(원본은 날짜 폴더에 유지)

---

## 8. 필터/정책

- 요청 간 딜레이: **0.8~1.6초 랜덤**(polite)
- 재시도: 기본 3회(백오프)
- 이미지 판별: HTTP `Content-Type`이 `image/*` 인지 확인
- 해상도 필터: 최소 한 변 **300px 이상**
- 중복 판별: `sha256(image_bytes)`
- 저장 방식: 다운로드 바이트 그대로 저장(변환/재인코딩 없음)

---

## 9. 종료 코드(Exit code)

`app.runner` 정책:

- `0 (EXIT_OK)`
  - 신규 저장(OK)이 있거나,
  - 새로 발견한 URL이 있었지만 전부 DUPLICATE/필터로 처리된 경우(정상 동작)
- `1 (EXIT_DEGRADED)`
  - 실행은 됐지만 “의미 있는 후보가 전혀 없음”(예: 후보 0)
- `2 (EXIT_ERROR)`
  - 예외 등으로 실행 자체가 실패

> 무인 주기 실행에서는 **EXIT_DEGRADED(1)** 도 “정상적인 상황”일 수 있습니다.

---

## 10. 트러블슈팅

### 10.1 `.env`가 커밋되면 안 됩니다
- 이 저장소는 `.gitignore`로 `.env`를 제외합니다.
- 혹시라도 `.env`가 Git에 올라갔다면 즉시 삭제 커밋 + 토큰 재발급이 필요합니다.

### 10.2 `status`는 뜨는데 이미지가 안 늘어요
- 중복 제거가 강하게 동작해서 대부분 `DUPLICATE`로 끝날 수 있습니다.
- `meta/failed.jsonl`, `logs/summary_YYYY-MM-DD.txt`를 먼저 확인하세요.

### 10.3 `NOT_IMAGE`가 많아요
- 제공자가 이미지 URL이 아닌 HTML/리다이렉트를 반환할 수 있습니다.
- providers를 줄이고(예: `naver,wikimedia,instagram_seed`) 먼저 안정화하는 것을 권장합니다.

### 10.4 Windows에서 경로/인코딩 문제가 있어요
- PowerShell에서 실행을 권장합니다.
- `PHOTO_ROOT`를 명시하면 Desktop 탐지 문제를 피할 수 있습니다.

---

## 11. 보안 체크리스트(중요)

이 프로젝트를 **퍼블릭 저장소**로 운영할 때 최소한 아래를 지키세요.

- [ ] `.env`는 절대 커밋하지 않기
- [ ] API 키/토큰은 README/이슈/PR에도 복붙하지 않기
- [ ] 로그 파일에 키가 찍히지 않는지 확인하기(필요 시 마스킹)
- [ ] seed 파일(예: 개인 계정 URL)이 민감할 수 있으면 공개 저장소에 넣지 않기

---

## 라이선스

필요하시면 라이선스(MIT 등)를 추가해 정리할 수 있습니다.
