# PV Profile Augmentation PRD (전체)

- 문서 버전: `v0.5`
- 작성일: `2026-02-28`
- 이전 버전: `PRD_v0.4.md` (덮어쓰기 금지)

## 1. 프로젝트 목표

핵심 목표는 `rps_rawdata`와 실제 세부 발전량 데이터 간 간극을 메우는 것이다.
현 단계는 배포가 아니라 자동화 파이프라인 완성에 집중한다.

## 2. 표준 실행 흐름

```
크롤러 (incremental) → preprocess.py (incremental) → parquet 갱신
```

별도 retry 스크립트 없음 — 지오코딩 재시도가 `preprocess.py` 내 인라인 처리됨.

## 3. 트랙별 진행 상태

### 3.1 크롤링 트랙 — 완료

- Playwright 기반 data.go.kr 시군구별 CSV 증분 다운로드 크롤러 완성
- 상태 파일(`pv_facility_profile_state.csv`) 기반 중복 방지/재실행 복구 동작
- 원천 CSV 135개, 119,558행 수집 완료 (2026-02-27 기준)
- 구현 파일: `generator_next/crawlers/data_go_kr_solar_download_playwright.py`

### 3.2 전처리 트랙 — 구현 완료, 실행 검증 필요

- `preprocess.py`: raw_csv 통합·필터링·지오코딩(retry 포함)·parquet 출력 파이프라인 구현
- `geocode_retry.py` 제거됨 — retry가 `preprocess.py` 인라인에 통합
- `geocode_failed_review.csv` 제거됨 — 실패 로그는 `geocode_failures_kakao_raw.csv`로 일원화
- 상세: `plan/preprocessing/PRD_v0.4.md` 참조

**미결 사항:**
- `preprocess.py` 실제 실행 검증 미완료
- `http_400` 4건 원인 미분류
- 증분 모드의 크롤러 `modified_date` 기반 변경 파일 감지 미구현

### 3.3 통계적 증강 트랙 — 미착수

- 문제정의 완료, 방법론 미확정
- 상세: `plan/statistical_augmentation/PRD_v0.1.md` 참조

## 4. 현재 블로커

1. 전처리 파이프라인 실행 검증 미완료 (코드는 있음)
2. `http_400` 4건 원인별 처리 규칙 미확정
3. 통계적 증강 방법론 미선정

## 5. 다음 작업 우선순위

1. `preprocess.py --no-geocode` 실행 → parquet 생성 확인
2. `KAKAO_API_KEY` 설정 후 지오코딩 포함 전체 실행 확인
3. `http_400` 4건 주소 직접 확인 → 원인 분류
4. 통계적 증강 방법론 논의 착수

## 6. 문서 운영 규칙

- 전체 계획 문서: `plan/overall/PRD_v0.5.md`
- 세부 계획 문서: 각 트랙 폴더에서 독립 버전 관리
- 다음 수정부터는 반드시 새 버전 파일 생성
