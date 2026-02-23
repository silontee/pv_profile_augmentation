# generator_next

신규 작업용 폴더입니다. 기존 `generator/`는 레거시로 보존하고, 새 수집/전처리 코드는 여기서 진행합니다.

## 실행 기준

- Playwright 크롤러: `generator_next/crawlers/data_go_kr_solar_download_playwright.py`
- Selenium 크롤러(백업): `generator_next/crawlers/data_go_kr_solar_download_selenium.py`
- 기본 다운로드 위치: `generator_next/source/raw_csv`

## 권장 실행

```bash
uv run playwright install chromium
uv run python generator_next/crawlers/data_go_kr_solar_download_playwright.py --headless
```

## 전환 원칙

1. 신규 기능은 `generator_next/`에만 추가
2. 기존 `generator/`는 참조만 하고 수정 최소화
3. 신규 파이프라인 검증 완료 후 `generator/` 제거 검토
