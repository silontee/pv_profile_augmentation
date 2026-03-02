# PRD — UI 시각화 트랙 v0.1

작성일: 2026-03-02
상태: **완료 (v0.1 기준)**

---

## 1. 목적

전처리·지오코딩이 완료된 발전소 데이터를 웹 브라우저에서 인터랙티브하게 탐색할 수 있는 풀스택 UI 구축.
folium 정적 HTML 출력(`generator_next/map/`)의 한계(레이어 토글 불가, 검색 불가, 대용량 렌더링 한계)를 해소.

---

## 2. 아키텍처

```
generator_next/ui/
  docker-compose.yml         # 4개 서비스 오케스트레이션
  backend/
    app/
      main.py                # FastAPI 앱 진입점
      models.py              # SQLAlchemy ORM (PostGIS)
      schemas.py             # Pydantic v2 응답 스키마
      api/
        facilities.py        # 발전소 API 엔드포인트
        infra.py             # 변전소·송배전선 API
        stats.py             # 대시보드 통계
      db/
        session.py           # asyncpg 연결 풀
        load_data.py         # ETL (parquet → PostgreSQL)
  frontend/
    src/
      components/
        map/MapView.tsx       # MapLibre GL 메인 지도
        map/LayerToggle.tsx   # 레이어 토글 UI
        panel/SearchPanel.tsx # 검색·필터 패널
        panel/DetailPanel.tsx # 발전소 상세 패널
        common/RangeSlider.tsx # 듀얼 핸들 범위 슬라이더
      hooks/
        useFacilities.ts     # 지도 데이터 로딩 훅
        useSearch.ts         # 검색 훅 (debounce 300ms)
      stores/
        mapStore.ts          # 뷰포트·선택 상태
        searchStore.ts       # 검색·필터 상태
        uiStore.ts           # 레이어 가시성·패널 모드
      api/
        facilities.ts        # 발전소 API 클라이언트
        infra.ts             # 인프라 API 클라이언트
```

### Docker 서비스

| 서비스 | 이미지 | 포트 | 역할 |
|---|---|---|---|
| `db` | postgis/postgis:16-3.4 | 5432 | PostgreSQL + PostGIS |
| `etl` | ui-backend (one-shot) | — | parquet → DB 적재 |
| `backend` | ui-backend | 8000 | FastAPI (uvicorn, hot-reload) |
| `frontend` | ui-frontend | 5173 | React + Vite dev server |

---

## 3. 백엔드 API

### GET /api/facilities/clusters
- zoom < 10 용 시군구 집계
- 응답: `sigungu, cnt, cnt_active, cnt_stopped, cnt_retired, center_lat, center_lng`
- 파라미터: `cap_min, cap_max, year_min, year_max` (선택)

### GET /api/facilities/bbox
- zoom ≥ 10 뷰포트 내 개별 마커
- 파라미터: `xmin, ymin, xmax, ymax, status, cap_min, cap_max, year_min, year_max`

### GET /api/facilities
- 텍스트 검색 + 필터 + 페이지네이션 (per_page 최대 200)
- 파라미터: `q, status, cap_min, cap_max, year_min, year_max, page, per_page`

### GET /api/facilities/{id}
- 단건 상세 + 반경 5km 내 발전소 수 + 최근접 변전소

### GET /api/infra/substations/bbox, /api/infra/powerlines/bbox
- 변전소·송배전선 bbox 조회

### GET /api/stats
- 전체 통계 (total, active, stopped, retired, no_coord, total_capacity_mw)

---

## 4. 프론트엔드 주요 기능

### 4-1. 지도 (MapView)

**zoom 전환 (임계: zoom 10)**
- zoom < 10: 시군구 집계 클러스터 원형 3개 레이어 표시
- zoom ≥ 10: 개별 마커 CircleLayer 표시

**클러스터 레이어 (zoom < 10)**
- `LYR_CLUSTERS_ACTIVE` (초록, #2ecc71): 정상가동 수 기준 크기
- `LYR_CLUSTERS_STOPPED` (회색, #95a5a6): 가동중단 수 기준 크기
- `LYR_CLUSTERS_RETIRED` (빨강, #e74c3c): 폐기 수 기준 크기
- hover 팝업: 시군구명 + 상태별 건수 breakdown

**개별 마커 레이어 (zoom ≥ 10)**
- 색상: 정상가동=초록, 가동중단=회색, 폐기=어두운 회색
- 클릭 → DetailPanel 전환 + 하이라이트

**인프라 레이어**
- 변전소: 파란 원형 마커 (bbox 기반 lazy load)
- 송배전선: 주황 라인 (bbox 기반 lazy load)

**기술 이슈 해결**
- `mapLoaded` state: 스타일 로드 완료 후 데이터 effect 재실행 (race condition 방지)
- `layersRef`: `onMove` 클로저에서 최신 레이어 상태 접근
- `usePolling: true` (vite.config.ts): Windows + Docker HMR 파일 변경 감지

### 4-2. 레이어 토글

- 정상가동 / 가동중단 / 폐기 각각 개별 토글
- 변전소 / 송배전선 / 시군구 경계 토글
- zoom 전환 시 레이어 상태 반영 (클러스터·마커 동시 제어)

### 4-3. 검색 패널

- 텍스트 검색 (시설명·주소, debounce 300ms)
- 가동상태 필터 버튼 (전체 / 정상가동 / 가동중단 / 폐기)
- 설비용량 슬라이더: 0 ~ 1,000 kW, step 10 (데이터 p99 기준)
- 설치연도 슬라이더: 2008 ~ 2025년, step 1 (유효 데이터 기준)
- 결과 리스트 + 페이지네이션 (50건/페이지)
- 행 클릭 → flyTo + DetailPanel 전환

### 4-4. RangeSlider (듀얼 핸들)

- 포인터 이벤트 기반 커스텀 구현 (input[type=range] z-index 버그 방지)
- `setPointerCapture`: 드래그 중 트랙 밖 이탈 시 끊김 없음
- `onChangeCommitted`: 손 뗄 때만 스토어 갱신 → API 호출 최소화
- 하단에 min/max 힌트 표시

---

## 5. 데이터 흐름

```
parquet (generator_next/source/processed/)
  └─ ETL (load_data.py)
       └─ PostgreSQL/PostGIS (pv_facility, substation, power_line)
            └─ FastAPI
                 ├─ /api/facilities/clusters  → useFacilities (zoom < 10)
                 ├─ /api/facilities/bbox      → useFacilities (zoom ≥ 10)
                 ├─ /api/facilities           → useSearch (검색 패널)
                 └─ /api/infra/*             → MapView (인프라 레이어)
```

---

## 6. 실행

```bash
cd generator_next/ui

# 최초 실행 (빌드 + ETL 적재 포함)
docker compose up --build

# 이후 실행
docker compose up -d

# 프론트 소스 변경 후 (vite.config.ts 등 볼륨 미마운트 파일 변경 시)
docker compose build frontend && docker compose up -d frontend
```

접속: `http://localhost:5173`

---

## 7. 현재 상태 및 미완료 항목

| 항목 | 상태 |
|---|---|
| DB 스키마 + ETL | 완료 |
| 전체 API 엔드포인트 | 완료 |
| 지도 클러스터/마커 | 완료 |
| 레이어 토글 | 완료 |
| 검색·필터 패널 | 완료 |
| 상세 패널 | 완료 |
| 시군구 경계 레이어 | 미구현 (boundary GeoJSON 미확보) |
| RPS 이용률 연동 | 미구현 (통계적 증강 트랙 의존) |
| 인증·배포 설정 | 미구현 (dev 환경 기준) |
