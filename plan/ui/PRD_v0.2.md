# PRD — UI 시각화 트랙 v0.2

작성일: 2026-03-03
이전 버전: PRD_v0.1.md
상태: **완료 (v0.2 기준)**

---

## 1. v0.2 변경 요약

v0.1 대비 추가된 기능:

| 기능 | 내용 |
|---|---|
| 3D 지형 | MapTiler DEM + hillshade 레이어, 피치 전환 |
| 토지피복 레이어 | 환경부 EGIS WFS → FastAPI 프록시 → 벡터 폴리곤 색상 표시 |
| 토지피복 범례 | 레이어 ON 시 우상단 오버레이 표시 (7개 중분류) |
| 필터 → 지도 동기화 | 설비용량·설치연도·상태 슬라이더가 지도 마커/클러스터에도 반영 |
| 토지피복 크롤러 | EGIS WFS 오프라인 다운로드 스크립트 추가 |

---

## 2. 새 API 엔드포인트

### GET /api/landcover

환경부 EGIS WFS를 프록시하여 벡터 GeoJSON 반환.

**파라미터**: `xmin, ymin, xmax, ymax` (float, bbox 경위도)

**응답**: GeoJSON FeatureCollection. 각 Feature의 `properties`에 `color` 필드 추가.

**EGIS WFS 설정**
```
URL:   https://api.mcee.go.kr/geoserver/wfs
레이어: EGIS:lv2_2025y  (중분류 22종)
CRS:   EPSG:4326
최대:  8,000 features/요청
```

> **CORS 이슈**: `api.mcee.go.kr`는 `Access-Control-Allow-Origin` 헤더 미제공.
> 브라우저 직접 요청 불가 → FastAPI 서버사이드 프록시로 우회.

**색상 매핑 (1자리 대분류 코드 기준)**

| 코드 | 분류 | 색상 |
|---|---|---|
| 1 | 시가화건조지역 | `#6b7280` |
| 2 | 농업지역 | `#ca8a04` |
| 3 | 산림지역 | `#15803d` |
| 4 | 초지 | `#86efac` |
| 5 | 습지 | `#0e7490` |
| 6 | 나지 | `#92400e` |
| 7 | 수역 | `#1d4ed8` |

---

## 3. 3D 지형 기능

- **DEM 소스**: MapTiler `terrain-rgb-v2` (래스터 타일)
- **MapTiler API 키**: `QDyL8SVpZi4TNH5AykBi` (MapView.tsx 하드코딩 — 배포 전 env 분리 필요)

| 토글 상태 | pitch | terrain | hillshade |
|---|---|---|---|
| OFF | 0° | null | none |
| ON | 50° | `{ source: SRC_TERRAIN, exaggeration: 1.5 }` | visible |

---

## 4. 토지피복 레이어 동작

**데이터 흐름**
```
지도 이동/줌 이벤트
  → (layers.landcover === true 시)
  → fetch /api/landcover?xmin=...&ymax=...
  → FastAPI → EGIS WFS → GeoJSON
  → GeoJSONSource.setData()
  → MapLibre fill 레이어 렌더링
```

**구현 패턴**
- AbortController: 이동 시 이전 요청 취소
- `fetchLandcoverOnMoveRef` (`useRef<() => void>`): stale closure 방지

**알려진 이슈 / 해결 경위**

| 이슈 | 원인 | 해결 |
|---|---|---|
| WMS 방식 CORS 차단 | `api.mcee.go.kr` 무 CORS 헤더 | WFS 벡터 + 서버 프록시로 전환 |
| `before: LYR_MARKERS` 오류 | markers 레이어 미존재 시 addLayer 실패 | `before` 파라미터 제거 |
| stale closure | `layersRef.current` 지연 갱신 | `useEffect` deps에 직접 사용 |
| lv3 세분류 데이터 과다 | 0.2°×0.2°에 238k features | lv2 중분류 + MAX_FEATURES=8000 |

---

## 5. 필터 → 지도 동기화

`useFacilities` 훅이 `searchStore`를 구독하도록 수정:
- `capRange`, `yearRange`, `status`를 `fetchBbox` / `fetchClusters` 에 전달
- `useEffect` deps에 `[..., status, capRange, yearRange]` 추가

---

## 6. pyproject.toml / Docker 변경

- `httpx>=0.27.0` 프로덕션 의존성 추가
- `uv lock` 재생성 필요 (변경 후 `docker compose build --no-cache backend`)
- DB 포트: `5432` → `5433` (기존 `pv-main-db` 컨테이너 충돌 방지)
- 볼륨 경로: `../source/` → `../data/`

---

## 7. 전체 기능 현황 (v0.2 기준)

| 항목 | 상태 |
|---|---|
| DB 스키마 + ETL | 완료 |
| 전체 API 엔드포인트 | 완료 |
| 지도 클러스터/마커 | 완료 |
| 레이어 토글 | 완료 |
| 검색·필터 패널 | 완료 |
| 상세 패널 | 완료 |
| 필터 → 지도 동기화 | **완료 (v0.2)** |
| 3D 지형 (MapTiler DEM + hillshade) | **완료 (v0.2)** |
| 토지피복 레이어 (환경부 EGIS WFS) | **완료 (v0.2)** |
| 토지피복 범례 | **완료 (v0.2)** |
| 토지피복 크롤러 (오프라인용) | **완료 (v0.2)** |
| 시군구 경계 레이어 | 미구현 |
| 경사도 레이어 (국토정보플랫폼 DEM) | 미구현 |
| RPS 이용률 연동 | 미구현 |
| 인증·배포 설정 | 미구현 |
