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

## 통합 QA Dashboard (2026-10-20)

기존 결함 집계와 단일 HTML 배포 구조를 유지하면서 상단 메뉴를 `결함 현황 / QA 업무 진행 현황 / QA 품질 관리`로 확장했습니다. 결함 내부 분석 화면은 Select로 전환하며 모든 화면은 HTML에 포함된 동일 데이터 스냅샷을 사용합니다.

- `qa_dashboard.py`: 실제 Notion 스키마 검증, QA 업무·품질 페이지 조회, 소스별 캐시 및 파생 지표
- `qa_dashboard.js`, `qa_dashboard.css`: 기존 HTML에 인라인으로 포함되는 확장 화면
- `data/`: 마지막 성공한 소스별 로컬 스냅샷. Git에서 제외하며 브라우저에 직접 제공하지 않습니다.
- `tests/`: 상태·날짜·장애 격리 단위 테스트 및 Chromium 화면 검증
- `QA_DASHBOARD_REPORT.md`: 분석 결과, 집계 기준, 검증 결과와 배포 절차

추가 선택 환경변수:

```bash
export NOTION_QA_TASK_DB_ID="7ab73fbd195182da9862015f449308d5"
export NOTION_QA_QUALITY_PAGE_ID="1fa73fbd195180a59f39d3ae80362936"
```

기존 `NOTION_TOKEN`을 재사용하며 해당 integration이 업무 DB, 연결된 QA 업무 페이지, 품질 관리 페이지를 읽을 수 있어야 합니다. DB ID를 바꾸어도 속성을 추정하지 않으며, 검증된 스키마가 다르면 해당 소스를 조회 실패로 표시합니다.

```bash
# 이 디렉터리에서 실행. 기존 기본값은 publish=True이므로 로컬 검토에는 명시적으로 지정합니다.
python3 generate_defect_dashboard.py --no-publish
python3 -m http.server 8765 --bind 127.0.0.1
# http://127.0.0.1:8765/defect_dashboard_embed.html

python3 -m unittest discover -s tests -v
# 개발 환경에 Playwright와 Chromium이 설치되어 있을 때 실행
python3 tests/browser_dashboard.py
```

검토 후 기존 방식으로 `python3 generate_defect_dashboard.py --publish`를 실행하면 생성된 단일 HTML이 Pages 저장소에 게시됩니다. 자동 동기화를 유지하려면 **HTML뿐 아니라 새 Python/JS/CSS 소스도 Bug_Dashboard 저장소에 반영**해야 합니다. 상위 workflow가 매번 원격 `Bug_Dashboard/main`을 가져오므로 로컬 수정만으로 Actions에는 적용되지 않습니다.

소스 갱신 실패 시 마지막 성공 데이터가 있으면 그 시각과 함께 표시하며, 없으면 조회 불가로 표시합니다. `data/`는 로컬 캐시이므로 새 GitHub Actions runner에는 이전 캐시가 없습니다. runner 간 마지막 성공 데이터를 유지하려면 별도의 비공개 캐시 보존 설정이 필요합니다. 이번 변경에서는 기존 workflow·인증·스케줄을 수정하지 않았습니다.

### 컴팩트 화면 구성

상단 설명과 빈 동기화 영역을 줄이고 글꼴·카드 간격을 축소했습니다. QA 업무는 PC에서 `현재 업무 / 예정 업무` 2열이며, 완료·중지·단계 완료 등은 상태 선택으로 확인합니다. Timeline은 화면 선택으로 분리했습니다. 품질 화면의 중복 업무 목록은 업무 탭으로 연결하고, 품질 세부 분석·프로젝트 상세도 Select로 필요한 내용만 표시합니다.

긴 표·버전·문서 목록은 화면 높이에 따라 이전/다음 페이지로 나눕니다. 작은 화면에서는 병렬 패널도 버튼으로 전환합니다. 스크롤바만 숨기거나 데이터를 삭제하는 방식이 아니며, 같은 데이터 스냅샷과 집계 기준을 사용합니다. 본문 13px·패널 제목 15px·KPI 28px로 가독성을 유지합니다. 브라우저 검증은 노션 화면과 유사한 실제 1390×860 iframe과 PC·태블릿·모바일 9개 크기를 검사합니다. 높이가 부족할 때는 글자를 더 축소하지 않고 표시 항목을 페이지로 나눕니다.

정상 동기화 상태 배지는 표시하지 않습니다. 동기화 실패 또는 이전 스냅샷 사용 시에만 해당 소스의 안내를 표시합니다.
