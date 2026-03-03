# 크롤링 PRD

- 문서 버전: `v0.2`
- 작성일: `2026-02-28`
- 이전 버전: `PRD_v0.1.md` (덮어쓰기 금지)

## 크롤러 목록

| 크롤러 | 대상 사이트 | 상태 | 세부 PRD |
|--------|------------|------|---------|
| `data_go_kr_solar_download_playwright.py` | data.go.kr | 완료 (135개 CSV) | — |
| `recloud_solar_crawler.py` | recloud.energy.or.kr | 완료 (228개 시군구) | `recloud_PRD_v0.1.md` |
| `openinframap_power_crawler.py` | Overpass API (OSM) | 완료 (전국 17개 시도) | `openinframap_PRD_v0.1.md` |

## 출력 경로 규약

모든 크롤러 산출물은 `src/data/` 하위에 저장:

```
src/data/
  raw_csv/          # data.go.kr 시군구별 전기사업허가 CSV
  recloud/          # recloud 시군구별 이용률 CSV
  openinframap/     # OSM 전력 인프라 GeoJSON (by_sido/)
  logs/
    crawler/        # 크롤 상태 로그
    geocode/        # 지오코딩 캐시/실패 로그
```

## 다음 작업

1. recloud 정기 수집 주기 결정 (월 1회?)
2. openinframap 갱신 주기 결정 (분기 1회?)
3. data.go.kr 실패 재시도 정책 명문화
