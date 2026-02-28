# OpenInfraMap 크롤러 PRD

- 문서 버전: `v0.1`
- 작성일: `2026-02-28`

## 목표

Overpass API(OSM)를 통해 한국 전력 인프라(변전소·송배전선·발전소)를 시도별로 수집한다.
OpenInfraMap이 보여주는 데이터와 동일한 OSM 원본.

## 구현 파일

- `generator_next/crawlers/openinframap_power_crawler.py` — 수집
- `generator_next/crawlers/visualize_infra_map.py` — folium 지도 시각화

## 실행

```bash
# 전국 수집 (이미 수집된 시도는 자동 스킵)
uv run python generator_next/crawlers/openinframap_power_crawler.py

# 특정 시도만 수집
uv run python generator_next/crawlers/openinframap_power_crawler.py --sido 인천광역시

# 강제 재수집
uv run python generator_next/crawlers/openinframap_power_crawler.py --force

# 지도 시각화
uv run python generator_next/crawlers/visualize_infra_map.py \
  --substations generator_next/source/openinframap/substations_*.geojson \
  --lines generator_next/source/openinframap/power_lines_*.geojson
```

## 수집 대상

| 타입 | OSM 태그 | 형태 | 내용 |
|------|---------|------|------|
| 변전소 | `power=substation` | Point | 이름·전압·운영자 |
| 송전선 | `power=line` | LineString | 전압·회선수·케이블수 |
| 배전선 | `power=minor_line` | LineString | 저압 배전 |
| 케이블 | `power=cable` | LineString | 지중·해저 케이블 |
| 발전소 | `power=plant` | Point | 발전원·출력·운영자 |
| 발전기 | `power=generator` | Point | 발전기 단위 |

## 출력 구조

```
generator_next/source/openinframap/
  by_sido/
    substations_{sido}.geojson    # 시도별 변전소
    power_lines_{sido}.geojson    # 시도별 송배전선
    plants_{sido}.geojson         # 시도별 발전소
```

## 특이사항

- Overpass 공개 미러 3개 병렬 활용 (rate limit 분산)
- 시도를 3개 그룹으로 나눠 미러별 할당, 그룹 간 동시 실행
- 시도별 즉시 저장 → 중간 중단 시 재실행하면 완료된 시도 스킵
- `--force` 없이 재실행 시 `by_sido/`에 3종 파일 모두 존재하는 시도는 스킵

## 현황 (2026-02-28 기준)

- 전국 17개 시도 수집 완료
- `by_sido/` 내 파일: 변전소 17개 + 송배전선 17개 + 발전소 17개 = 51개
- 수집 일자: 2026-02-27
