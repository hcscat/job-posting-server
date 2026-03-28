# Job Posting Server

한국어 원문 번역입니다. 영문 원문은 [README.md](./README.md)에서 볼 수 있습니다.

FastAPI 기반 채용 공고 수집 서버 및 웹 대시보드입니다.

이 서버는 다음 기능을 제공합니다.

- 웹 UI에서 수집 설정 저장
- 광범위 IT/개발 채용공고 수동 수집
- 하루 중 특정 시각 또는 몇 시간 간격으로 수집
- 구조화 메타데이터는 SQLite에 저장
- 원본 listing/detail HTML은 압축 raw blob으로 저장
- 상세 페이지를 휴리스틱 또는 OpenAI로 정리
- 브라우저에서 수집된 공고와 실행 이력 조회

## 기술 스택

- Backend: FastAPI
- Scheduler: APScheduler
- ORM: SQLAlchemy
- Template UI: Jinja2 + Vanilla JavaScript
- 기본 DB: SQLite

## Git Bash 빠른 시작

작업 폴더로 이동한 뒤, 한 번만 가상환경을 만들면 됩니다.

```bash
cd /d/HCS/work/automation
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

그 다음부터는 메뉴 스크립트를 실행하면 됩니다.

```bash
cd /d/HCS/work/automation
./job_harvest.sh
```

메뉴에서 다음 작업을 선택할 수 있습니다.

- 의존성 설치 또는 업데이트
- 웹 서버 실행
- 자동 리로드 모드로 웹 서버 실행
- `config.yaml` 기준 1회 수집
- `config.yaml` 기준 스케줄 수집
- 생성되는 검색어 확인
- 테스트 실행
- config 경로, host, port 변경

## 수집 방식

현재 기본 모드는 `broad_it_scan` 입니다.

- 하나의 긴 검색문자열에 의존하지 않고, 넓은 IT 시드를 기준으로 여러 사이트를 순회합니다.
- 사이트에서 더 이상 새로운 URL을 주지 않을 때까지 페이지를 넘기며 수집합니다. `listing_page_limit` 이 0이면 페이지 끝까지 갑니다.
- listing/detail 원문 HTML은 `data/raw/` 아래에 gzip 압축 blob으로 저장합니다.
- URL 기반 중복 제거로 이미 알고 있는 공고는 상세 재수집 주기 안에서는 다시 긁지 않습니다.
- 상세 본문을 읽어 직군, 기술스택, 요구사항, 주요업무, 복지 같은 정리 데이터를 함께 저장합니다.

OpenAI 기반 정리를 쓰려면:

- 로컬 환경 변수 `OPENAI_API_KEY` 설정
- UI 또는 `config.yaml` 에서 `AI provider` 를 `openai` 로 변경
- 사용할 `AI model` 지정

## 수동 명령 실행

메뉴를 거치지 않고 직접 실행하고 싶다면:

```bash
cd /d/HCS/work/automation
./.venv/Scripts/python.exe -m job_harvest serve --host 127.0.0.1 --port 8000
```

자주 쓰는 다른 명령은 다음과 같습니다.

```bash
./.venv/Scripts/python.exe -m job_harvest serve --host 127.0.0.1 --port 8000 --reload
./.venv/Scripts/python.exe -m job_harvest --config ./config.yaml run
./.venv/Scripts/python.exe -m job_harvest --config ./config.yaml schedule
./.venv/Scripts/python.exe -m job_harvest --config ./config.yaml show-queries
./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

브라우저에서 [http://127.0.0.1:8000](http://127.0.0.1:8000) 을 열면 됩니다.

## 환경 변수

- `JOB_HARVEST_DATABASE_URL`
  - 기본값은 SQLite 입니다.
  - 나중에 PostgreSQL 또는 Supabase 연결 문자열로 바꿔 사용할 수 있습니다.
- `JOB_HARVEST_DATA_DIR`
  - SQLite 파일과 export 저장 기본 경로를 변경합니다.
- `OPENAI_API_KEY`
  - `AI provider` 가 `openai` 일 때만 필요합니다.

## 설정 적용 방식

서버 시작 시 동작은 다음과 같습니다.

- DB에 설정이 이미 있으면 DB 값을 사용합니다.
- DB 설정이 아직 없고 `config.yaml` 이 있으면 그 값을 초기값으로 불러옵니다.
- 이후에는 웹 UI에서 저장한 설정이 기본 기준값이 됩니다.

## 주요 API

- `GET /api/settings`
- `PUT /api/settings`
- `POST /api/collect`
- `GET /api/jobs`
- `GET /api/runs`
- `GET /api/scheduler`
- `GET /health`

## 데이터 경로

기본 로컬 데이터는 `data/` 아래에 저장됩니다.

- `data/app.db`: SQLite 데이터베이스
- `data/raw/...`: 압축 raw listing/detail HTML blob
- `data/exports/runs/...`: 실행별 JSON, CSV, Markdown export

이 경로들은 `.gitignore` 에 포함되어 있어 Git에 올라가지 않습니다.
