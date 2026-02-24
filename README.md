# 고윤정 사진봇 (goyoonjung_photo_collector)

공개적으로 접근 가능한 소스(검색/오픈 데이터/seed URL 등)에서 배우 **고윤정** 관련 이미지를 수집해
로컬에 저장하는 Python CLI/배치 수집기입니다.

- 유료 API/유료 서비스 미사용(선택적으로 네이버 OpenAPI 키 사용 가능)
- 원본 바이트 그대로 저장(리사이즈/재인코딩 없음)
- 중복 제거(sha256 + SQLite)
- 기본 품질 게이트: **짧은 변 720px 이상만 저장**

> ⚠️ 원칙
> - 로그인/차단 우회, 비공개 콘텐츠 접근을 목표로 하지 않습니다.

---

## 문서
- 초보자용 사용설명서: `사용설명서.md`

---

## 빠른 시작

```bash
cd ~/Desktop/goyoonjung_photo_collector
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# (선택) NAVER_CLIENT_ID / NAVER_CLIENT_SECRET / PHOTO_ROOT 설정

python -m app.cli run --once --dry-run
python -m app.cli run --once
python -m app.cli status
```

---

## 저장 위치

기본:
- `Desktop/Goyoonjung_Photos/`

---

## Providers(수집 소스)

기본 조합 예시:
- `naver`(키 필요)
- `wikimedia`
- `instagram_seed`(seed 파일 기반)
- `google`(best-effort)

---

## 보안

- `.env`는 절대 커밋 금지
- 로그/seed 파일에 민감정보가 섞이지 않도록 주의
