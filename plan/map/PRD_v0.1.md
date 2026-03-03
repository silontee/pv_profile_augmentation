# 지도 시각화 PRD

- 문서 버전: `v0.1`
- 작성일: `2026-02-28`

## 현재 구현 상태 — v1 완료 (folium HTML)

`src/map/generate_map.py`로 정적 HTML 지도 생성.
추후 풀스택 웹앱으로 전환 예정.

## 실행

```bash
uv run python src/map/generate_map.py
uv run python src/map/generate_map.py --no-infra        # 인프라 레이어 제외
uv run python src/map/generate_map.py --status 정상가동  # 특정 상태만
```

출력: `src/map/output/pv_map.html`

## v1 구현 내용

### 데이터 소스

| 레이어 | 소스 | 수량 |
|---|---|---|
| 태양광 발전소 (정상가동) | `pv_facility_processed.parquet` | 111,155개 |
| 태양광 발전소 (가동중단) | 동일 | 6,874개 |
| 태양광 발전소 (폐기) | 동일 | 1,529개 |
| 변전소 | `source/openinframap/by_sido/substations_*.geojson` | 1,185개 |
| 송배전선 | `source/openinframap/by_sido/power_lines_*.geojson` | 4,685개 |

좌표 결측 4,718건은 제외됨 (parquet 필터링).

### 마커 스펙

| 가동상태 | 색상 | 반경 | 기본 표시 |
|---|---|---|---|
| 정상가동 | `#2ecc71` (초록) | 4px | ON |
| 가동중단 | `#f39c12` (주황) | 4px | OFF |
| 폐기 | `#e74c3c` (빨강) | 3px | OFF |
| 변전소 | `#3498db` (파랑) | 5px | ON |

### 팝업 정보

- 발전소: 시설명 / 설비용량(kW) / 허가일자
- 변전소: 시설명 / 전압 / 타입
- 송배전선: 노선명 / 전압

### 기술 스택

- `folium` + `FastMarkerCluster`: 대량 포인트 렌더링
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
