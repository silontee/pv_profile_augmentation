# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

태양광 발전소 전기사업허가 데이터(data.go.kr)를 자동 수집·정제·지오코딩하여 `rps_rawdata`와 실제 세부 발전량 데이터 간 간극을 보완하는 파이프라인. 최종 목표는 통계적 증강까지 포함.

PRD 문서: `plan/overall/PRD_v0.5.md` (단일 기준 문서)
세부 트랙 PRD: `plan/crawling/`, `plan/preprocessing/`, `plan/statistical_augmentation/`

## 환경 및 실행

패키지 관리자: `uv` (pyproject.toml + uv.lock)
Python: 3.12+
핵심 라이브러리: Polars, Pandas, Playwright, requests

```bash
# 의존성 설치
uv sync

# 크롤러 실행 (프로젝트 루트에서)
uv run python generator_next/crawlers/data_go_kr_solar_download_playwright.py

# 헤드리스 모드로 실행
uv run python generator_next/crawlers/data_go_kr_solar_download_playwright.py --headless
```

## 코드 구조

```
generator/          # 레거시 — 건드리지 않음, 안정화 후 제거 예정
generator_next/     # 모든 신규 개발은 여기서만
  crawlers/         # 수집 스크립트
  source/
    raw_csv/        # data.go.kr 시군구별 전기사업허가 CSV
    recloud/        # recloud 시군구별 이용률 CSV
    openinframap/   # OSM 전력 인프라 GeoJSON (by_sido/)
    processed/      # 전처리 산출물 (parquet)
    logs/
      crawler/      # 크롤 상태/다운로드 로그
      geocode/      # 지오코딩 캐시/실패 로그
plan/               # PRD 문서들 (버전 관리, 덮어쓰기 금지)
  crawling/         # 크롤러별 PRD
  preprocessing/    # 전처리 PRD
  statistical_augmentation/
```

## 파이프라인 3단계

**1. 크롤링** (`generator_next/crawlers/data_go_kr_solar_download_playwright.py`)
- Playwright로 data.go.kr에서 시군구별 CSV 증분 다운로드
- 상태 파일(`pv_facility_profile_state.csv`)로 중복 방지: `uid:{uuid}` 또는 `title:{제목}` 키
- 상태 `ok`, `skipped:up_to_date`, `timeout`, `error:{type}`, `warn:close_failed`
- 기본 경로: `--download-dir generator_next/source/raw_csv`, `--state-path generator_next/source/logs/crawler/pv_facility_profile_state.csv`

**2. 전처리** (`generator_next/preprocessing/preprocess.py`)
- raw_csv → Polars로 통합·정규화 → parquet 출력
- 주소 기반 Kakao API 지오코딩 (결측 위도/경도 보완) — 실패 시 `geocode_failures_kakao_raw.csv`
- fallback 순서: `소재지도로명주소` → `소재지지번주소` (각각 원본 → 정제 주소 순으로 인라인 재시도)

**3. 통계적 증강** (미구현 — 방법론 미확정)
- `rps_rawdata.csv`(프로젝트 루트)와 세부 발전량 간 간극 보완

## 핵심 파일 스키마

**raw_csv 컬럼** (원천 CSV):
`태양광발전시설명, 소재지도로명주소, 소재지지번주소, 위도, 경도, 설치상세위치구분명, 가동상태구분명, 설비용량, 공급전압, 주파수, 설치연도, 세부용도, 허가일자, 허가기관, 설치면적, 데이터기준일자`

**지오코딩 캐시** (`geocode_cache_kakao_raw.csv`):
`geo_addr, lon, lat, status, updated_at` — status: `ok` / `no_result` / `error`

**지오코딩 실패 로그** (`geocode_failures_kakao_raw.csv`):
`geo_addr, reason, updated_at`

## 데이터 현황 (2026-02-27 기준)

- 원천 CSV 통합 행 수: 119,558
- 지오코딩 캐시: 48,401건 (ok: 37,714 / no_result: 10,683 / error: 4)
- 실패 로그: 21,370건 (no_result: 21,366 / http_400: 4)

## 현재 블로커

1. 전처리 파이프라인 실행 검증 미완료 (코드는 있음)
2. `http_400` 4건 원인 미분류
3. 통계적 증강 방법론 미선정

## 개발 규칙

- 신규 코드는 반드시 `generator_next/`에 작성
- PRD 문서는 덮어쓰기 금지 — 수정 시 버전 올린 새 파일 생성 (예: `PRD_v0.4.md`)
- 인코딩: CSV 읽기/쓰기 시 `utf-8-sig` 사용 (BOM 포함, 한글 호환)
- 경로는 프로젝트 루트 기준 상대경로 사용
