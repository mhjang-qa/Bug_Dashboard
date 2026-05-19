# Bug Dashboard

Notion 결함 데이터베이스를 조회해 Notion iframe/embed에 삽입 가능한 단일 정적 HTML 대시보드를 생성합니다.

## 산출물

- `generate_defect_dashboard.py`: Notion 조회, 데이터 집계, HTML 생성, 선택적 GitHub Pages publish 스크립트
- `defect_dashboard_embed.html`: Notion embed용 단일 HTML 파일

## 주요 기능

- 상단 요약 카드: 전체 결함, 신규, 진행중, 수정완료, 종료/완료, 금일 신규, 전일 대비 증감
- 결함 처리 퍼널: 등록, 검토, 배정, 진행중, 수정완료, QA확인, 종료
- 일별 추이: 최근 7일, 14일, 30일 신규/수정완료/종료 건수 전환
- 버전별 결함 집계: 전체 결함 수, Major/Critical 결함 수, 처리 완료율
- 상태, 심각도, 우선순위, OS 분포
- 최근 30일 등록 결함 히트맵
- 최근 등록 결함 10건 리스트

## 환경 변수

필수:

```bash
export NOTION_TOKEN="notion integration token"
```

결함 DB ID는 아래 순서로 사용합니다.

```bash
export NOTION_DEFECT_DB_ID="notion database id"
export DEFECT_NOTION_DB_ID="notion database id"
export NOTION_QA_DEFECT_DB_ID="notion database id"
export NOTION_DATABASE_ID="notion database id"
```

값이 없으면 기존 QA 결함 히트맵 DB ID(`21473fbd1951800d8321fc2e34c2548e`)를 기본값으로 사용합니다. 자동화 모니터용 `NOTION_DB_ID`와 충돌하지 않도록 `NOTION_DB_ID`는 결함 대시보드 DB ID로 사용하지 않습니다.

선택:

```bash
export DEFECT_DASHBOARD_REPO_URL="https://github.com/mhjang-qa/Bug_Dashboard.git"
export DEFECT_DASHBOARD_BRANCH="main"
export DEFECT_DASHBOARD_PUBLISH_DIR=".publish/defect-dashboard"
```

## 실행

로컬 HTML만 생성:

```bash
python3 generate_defect_dashboard.py --no-publish
```

GitHub Pages 저장소까지 커밋/푸시:

```bash
python3 generate_defect_dashboard.py --publish
```

출력 파일과 기본 추이 기간 지정:

```bash
python3 generate_defect_dashboard.py --output defect_dashboard_embed.html --days 30 --publish
```

`--days`는 `7`, `14`, `30`을 지원합니다. HTML 안에서는 일별 추이 탭에서 7일, 14일, 30일을 다시 전환할 수 있습니다.

## Notion 속성 매핑

Notion DB의 속성명이 다르면 `generate_defect_dashboard.py` 상단의 `FIELD_MAP`을 수정합니다.

기본 매핑 대상:

- 제목
- 상태
- 심각도
- 우선순위
- 담당자
- 버전
- OS
- 등록일
- 수정완료일
- 종료일
- 결함 ID

누락된 속성은 `미지정` 또는 Notion 기본 생성/수정 시각으로 보정되며, 누락값 때문에 스크립트가 중단되지 않도록 처리합니다.

## 통합 실행기

상위 프로젝트의 `run_all_notion.py`에서도 결함 대시보드를 함께 갱신할 수 있습니다.

```bash
python3 ../run_all_notion.py --no-publish
python3 ../run_all_notion.py --skip-defect-dashboard
python3 ../run_all_notion.py --defect-days 30
```

실행 결과는 상위 프로젝트의 `notion_run_summary.json`에 `defect_dashboard` 단계로 기록됩니다.
