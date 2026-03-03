# 지도 시각화 PRD

- 문서 버전: `v0.4`
- 작성일: `2026-03-01`
- 이전 버전: `PRD_v0.3.md` (덮어쓰기 금지)

## 변경 사항 (v0.3 → v0.4)

- 시군구 경계 데이터 교체: 2013 simple GeoJSON → 2018 topo-simple 변환본
  - 기존 362KB(과단순화, 경계 각짐) → 731KB(shapely simplify 0.005°, 부드러운 경계)
- 경계 렌더링 방식 변경: `folium.GeoJson` → `folium.PolyLine`
  - GeoJson 클릭 시 속성 테이블 팝업이 뜨는 문제 해결
  - PolyLine은 클릭 팝업 없음, hover 툴팁(시군구명)만 유지
- `topojson` + `shapely` 의존성 추가

## 경계 데이터 처리 과정

```
southkorea-maps (2018 topo-simple, 553KB)
  → topojson Python 라이브러리로 GeoJSON 변환 (3.2MB)
  → shapely simplify(tolerance=0.005°, ≈500m 해상도) 적용
  → sigungu_2018_simple.geojson (731KB, 250개 시군구)
```

저장 경로: `src/data/boundaries/sigungu_2018_simple.geojson`

## 현재 구현 레이어 전체 목록

| 레이어명 | 데이터 소스 | 수량 | 기본 표시 |
|---|---|---|---|
| 시군구 경계 | `source/boundaries/sigungu_2018_simple.geojson` | 250개 | ON |
| 태양광 정상가동 | `pv_facility_processed.parquet` | 111,155개 | ON |
| 태양광 가동중단 | 동일 | 6,874개 | OFF |
| 태양광 폐기 | 동일 | 1,529개 | OFF |
| 변전소 | `openinframap/by_sido/substations_*.geojson` | 1,185개 | ON |
| 송배전선 | `openinframap/by_sido/power_lines_*.geojson` | 4,685개 | ON |

## 마커/스타일 스펙

| 항목 | 색상 | 비고 |
|---|---|---|
| 정상가동 | `#2ecc71` 초록 | r=4 |
| 가동중단 | `#95a5a6` 회색 | r=4 |
| 폐기 | `#2c3e50` 검정 | r=3 |
| 변전소 | `#3498db` 파랑 | 전압 등급별 r=3~16 |
| 송전선 | `#e67e22` 주황 | weight=2 |
| 배전선 | `#95a5a6` 회색 | weight=1 |
| 경계선 | `#555555` 진회색 | weight=0.8 |

## v2 계획 — 풀스택 웹앱 (미착수)

- 프레임워크: 미결정 (React + deck.gl 또는 SvelteKit + Leaflet 검토 중)
- 기능: 지도 + 통계 대시보드 + CSV/GeoJSON 다운로드
- 시점: 통계적 증강 완료 후

## 미결 사항

1. 풀스택 웹앱 기술 스택 결정
2. 발전량 추정 결과 시각화 레이어 (통계 증강 후)
3. 경계 데이터 행정구역 변동 미반영 가능성 (2018 기준, 이후 통합·분리 미포함)
