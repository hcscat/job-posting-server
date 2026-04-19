# 채용 사이트별 조회 조건 조사

조사일: 2026-04-19  
대상 사이트: 사람인, 잡코리아, LinkedIn, 점핏, 원티드, 로켓펀치, 리멤버, 잡플래닛, Blind

## 목적

프로젝트에서 여러 채용 사이트의 검색 조건을 하나의 표준 필드로 정리하기 위한 조사 문서다.  
현재 프로젝트 설정에 바로 매핑 가능한 필드와, 차기 확장이 필요한 필드를 구분한다.

## 표준 필드

### 현재 설정에 바로 수용 가능한 필드

- `roles`: 직무, 직군, 포지션, 상위 직무
- `keywords`: 자유 키워드, 기술 키워드, 제목/본문 검색어
- `locations`: 국가, 지역, 시/도, 시/군/구, 원격 근무 범위
- `companies`: 회사명
- `experience_levels`: 신입/경력, 연차, 시니어리티
- `education_levels`: 학력
- `employment_types`: 정규직, 계약직, 인턴, 프리랜서 등
- `required_terms`: 반드시 포함해야 하는 용어
- `exclude_keywords`: 제외어

### 차기 확장 권장 필드

- `industries`: 산업/업종, 사업 분야
- `salary_ranges`: 연봉, 보상 범위
- `company_types`: 대기업, 외국계, 공기업, 상장사, 헤드헌팅 여부
- `company_sizes`: 회사 규모
- `position_levels`: 직급, 직책, 레벨
- `majors`: 전공
- `certifications`: 자격증, 라이선스
- `preferred_conditions`: 우대조건, 언어, 근무 가능 조건
- `welfare`: 복리후생
- `skills`: 기술스택, 구조화된 스킬
- `tags`: 사이트 태그, 전문분야 태그
- `workplace_types`: 원격, 하이브리드, 상시 출근
- `date_posted`: 등록일, 게시일
- `deadline`: 마감일
- `easy_apply`: 간편 지원, Easy Apply
- `applicant_signals`: 지원자 수, 경쟁도
- `network_signals`: 내 네트워크, 추천 연결
- `leader_positions`: 리더급 전용
- `headhunting`: 헤드헌팅 공고 포함/제외
- `theme_tags`: 적극 채용 중, AI 선도 기업 같은 테마형 태그

## 사이트별 정리

### 사람인

- 확인된 조회 조건
  - 키워드
  - 근무지/지역
  - 산업/업종
  - 상위 직무, 세부 직무
  - 근무형태/고용형태
  - 학력
  - 상장 여부
  - 등록일, 수정일
  - 마감일
  - 헤드헌팅/파견 제외
  - 정렬
- 프로젝트 매핑
  - `keywords` -> `keywords`
  - `loc_cd`, `loc_mcd`, `loc_bcd` -> `locations`
  - `job_mid_cd`, `job_cd` -> `roles`
  - `job_type` -> `employment_types`
  - `edu_lv` -> `education_levels`
  - `ind_cd` -> `industries`
  - `stock` -> `company_types`
  - `published`, `updated` -> `date_posted`
  - `deadline` -> `deadline`
  - `sr=directhire` -> `headhunting`
- 근거
  - 공식 API 문서에 요청 파라미터가 명시되어 있어 가장 신뢰도가 높다.

### 잡코리아

- 확인된 조회 조건
  - 지역
  - 직무
  - 산업
  - 고용형태
  - 직급/직책/급여
  - 학력
  - 전공
  - 자격증
  - 우대조건
  - 복리후생
  - 대기업, 외국계, 공기업, 상장기업 등 기업 구분
  - 공채, 학력별, 산업별, 직무별 탐색
- 프로젝트 매핑
  - 직무 -> `roles`
  - 지역 -> `locations`
  - 고용형태 -> `employment_types`
  - 학력 -> `education_levels`
  - 산업 -> `industries`
  - 직급/직책 -> `position_levels`
  - 급여 -> `salary_ranges`
  - 전공 -> `majors`
  - 자격증 -> `certifications`
  - 우대조건 -> `preferred_conditions`
  - 복리후생 -> `welfare`
  - 기업 구분 -> `company_types`
