# PRD — 태양광 발전소 프로파일 증강 파이프라인 v0.7

작성일: 2026-03-02
이전 버전: PRD_v0.6.md

---

## 1. 프로젝트 목적

태양광 발전소 전기사업허가 데이터(data.go.kr)를 자동 수집·정제·지오코딩하여 `rps_rawdata`와 실제 세부 발전량 데이터 간 간극을 보완하는 파이프라인 구축.

최종 목표: 발전소별 발전량 추정 및 입지 적합성 분석 가능한 증강 데이터셋 생성.

---

## 2. 전체 파이프라인 (5단계)

```
[1. 크롤링] → [2. 전처리·지오코딩] → [3. UI 시각화] → [4. 통계적 증강] → [산출물]
```

### Track 1. 크롤링 — 완료
- `data_go_kr_solar_download_playwright.py`: Playwright, 시군구별 CSV 증분 수집
- `recloud_solar_crawler.py`: recloud.energy.or.kr RPS 이용률 비동기 수집
- `openinframap_power_crawler.py`: Overpass API, OSM 전력 인프라 GeoJSON

### Track 2. 전처리·지오코딩 — 완료
- raw_csv → Polars 통합·정규화 → parquet
- Kakao API 지오코딩 (도로명→지번 fallback, retry)
- 산출물: `src/data/processed/pv_facility_processed.parquet`

### Track 3. UI 시각화 — **v0.1 완료**
- 풀스택 Docker 구성 (PostgreSQL+PostGIS / FastAPI / React+MapLibre)
- 인터랙티브 지도: 시군구 클러스터 + 개별 마커 (zoom 10 전환)
- 클러스터 상태별 3레이어 (정상가동=초록, 가동중단=회색, 폐기=빨강)
- 검색·필터 패널, 발전소 상세 패널, 레이어 토글
- 세부: `plan/ui/PRD_v0.1.md`

### Track 4. 통계적 증강 — **미착수**
- recloud RPS 이용률 × data.go.kr 발전소 허가 데이터 결합
- 발전량 추정 모델링
- 입지 적합성 스코어링
- 방법론 미확정 → 별도 PRD 필요

---

## 3. 데이터 현황 (2026-03-02 기준)

| 데이터 소스 | 수량 | 비고 |
|---|---|---|
| data.go.kr 원천 CSV | 119,558행 | 정상가동 111,155 / 가동중단 6,874 / 폐기 1,529 |
| 좌표 보유 (parquet) | 114,840건 | 지오코딩 완료 포함 |
| 좌표 결측 (parquet) | 4,718건 | 주소 불명확으로 지오코딩 실패 |
| recloud RPS | 196,295개소 | 시군구별 이용률 집계 (cnt 합산 기준) |
| OSM 변전소 | 1,185건 | by_sido GeoJSON |
| OSM 송배전선 | 4,685건 | by_sido GeoJSON |
| OSM 태양광발전소 | 10,646건 | by_sido GeoJSON (참고용) |

**설비용량 분포 (유효 데이터 기준)**
- 중앙값: 99 kW / p90: 324 kW / p99: 999 kW
- 실질 범위: 0 ~ 1,000 kW (1% 초과분은 오기 또는 대형 설비)

**설치연도 분포 (유효 데이터 기준)**
- 유효 범위: 2008 ~ 2025년
- 주요 구간: 2014 ~ 2025년 (전체 데이터의 95%+)
- 오기 데이터: 1900년(3,270건), 9999년(79건) 등 → 필터 필요

---

## 4. 코드 구조

```
generator/              # 레거시 — 건드리지 않음
src/         # 모든 신규 개발
  crawlers/             # Track 1
  preprocessing/        # Track 2
  map/                  # 정적 HTML 지도 (folium) — 레거시화 예정
  ui/                   # Track 3 — 풀스택 UI
    docker-compose.yml
    backend/            # FastAPI + PostGIS
    frontend/           # React + MapLibre GL JS
  source/
    raw_csv/            # data.go.kr CSV
    recloud/            # RPS 이용률 CSV
    openinframap/       # OSM GeoJSON
    processed/          # parquet 산출물
    logs/
plan/
  overall/              # 전체 PRD
  ui/                   # UI 트랙 PRD
  crawling/             # 크롤링 트랙 PRD
  preprocessing/        # 전처리 트랙 PRD
  statistical_augmentation/  # 통계 증강 트랙 PRD (미작성)
```

---

## 5. 환경 및 실행

```bash
# Python 파이프라인 (Track 1, 2)
uv sync
uv run python src/crawlers/data_go_kr_solar_download_playwright.py --headless
uv run python src/preprocessing/preprocess.py

# UI (Track 3)
cd src/ui
docker compose up --build   # 최초
docker compose up -d         # 이후
# 접속: http://localhost:5173
```

---

## 6. 현재 블로커

1. `http_400` 4건 크롤링 오류 원인 미분류
2. 설치연도/설비용량 오기 데이터 클렌징 미완료 (UI 슬라이더 범위로 우회 중)
3. 통계적 증강 방법론 미선정

---

## 7. 다음 단계

- [ ] Track 4 통계적 증강 PRD 작성 및 방법론 확정
- [ ] UI: 시군구 경계 GeoJSON 확보 → boundary 레이어 구현
- [ ] UI: RPS 이용률 데이터 DB 적재 → 클러스터 팝업에 이용률 표시
- [ ] 오기 설치연도 데이터 전처리 단계에서 클렌징
