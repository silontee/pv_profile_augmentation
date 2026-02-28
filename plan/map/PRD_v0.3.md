# 지도 시각화 PRD

- 문서 버전: `v0.3`
- 작성일: `2026-02-28`
- 이전 버전: `PRD_v0.2.md` (덮어쓰기 금지)

## 변경 사항 (v0.2 → v0.3)

- 시군구 행정경계 레이어 추가 (southkorea-maps, 2013 kostat 기준, 251개)
- 경계 데이터: `source/boundaries/sigungu_2013_simple.geojson`
- hover 시 시군구명 툴팁, 레이어 on/off 가능

## 현재 구현 레이어 전체 목록

| 레이어명 | 데이터 소스 | 수량 | 기본 표시 |
|---|---|---|---|
| 시군구 경계 | `source/boundaries/sigungu_2013_simple.geojson` | 251개 | ON |
| 태양광 정상가동 | `pv_facility_processed.parquet` | 111,155개 | ON |
| 태양광 가동중단 | 동일 | 6,874개 | OFF |
| 태양광 폐기 | 동일 | 1,529개 | OFF |
| 변전소 | `openinframap/by_sido/substations_*.geojson` | 1,185개 | ON |
| 송배전선 | `openinframap/by_sido/power_lines_*.geojson` | 4,685개 | ON |

## 마커 색상표

| 항목 | 색상 |
|---|---|
| 정상가동 | `#2ecc71` 초록 |
| 가동중단 | `#95a5a6` 회색 |
| 폐기 | `#2c3e50` 검정 |
| 변전소 | `#3498db` 파랑 (크기 전압 등급별) |
| 송전선 | `#e67e22` 주황 |
| 배전선 | `#95a5a6` 회색 |
| 경계선 | `#555555` 진회색, weight 0.8 |

## 데이터 소스 출처

| 데이터 | 출처 | 비고 |
|---|---|---|
| 태양광 발전소 | data.go.kr 전기사업허가 | 2026-02-27 기준 |
| 변전소 / 송배전선 | OpenStreetMap (Overpass API) | KEPCO 집계 대비 154kV+ 94.6% 커버 |
| 시군구 경계 | southkorea/southkorea-maps (kostat 2013) | 251개 시군구, 경계 변동 미반영 가능성 있음 |

## v2 계획 — 풀스택 웹앱 (미착수)

- 프레임워크: 미결정 (React + deck.gl 또는 SvelteKit + Leaflet 검토 중)
- 기능: 지도 + 통계 대시보드 + CSV/GeoJSON 다운로드
- 시점: 통계적 증강 완료 후

## 미결 사항

1. 풀스택 웹앱 기술 스택 결정
2. 경계 데이터 최신화 (2018+ 기준, 행정구역 변동 반영)
3. 발전량 추정 결과 시각화 레이어 (통계 증강 후)
