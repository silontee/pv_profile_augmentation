# 전처리 PRD

- 문서 버전: `v0.4`
- 작성일: `2026-02-28`
- 이전 버전: `PRD_v0.3.md` (덮어쓰기 금지)

## 변경 사항 (v0.3 → v0.4)

- `geocode_retry.py` 제거 — retry 로직이 `preprocess.py` 내 인라인으로 통합되어 있음
- `geocode_failed_review.csv` 제거 — 불필요
- 파이프라인을 `preprocess.py` 단일 실행으로 단순화

## 목표

크롤러가 수집한 `raw_csv/` 데이터를 정제·지오코딩하여 분석 가능한 parquet 산출물 생성.
증분 처리 지원으로 월 1회 크롤 후 변경 파일만 재처리.

## 구현 스크립트

### `src/preprocessing/preprocess.py` — 메인 파이프라인 (유일한 실행 진입점)

```bash
# 전체 실행 (기본)
uv run python src/preprocessing/preprocess.py

# 증분 실행 (신규 파일만)
uv run python src/preprocessing/preprocess.py --mode incremental

# 지오코딩 없이 필터링만
uv run python src/preprocessing/preprocess.py --no-geocode

# 전체 옵션
uv run python src/preprocessing/preprocess.py \
  --raw-csv-dir    src/data/raw_csv \
  --output-dir     src/data/processed \
  --cache-path     src/data/logs/geocode/geocode_cache_kakao_raw.csv \
  --failures-path  src/data/logs/geocode/geocode_failures_kakao_raw.csv \
  --crawler-state  src/data/logs/crawler/pv_facility_profile_state.csv \
  --mode           full | incremental \
  --no-geocode
```

환경변수: `KAKAO_API_KEY` (지오코딩 사용 시 필수)

## 표준 실행 흐름

```
크롤링 (incremental) → preprocess.py (incremental) → parquet 갱신
```

1. 크롤러가 새 CSV 수집 (`raw_csv/`)
2. `preprocess.py --mode incremental` 실행
   - 미처리 파일만 선별 (`preprocess_state.csv` 기준)
   - 통합·필터링·지오코딩(인라인 retry 포함) 수행
   - 기존 parquet에 병합 저장
3. 별도 retry 스크립트 불필요 — 지오코딩 재시도가 Step 2 안에서 자동 처리됨

## 파이프라인 단계

### Step 1. raw_csv 통합 + 필터링

- `raw_csv/*.csv` glob 읽기 (`utf8-lossy` 인코딩, 전체 컬럼 문자열로 로드)
- `source_file` 컬럼 추가 (파일명 기준, 증분 추적용)
- `가동상태구분명 == "정상가동"` 필터 (빈 문자열·가동중단 제거)
- `위도`, `경도`: 빈 문자열 → null → Float64 cast

### Step 2. 지오코딩 (인라인 retry 포함)

- 기존 캐시 로드 → dict 메모리 유지
- 대상: `위도` 또는 `경도` null 행
- 각 행마다 아래 순서로 시도, 성공하면 즉시 멈춤:
  1. `소재지도로명주소` (원본)
  2. `소재지도로명주소` 정제 후 (원본과 다른 경우만)
  3. `소재지지번주소` (원본)
  4. `소재지지번주소` 정제 후 (원본과 다른 경우만)
- 캐시 히트 → API 호출 없이 재사용
- API 성공 → `documents[0].address.x/y` 사용
- 좌표 유효성 검증: 위도 30~45, 경도 120~135
- API 호출 간격: 0.05초

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

| 파일 | 기록 내용 |
|------|----------|
| `geocode_cache_kakao_raw.csv` | API 호출 결과 전체 (ok / no_result / error) — 신규 항목만 append |
| `geocode_failures_kakao_raw.csv` | 모든 후보 주소 시도 후에도 좌표 미확보된 행 — reason: `no_result` / `http_400` / `error:{type}` |

### Step 4. 출력

- `pv_facility_processed.parquet`: 필터링 + 지오코딩 반영 결과
- `preprocess_state.csv`: 파일별 처리 이력

## 입출력 규약

### 입력

| 경로 | 설명 |
|------|------|
| `src/data/raw_csv/*.csv` | 시군구별 원천 CSV (`utf-8-sig` BOM) |
| `src/data/logs/geocode/geocode_cache_kakao_raw.csv` | 기존 지오코딩 캐시 |
| `src/data/logs/crawler/pv_facility_profile_state.csv` | 크롤러 상태 (증분 모드용) |

### 출력

| 경로 | 컬럼 |
|------|------|
| `src/data/processed/pv_facility_processed.parquet` | 원천 컬럼 전체 + `source_file` |
| `src/data/processed/preprocess_state.csv` | `source_file, row_count_raw, row_count_filtered, processed_at` |
| `src/data/logs/geocode/geocode_cache_kakao_raw.csv` | 신규 지오코딩 결과 append |
| `src/data/logs/geocode/geocode_failures_kakao_raw.csv` | 실패 행 append |

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

1. `preprocess.py` 실제 실행 검증 미완료
2. `http_400` 4건 원인 미분류 — 주소 자체 문제인지 API 문제인지 확인 필요
3. 증분 모드의 크롤러 `modified_date` 기반 변경 파일 감지 미구현

## 의존성

- `polars`: CSV 읽기/parquet 쓰기
- `requests`: Kakao API 호출
- `csv` (표준): 로그 append
