# 태양광 발전소 프로파일 증강 파이프라인

태양광 발전소 전기사업허가 데이터(data.go.kr)를 자동 수집·정제·지오코딩하여
RPS 이용률(recloud) 및 OSM 전력 인프라 데이터와 결합하는 파이프라인.
최종 목표는 발전소별 발전량 추정 및 입지 적합성 분석이 가능한 증강 데이터셋 생성.

---

## 파이프라인 전체 흐름

```
data.go.kr          recloud.energy.or.kr   OpenInfraMap (OSM)
     │                      │                      │
     ▼                      ▼                      ▼
[Playwright 크롤러]   [aiohttp 크롤러]    [Overpass API 크롤러]
     │                      │                      │
     ▼                      │                      │
src/data/raw_csv/    src/data/recloud/   src/data/openinframap/
     │                      │                      │
     └──────────────────────┴──────────────────────┘
                            │
                            ▼
                  [Polars 전처리 + Kakao 지오코딩]
                            │
                            ▼
             src/data/processed/pv_facility_processed.parquet
                            │
                            ▼
              ┌─────────────────────────────┐
              │  Docker Compose             │
              │  ┌──────────────────────┐   │
              │  │  PostgreSQL + PostGIS │   │
              │  └──────────┬───────────┘   │
              │             │               │
              │  ┌──────────▼───────────┐   │
              │  │  FastAPI (backend)   │   │
              │  └──────────┬───────────┘   │
              │             │               │
              │  ┌──────────▼───────────┐   │
              │  │  React + MapLibre    │   │
              │  └──────────────────────┘   │
              └─────────────────────────────┘
                    http://localhost:5173
```

---

## 빠른 시작

```bash
# 의존성 설치
uv sync

# 1. 크롤링 (data.go.kr)
uv run python src/crawlers/data_go_kr_solar_download_playwright.py --headless

# 2. 전처리 + 지오코딩
uv run python src/preprocessing/preprocess.py

# 3. UI 실행
cd src/ui
docker compose up --build   # 최초 빌드
docker compose up -d        # 이후 실행
# → http://localhost:5173
```

---

## 코드 구조

```
src/
  crawlers/       수집 — Playwright, aiohttp, Overpass API
  preprocessing/  전처리 — Polars, Kakao 지오코딩
  pipeline/       구버전 파이프라인 스크립트 (참고용)
  map/            정적 HTML 지도 — folium (레거시화 예정)
  ui/             풀스택 UI
    backend/      FastAPI + asyncpg + PostGIS
    frontend/     React + Vite + MapLibre GL JS
  data/
    raw_csv/      data.go.kr 시군구별 CSV
    recloud/      RPS 이용률 CSV
    openinframap/ OSM 전력 인프라 GeoJSON
    processed/    전처리 산출물 (parquet)
    logs/         크롤·지오코딩 상태 로그
plan/             PRD 문서 (버전 관리)
```

---

## 기술 스택 선택 이유 및 트레이드오프

실제로 왜 이 도구를 골랐는지, 무엇을 포기했는지 정리.

---

### uv — Python 패키지 관리자

**왜 썼나**
pip/poetry 대비 패키지 설치 속도가 10~100배 빠르다. Rust로 작성되어 의존성
해석과 설치가 거의 즉각적. `pyproject.toml` + `uv.lock`으로 재현 가능한 환경 보장.

**장점**
- `uv sync` 한 줄로 가상환경 + 의존성 설치 완료
- lock 파일로 다른 머신에서도 동일한 환경 재현
- pip과 인터페이스 호환 (`uv pip install` 가능)

**단점/트레이드오프**
- 상대적으로 새로운 도구라 레퍼런스가 pip보다 적음
- poetry에 비해 플러그인 생태계가 아직 얇음

---

### Playwright — data.go.kr 크롤러

**왜 썼나**
data.go.kr은 JavaScript로 동적 렌더링되는 페이지. 단순 `requests`로는 데이터를
가져올 수 없고 실제 브라우저가 JS를 실행해야 한다. Selenium 대비 Playwright가
더 빠르고, 비동기 지원이 잘 되어 있으며 API가 직관적.

