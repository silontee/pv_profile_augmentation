# 지도 시각화 PRD

- 문서 버전: `v0.2`
- 작성일: `2026-02-28`
- 이전 버전: `PRD_v0.1.md` (덮어쓰기 금지)

## 변경 사항 (v0.1 → v0.2)

- 변전소 원 크기를 전압 등급별로 차등 적용 (고정 r=5 → 등급별 r=3~16)
- 변전소 팝업에 전체 OSM 속성 표시 (영문명, 전압 kV 변환, 용량 등급, 타입, 주파수, 운영사, 위치형태, OSM ID)
- 태양광 발전소 팝업에 전체 parquet 컬럼 표시 (주소, 허가기관, 설치연도, 설치면적, 공급전압, 주파수, 설치위치, 세부용도, 데이터기준일자)
- OSM 변전소 데이터 KEPCO 공식 집계와 1차 검증 완료 (154kV+ 기준 94.6% 커버)

## 현재 구현 상태 — v1.2 (folium HTML)

`generator_next/map/generate_map.py`로 정적 HTML 지도 생성.
추후 풀스택 웹앱으로 전환 예정.

## 실행

```bash
uv run python generator_next/map/generate_map.py
uv run python generator_next/map/generate_map.py --no-infra        # 인프라 레이어 제외
uv run python generator_next/map/generate_map.py --status 정상가동  # 특정 상태만
```

출력: `generator_next/map/output/pv_map.html`

## 구현 내용

### 데이터 소스

| 레이어 | 소스 | 수량 |
|---|---|---|
| 태양광 발전소 (정상가동) | `pv_facility_processed.parquet` | 111,155개 |
| 태양광 발전소 (가동중단) | 동일 | 6,874개 |
| 태양광 발전소 (폐기) | 동일 | 1,529개 |
| 변전소 | `source/openinframap/by_sido/substations_*.geojson` | 1,185개 |
| 송배전선 | `source/openinframap/by_sido/power_lines_*.geojson` | 4,685개 |

좌표 결측 4,718건 제외 (parquet 필터링). 좌표 보유 114,840건 표시.

### 마커 스펙 — 태양광 발전소

| 가동상태 | 색상 | 반경 | 기본 표시 |
|---|---|---|---|
| 정상가동 | `#2ecc71` (초록) | 4px | ON |
| 가동중단 | `#f39c12` (주황) | 4px | OFF |
| 폐기 | `#e74c3c` (빨강) | 3px | OFF |

### 마커 스펙 — 변전소 (전압 등급별 차등)

| 전압 등급 | 용량 등급 | 반경 | KEPCO 집계 | OSM 수량 |
|---|---|---|---|---|
| 765kV | 1000MW급 | 16px | 8개 | 9개 |
| 345kV | 500MW급 | 10px | 117개 | 108개 |
| 154kV | 100MW급 | 6px | 770개 | 730개 |
| 기타 | - | 3px | - | 194개 |
| 전압 미등록 | - | 3px | - | 144개 |

> OSM 154kV+ 커버리지: **94.6%** (KEPCO 895개 대비 OSM 847개)

### 팝업 정보 — 태양광 발전소

| 항목 | 컬럼 |
|---|---|
| 시설명 | `태양광발전시설명` |
| 가동상태 | `가동상태구분명` |
| 설비용량 | `설비용량` (kW) |
| 주소 | `소재지도로명주소` 우선, 없으면 `소재지지번주소` |
| 허가일자 / 허가기관 | `허가일자`, `허가기관` |
| 설치연도 / 설치면적 | `설치연도`, `설치면적` (m²) |
| 공급전압 / 주파수 | `공급전압` (V), `주파수` (Hz) |
| 설치상세위치 / 세부용도 | `설치상세위치구분명`, `세부용도` |
| 데이터기준일자 | `데이터기준일자` |

### 팝업 정보 — 변전소

| 항목 | 소스 |
|---|---|
| 시설명 / 영문명 | `name`, `name_en` |
| 전압 | `voltage` (V → kV 변환 표기) |
| 용량 등급 | 전압 기반 자동 산출 |
| 타입 | `substation_type` |
| 주파수 / 운영사 / 위치형태 | `frequency`, `operator`, `location` |
| OSM ID | `osm_type/osm_id` |

### 기술 스택

- `folium` + `FastMarkerCluster`: 대량 포인트 클러스터링 렌더링
- `folium.LayerControl`: 레이어 on/off
- Base tile: CartoDB Positron

## v2 계획 — 풀스택 웹앱 (미착수)

- 프레임워크: 미결정 (React + deck.gl 또는 SvelteKit + Leaflet 검토 중)
- 기능: 지도 + 통계 대시보드 + CSV/GeoJSON 다운로드
- 데이터: PostGIS 또는 Parquet 직접 서빙
- 시점: 통계적 증강 완료 후

## 미결 사항

1. 풀스택 웹앱 기술 스택 결정
2. 발전량 추정 결과 시각화 레이어 (통계 증강 후)
3. 등고선·일사량 래스터 레이어 검토
