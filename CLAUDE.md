# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

태양광 발전소 전기사업허가 데이터(data.go.kr)를 자동 수집·정제·지오코딩하여 `rps_rawdata`와 실제 세부 발전량 데이터 간 간극을 보완하는 파이프라인. 최종 목표는 통계적 증강까지 포함.

PRD 문서: `plan/overall/PRD_v0.6.md` (단일 기준 문서)
세부 트랙 PRD: `plan/crawling/`, `plan/preprocessing/`, `plan/map/`, `plan/statistical_augmentation/`

## 환경 및 실행

패키지 관리자: `uv` (pyproject.toml + uv.lock)
Python: 3.12+
핵심 라이브러리: Polars, Playwright, requests, folium

```bash
# 의존성 설치
uv sync

# 크롤러 실행 (프로젝트 루트에서)
uv run python generator_next/crawlers/data_go_kr_solar_download_playwright.py --headless

# 전처리 + 지오코딩 실행
uv run python generator_next/preprocessing/preprocess.py

# 지도 생성
uv run python generator_next/map/generate_map.py
```

## 코드 구조

```
generator/          # 레거시 — 건드리지 않음, 안정화 후 제거 예정
generator_next/     # 모든 신규 개발은 여기서만
  crawlers/         # 수집 스크립트
  preprocessing/    # 전처리 스크립트
  map/              # 지도 시각화 스크립트 + output/
  source/
    raw_csv/        # data.go.kr 시군구별 전기사업허가 CSV
    recloud/        # recloud 시군구별 RPS 이용률 CSV (rps_*.csv)
    openinframap/   # OSM 전력 인프라 GeoJSON (by_sido/)
    processed/      # 전처리 산출물 (parquet, preprocess_state.csv)
    logs/
      crawler/      # 크롤 상태/다운로드 로그
      geocode/      # 지오코딩 캐시/실패 로그
plan/               # PRD 문서들 (버전 관리, 덮어쓰기 금지)
  crawling/
  preprocessing/
  map/
  statistical_augmentation/
```

## 파이프라인 4단계

**1. 크롤링** (`generator_next/crawlers/`)
- `data_go_kr_solar_download_playwright.py`: Playwright로 data.go.kr 시군구별 CSV 증분 다운로드
- `recloud_solar_crawler.py`: recloud.energy.or.kr에서 시군구별 RPS 이용률 비동기 수집
- `openinframap_power_crawler.py`: Overpass API로 OSM 전력 인프라(변전소·송배전선·발전소) GeoJSON 수집

**2. 전처리** (`generator_next/preprocessing/preprocess.py`) — 완료
- raw_csv → Polars 통합·정규화 → parquet 출력 (가동상태 전체 보존)
- Kakao API 지오코딩 인라인 retry: 도로명→지번, 원본→정제 순 fallback
- 실패 로그: `geocode_failures_kakao_raw.csv`

**3. 지도 시각화** (`generator_next/map/generate_map.py`) — 완료
- folium + FastMarkerCluster로 114,840개 발전소 포인트 클러스터링
- 가동상태별 색상 구분 + 변전소·송배전선 레이어
- 출력: `generator_next/map/output/pv_map.html`

**4. 통계적 증강** (미착수 — 방법론 미확정)
- recloud RPS 이용률과 data.go.kr 발전소 허가 데이터 결합
- 발전량 추정, 입지 적합성 분석 예정

## 핵심 파일 스키마

**raw_csv 컬럼** (원천 CSV):
`태양광발전시설명, 소재지도로명주소, 소재지지번주소, 위도, 경도, 설치상세위치구분명, 가동상태구분명, 설비용량, 공급전압, 주파수, 설치연도, 세부용도, 허가일자, 허가기관, 설치면적, 데이터기준일자`

**지오코딩 캐시** (`geocode_cache_kakao_raw.csv`):
`geo_addr, lon, lat, status, updated_at` — status: `ok` / `no_result` / `error`

**지오코딩 실패 로그** (`geocode_failures_kakao_raw.csv`):
`geo_addr, reason, updated_at`

## 데이터 현황 (2026-02-28 기준)

| 데이터 소스 | 수량 | 비고 |
|---|---|---|
| data.go.kr 원천 CSV | 119,558행 | 정상가동 111,155 / 가동중단 6,874 / 폐기 1,529 |
| 좌표 보유 (parquet) | 114,840건 | 지오코딩 완료 포함 |
| 좌표 결측 (parquet) | 4,718건 | 주소 불명확으로 지오코딩 실패 |
| recloud RPS | 196,295개소 | 시군구별 이용률 집계 |
| OSM 변전소 | 1,185건 | by_sido GeoJSON |
| OSM 송배전선 | 4,685건 | by_sido GeoJSON |
| OSM 태양광발전소 | 10,646건 | by_sido GeoJSON (참고용) |

## 현재 블로커

1. `http_400` 4건 원인 미분류
2. 통계적 증강 방법론 미선정

## 개발 규칙

- 신규 코드는 반드시 `generator_next/`에 작성
- PRD 문서는 덮어쓰기 금지 — 수정 시 버전 올린 새 파일 생성 (예: `PRD_v0.4.md`)
- 인코딩: CSV 읽기/쓰기 시 `utf-8-sig` 사용 (BOM 포함, 한글 호환)
- 경로는 프로젝트 루트 기준 상대경로 사용