- 근거
  - 공개 채용 상세검색 페이지에 필터명이 직접 노출된다.

### LinkedIn

- 확인된 조회 조건
  - Location
  - Date posted
  - Easy Apply
  - Company
  - Experience level
  - Employment type
  - Under 10 applicants
  - In your network
- 프로젝트 매핑
  - `Location` -> `locations`
  - `Date posted` -> `date_posted`
  - `Easy Apply` -> `easy_apply`
  - `Company` -> `companies`
  - `Experience level` -> `experience_levels`
  - `Employment type` -> `employment_types`
  - `Under 10 applicants` -> `applicant_signals`
  - `In your network` -> `network_signals`
- 근거
  - LinkedIn Help 공식 문서에 필터 목록이 명시된다.

### 점핏

- 확인된 조회 조건
  - 기술스택
  - 경력
  - 지역
  - 태그
- 프로젝트 매핑
  - 기술스택 -> `skills`
  - 경력 -> `experience_levels`
  - 지역 -> `locations`
  - 태그 -> `tags`
- 근거
  - 공개 포지션 탐색 페이지에서 필터명이 직접 확인된다.
- 해석
  - 점핏은 일반 채용 포털보다 개발자 전용 구조가 강하므로, `skills`와 `tags` 필드의 우선순위가 높다.

### 원티드

- 공개적으로 확인된 탐색 조건
  - 재택근무
  - 계약직
  - 인턴
  - 일본 현지 취업
  - 대규모 채용 중
  - 적극 채용 중
  - AI 선도 기업
  - 누적투자 100억 이상
  - 회사 규모형 태그
  - 인원 급성장
  - 퇴사율 5% 이하
  - 보너스
  - 외국어 필수 포지션
- 프로젝트 매핑
  - 재택근무 -> `workplace_types`
  - 계약직, 인턴 -> `employment_types`
  - 외국어 필수 포지션 -> `preferred_conditions`
  - 회사 규모형 태그 -> `company_sizes`
  - 나머지 배지/테마 -> `theme_tags`
- 주의
  - 공개 정적 HTML 기준으로는 지역, 경력, 직군 필터가 명시적으로 노출되지 않았다.
  - 실제 로그인 상태나 클라이언트 렌더링 이후 더 많은 필터가 있을 가능성은 있으나, 이번 조사에서는 공식적으로 확인된 범위만 표준화 대상으로 반영한다.

### 로켓펀치

- 확인된 조회 조건
  - 직군
  - 산업
  - 채용조건
  - 전문분야
  - 개별 공고 스니펫 기준 `Seniority`, `Employment Type`, `Work Type`
- 프로젝트 매핑
  - 직군 -> `roles`
  - 산업 -> `industries`
  - 채용조건 -> `employment_types`
  - 전문분야 -> `tags`
  - Seniority -> `experience_levels`
  - Work Type -> `workplace_types`
- 주의
  - 현재 `rocketpunch.com/jobs`는 봇 차단으로 공개 HTML 직접 열람이 제한된다.
  - 공식 채용 서비스 소개서에 구직자 검색 조건이 명시되어 있어 해당 문서를 기준으로 정리했다.

### 리멤버

- 확인된 조회 조건
  - 직무
  - 연봉
  - 지역
  - 경력
  - 기업 유형
  - 산업/업종
  - 리더급 포지션만 보기
  - 헤드헌팅 공고 포함
  - 간편 지원만 보기
  - 지원한 공고 포함
  - 적극 채용 중인 공고
- 프로젝트 매핑
  - 직무 -> `roles`
  - 연봉 -> `salary_ranges`
  - 지역 -> `locations`
  - 경력 -> `experience_levels`
  - 기업 유형 -> `company_types`
  - 산업/업종 -> `industries`
  - 리더급 포지션만 보기 -> `leader_positions`
  - 헤드헌팅 공고 포함 -> `headhunting`
  - 간편 지원만 보기 -> `easy_apply`
  - 적극 채용 중인 공고 -> `theme_tags`
