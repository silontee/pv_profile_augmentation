# PRD — 태양광 발전소 프로파일 증강 파이프라인 v0.9

작성일: 2026-03-03
이전 버전: PRD_v0.8.md

---

## 1. 프로젝트 목적

태양광 발전소 전기사업허가 데이터(data.go.kr)를 자동 수집·정제·지오코딩하여 `rps_rawdata`와 실제 세부 발전량 데이터 간 간극을 보완하는 파이프라인 구축.

최종 목표: 발전소별 발전량 추정 및 입지 적합성 분석 가능한 증강 데이터셋 생성.

---

## 2. v0.9 변경 요약 (v0.8 대비)

| 항목 | 변경 내용 |
|---|---|
| 토지피복 버그픽스 | WFS 필드명 `lcm_cd` → `l2_code` 수정 (색상 미표시 해결) |
| 레거시 삭제 | `src/map/` (folium 정적 지도), `generator/` (구버전 RPS 데이터) 제거 |
| UI Track | v0.2 → **v0.3** |

---

## 3. 전체 파이프라인

```
[1. 크롤링] → [2. 전처리·지오코딩] → [3. UI 시각화] → [4. 통계적 증강] → [산출물]
```

### Track 1. 크롤링 — 완료

- `data_go_kr_solar_download_playwright.py`: Playwright, 시군구별 CSV 증분 수집
- `recloud_solar_crawler.py`: recloud.energy.or.kr RPS 이용률 비동기 수집
- `openinframap_power_crawler.py`: Overpass API, OSM 전력 인프라 GeoJSON
- `land_cover_crawler.py`: 환경부 EGIS WFS 토지피복 오프라인 수집

### Track 2. 전처리·지오코딩 — 완료

- raw_csv → Polars 통합·정규화 → parquet
- Kakao API 지오코딩 (도로명→지번 fallback, retry)
- 산출물: `src/data/processed/pv_facility_processed.parquet`

### Track 3. UI 시각화 — **v0.3 완료**

- 풀스택 Docker 구성 (PostgreSQL+PostGIS / FastAPI / React+MapLibre)
- 인터랙티브 지도: 시군구 클러스터 + 개별 마커 (zoom 10 전환)
- 검색·필터 패널, 발전소 상세 패널, 레이어 토글
- 3D 지형: MapTiler DEM + hillshade + pitch 50°
- 토지피복: EGIS WFS → FastAPI 프록시 → 7색 벡터 폴리곤 (색상 정상화 v0.3)
- 토지피복 범례 (우상단 오버레이)
- 필터 → 지도 동기화
- 세부: `plan/ui/PRD_v0.3.md`

### Track 4. 통계적 증강 — **미착수**

- recloud RPS 이용률 × data.go.kr 발전소 허가 데이터 결합
- 발전량 추정 모델링
- 입지 적합성 스코어링 (토지피복 + 경사도 활용 예정)

---

## 4. 데이터 현황 (2026-03-03 기준)

| 데이터 소스 | 수량 | 비고 |
|---|---|---|
| data.go.kr 원천 CSV | 119,558행 | 정상가동 111,155 / 가동중단 6,874 / 폐기 1,529 |
| 좌표 보유 (parquet) | 114,840건 | 지오코딩 완료 포함 |
| 좌표 결측 (parquet) | 4,718건 | 주소 불명확 |
| recloud RPS | 196,295개소 | 시군구별 이용률 집계 |
| OSM 변전소 | 1,185건 | by_sido GeoJSON |
| OSM 송배전선 | 4,685건 | by_sido GeoJSON |
| EGIS 토지피복 (온라인) | — | `/api/landcover` 실시간 프록시 |
| EGIS 토지피복 (오프라인) | 미수집 | `land_cover_crawler.py`로 수집 예정 |

---

## 5. 코드 구조 (v0.9)

```
src/
  crawlers/
    data_go_kr_solar_download_playwright.py
    recloud_solar_crawler.py
    openinframap_power_crawler.py
    land_cover_crawler.py
  preprocessing/preprocess.py
  ui/
    docker-compose.yml             # DB 포트: 5433
    backend/app/api/
      facilities.py / infra.py / stats.py
      landcover.py                 # WFS 필드: l2_code (v0.9 수정)
    frontend/src/components/map/
      MapView.tsx
      LayerToggle.tsx
      LandcoverLegend.tsx
  data/
    raw_csv / recloud / openinframap / processed / logs
    landcover/                     # EGIS 오프라인 수집 예정
plan/
  overall/ ui/ crawling/ preprocessing/ statistical_augmentation/
```

---

## 6. 환경 및 실행

```bash
# Python 파이프라인
uv sync
uv run python src/crawlers/data_go_kr_solar_download_playwright.py --headless
uv run python src/preprocessing/preprocess.py

# 토지피복 오프라인 수집 (선택)
uv run python src/crawlers/land_cover_crawler.py --sido 서울 경기

# UI
cd src/ui
docker compose up --build   # 최초 (pyproject.toml 변경 시 --no-cache)
docker compose up -d
# 접속: http://localhost:5173 / DB: localhost:5433
```

---

## 7. 현재 블로커

1. `http_400` 4건 크롤링 오류 미분류
2. 설치연도/설비용량 오기 데이터 클렌징 미완료
3. 통계적 증강 방법론 미선정
4. UI 시군구 경계 GeoJSON 미확보
5. MapTiler API 키 소스 하드코딩 (배포 전 env 분리 필요)

---

## 8. 다음 단계

- [ ] Track 4 통계적 증강 PRD 작성
- [ ] 국토정보플랫폼 DEM → 경사도 레이어
- [ ] EGIS 토지피복 → PostGIS ETL (실시간 프록시 → 오프라인 전환)
- [ ] 시군구 경계 GeoJSON 확보
- [ ] MapTiler API 키 환경 변수 분리
