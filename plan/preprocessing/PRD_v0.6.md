# 전처리 PRD

- 문서 버전: `v0.6`
- 작성일: `2026-02-28`
- 이전 버전: `PRD_v0.5.md` (덮어쓰기 금지)

## 변경 사항 (v0.5 → v0.6)

- 전체 파이프라인 실행 완료 (preprocess.py full run + Kakao 지오코딩)
- parquet 최종 현황 확정: 119,558행, 좌표 보유 114,840건
- 지오코딩 결과 반영: 13,737 대상 → 9,019 성공 / 4,718 실패
- "parquet 전체 재생성 필요" 미결 사항 해소

## 상태

**완료** — 코드 구현 + 실행 검증 모두 완료.

## 목표

크롤러 수집 `raw_csv/`를 정제·지오코딩하여 분석 가능한 parquet 산출물 생성.
가동상태 무관 전체 시설 보존. 증분 처리로 월 1회 크롤 후 변경 파일만 재처리.

## 구현 스크립트

### `src/preprocessing/preprocess.py`

```bash
# 전체 실행
uv run python src/preprocessing/preprocess.py

# 증분 실행 (신규 파일만)
uv run python src/preprocessing/preprocess.py --mode incremental

# 지오코딩 없이 변환만
uv run python src/preprocessing/preprocess.py --no-geocode
```

환경변수: `KAKAO_API_KEY` (`.env` 파일에 저장, 지오코딩 사용 시 필수)

## 파이프라인 단계

### Step 1. raw_csv 통합 + float 변환

- `raw_csv/*.csv` glob 읽기 (`utf8-lossy`)
- `source_file` 컬럼 추가 (증분 추적용)
- 가동상태 필터 없음 — 정상가동·가동중단·폐기 전체 보존
- `위도`, `경도`: 빈 문자열 → null → Float64 cast

### Step 2. 지오코딩 (인라인 retry 포함)

- 기존 캐시 로드 → dict 메모리 유지
- 대상: `위도` 또는 `경도` null 행
- 각 행마다 순서대로 시도, 성공하면 즉시 멈춤:
  1. `소재지도로명주소` (원본)
  2. `소재지도로명주소` 정제 후
  3. `소재지지번주소` (원본)
  4. `소재지지번주소` 정제 후
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
| `geocode_cache_kakao_raw.csv` | API 호출 결과 전체 (ok / no_result / error) |
| `geocode_failures_kakao_raw.csv` | 모든 후보 주소 실패 행 (reason: `no_result` / `http_400`) |

### Step 4. 출력

- `pv_facility_processed.parquet`: 전체 결과
- `preprocess_state.csv`: 파일별 처리 이력

## 현황 (2026-02-28 기준)

| 항목 | 수치 |
|------|------|
| raw_csv 파일 수 | 135개 |
| 통합 행 수 | 119,558 |
| 정상가동 | 111,155 |
| 가동중단 | 6,874 |
| 폐기 | 1,529 |
| 지오코딩 대상 (좌표 결측) | 13,737 |
| 지오코딩 성공 | 9,019 |
| 지오코딩 실패 | 4,718 |
| 최종 좌표 보유 | 114,840 |
| 최종 좌표 결측 | 4,718 |

## 미결 사항

1. `http_400` 4건 원인 미분류
2. 크롤러 `modified_date` 기반 변경 파일 감지 미구현 (증분 모드 고도화)

## 의존성

- `polars`: CSV 읽기 / parquet 쓰기
- `requests`: Kakao 로컬 API 호출
- `python-dotenv` 또는 shell `.env`: KAKAO_API_KEY 주입
