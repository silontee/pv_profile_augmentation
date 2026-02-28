# 전처리 PRD

- 문서 버전: `v0.3`
- 작성일: `2026-02-28`
- 이전 버전: `PRD_v0.2.md` (덮어쓰기 금지)

## 목표

크롤러가 수집한 `raw_csv/` 데이터를 정제·지오코딩하여 분석 가능한 parquet 산출물 생성.
증분 처리 지원으로 월 1회 크롤 후 변경 파일만 재처리.

## 구현 완료 스크립트

### `generator_next/preprocessing/preprocess.py` — 메인 파이프라인

```bash
# 전체 실행 (기본)
uv run python generator_next/preprocessing/preprocess.py

# 증분 실행 (신규 파일만)
uv run python generator_next/preprocessing/preprocess.py --mode incremental

# 지오코딩 없이 필터링만
uv run python generator_next/preprocessing/preprocess.py --no-geocode

# 전체 옵션
uv run python generator_next/preprocessing/preprocess.py \
  --raw-csv-dir    generator_next/source/raw_csv \
  --output-dir     generator_next/source/processed \
  --cache-path     generator_next/source/logs/geocode/geocode_cache_kakao_raw.csv \
  --failures-path  generator_next/source/logs/geocode/geocode_failures_kakao_raw.csv \
  --crawler-state  generator_next/source/logs/crawler/pv_facility_profile_state.csv \
  --mode           full | incremental \
  --no-geocode
```

### `generator_next/preprocessing/geocode_retry.py` — 지오코딩 재시도

```bash
uv run python generator_next/preprocessing/geocode_retry.py
```

- 이미 생성된 parquet의 좌표 결측 행만 대상
- 주소 정제(`clean_addr_for_geocode`) 후 달라진 주소로만 Kakao API 재호출
- 원본 주소는 이미 캐시에 `no_result` → 재호출 없이 스킵
- 성공 시 parquet 좌표 갱신 + 캐시 append

환경변수: `KAKAO_API_KEY` (지오코딩 사용 시 필수)

## 파이프라인 단계

### Step 1. raw_csv 통합 + 필터링

- `raw_csv/*.csv` glob 읽기 (`utf8-lossy` 인코딩, 전체 컬럼 문자열로 로드)
- `source_file` 컬럼 추가 (파일명 기준, 증분 추적용)
- `가동상태구분명 == "정상가동"` 필터 (빈 문자열·가동중단 제거)
- `위도`, `경도`: 빈 문자열 → null → Float64 cast

### Step 2. 지오코딩

- 기존 캐시 로드 → dict 메모리 유지
- 대상: `위도` 또는 `경도` null 행
- 주소 시도 순서: `소재지도로명주소` → `소재지지번주소` (fallback)
- 각 주소에 대해 원본 → 정제(`clean_addr_for_geocode`) 순으로 시도
- 캐시 히트 → API 호출 없이 재사용
- API 성공 → `documents[0].address.x/y` 사용
- 좌표 유효성 검증: 위도 30~45, 경도 120~135
- API 호출 간격: 0.05초 (부하 방지)

#### 주소 정제 규칙 (`clean_addr_for_geocode`)

| 패턴 | 처리 |
|------|------|
| `(괄호내용)` | 제거 |
| `토지위`, `건물 위`, `부지 위` 등 | 제거 |
| `외N필지` | 제거 |
| `N번지 M호` | `N-M` 변환 |
| `번지` 접미사 | 제거 |
| 쉼표 포함 다필지 주소 | 첫 번째만 사용 |
| 공백 구분 다필지 번지 | 첫 번째만 사용 |

### Step 3. 로그 갱신

- `geocode_cache_kakao_raw.csv`: 신규 항목만 append (기존 항목 보존)
- `geocode_failures_kakao_raw.csv`: 실패 항목 append
  - reason: `no_result` / `http_400` / `error:{type}`

### Step 4. 출력

- `pv_facility_processed.parquet`: 필터링 + 지오코딩 반영 결과
- `preprocess_state.csv`: 파일별 처리 이력

## 입출력 규약

### 입력

| 경로 | 설명 |
|------|------|
| `generator_next/source/raw_csv/*.csv` | 시군구별 원천 CSV (`utf-8-sig` BOM) |
| `generator_next/source/logs/geocode/geocode_cache_kakao_raw.csv` | 기존 지오코딩 캐시 |
| `generator_next/source/logs/crawler/pv_facility_profile_state.csv` | 크롤러 상태 (증분 모드용) |

### 출력

| 경로 | 컬럼 |
|------|------|
| `generator_next/source/processed/pv_facility_processed.parquet` | 원천 컬럼 전체 + `source_file` |
| `generator_next/source/processed/preprocess_state.csv` | `source_file, row_count_raw, row_count_filtered, processed_at` |

## 증분 처리 (`--mode incremental`)

1. `preprocess_state.csv`에서 기처리 파일 목록 로드
2. `raw_csv/`에서 미처리 파일 탐색 (신규 파일만)
3. 기존 parquet 로드 → 해당 `source_file` 행 제거 → 신규 처리 결과 concat → 저장
4. `preprocess_state.csv` upsert (기존 항목 유지, 재처리 항목만 갱신)

## 현황 (2026-02-27 기준)

| 항목 | 수치 |
|------|------|
| raw_csv 파일 수 | 135개 |
| 통합 행 수 | 119,558 |
| 정상가동 필터 후 | 111,155 |
| 좌표 결측 (지오코딩 대상) | 13,021 |
| 지오코딩 캐시 | 48,401건 (ok: 37,714 / no_result: 10,683 / error: 4) |
| 실패 로그 | 21,370건 (no_result: 21,366 / http_400: 4) |

## 미결 사항

1. `geocode_retry.py` 실행 후 좌표 복구 수치 미확인
2. `http_400` 4건 원인 미분류 — 주소 자체 문제인지 API 문제인지 확인 필요
3. 증분 모드의 변경 파일 감지: 현재 신규 파일만 처리, 크롤러 `modified_date` 비교 미구현

## 의존성

- `polars`: CSV 읽기/parquet 쓰기
- `requests`: Kakao API 호출
- `csv` (표준): 로그 append
