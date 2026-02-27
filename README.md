# pv_profile_augmentation

전국 태양광 발전 데이터 파이프라인 프로젝트입니다.

이 프로젝트의 1차 목표는 다음 3가지입니다.

1. 공공 데이터 소스에서 데이터를 주기적으로 수집한다.
2. 수집 데이터를 행정구역 기준으로 정규화한다.
3. 발전소/설비 정보를 grid(공간 격자) 기준으로 매핑한다.

통계적 증강(누락 샘플 보정)은 중요하지만, 현재는 후속 단계로 두고 데이터 수집과 공간 기준 정합성을 먼저 완성합니다.

## Session Handoff (2026-02-24)

데스크톱에서 바로 이어서 작업할 수 있도록 현재 상태를 요약합니다.

1. 최신 코드 기준 커밋: `daf9bf9` (origin/master 반영 완료)
2. 크롤러는 Playwright 단일 경로만 사용 (Selenium 제거됨)
3. 증분 기준은 `수정일` 기반이며 상태 파일을 사용
4. 수집 상태:
- `generator_next/source/raw_csv/pv_facility_profile_state.csv` 기준 `135`건
- 페이지 기준 `27페이지 x 5개` 목록을 커버하는 상태까지 수집 완료
5. 핵심 실행 명령:

```bash
uv sync
uv run playwright install chromium
uv run python generator_next/crawlers/data_go_kr_solar_download_playwright.py --headless
```

6. 주요 산출물:
- `generator_next/source/raw_csv/*.csv` (원천 CSV 스냅샷)
- `generator_next/source/raw_csv/pv_facility_profile_state.csv` (증분 상태)
- `generator_next/source/raw_csv/download_log_playwright.csv` (최근 실행 로그)

7. 다음 작업 권장:
- `raw_csv`를 입력으로 DB 적재 스크립트 작성 (`upsert` 방식)
- 행정구역/격자 매핑 파이프라인(`geo_enrich`) 구현
- 월간 배치 스케줄러와 실패 알림 추가

## 배경

- RPS 계열 데이터는 모수(전체 규모)는 크지만 상세 프로필이 비어 있는 레코드가 존재할 수 있습니다.
- data.go.kr 상세 파일은 속성은 풍부하지만 커버리지/업데이트 주기가 일정하지 않을 수 있습니다.
- 따라서 월 단위 자동 수집 + 표준화 + 공간 매핑 파이프라인을 먼저 고정해야 이후 증강 모델의 신뢰도가 올라갑니다.

## 현재 작업 원칙

- 신규 기능 개발은 `generator_next/`에서 진행
- `generator/`는 레거시로 보존(참조만, 수정 최소화)
- 크롤링/수집 자동화 우선, 증강 모델링은 2단계
- 수집 엔진은 Playwright 단일 경로로 운영

자세한 신규 작업 원칙은 `generator_next/README.md`를 참고합니다.

## 디렉터리 개요

- `generator_next/`: 신규 파이프라인 개발 영역
- `generator_next/crawlers/`: 수집 스크립트(Playwright)
- `generator_next/source/raw_csv/`: 원천 CSV 저장소
- `generator/v2/`: 레거시 코드/산출물
- `generator/v2/source/openstreetmap/subs_region_mapping.csv`: 행정구역 매핑 참고 데이터
- `rps_rawdata.csv`: RPS 원천 샘플(루트 보관)

## 데이터 소스(초안)

- RPS 계열 원천 데이터(크롤링/원천 파일)
- data.go.kr 태양광 발전소 상세 CSV(지역별 파일)
- 국토/행정구역 경계 데이터(추후 사용자 제공 예정)
- 필요 시 OSM/보조 지오데이터(주소/행정구역 정합 보조)

## 운영 목표 아키텍처

월 1회 정기 실행을 기본으로 설계합니다.

1. `ingest_rps`
- RPS 원천 수집/갱신
- 수집 시점(`snapshot_date`) 기록

2. `ingest_profile`
- data.go.kr 상세 CSV 수집(Playwright)
- `수정일` 기반 증분 수집
- 상태 파일(`pv_facility_profile_state.csv`) 기록

3. `normalize`
- 컬럼명/단위/코드 표준화
- 행정구역 코드(SIG/CD 등) 정규화
- 주소/지명 정리

4. `geo_enrich`
- 좌표가 있어도 단순 lat/lon 사용에 그치지 않음
- 행정구역 경계 데이터와 공간 조인
- grid cell ID 부여(공통 격자 체계)

5. `publish_base_dataset`
- 분석/모델 입력용 기준 테이블 생성
- 데이터 품질 지표(누락률, 매핑률) 산출

6. `augment` (후속 단계)
- 누락 구간 통계적 보정
- 행정구역/격자 제약을 만족하는 방식으로 증강

## 공간 처리 원칙

- 단순 좌표 기반 집계만 사용하지 않음
- 행정구역 경계 안에 들어가는지 우선 검증
- grid 매핑은 행정구역 정보를 유지한 상태로 수행
- 공간 정합 실패 레코드는 별도 큐로 분리해 재처리

## 자동화 원칙

- 기본 배치 주기: 월 1회
- 변경 감지 점검: 주 1회(원천 업데이트 여부 확인)
- 실패 알림/재시도 정책 포함
- 실행 결과는 로그 + 메타테이블로 관리

## 실행 환경

- Python 3.12+
- 패키지 관리: `uv`
- 주요 의존성: `playwright`, `pandas`

예시:

```bash
uv sync
uv run playwright install chromium
uv run python generator_next/crawlers/data_go_kr_solar_download_playwright.py --headless
```

## 단기 로드맵

1. 수집 파이프라인 안정화(재시도/모니터링)
2. 행정구역/격자 표준 스키마 확정
3. 국토 데이터 반영한 공간 조인 파이프라인 구축
4. 월간 자동 실행(job/scheduler) 구성
5. 기준 데이터셋 품질 리포트 자동 생성

## 네이밍 제안

`detailprofiledata` 대신 아래 명칭을 권장합니다.

- `pv_facility_profile` (권장)
- `pv_profile_detail`

이유: 데이터 의미(태양광 설비 프로필)와 테이블 목적이 명확하고 운영/협업 시 혼선이 적습니다.
