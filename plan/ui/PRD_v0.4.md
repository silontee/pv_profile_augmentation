# PRD — UI 시각화 트랙 v0.4

작성일: 2026-03-03
이전 버전: PRD_v0.3.md
상태: **완료 (v0.4 기준)**

---

## 1. v0.4 변경 요약

| 항목 | 내용 |
|---|---|
| 토지피복 색상 조정 | 채도 과다 → 적정 수준으로 낮춤 |
| 레이어 패널 불투명화 | LayerToggle · LandcoverLegend 투명 제거 |
| fill-opacity 상향 | 0.45 → 0.65 (폴리곤 가시성 개선) |

---

## 2. 토지피복 색상 변경

다크 배경(#0a0a0f)에서 채도가 너무 높아 눈에 띄게 과했던 색상을 한 단계 낮춤.

| 분류 | v0.3 (과채도) | v0.4 (조정) |
|---|---|---|
| 시가화건조지역 | `#f97316` | `#ea580c` |
| 농업지역 | `#facc15` | `#eab308` |
| 산림지역 | `#4ade80` | `#22c55e` |
| 초지 | `#a3e635` | `#84cc16` |
| 습지 | `#22d3ee` | `#06b6d4` |
| 나지 | `#fb923c` | `#d97706` |
| 수역 | `#60a5fa` | `#3b82f6` |

변경 위치: `backend/app/api/landcover.py`, `frontend/src/components/map/LandcoverLegend.tsx`

---

## 3. 레이어 패널 불투명화

`bg-[var(--bg-elevated)]/90 backdrop-blur-sm` → `bg-[var(--bg-elevated)]`

지도 위에 패널이 떠있을 때 반투명 처리로 인해 글자가 보이지 않는 문제 수정.
`--bg-elevated` = `#222236` (완전 불투명 적용).

변경 위치:
- `frontend/src/components/map/LayerToggle.tsx`
- `frontend/src/components/map/LandcoverLegend.tsx`

---

## 4. fill-opacity 조정

`MapView.tsx` 토지피복 fill 레이어: `0.45` → `0.65`

반투명도가 낮아 다크 배경에 묻히던 폴리곤 가시성 개선.

---

## 5. 전체 기능 현황 (v0.4 기준)

| 항목 | 상태 |
|---|---|
| DB 스키마 + ETL | 완료 |
| 전체 API 엔드포인트 | 완료 |
| 지도 클러스터/마커 | 완료 |
| 레이어 토글 | 완료 |
| 검색·필터 패널 | 완료 |
| 상세 패널 | 완료 |
| 필터 → 지도 동기화 | 완료 |
| 3D 지형 (MapTiler DEM + hillshade) | 완료 |
| 토지피복 레이어 색상 표시 | 완료 (v0.3 버그픽스) |
| 토지피복 색상·패널 UI 개선 | **완료 (v0.4)** |
| 시군구 경계 레이어 | 미구현 |
| 토지피복 오프라인 ETL (PostGIS) | 미구현 |
| 경사도 레이어 | 미구현 |
| MapTiler 키 사용량 모니터링 | 미구현 |
