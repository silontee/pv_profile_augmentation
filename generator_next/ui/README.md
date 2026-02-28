# PV Profile Map — 태양광 발전소 인터랙티브 지도

data.go.kr 전기사업허가 데이터 119,558개소 + OpenInfraMap 전력 인프라를 PostGIS 기반으로 실시간 조회하는 풀스택 웹 애플리케이션.

## 기술 스택

| 계층 | 기술 | 버전 |
|------|------|------|
| Frontend | React + TypeScript + MapLibre GL JS | 18.3 / 5.6 / 4.7 |
| 번들러 | Vite | 5.4 |
| 상태관리 | Zustand | 5.0 |
| 스타일링 | TailwindCSS (다크 테마) | 3.4 |
| Backend | FastAPI (async) | 0.115+ |
| ORM | SQLAlchemy 2.0 + asyncpg | 2.0 |
| DB | PostgreSQL 16 + PostGIS 3.4 | 16 |
| 패키지 관리 | uv (backend) / pnpm (frontend) | - |
| 컨테이너 | Docker Compose | - |

## 빠른 시작

```bash
cd generator_next/ui
docker compose up --build
```

기동 순서: `db` (healthcheck) → `etl` (데이터 적재, ~5초) → `backend` → `frontend`

| 서비스 | URL | 설명 |
|--------|-----|------|
| Frontend | http://localhost:5173 | 인터랙티브 지도 |
| Backend API | http://localhost:8000 | REST API |
| Swagger Docs | http://localhost:8000/docs | API 문서 자동 생성 |
| PostgreSQL | localhost:5432 | DB 직접 접속 (`pv_user` / `pv_password`) |

종료:
```bash
docker compose down          # 컨테이너 종료 (DB 데이터 유지)
docker compose down -v       # 컨테이너 + DB 볼륨 삭제 (초기화)
```

## 디렉토리 구조

```
ui/
├── docker-compose.yml              # 풀스택 오케스트레이션
├── README.md
├── backend/
│   ├── Dockerfile                  # Python 3.12 + uv (multi-stage)
│   ├── pyproject.toml
│   ├── uv.lock
│   └── app/
│       ├── main.py                 # FastAPI 진입점, CORS, 라이프사이클
│       ├── models.py               # SQLAlchemy ORM 모델
│       ├── schemas.py              # Pydantic v2 응답 스키마
│       ├── api/
│       │   ├── facilities.py       # 발전소 엔드포인트 (5개)
│       │   ├── infra.py            # 인프라 엔드포인트 (3개)
│       │   └── stats.py            # 대시보드 통계 (1개)
│       └── db/
│           ├── session.py          # AsyncIO 세션 설정
│           └── load_data.py        # ETL: parquet/GeoJSON → PostGIS
└── frontend/
    ├── Dockerfile                  # Node 20 + pnpm
    ├── package.json
    ├── vite.config.ts              # API 프록시 + HMR
    └── src/
        ├── App.tsx                 # 루트 레이아웃
        ├── api/                    # API 클라이언트
        ├── components/
        │   ├── map/
        │   │   ├── MapView.tsx     # MapLibre GL 메인 지도
        │   │   └── LayerToggle.tsx # 레이어 토글 패널
        │   ├── panel/
        │   │   ├── SidePanel.tsx       # 패널 컨테이너
        │   │   ├── SearchPanel.tsx     # 검색 + 필터 + 페이지네이션
        │   │   ├── DetailPanel.tsx     # 발전소 상세 정보
        │   │   └── DashboardSummary.tsx # 통계 카드
        │   └── layout/
        │       ├── TopBar.tsx      # 상단바 (로고, 상태 뱃지, 검색)
        │       ├── MainLayout.tsx  # 지도 + 사이드패널 레이아웃
        │       └── ErrorBanner.tsx # DB 장애 배너 (503)
        ├── hooks/                  # useFacilities, useSearch 등
        ├── stores/                 # Zustand (mapStore, searchStore, uiStore)
        └── types/index.ts          # TypeScript 타입 정의
```

