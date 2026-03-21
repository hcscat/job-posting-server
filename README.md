# Job Posting Server

FastAPI 기반의 채용공고 수집 서버다. 웹 화면에서 검색 조건과 스케줄을 설정하고, 사람인/잡코리아/LinkedIn 등을 주기적으로 수집해 DB에 저장한 뒤 브라우저에서 조회할 수 있다.

## 현재 구현 범위

- 웹 UI
  - 대시보드
  - 설정 화면
  - 저장된 채용공고 조회 화면
- API
  - 설정 조회/저장
  - 수동 수집 실행
  - 저장 공고 조회
  - 실행 이력 조회
  - 스케줄 상태 조회
- 스케줄
  - 하루 중 특정 시각 실행
  - 몇 시간마다 반복 실행
- 저장소
  - 기본값: SQLite
  - 수집 결과: DB 저장
  - 실행별 export: `data/exports/runs/...`

## 기술 스택

- Backend: FastAPI
- Scheduler: APScheduler
- ORM/DB access: SQLAlchemy
- Template UI: Jinja2 + Vanilla JavaScript
- Default DB: SQLite

현재 구조는 빠르게 동작하는 단일 서버형 MVP에 맞춰져 있다. 추후 프론트엔드를 분리하고 싶으면 React/Next.js로 바꾸더라도 API 레이어는 그대로 재사용할 수 있다.

## 빠른 시작

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m job_harvest serve --host 127.0.0.1 --port 8000
```

브라우저에서 `http://127.0.0.1:8000`을 연다.

## 환경 변수

- `JOB_HARVEST_DATABASE_URL`
  - 지정하지 않으면 기본값으로 `SQLite`를 사용한다.
  - 예: Postgres 또는 Supabase 연결 문자열
- `JOB_HARVEST_DATA_DIR`
  - SQLite 파일과 export 기본 경로를 바꾸고 싶을 때 사용한다.

## 설정 방식

서버 시작 후 설정은 DB에 저장된다. 첫 실행 시 `config.yaml`이 있으면 그 값을 초기값으로 읽는다. 이후에는 웹 UI에서 저장한 값이 기준이다.

설정 가능한 항목:

- 지역
- 직무
- 학력
- 경력
- 고용형태
- 포함/제외 키워드
- 직접 검색어
- 하루 중 특정 실행 시각
- 몇 시간마다 반복 실행

## 주요 API

- `GET /api/settings`
- `PUT /api/settings`
- `POST /api/collect`
- `GET /api/jobs`
- `GET /api/runs`
- `GET /api/scheduler`
- `GET /health`

## 저장 구조

기본 로컬 데이터는 `data/` 아래에 저장된다.

- `data/app.db`: SQLite DB
- `data/exports/runs/...`: 실행별 JSON/CSV/Markdown export

이 경로들은 `.gitignore`에 포함되어 있어 GitHub에 올라가지 않는다.

## 구버전 YAML 실행도 유지

웹 서버가 아니라 단발 실행이 필요하면 아래도 사용할 수 있다.

```powershell
python -m job_harvest --config .\config.yaml show-queries
python -m job_harvest --config .\config.yaml run
python -m job_harvest --config .\config.yaml schedule
```

## 테스트

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
```