**장점**
- JS 렌더링이 필요한 페이지 자동화 가능
- `--headless` 모드로 서버 환경에서도 실행
- 다운로드 이벤트 핸들링, 네트워크 인터셉트 등 고급 기능 내장
- Chromium/Firefox/Webkit 모두 지원

**단점/트레이드오프**
- 일반 HTTP 요청 대비 무겁고 느림 (브라우저를 실제로 띄움)
- 메모리 사용량이 높음
- 사이트 구조가 바뀌면 셀렉터를 다시 맞춰야 함

---

### aiohttp + asyncio — recloud 크롤러

**왜 썼나**
recloud는 단순 JSON API. JS 렌더링이 필요 없으므로 Playwright 없이
비동기 HTTP 요청만으로 충분. 시군구 250개를 순차적으로 요청하면 느리기 때문에
asyncio로 동시에 여러 요청을 보내 속도를 높임.

**장점**
- I/O 바운드 작업(HTTP 요청)에서 동시성으로 속도 대폭 향상
- 메모리 효율적 (스레드 없이 이벤트 루프 기반)
- requests 대비 비동기 네이티브

**단점/트레이드오프**
- 동기 코드보다 구조가 복잡 (async/await 이해 필요)
- 디버깅이 상대적으로 어려움
- 서버에 과부하 줄 수 있어 rate limiting 고려 필요

---

### Polars — 전처리 DataFrame 라이브러리

**왜 썼나**
11만+ 행의 CSV를 병합·정제하는 작업. pandas보다 훨씬 빠르고 메모리 효율적.
특히 Rust 기반이라 멀티코어를 자동 활용하고, lazy evaluation으로 불필요한
중간 계산을 건너뜀.

**장점**
- pandas 대비 수~수십 배 빠름 (특히 그룹 집계, 조인)
- 메모리 사용량 적음 (Apache Arrow 포맷 내부 사용)
- 표현식(expression) API가 직관적이고 체이닝에 강함
- 타입이 엄격해서 묵시적 타입 변환으로 인한 버그가 적음

**단점/트레이드오프**
- pandas와 API가 달라서 기존 pandas 코드 재사용 불가
- 생태계가 pandas보다 좁음 (scikit-learn 등과 직접 연동 시 변환 필요)
- lazy frame 개념을 처음 배울 때 러닝 커브 있음

---

### Parquet — 중간 산출물 저장 포맷

**왜 썼나**
CSV보다 읽기/쓰기가 빠르고, 컬럼 타입 정보를 보존. 11만 행짜리 파일을
DB에 적재하거나 Python에서 다시 불러올 때 CSV 대비 월등히 빠름.

**장점**
- 컬럼형 저장 → 특정 컬럼만 읽을 때 I/O 최소화
- 타입 정보 보존 (CSV는 읽을 때마다 타입 추론 필요)
- 압축 효율 좋음 (같은 데이터 CSV 대비 1/3~1/5 크기)
- Polars, pandas, DuckDB, Spark 모두 지원

**단점/트레이드오프**
- 바이너리 포맷이라 텍스트 에디터로 직접 열람 불가
- 엑셀/스프레드시트 도구와 직접 호환 안 됨
- 소규모 데이터라면 CSV가 오히려 편함

---

### PostgreSQL + PostGIS — 지리 데이터베이스

**왜 썼나**
발전소 11만 건의 위경도 데이터를 지도에서 빠르게 쿼리해야 함. 일반 RDB는
공간 인덱스가 없어서 "이 범위 안에 있는 발전소들 찾기" 같은 쿼리가 느림.
PostGIS는 PostgreSQL 위에서 공간 인덱스(GiST)와 공간 함수를 제공.

**장점**
- `ST_Within`, `ST_DWithin` 등 공간 쿼리를 SQL로 자연스럽게 표현
- GiST 인덱스로 바운딩 박스 쿼리가 빠름
- GeoJSON 직접 반환 (`ST_AsGeoJSON`)
- ACID 보장, 트랜잭션 안전

**단점/트레이드오프**
- 설치/설정이 일반 PostgreSQL보다 복잡 (PostGIS 확장 따로 활성화)
- SQLite + SpatiaLite 대비 무겁고 단독 실행 불가
- 이 프로젝트 규모에서는 사실 SQLite로도 충분할 수 있음

---