## Docker Compose 서비스

### db (PostgreSQL + PostGIS)

```yaml
이미지: postgis/postgis:16-3.4
컨테이너명: pv_profile_db
포트: 5432
볼륨: pv_pgdata (영속)
익스텐션: postgis, pg_trgm
```

### etl (초기 데이터 적재)

`backend` 이미지를 재사용하여 `load_data.py`를 실행하는 one-shot 서비스.

- 의존: `db` healthy 이후 실행
- 적재 소스:
  - `../source/processed/pv_facility_processed.parquet` → `pv_facility` 테이블
  - `../source/openinframap/by_sido/substations_*.geojson` → `substation` 테이블
  - `../source/openinframap/by_sido/power_lines_*.geojson` → `power_line` 테이블
- 매번 `TRUNCATE` 후 재적재 (멱등)
- 배치 크기: 5,000행
- 좌표 검증: 위도 33~39, 경도 124~132 (한반도 범위)

### backend (FastAPI)

```yaml
포트: 8000
환경변수:
  DATABASE_URL: postgresql+asyncpg://pv_user:pv_password@db:5432/pv_profile
  BOUNDARIES_PATH: /data/boundaries/sigungu_2018_simple.geojson
개발모드: uvicorn --reload (소스코드 bind mount)
```

### frontend (Vite dev server)

```yaml
포트: 5173
환경변수:
  VITE_API_TARGET: http://backend:8000
개발모드: pnpm dev --host 0.0.0.0 (소스코드 bind mount)
```

## 데이터베이스 스키마

### pv_facility (119,558행)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | - |
| name | TEXT | 태양광발전시설명 |
| addr_road | TEXT | 소재지도로명주소 |
| addr_jibun | TEXT | 소재지지번주소 |
| geom | GEOMETRY(POINT, 4326) | PostGIS 좌표 (nullable) |
| has_coord | BOOLEAN (GENERATED) | geom IS NOT NULL 자동 계산 |
| status | TEXT NOT NULL | 정상가동 / 가동중단 / 폐기 |
| capacity_kw | NUMERIC(15,2) | 설비용량 (kW) |
| voltage | TEXT | 공급전압 |
| frequency | TEXT | 주파수 |
| install_year | SMALLINT | 설치연도 |
| usage_detail | TEXT | 세부용도 |
| permit_date | DATE | 허가일자 |
| permit_org | TEXT | 허가기관 (시군구) |
| install_area_m2 | NUMERIC(15,2) | 설치면적 (m²) |
| data_date | DATE | 데이터기준일자 |
| source_file | TEXT | 원천 CSV 파일명 |

인덱스: GIST(geom), GIN(name trigram), GIN(addr_road trigram), B-tree(status, capacity_kw, install_year)

### substation (1,185행)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | - |
| name | TEXT | 변전소명 |
| name_en | TEXT | 영문명 |
| geom | GEOMETRY(POINT, 4326) NOT NULL | 위치 |
| voltage | TEXT | 전압 |
| sub_type | TEXT | 유형 (transmission, distribution 등) |
| operator | TEXT | 운영자 |
| osm_id | BIGINT | OpenStreetMap ID |
| sido | TEXT | 시도 |

### power_line (4,685행)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL PK | - |
| name | TEXT | 송배전선명 |
| geom | GEOMETRY(LINESTRING, 4326) NOT NULL | 경로 |
| power_type | TEXT | transmission / distribution |
| voltage | TEXT | 전압 |
| sido | TEXT | 시도 |

## API 레퍼런스

### 헬스체크

```
GET /health
→ {"status": "ok"}
```

### 발전소

#### 목록 검색

