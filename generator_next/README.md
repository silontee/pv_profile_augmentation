# generator_next

신규 수집/전처리 작업 폴더. 기존 `generator/`는 레거시로 보존하고, 신규 코드는 여기서 진행한다.

## 디렉토리 구조

```
generator_next/
├── crawlers/
│   ├── data_go_kr_solar_download_playwright.py   # 공공데이터포털 태양광 CSV 다운로더
│   ├── recloud_solar_crawler.py                  # RE:Cloud 태양광 발전소 현황 크롤러
│   ├── openinframap_power_crawler.py             # OpenInfraMap(OSM) 송·변전 인프라 크롤러
│   └── visualize_infra_map.py                    # 송·변전 인프라 지도 시각화
├── data/
│   ├── openinframap/       # 송·변전 GeoJSON + 지도 HTML
│   └── recloud/            # RE:Cloud 수집 CSV
└── README.md
```

## 의존성 설치

```bash
# 공통
pip install aiohttp

# 공공데이터포털 크롤러
pip install playwright
playwright install chromium

# 지도 시각화
pip install folium
```

## 1. 공공데이터포털 태양광 CSV 다운로더

data.go.kr에서 태양광 발전설비 프로필 CSV를 증분 다운로드한다.

```bash
# 기본 실행 (headless 브라우저)
python3 generator_next/crawlers/data_go_kr_solar_download_playwright.py --headless
```

- 상태 파일(`pv_facility_profile_state.csv`)로 수정일 비교 → 변경분만 다운로드
- 출력: `generator_next/source/raw_csv/`

## 2. RE:Cloud 태양광 발전소 현황 크롤러

recloud.energy.or.kr에서 전국 시도·시군구별 태양광 발전소 개소/설비용량/이용률을 수집한다.

```bash
# 전국 수집
python3 generator_next/crawlers/recloud_solar_crawler.py

# 특정 시도만
python3 generator_next/crawlers/recloud_solar_crawler.py --sido 28

# 출력 디렉토리 변경
python3 generator_next/crawlers/recloud_solar_crawler.py --output-dir generator_next/data/recloud
```

- 출력: `generator_next/data/recloud/` (sido_summary + gugun_detail CSV)

## 3. OpenInfraMap(OSM) 송·변전 인프라 크롤러

Overpass API를 통해 한국의 변전소·송전선·배전선·케이블 데이터를 GeoJSON으로 수집한다.

```bash
# 전국 수집
python3 generator_next/crawlers/openinframap_power_crawler.py

# 특정 시도만
python3 generator_next/crawlers/openinframap_power_crawler.py --sido 서울특별시

# 출력 디렉토리 변경
python3 generator_next/crawlers/openinframap_power_crawler.py --output-dir generator_next/data/openinframap
```

수집 대상:
| 태그 | 설명 | 지오메트리 |
|------|------|-----------|
| `power=substation` | 변전소 | Point |
| `power=line` | 송전선 (고압) | LineString |
| `power=minor_line` | 배전선 (저압) | LineString |
| `power=cable` | 지중·해저 케이블 | LineString |

- 출력: `generator_next/data/openinframap/` (substations + power_lines GeoJSON)
- Overpass API rate limit 대응: 시도별 순차 처리, 자동 재시도

## 4. 송·변전 인프라 지도 시각화

수집한 GeoJSON을 인터랙티브 지도(HTML)로 시각화한다.

```bash
# data 디렉토리에서 최신 GeoJSON 자동 탐색
python3 generator_next/crawlers/visualize_infra_map.py --data-dir generator_next/data/openinframap

# 파일 직접 지정
python3 generator_next/crawlers/visualize_infra_map.py \
  --substations generator_next/data/openinframap/substations_XXXXXX.geojson \
  --lines generator_next/data/openinframap/power_lines_XXXXXX.geojson

# 정적 이미지로 출력 (matplotlib)
python3 generator_next/crawlers/visualize_infra_map.py \
  --data-dir generator_next/data/openinframap \
  --output generator_next/data/openinframap/infra_map.png
```

- `.html` 출력: folium 인터랙티브 맵 (어두운 배경, 전압별 색상/굵기 구분)
- `.png` 출력: matplotlib 정적 이미지
- 출력: `generator_next/data/openinframap/infra_map.html`

## 전환 원칙

1. 신규 기능은 `generator_next/`에만 추가
2. 기존 `generator/`는 참조만 하고 수정 최소화
3. 신규 파이프라인 검증 완료 후 `generator/` 제거 검토
