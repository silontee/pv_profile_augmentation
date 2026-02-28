# PV Profile Augmentation PRD (전체)

- 문서 버전: `v0.6`
- 작성일: `2026-02-28`
- 이전 버전: `PRD_v0.5.md` (덮어쓰기 금지)

## 1. 프로젝트 목표

태양광 발전소 허가 데이터(data.go.kr)를 수집·정제·지오코딩하고,
recloud RPS 이용률 데이터·OSM 전력 인프라와 결합하여 발전소 입지 및 발전량 추정을 위한
통계적 증강 파이프라인 구축. 최종 출력은 GeoJSON/Parquet + 웹 시각화.

## 2. 표준 실행 흐름

```
크롤러 (incremental) → preprocess.py (incremental) → parquet 갱신 → generate_map.py
```

## 3. 트랙별 진행 상태

### 3.1 크롤링 트랙 — 완료

| 크롤러 | 대상 | 출력 | 상태 |
|---|---|---|---|
| `data_go_kr_solar_download_playwright.py` | data.go.kr 전기사업허가 | `raw_csv/*.csv` | 완료 |
| `recloud_solar_crawler.py` | recloud RPS 이용률 | `recloud/rps_*.csv` | 완료 |
| `openinframap_power_crawler.py` | OSM 전력 인프라 | `openinframap/by_sido/*.geojson` | 완료 |

- 원천 CSV: 119,558행 (135개 파일, 2026-02-27 기준)
- recloud RPS: 196,295개소 (228 시군구)
- OSM: 변전소 1,185 / 송배전선 4,685 / 태양광발전소 10,646

### 3.2 전처리 트랙 — 완료

- `preprocess.py` 전체 파이프라인 실행 완료 (Kakao 지오코딩 포함)
- 가동상태 전체 보존 (정상가동·가동중단·폐기)
- 산출물: `pv_facility_processed.parquet` 119,558행 (좌표 보유 114,840)
- 상세: `plan/preprocessing/PRD_v0.6.md`

### 3.3 지도 시각화 트랙 — 완료 (v1)

- `generate_map.py`: folium + FastMarkerCluster 기반 HTML 지도 생성
- 114,840개 발전소 포인트 + 변전소 1,185 + 송배전선 4,685
- 출력: `generator_next/map/output/pv_map.html`
- 상세: `plan/map/PRD_v0.1.md`

### 3.4 통계적 증강 트랙 — 미착수

- 문제 정의 완료, 방법론 미확정
- recloud RPS(196,295) vs data.go.kr(119,558) 간 gap 분석 필요
- 상세: `plan/statistical_augmentation/PRD_v0.1.md`

## 4. 현재 블로커

1. `http_400` 4건 주소 원인 미분류 (전처리 로그에서 재확인 필요)
2. 통계적 증강 방법론 미선정

## 5. 다음 작업 우선순위

1. 통계적 증강 방법론 논의 착수 (recloud × data.go.kr 매핑 전략)
2. 풀스택 웹 시각화 (folium HTML은 임시, 본격 웹앱으로 전환 예정)
3. `http_400` 4건 주소 직접 확인

## 6. 문서 운영 규칙

- 전체 계획 문서: `plan/overall/` (큰 변화 있을 때만 버전 올림)
- 세부 계획 문서: 각 트랙 폴더에서 독립 버전 관리
- 덮어쓰기 금지 — 항상 새 버전 파일 생성