- 근거
  - 공개 채용공고 목록 화면에서 필터명이 직접 노출된다.

### 잡플래닛

- 확인된 조회 조건
  - 공채
  - 경력
  - 근무 지역
  - 고용 형태
  - 학력
  - 산업 카테고리 탐색
- 프로젝트 매핑
  - 공채 -> `theme_tags`
  - 경력 -> `experience_levels`
  - 근무 지역 -> `locations`
  - 고용 형태 -> `employment_types`
  - 학력 -> `education_levels`
  - 산업 카테고리 -> `industries`
- 주의
  - 공개 검색 페이지에서는 직무 필터가 명시적으로 보이지 않았고, 검색창 중심 구조가 강하다.

### Blind

- 확인된 조회 조건
  - Search by job title or company
  - Date Posted
  - Location
  - Remote Only
  - Required Experience
  - Salary
  - Company Size
  - Company Technologies
- 프로젝트 매핑
  - 제목/회사 검색 -> `keywords`
  - Date Posted -> `date_posted`
  - Location -> `locations`
  - Remote Only -> `workplace_types`
  - Required Experience -> `experience_levels`
  - Salary -> `salary_ranges`
  - Company Size -> `company_sizes`
  - Company Technologies -> `skills`

## 프로젝트 반영 우선순위

### 1차

- `industries`
- `skills`
- `workplace_types`
- `salary_ranges`
- `company_types`

이 다섯 개를 먼저 추가하면 사람인, 잡코리아, 점핏, 리멤버, 블라인드의 주요 필터를 대부분 흡수할 수 있다.

### 2차

- `position_levels`
- `preferred_conditions`
- `tags`
- `date_posted`
- `deadline`
- `easy_apply`
- `headhunting`

### 3차

- `company_sizes`
- `welfare`
- `majors`
- `certifications`
- `network_signals`
- `applicant_signals`
- `theme_tags`

## 현재 구현상 권장 해석

- `직무`, `직군`, `포지션`, `상위 직무`는 우선 `roles`로 통합한다.
- `기술스택`, `회사 기술`, `전문분야`는 현재는 `keywords` 또는 `required_terms`에 흡수할 수 있지만, 구조화 손실이 크므로 `skills` 필드 추가를 권장한다.
- `산업/업종`, `사업분야`는 현재 설정에 직접 대응 필드가 없으므로 `industries`를 별도 필드로 추가하는 것이 맞다.
- `원격`, `하이브리드`, `상시 출근`은 위치와 분리하여 `workplace_types`로 관리해야 한다.
- `리더급`, `대규모 채용`, `적극 채용`, `AI 선도 기업` 같은 값은 `theme_tags`로 수용하고, 랭킹/추천 로직에 활용하는 것이 적합하다.

## 참고 링크

- 사람인 API: https://oapi.saramin.co.kr/guide/job-search
- 잡코리아 채용 상세검색: https://www.jobkorea.co.kr/recruit/joblist
- LinkedIn Help: https://www.linkedin.com/help/linkedin/answer/a511259
- 점핏 포지션 탐색: https://jumpit.saramin.co.kr/positions
- 원티드 메인: https://www.wanted.co.kr/
- 원티드 공고 노출 기준: https://help.wanted.co.kr/hc/ko/articles/22577722059673-%EA%B3%B5%EA%B3%A0-%EB%85%B8%EC%B6%9C-%EC%88%9C%EC%84%9C-%EA%B8%B0%EC%A4%80%EC%9D%B4-%EA%B6%81%EA%B8%88%ED%95%B4%EC%9A%94
- 로켓펀치 채용 서비스 소개서: https://static.rocketpunch.com/service/RocketPunch-Service-Kit-Recruiting-201706.pdf
- 리멤버 채용공고: https://career.rememberapp.co.kr/job/postings
- 잡플래닛 채용 검색: https://www.jobplanet.co.kr/job/search
- Blind Jobs: https://www.teamblind.com/jobs/
