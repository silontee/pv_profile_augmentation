# recloud 크롤러 PRD

- 문서 버전: `v0.1`
- 작성일: `2026-02-28`

## 목표

recloud.energy.or.kr에서 시군구 단위 태양광 발전소 이용률 데이터를 수집한다.
RPS 발전설비 이용률 기준 집계 데이터 — 개소수·설비용량·발전량·이용률 비교값 포함.

## 구현 파일

`generator_next/crawlers/recloud_solar_crawler.py`

## 실행

```bash
# 전국 수집 (기본)
uv run python generator_next/crawlers/recloud_solar_crawler.py

# 특정 시도만 수집 (예: 인천 = 28)
uv run python generator_next/crawlers/recloud_solar_crawler.py --sido 28

# 출력 경로 지정
uv run python generator_next/crawlers/recloud_solar_crawler.py \
  --output-dir generator_next/source/recloud \
  --concurrency 5
```

## 데이터 흐름

1. `main01.do` → 전국 + 17개 광역시도 집계 (JSONP 파싱)
2. `area_code/gugun.do` → 시도별 시군구 5자리 코드 목록
3. `main_cgg_power01.do` → 시군구별 발전소 현황

## 수집 항목

| 컬럼 | 설명 |
|------|------|
| `sido_code` / `sido_name` | 광역시도 코드/이름 |
| `gugun_code` / `gugun_name` | 시군구 코드/이름 |
| `cnt` | 발전소 개소수 |
| `inst_capa` | 설비용량 (kW) |
| `gelec_qty` | 발전량 |
| `cnt_ratio` | 개소수 비율 |
| `capa_ratio` | 설비용량 비율 |
| `gelec_diff` | 발전량 전년 대비 |

## 출력

| 경로 | 내용 |
|------|------|
| `generator_next/source/recloud/sido_summary_{timestamp}.csv` | 광역시도 집계 (18건) |
| `generator_next/source/recloud/gugun_detail_{timestamp}.csv` | 시군구별 상세 (228건) |

## 특이사항

- 비동기(aiohttp), 동시요청 5개 제한
- "시+구" 형태 도시(수원·청주 등 11개): 구 단위 대신 시 단위 코드로 합산 조회
- 군위군: 2023년 대구 편입으로 코드 불일치 보정 내장 (`CODE_REMAP`)
- 광역시도별 병렬 수집, 시군구별 순차 수집

## 현황 (2026-02-28 기준)

- 최신 수집: `gugun_detail_20260228_184855.csv` (228건)
- 광역시도 집계: `sido_summary_20260228_184855.csv` (18건)