```
GET /api/facilities?q=&status=&cap_min=&cap_max=&year_min=&year_max=&page=1&per_page=50

파라미터:
  q          텍스트 검색 (시설명, 도로명주소 ILIKE)
  status     정상가동 | 가동중단 | 폐기
  cap_min    최소 설비용량 (kW)
  cap_max    최대 설비용량 (kW)
  year_min   최소 설치연도
  year_max   최대 설치연도
  page       페이지 번호 (1부터)
  per_page   페이지 크기 (1~200, 기본 50)

응답: { total, page, per_page, items: Facility[] }
정렬: capacity_kw DESC NULLS LAST
```

#### 뷰포트 마커 (zoom ≥ 10)

```
GET /api/facilities/bbox?xmin=&ymin=&xmax=&ymax=&status=

파라미터: xmin, ymin, xmax, ymax (필수), status (선택)
응답: { items: [{ id, name, status, capacity_kw, lng, lat }] }
좌표 있는 것만 반환 (has_coord=true)
```

#### 반경 검색

```
GET /api/facilities/nearby?lng=&lat=&radius_m=5000

파라미터: lng, lat (필수), radius_m (100~50000, 기본 5000)
응답: { items: [{ ...facility, dist_m }] }
최대 50건, 거리순 정렬
PostGIS ST_DWithin + KNN 연산자
```

#### 시군구 클러스터 (zoom < 10)

```
GET /api/facilities/clusters

응답: { items: [{ sigungu, cnt, center_lat, center_lng }] }
permit_org 기준 GROUP BY, 건수 내림차순
```

#### 단건 상세

```
GET /api/facilities/{id}

응답: Facility + { nearby_count, nearest_substation_name, nearest_substation_dist_m }
좌표 있으면 5km 반경 인근 시설 수 + 최근접 변전소 계산
404: 해당 ID 없음
```

### 인프라

#### 변전소 (bbox)

```
GET /api/substations/bbox?xmin=&ymin=&xmax=&ymax=

응답: { items: [{ id, name, name_en, voltage, sub_type, frequency, operator, osm_id, sido, lng, lat }] }
```

#### 송배전선 (bbox)

```
GET /api/power-lines/bbox?xmin=&ymin=&xmax=&ymax=

응답: { items: [{ id, name, power_type, voltage, sido, coordinates: [[lng, lat], ...] }] }
bbox 파라미터 모두 필수 (하나라도 없으면 400)
```

#### 시군구 경계

```
GET /api/boundaries

응답: GeoJSON FeatureCollection (sigungu_2018_simple.geojson)
Cache-Control: public, max-age=3600
```

### 통계

```
GET /api/stats

응답: { total, active, stopped, retired, no_coord, total_capacity_mw, sigungu_count }
인메모리 캐시 TTL 60초
```

### 에러 응답

| 코드 | 상황 | 본문 |
|------|------|------|
| 400 | bbox 파라미터 누락 | `{ "detail": "xmin, ymin, xmax, ymax 파라미터가 모두 필요합니다." }` |
| 404 | 발전소/파일 없음 | `{ "detail": "..." }` |
| 503 | DB 장애 | `{ "error": "서비스 일시 중단", "retry_after": 30 }` |

## 프론트엔드 기능

### 지도 (MapView)

- **베이스맵**: CartoDB Dark Matter
- **줌 전환**: zoom < 10 → 시군구 클러스터(인디고 원형 + 건수), zoom ≥ 10 → 개별 마커
- **마커 색상**: 정상가동 `#2ecc71` / 가동중단 `#95a5a6` / 폐기 `#4a5568`
- **인프라 레이어**: 변전소 `#3498db` (파란점) / 송배전선 `#e67e22` (주황선)
- **인터랙션**: hover → 팝업 (이름, 용량/전압), click → 하이라이트 + 상세패널
- **클러스터 클릭**: flyTo zoom 12 애니메이션
- **URL 딥링크**: `?id=12345&lng=127.1&lat=37.5&z=15`

### 레이어 토글

지도 좌하단 접기/펼치기 패널. 체크박스로 각 레이어 표시/숨김:
- 정상가동 / 가동중단 / 폐기
- 변전소 / 송배전선 / 시군구 경계

### 검색 패널 (사이드바)

