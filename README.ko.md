# Job Posting Server

영문 문서는 [README.md](./README.md)에서 볼 수 있습니다.

FastAPI 기반 채용 공고 수집기이자 수동 실행 중심의 웹 콘솔입니다.

## 주요 기능

- 웹 화면에서 수집 설정 저장
- IT/개발 채용 공고 수동 수집
- SQLite에 정규화된 공고 데이터 저장
- 목록/상세 raw 응답을 압축 blob으로 저장
- 휴리스틱 또는 OpenAI 기반 상세 정보 정리
- 실행 이력, 공고 상세, raw snapshot 조회

## 기술 스택

- Backend: FastAPI
- ORM: SQLAlchemy
- UI: Jinja2 + Vanilla JavaScript
- 기본 DB: SQLite
- 선택적 AI 정리: OpenAI API

## Git Bash 빠른 시작

```bash
git clone <repository-url>
cd job-posting-server
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./job_harvest.sh
```

메뉴에서 할 수 있는 작업은 다음과 같습니다.

- 의존성 설치 또는 업데이트
- 웹 서버 실행
- 리로드 모드 서버 실행
- `config.yaml` 기준 1회 수집
- 생성되는 검색어 확인
- 테스트 실행
- config 경로, host, port 변경

## 수동 실행 흐름

1. 서버를 실행합니다.
2. 브라우저에서 [http://127.0.0.1:8000](http://127.0.0.1:8000)을 엽니다.
3. 웹 화면에서 수집 설정을 저장합니다.
4. 대시보드 또는 `POST /api/collect`로 수집을 실행합니다.
5. 결과는 다음 화면에서 확인합니다.
   - `/jobs`: 정규화된 공고 목록
   - `/jobs/{job_id}`: 공고 상세와 raw 연결 정보
   - `/runs/{run_id}`: 실행 단위 공고 목록과 raw manifest
   - `/raw/{category}/{sha256}`: 저장된 raw 본문

## 수집 방식

기본 모드는 `broad_it_scan` 입니다.

- 하나의 긴 검색 문자열 대신 여러 IT 시드를 사용합니다.
- 사이트가 더 이상 새 URL을 주지 않을 때까지 페이지를 순회합니다.
- URL 기준 중복 제거로 refetch window 안의 상세 재수집을 줄입니다.
- raw 데이터와 정규화 데이터는 분리 저장합니다.
- 상세 본문은 직군, 기술 스택, 요구사항, 주요 업무, 복지 등으로 정리합니다.

OpenAI 정리를 사용하려면:

- 서버 환경 변수에 `OPENAI_API_KEY`를 설정합니다.
- UI에서 `AI provider`를 `openai`로 바꿉니다.
- UI에서 `AI model`을 지정합니다.

## 자주 쓰는 명령

```bash
./.venv/Scripts/python.exe -m job_harvest serve --host 127.0.0.1 --port 8000
./.venv/Scripts/python.exe -m job_harvest serve --host 127.0.0.1 --port 8000 --reload
./.venv/Scripts/python.exe -m job_harvest --config ./config.yaml run
./.venv/Scripts/python.exe -m job_harvest --config ./config.yaml show-queries
./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

## 환경 변수

- `JOB_HARVEST_DATABASE_URL`
  SQLite 대신 PostgreSQL 또는 Supabase를 사용할 때 지정합니다.
- `JOB_HARVEST_DATA_DIR`
  SQLite, raw blob, export 저장 루트를 바꿉니다.
- `OPENAI_API_KEY`
  `AI provider`가 `openai`일 때만 필요합니다.

## 주요 API

- `GET /api/settings`
- `PUT /api/settings`
- `POST /api/collect`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/raw/{category}/{sha256_hex}`
- `GET /health`

## 데이터 경로

기본 데이터는 `data/` 아래에 저장됩니다.

- `data/app.db`: SQLite 데이터베이스
- `data/raw/...`: 압축 raw listing/detail blob
- `data/exports/runs/...`: 실행별 JSON, CSV, Markdown export

이 경로들은 `.gitignore`에 포함되어 Git에 올라가지 않습니다.

## 프로젝트 문서

- 프로젝트 정체성 문서: [docs/project-identity.ko.md](./docs/project-identity.ko.md)
- 채용 사이트 조회 조건 조사: [docs/research/job-site-filters.ko.md](./docs/research/job-site-filters.ko.md)
- 필터 표준화 코드 맵: [job_harvest/filter_taxonomy.py](./job_harvest/filter_taxonomy.py)
- 에이전트 스킬 팩: [agent-pack/README.md](./agent-pack/README.md)