### FastAPI — 백엔드 API 서버

**왜 썼나**
Python 생태계(Polars, asyncpg)와 자연스럽게 연결. 비동기(async/await) 네이티브라
DB 쿼리 중 블로킹 없이 처리 가능. 자동 OpenAPI 문서가 생성되어 프론트엔드
개발 시 API 구조 확인이 편리.

**장점**
- Pydantic 기반 요청/응답 자동 검증 + 직렬화
- `/docs`에서 Swagger UI 자동 제공
- 비동기 네이티브 (asyncpg와 궁합 좋음)
- Django/Flask 대비 코드량 적고 성능 높음

**단점/트레이드오프**
- Django처럼 admin, ORM, auth 등 통합 기능 없음 (직접 조합해야 함)
- Flask보다 새로운 패턴(Pydantic, async)에 익숙해야 함
- 작은 스크립트 수준이라면 Flask가 더 단순할 수 있음

---

### React + MapLibre GL JS — 프론트엔드 지도 UI

**왜 MapLibre인가**
Leaflet은 Canvas/SVG 기반이라 10만 개 마커를 그리면 무거워짐.
MapLibre는 WebGL 기반이라 GPU가 렌더링을 처리하므로 대량 데이터에도
부드럽게 동작. Mapbox GL JS의 오픈소스 포크라 라이선스 비용 없음.

**MapLibre 장점**
- WebGL 기반 → 11만 개 발전소를 60fps로 렌더링
- Vector tile 지원 (래스터 타일 대비 스타일 자유도 높음)
- 오픈소스 (Mapbox처럼 API 키 과금 없음)

**MapLibre 단점/트레이드오프**
- Leaflet보다 API가 복잡 (Layer/Source 개념 이해 필요)
- 문서가 Mapbox 대비 얇을 때가 있음

**왜 React인가**
MapLibre 상태(선택된 발전소, 활성 레이어, 필터 값)를 컴포넌트 트리로 관리하기
편리. Zustand로 전역 상태 관리, Vite로 빠른 개발 서버.

**React 단점/트레이드오프**
- 간단한 지도 뷰어라면 Vanilla JS + MapLibre만으로도 충분
- 번들 크기가 있음 (이 프로젝트에서는 Vite로 최적화)

---

### Docker Compose — UI 스택 실행

**왜 썼나**
PostgreSQL+PostGIS, FastAPI, React 세 프로세스를 각자 실행하면 환경 차이로
인한 버그가 생기기 쉬움. Docker Compose로 세 컨테이너를 하나의 `docker-compose.yml`로
묶어서 `docker compose up` 한 줄로 전체 스택 실행.

**장점**
- 어떤 머신에서도 동일한 환경 재현
- 컨테이너 간 네트워크 자동 구성
- 데이터 볼륨 분리로 컨테이너 재시작 시 DB 데이터 보존

**단점/트레이드오프**
- Docker 없이 실행하려면 각 컴포넌트를 직접 설치해야 함
- 개발 중 코드 수정 → 이미지 재빌드 사이클이 번거로울 수 있음 (volume mount로 해결)
- 로컬 개발에서는 오버킬일 수 있음

---

## 데이터 현황 (2026-03-02 기준)

| 데이터 소스 | 수량 | 상태 |
|---|---|---|
| data.go.kr 원천 CSV | 119,558행 | 정상가동 111,155 / 가동중단 6,874 / 폐기 1,529 |
| 좌표 보유 (parquet) | 114,840건 | 지오코딩 완료 포함 |
| 좌표 결측 (parquet) | 4,718건 | 주소 불명확으로 지오코딩 실패 |
| recloud RPS | 196,295개소 | 시군구별 이용률 집계 |
| OSM 변전소 | 1,185건 | by_sido GeoJSON |
| OSM 송배전선 | 4,685건 | by_sido GeoJSON |

---

## 환경 변수

`.env` (프로젝트 루트):

```
KAKAO_API_KEY=...   # 전처리 지오코딩용
```

---

## 관련 문서

- 전체 PRD: `plan/overall/PRD_v0.7.md`
- UI 상세: `plan/ui/PRD_v0.1.md`
- 크롤링: `plan/crawling/`
- 전처리: `plan/preprocessing/`