- 텍스트 검색 (300ms 디바운싱, pg_trgm ILIKE)
- 상태 필터 버튼 (전체 / 정상가동 / 가동중단 / 폐기)
- 설비용량 범위 슬라이더
- 설치연도 범위 슬라이더
- 결과 리스트 (50건/페이지, 페이지네이션)
- 결과 클릭 → 지도 flyTo + 상세 패널 전환

### 상세 패널

- 기본 정보: 시설명, 주소, 상태, 용량, 전압
- 위치 정보: 도로명/지번, 설치구분, 면적
- 허가 정보: 허가일자, 허가기관
- 주변 정보 (PostGIS 계산): 5km 반경 발전소 수, 최근접 변전소 이름/거리

### 상태관리 (Zustand)

| 스토어 | 역할 |
|--------|------|
| mapStore | 뷰포트 (center, zoom, bbox), 선택/하이라이트 마커 |
| searchStore | 검색어, 필터, 페이지, 결과 |
| uiStore | 패널 모드 (search/detail), 레이어 가시성, DB 에러 상태 |

## 데이터 현황 (2026-02-28)

| 항목 | 수량 | 비고 |
|------|------|------|
| 전체 발전소 | 119,558 | data.go.kr 전기사업허가 |
| 좌표 보유 | 114,840 | Kakao API 지오코딩 완료 |
| 좌표 결측 | 4,718 | 주소 불명확으로 실패 |
| 정상가동 | 111,155 | |
| 가동중단 | 6,874 | |
| 폐기 | 1,529 | |
| 변전소 | 1,185 | OSM OpenInfraMap |
| 송배전선 | 4,685 | OSM OpenInfraMap |

## 개발 가이드

### 로컬 (Docker 없이) 실행

DB만 Docker로 띄우고 나머지는 로컬에서 실행할 수도 있다:

```bash
# 1. DB
docker compose up db -d

# 2. ETL (최초 1회)
cd backend
uv run python -m app.db.load_data

# 3. Backend
uv run uvicorn app.main:app --reload --port 8000

# 4. Frontend (별도 터미널)
cd ../frontend
pnpm install
pnpm dev
```

### 환경변수

| 변수 | 서비스 | 기본값 | 설명 |
|------|--------|--------|------|
| DATABASE_URL | backend | `postgresql+asyncpg://pv_user:pv_password@localhost:5432/pv_profile` | SQLAlchemy 비동기 연결 |
| DB_HOST | etl | `localhost` | psycopg2 호스트 |
| DB_PORT | etl | `5432` | psycopg2 포트 |
| DB_NAME | etl | `pv_profile` | DB명 |
| DB_USER | etl | `pv_user` | DB 사용자 |
| DB_PASSWORD | etl | `pv_password` | DB 비밀번호 |
| DATA_ROOT | etl | (없음) | 설정 시 Docker 모드 (/data/) |
| BOUNDARIES_PATH | backend | (parents[5] 기반) | 시군구 경계 GeoJSON 경로 |
| VITE_API_TARGET | frontend | `http://localhost:8000` | API 프록시 대상 |

### Hot Reload

Docker Compose의 bind mount로 소스 코드 변경이 즉시 반영됨:
- **Backend**: `./backend/app/` → `/app/app/` (uvicorn `--reload`)
- **Frontend**: `./frontend/src/` + `index.html` → `/app/` (Vite HMR)

### 성능 최적화

**Backend:**
- PostGIS GIST 인덱스 (공간 쿼리)
- pg_trgm GIN 인덱스 (ILIKE 텍스트 검색)
- asyncpg 비동기 커넥션 풀 (pool_size=10, max_overflow=20)
- /api/stats 인메모리 캐시 (TTL 60초)
- per_page 상한 200건

**Frontend:**
- 뷰포트 변경 시 이전 API 요청 자동 취소 (AbortController)
- 검색 입력 300ms 디바운싱
- MapLibre feature-state로 리렌더 없이 하이라이트
- Zustand 세분화 셀렉터로 불필요 리렌더 방지
