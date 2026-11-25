# 2026-11-25 운영 배포 완료 기록

사용자의 “푸시 배포” 승인 후 두 저장소 main에 수정본을 반영하고 실제 운영 검증을 완료했습니다. 아래 개발 단계의 미배포·승인 대기 기록은 이 기록 이전 시점의 이력입니다.

- Bug_Dashboard 소스 반영 `3a762fa`, 상위 run_all_notion 반영 `84714b4`.
- [첫 운영 동기화](https://github.com/mhjang-qa/run_all_notion/actions/runs/45543913940) **SUCCESS**.
- [캐시 복원 후 운영 재실행](https://github.com/mhjang-qa/run_all_notion/actions/runs/45544144550) **SUCCESS**.
- 실제 runner에서 5개 소스의 암호화 캐시 복원 및 재보존을 확인했습니다. 테스트 fixture의 캐시 로그와 실제 운영 복원 로그를 구분해 확인했습니다.
- [Pages 배포](https://github.com/mhjang-qa/Bug_Dashboard/actions/runs/45544325515) **SUCCESS**.
- [운영 대시보드](https://mhjang-qa.github.io/Bug_Dashboard/defect_dashboard_embed.html) HTTP 200, 모든 소스 ok, PAT 입력 제거 확인.
- 운영 재수집에서 새 결함 1건이 반영되어 전체 **2,253** / Hanpass **1,807** / Gohanpass **446**입니다. 개발 단계 검증의 2,252건 이후 추가된 데이터이며 하드코딩하지 않았습니다.
- 실제 운영 URL에서 9개 해상도·Notion iframe·메뉴·페이지 이동 **297개 검사 PASS**, 콘솔 오류 0.
- GitHub 인증·Notion Secrets를 변경하지 않았으며, 새 Bot이나 Notion 원본 데이터 변경은 하지 않았습니다.
- 배포별 상세 수치·시각·커밋은 `validation/deployment_results.json`에 기록했습니다.

---

# 2026-11-25 결함 조회 장애 수정 결과

실제 Notion 읽기 전용 검증과 로컬 수정·회귀 테스트를 완료했습니다. 원격 Push 및 운영 배포는 수행하지 않았습니다. 기존 프로젝트 원본은 변경하지 않고 두 저장소의 별도 체크아웃에서 수정했습니다.

## 원인과 최초 확인 지점

- 최초 실패 위치는 `fetch_database_pages` → `POST /v1/databases/{database_id}/query`입니다.
- 기존 `Notion-Version: 2022-06-28`에서 **400 / validation_error / multiple_data_sources_for_database**를 실제 재현했습니다. 응답은 `Databases with multiple data sources are not supported in this API version.`입니다.
- 결함 DB `21473fbd-1951-800d-8321-fc2e34c2548e`에 `QA_ISSUES`와 `New data source` 두 소스가 있습니다. 올바른 QA_ISSUES 소스는 `21473fbd-1951-808b-ad5d-000b0217526f`입니다. 임의로 새 소스나 티켓을 만들지 않았습니다.
- `2025-09-03`의 DB 메타데이터 조회 및 data source query는 200입니다. [Notion 공식 마이그레이션 가이드](https://developers.notion.com/guides/get-started/upgrade-guide-2025-09-03)는 기존 API의 다중 소스 DB 조회 실패와 DB → data source ID 검색 절차를 명시합니다.
- 마지막 확인된 정상 산출물은 `909f022`, 2026-11-24 **16:02:33 KST**, 2,234건입니다. 첫 실패 산출물은 `926341b`, 2026-11-25 **04:38:58 KST**입니다. 데이터 소스가 추가된 정확한 사용자 조작 시각은 확인하지 않았습니다.
- 정상/실패 구간의 Python·JS·CSS 코드 차이는 없습니다. 외부 Notion DB 구성 변경으로 기존 API의 호환성 제한에 걸린 사례입니다.
- 기존 `sync_source`는 예외를 상태값으로 바꾸지만 main은 `data or []`를 통계로 만들어 0건 HTML을 덮어쓰고 업로드했습니다. 정상 수집과 HTML 생성 성공을 분리하지 않은 것이 2차 원인입니다.
- 최근 [운영 Actions](https://github.com/mhjang-qa/run_all_notion/actions/runs/45515784176)는 전체 failure였습니다. 별도 heatmap 단계도 동일한 400으로 실패한 반면, dashboard 단계는 `with 0 rows` HTML을 생성·업로드했습니다. 따라서 전체 workflow가 성공했다는 의미로 분석하지 않았습니다.

## 수정 전후 및 실제 데이터 정합성

| 항목 | 수정 전 최신 배포 스냅샷 | 수정 후 실제 API/로컬 화면 |
|---|---:|---:|
| 결함 전체 | 조회 실패인데 0 표시 | 2,252 |
| Hanpass | 조회 실패인데 0 표시 | 1,806 |
| Gohanpass | 조회 실패인데 0 표시 | 446 |
| 결함 페이지네이션 | 첫 요청 400 | 23페이지, 마지막 52건 |
| 파싱 제외 | 전체 실패 | 0 |
| 최근 30일 결함 | 조회 불가 | 226 |
| QA 업무 | 정상 | 24 |
| 품질 문서 링크 | 정상 | 12 |

원본 Page ID 2,252개가 중복 없이 수집됐고, 정규화 2,252개 및 대시보드 전체 합계가 일치합니다. Hanpass + Gohanpass = 전체이며 기존 목표버전·제목 기반 서비스 분류 규칙은 유지했습니다. 서비스가 모호한 항목을 Hanpass로 분류하는 기존 규칙의 한계도 화면 안내에 유지했습니다.

제보 DB는 별도 소스입니다. 실제 원본은 Hanpass 2건 / Gohanpass 6건이며, KST 최근 30일에 해당하는 제보는 둘 다 0건입니다. 이 0건은 정상 조회 결과입니다. 결함 수와 제보 수를 합치거나 임의의 데이터로 채우지 않았습니다.

실제 API 검증에는 기존 로컬 인증 파일을 읽기만 했습니다. Notion 원본·인증 파일 수정, 메시지 발송, 토큰 출력은 하지 않았습니다. API 원문과 상세 결함은 Git 제외 `data/`에만 보관합니다. 공개 가능한 검증 요약은 `validation/live_results.json`입니다.

## 구현 변경

| 파일 | 변경 |
|---|---|
| `notion_api.py` | 읽기 전용 transport, 2025-09-03, 소스 소속 검증, 모호한 소스 선택 차단, 페이지네이션·커서 검증, 제한 재시도·안전 로그 |
| `generate_defect_dashboard.py` | 명시적 QA_ISSUES 조회, 행별 파싱 격리·제외 집계, KST 날짜·30일 경계, 소스 상태 검사, 원자적 HTML 교체, 실패 종료/배포 차단, 프로세스 잠금, 기본 publish=False |
| `qa_dashboard.py` | 소스별 성공 캐시, DB 식별자 검증, 마지막 시도/성공 시각, 안전한 임시 파일·교체, 실패 진단 메타데이터 |
| `qa_dashboard.js` | 부분/실패/이전 데이터 구분 안내, 기존 정상 메뉴 유지 |
| `qa_dashboard.css` | 수집·시도·생성 시각이 모바일 화면을 넓히지 않도록 줄바꿈 |
| `defect_dashboard_embed.html` | 실제 수집된 검증 스냅샷으로 재생성 |
| `tests/test_pipeline.py` | API·수집·집계·보존·잠금·배포 차단 테스트 |
| `tests/test_live_notion.py` | opt-in 읽기 전용 실제 API 원본/집계 정합성 검사 |
| `tests/browser_dashboard.py` | 기존 메뉴·모바일·iframe 검사 유지, 실패 지표 —·이전 수치·토큰 없는 동기화 검사 추가 |
| `README.md`, `validation/*results.json` | 실행·운영 정책·검증 결과 |
| 상위 `notion_hit/generate_heatmap.py` | 동일 DB 오류를 공통 notion_api 모듈 재사용으로 해결 |
| 상위 `.github/workflows/run_all_notion.yml` | 직렬 실행, 회귀 테스트 선행, 성공 소스 암호화 캐시 복원/보존 |
| 상위 `.github/scripts/dashboard_cache.py` | 공개 캐시에 원문을 남기지 않도록 암호화+HMAC 인증, 허용 파일만 복원 |
| 상위 `tests/test_dashboard_resilience.py`, `.gitignore` | 암호화 변조·상위 실패 전파·히트맵 소스 선택 검사, 캐시 Git 제외 |

수집 소스 하나라도 ok가 아니면 운영 HTML을 교체하지 않고 exit 1로 종료합니다. 정상 DB는 소스별 캐시에 독립적으로 보존하며 실패 미리보기 `data/failed-dashboard.html`에는 해당 DB의 이전 정상 데이터 또는 조회 가능한 목록을 보여줍니다. `data/last-attempt.json`에 안전한 시도 결과를 남깁니다. 부분 데이터가 완전한 최신 데이터로 배포되지 않도록 publish에서도 상태를 다시 검증합니다.

정적 Pages는 실패 실행의 로컬 상태 파일을 읽을 수 없습니다. 실패 이후 운영 화면에는 마지막 성공 HTML과 성공 시각이 유지됩니다. 최신 실패 결과는 Actions에서 확인합니다. 실패 미리보기 및 원문 캐시를 공개 배포하지 않습니다.

## 동기화 동작

PAT를 브라우저에서 받아 GitHub API에 직접 보내던 코드를 제거했습니다. 동기화 버튼은 GitHub workflow 화면으로 안내하고, 사용자가 로그인 후 Run workflow를 선택해 실제 수집을 실행합니다. 페이지에서 GitHub 실행 화면을 여는 것만으로 요청·성공으로 표시하지 않습니다. 이전 세션 토큰도 제거합니다.

새로고침 감시는 생성 시각뿐 아니라 모든 소스의 성공 상태를 확인합니다. 수집 성공·마지막 시도·HTML 생성 시각을 별도로 표시합니다. 기존 외부 실행 서버가 없어 Pages 내 직접 dispatch 및 작업 상태 API는 제공하지 않았습니다. 실제 실행·진행/실패 확인은 GitHub Actions 인증 화면에서 수행합니다.

## 자동 테스트 결과

- 오프라인 단위 테스트 **33개 PASS** (dashboard 30 + runner 3).
- 기본 테스트에서 실제 API 테스트 1개는 의도적으로 SKIP. 별도 opt-in 실행에서 **실제 API 통합 테스트 1개 PASS** (23.4초).
- Chromium **9개 해상도 / 297개 레이아웃·페이지 이동 검사 PASS**, Notion 크기 iframe 1390×860 PASS. 콘솔 오류 0, 메뉴 전환 데이터 요청 0.
- 실패 차트 — 표시, 정상 업무 메뉴 보존, 이전 성공 수치 유지, 토큰 입력 제거 검사 PASS.
- workflow YAML 구문 검사 PASS. 수정 후 운영 workflow 및 Pages 배포는 승인 전이므로 미실행입니다.

| TC | 결과 및 범위 |
|---|---|
| TC_001 | PASS · mock transport + 실제 API 200 |
| TC_002 | PASS · 401 무재시도, 소스 캐시 보존 단위 테스트 |
| TC_003 | PASS · 400/403/404 무재시도 및 안전 오류 기록 |
| TC_004 | PASS · 429/503/네트워크 제한 재시도 mock, 실제 장애 유발 미수행 |
| TC_005 | PASS · 정상 빈 결과는 ok/0건, 실제 최근 30일 제보 0건 확인 |
| TC_006 | PASS · 출력 보존·exit 1·publish 미호출, 브라우저 — 표시 |
| TC_007 | PASS · 한 DB 실패 시 다른 DB 최신 자료 + 실패 DB 이전 성공 자료 유지 |
| TC_008 | PASS · malformed 속성 fallback/행별 제외·건수 기록 |
| TC_009 | PASS · cursor 경계 mock + 실제 23페이지 전체 조회 |
| TC_010 | PASS · 서비스 분류·합계 보존 및 실제 원본 정합성 |
| TC_011 | PASS · UTC→KST 자정·30일 시작/종료·미래 날짜 경계 |
| TC_012 | PASS · 정적 환경 안내 및 토큰 제거, 로그인 후 Run workflow는 운영 승인 후 확인 |
| TC_013 | PASS · 원자적 replace 실패 시 기존 HTML 유지 |
| TC_014 | PASS · 비정상 소스 publish 차단/상위 실패 전파 mock. 실제 배포 실패 유발은 미수행 |
| TC_015 | PASS · 전체 메뉴·필터·퍼널·히트맵·제보·추이·버전·프로젝트·업무·품질·Notion 링크 회귀 |
| TC_016 | PASS · 실제 Notion 2,252 = 정규화 2,252 = 전체 집계 2,252 |

## 배포 상태와 남은 운영 검증

1. **미배포**입니다. 첨부 요청의 “운영 배포 및 원격 Push는 사용자 승인 없이 수행하지 않는다” 조건을 지켰습니다.
2. 먼저 Bug_Dashboard 소스와 검증된 HTML을 반영하고, 다음 run_all_notion 공통 히트맵 어댑터·workflow·캐시 스크립트를 반영해야 합니다. 상위 workflow는 매번 Bug_Dashboard/main 최신 코드를 가져옵니다.
3. 승인 후 실제 workflow 1회, 소스 캐시 복원 1회, Pages 배포와 운영 URL 수치를 확인해야 합니다. GitHub Secrets 값은 읽을 수 없으며 실제 실행 결과로 확인합니다.
4. 캐시 소실·토큰 교체 시 재수집하며, 수집 실패 시에는 기존 성공 배포물을 보존합니다. 데이터 소스가 추가되더라도 명시 ID가 DB에 속하는 한 해당 QA_ISSUES만 조회합니다.
5. 별도 히트맵 어댑터는 단위 테스트를 통과했고 사용하는 공통 transport는 실제 API에서 검증했습니다. 상위의 전체 HQI/monitor/heatmap 운영 동시 실행은 미실행입니다.

---

아래는 기존 보고서 기록입니다.

# 통합 QA Dashboard 작업 보고

검증 기준: 2026-10-20 KST. 실제 Notion API 응답을 조회한 뒤 구현했으며 원본 Notion 데이터는 변경하지 않았습니다. 로컬 구현 및 검증 완료, 원격 게시·Actions 실행은 수행하지 않았습니다.

## 1. 기존 프로젝트 분석 결과

`Bug_Dashboard`는 별도 Git 저장소입니다. 기존 `generate_defect_dashboard.py`가 Notion 결함 DB와 Hanpass/GoHanpass 제보함 DB를 페이지네이션 조회하고, Python에서 서비스별 KPI·차트·프로젝트 상세를 집계한 후 단일 `defect_dashboard_embed.html`을 생성합니다. 차트는 기존 SVG/HTML 렌더링을 재사용합니다.

상위 `run_all_notion.py`가 생성기를 호출합니다. `.github/workflows/run_all_notion.yml`은 KST 08:30/17:30 실행, 수동 실행, 기존 Secrets를 사용하며 매 실행 시 원격 Bug_Dashboard/main을 갱신합니다. 생성기의 기존 publish 함수는 `.publish/defect-dashboard` 체크아웃에 HTML을 복사하고 커밋·푸시합니다.

운영 URL은 웹 도구로 직접 읽을 수 없었습니다. 분석·비교는 로컬 운영 소스, 기존 생성 HTML, 실제 Notion API 데이터를 근거로 수행했습니다.

## 2. Notion DB 분석 결과

### 결함 DB

- DB: `21473fbd1951800d8321fc2e34c2548e`, 실제 데이터 1,992건.
- 확인한 속성: `결함 제목` title, `상태` status, `심각도` select, `목표버전` select, `결함 유형` select, `조치 담당자` people, `우선순위` status, 생성 시각, 제보함 relation, 자기참조 `관련된 이슈` relation 등.
- 실제 심각도: Critical / Major / Minor / 개선 의견.
- 실제 상태: 등록 (Registered), 배정 (Assigned), 기획서 수정, 처리중 (In Progress), 개발 완료 (Dev Done), 결함 재발생 (Reopen), QA 검증 -회귀 (QA Verification), Known-Issue, 추척 관찰-백로그, 결함 아님 (Not an issue), 추후 수정 백로그 이관, 완료 (Done).
- 서비스 전용 속성은 없습니다. 기존 `목표버전`의 `[G.H]`, `[Go.Hanpass]`, Hanpass 버전·기능명 및 제목 기반 분류를 보존했습니다. 모호한 11건(버전 없음 8건, 결함 아님 버전 3건)은 기존처럼 Hanpass에 포함됩니다. GoHanpass 제보함 relation이 있는 행과 기존 GoHanpass 판정이 충돌하는 사례는 이번 원본에서 0건입니다. 서비스별 완전한 정답 속성이 있다는 뜻은 아닙니다.

### QA 업무 DB

- DB: `7ab73fbd195182da9862015f449308d5`, 실제 데이터 15건.
- 실제 속성: `이름` title, `선택` select, `날짜` date(range), `TC 개발 유/무` select, `TC 개수` number, `최소 테스트 예상 기간` rich_text, `우선순위` select, 선행/후속 작업 relation, `❤️‍🔥 QA 업무 진행 현황` relation.
- 실제 상태: 테스트 진행중 / 1차 테스트 완료 / 테스트 예정 / **태스트 완료** / 테스트 중지. 원본 오탈자를 수정하지 않고 화면에서 완료로 분류했습니다.
- 분류 결과: 진행중 2 / 예정 4 / 완료 6 / 단계 완료 1 / 중지 2. 지연·주의 2건은 이 분류와 중복되는 별도 지표입니다.
- 담당자 전용 속성은 없지만 연결된 QA 업무 DB(`2a773fbd19518018af97e393d017f526`)에는 `담당자` people 속성이 있습니다. 실제 relation으로 연결된 페이지에 한해 담당자를 가져오고 출처를 표시합니다. 제목이 비슷하다는 이유로 연결하지 않습니다.
- 서비스·퍼센트 진행률·Release 연결 속성은 없으므로 해당 지표는 만들지 않았습니다. TC 개수는 규모로 표시하며 수행률·통과율로 해석하지 않습니다.

### IT Quality Assurance

- Page: `1fa73fbd195180a59f39d3ae80362936`.
- 최초 분석에서 333개 block의 구조·실제 내용을 확인했습니다. 실행 시 최대 3단계, 48개 컨테이너를 조회했고 하위 조회 실패는 0건입니다.
- QA 업무 진행 현황, TC 진행 현황, 테스트 정보, 장애보고서, 서비스별 테스트 케이스 DB, 테스트 계획서·결과서·운영 배포 테스트·Test Design·Release 문서 등을 확인했습니다.
- 하위 DB 17개는 구조·링크를 확인했습니다. 모든 DB의 행을 읽어 지표화한 것은 아닙니다. 검증하지 않은 DB에 근거한 통과율·Coverage·릴리즈 등급을 만들지 않았습니다.

## 3. 변경된 Dashboard IA

```
QA DASHBOARD
├─ 결함 현황
│  ├─ 서비스: 전체 / Hanpass / Gohanpass
│  └─ 분석 화면 Select: 흐름 요약 / 일별 추이 / 버전·분포 / 최근 결함 / 프로젝트별 현황
├─ QA 업무 진행 현황
│  ├─ 진행·예정·완료·주의 KPI, 상태/일정 필터
│  ├─ 상태별 업무 목록, TC 준비, 실제 연결 담당자
│  └─ 진행·예정 Timeline
└─ QA 품질 관리
   ├─ Executive Summary
   ├─ 미해결 Critical/Major
   ├─ 장기 미처리 결함
   ├─ QA 일정·TC 준비 상태
   └─ 주요 문서·링크
```

상단 메뉴는 sticky 처리했습니다. 각 화면 전환에는 Notion API 요청이 없습니다. 업무의 서비스 정보가 없으므로 품질 화면의 서비스 필터는 결함 지표에만 적용한다고 명시했습니다.

## 4. 추가/수정 파일

| 파일 | 내용 |
| --- | --- |
| generate_defect_dashboard.py | 기존 생성기에 신규 데이터·화면 통합, 제보함별 장애 격리, 분석 Select, Critical·금일 종료 KPI |
| qa_dashboard.py | 실제 스키마 검증, QA 소스 동기화, 캐시, 파생 지표, Risk 정책 분리 |
| qa_dashboard.js | 상단 탭, 업무 목록·필터·Timeline, 품질 관리 화면 |
| qa_dashboard.css | 기존 색상·카드 스타일을 사용하는 반응형 확장 |
| defect_dashboard_embed.html | 실제 데이터로 생성한 통합 화면 |
| tests/test_qa_dashboard.py | 상태·날짜·스키마·캐시·장애 격리·JSON 보안 테스트 |
| tests/browser_dashboard.py | 탭·분석·서비스·버전·링크·반응형·소스 실패 브라우저 검증 |
| validation/browser_results.json | 브라우저 검증 결과 |
| README.md / .gitignore | 실행 안내 및 내부 캐시·화면 캡처 Git 제외 |
| QA_DASHBOARD_REPORT.md | 본 보고서 |

`validation/*.png`에 실제 결함·업무·품질·태블릿·모바일 화면을 저장했습니다. 내부 데이터가 포함되어 Git에서는 제외했습니다.

## 5. 결함 현황 변경사항

- 기존 5개 분석 버튼을 Select로 변경하고 상단 3개 메뉴와 분리했습니다.
- 서비스 표시명은 Hanpass/Gohanpass로 정리하되 내부 키와 분류·통계 기준은 유지했습니다.
- 기존 KPI를 보존하고 Critical, 금일 종료를 추가했습니다.
- 퍼널, 30일 히트맵, 제보함, 일별 차트, 버전 분포, 최근 10건, 프로젝트별 상세·완료버전 제외·버전 새로고침을 유지했습니다.
- 서비스 전환 시 선택한 일별 기간이 유지되도록 수정했습니다.
- 최근 결함 링크는 API의 실제 `https://app.notion.com/p/...` URL과 일치함을 확인했습니다.

## 6. QA 업무 진행 현황 구현 내용

상태별 카드·목록과 7/14/30일 일정 겹침 필터를 제공합니다. 기본은 전체 일정입니다. 기간 필터 적용 시 날짜 미정 업무는 해당 기간에 포함할 근거가 없어 제외되며, 전체 일정에서는 조회됩니다.

지연은 실제 날짜의 **end**가 KST 기준 오늘보다 이전이면서 진행중·예정·단계 완료일 때만 파생 표시합니다. 시작일만 있는 업무에는 종료일을 만들지 않습니다. 완료·중지 업무는 지연에서 제외합니다. 원본 상태는 함께 표시합니다.

Timeline은 오늘 −14일 ~ +30일이며 진행·예정·단계 완료 중 날짜가 있는 업무만 시간축에 표시합니다. 종료일이 없으면 시작일 위치만 표시합니다. 기간 밖 및 일정 미정 건수를 안내하고 전체 목록에서 원본을 열 수 있습니다.

## 7. QA 품질 관리 구현 내용

실제 데이터에 근거한 5개 영역을 제공합니다. 전체 서비스 기준 미해결 Critical 20건, Major 210건, 개발 완료·미검증 11건, 등록 후 30일 이상 미처리 272건입니다. 상세 목록은 최대 50건과 전체 건수를 구분해 표시합니다.

미해결 판정은 기존 프로젝트 상세의 `is_done_row`, `is_backlog_transfer_row`, `is_dev_done_row`를 재사용합니다. 개발 완료는 최종 완료가 아닙니다. 장기 미처리는 상태 체류 시간이 아니라 등록 후 경과일 기준입니다.

`release_risk()`로 향후 정책 수정 지점을 분리했습니다. 검증된 릴리즈 연결·배포 예정일이 없어 등급은 미산출하고 사유를 표시합니다. 자기참조 relation만으로 반복 발생 결함이라고 단정하지 않았습니다.

## 8. 데이터 동기화 구조

```
Notion (기존 NOTION_TOKEN)
 → 기존 Python 생성기 + qa_dashboard.py
 → 소스별 로컬 data/*.json 성공 스냅샷
 → 집계 및 QA 파생 지표
 → JSON/JS/CSS를 인라인으로 포함한 단일 HTML
 → 기존 GitHub Pages publish
```

결함 / 업무 / 품질 / 각 제보함의 성공·실패·마지막 성공 시각을 분리합니다. 실패 시 해당 소스의 이전 성공 스냅샷만 사용하고 stale을 표시합니다. 캐시가 없으면 조회 실패를 표시합니다. 내부 API 오류 응답 전체나 인증값은 HTML에 넣지 않습니다.

로컬 캐시는 Git 제외입니다. 새 Actions runner에는 이전 로컬 캐시가 없으므로 runner 간 복구까지 원하면 별도의 비공개 캐시 보존 설정이 필요합니다. 이번 작업에서는 기존 Actions 설정을 변경하지 않았습니다.

## 9. 기존 기능 영향도

같은 1,992개 원본 행으로 변경 전 코드와 변경 후 코드를 비교했습니다. 정규화된 모든 행과 3개 scope의 기존 summary, funnel, daily, versions, versionGroups, projectProgress, distributions, heatmap, reportBoard, recent 및 기본 선택값이 동일했습니다. 생성 HTML에 들어간 집계도 같은 기준으로 비교했습니다.

| 비교 기준 | 전체 | Hanpass | GoHanpass |
| --- | ---: | ---: | ---: |
| 기존 로컬 HTML (10/13) | 1,925 | 1,479 | 446 |
| 기존 코드 + 10/20 동일 원본 | 1,992 | 1,546 | 446 |
| 신규 코드 + 10/20 동일 원본 | 1,992 | 1,546 | 446 |

기존 HTML 대비 67건 차이는 최신 원본에 추가된 Hanpass 데이터이며 집계 변경 때문이 아닙니다. 시간에 따라 달라지는 지표를 옛 HTML과 숫자만 비교하지 않았습니다.

기존 환경변수, Notion API 버전, publish 위치·브랜치, workflow dispatch 방식, 통합 실행기와 GitHub Pages 파일명을 유지했습니다.

## 10. 테스트 결과

- Python 단위 테스트 12개 통과: 지연 경계일, 종료일 누락, 완료·중지·단계 완료, 미확인 상태, 미래 일정의 완료 상태 경고, KST 날짜, 캐시 보존, 스키마 변경 차단, Risk 미산출, 기존 상세 판정 재사용, JSON script 종료 주입 방지, 신규 소스 실패 시 기존 집계 유지.
- 변경 전 코드와 실제 원본 기준 전체 집계 비교 통과.
- Chromium: 상단 3개 탭, 5개 분석 화면, 서비스별 KPI, Target Version 및 완료버전 제외, 7일 필터 유지, 원본 Notion URL 일치 확인.
- 업무 상태 필터, 일정 범위, Timeline, 품질 서비스 선택 확인.
- QA 품질 소스 실패를 재현해 결함 1,992건과 업무 15건 및 탭 동작 유지 확인.
- 화면 너비 1440 / 768 / 390px 검증, 태블릿·모바일 페이지 전체 가로 넘침 없음. 넓은 표는 내부 스크롤 처리.
- 브라우저 JavaScript 오류 0건. 화면·필터 전환 중 네트워크 요청 0건. 기존 5분 주기 배포 갱신 감시와 명시적 동기화 요청은 유지.
- 설정된 실제 Notion/PUBLISH 토큰이 생성 HTML에 포함되지 않음을 검사했습니다. JSON 안의 `<`를 Unicode escape하여 script 종료 삽입을 방지합니다.
- Python 컴파일 및 JavaScript 문법 검사 통과.
- 원격 GitHub Actions 실행·실제 Pages 배포 후 동작은 미검증입니다. 로컬 HTTP에서 배포와 동일한 단일 정적 HTML의 동작을 검증했습니다.

## 11. 발견된 문제 / 추가 개선 권고

1. **서비스 판정의 모호성:** 원본 결함 DB에 서비스 속성을 추가하면 11개 모호한 행을 명시적으로 분류할 수 있습니다. 이번에는 집계 기준 보존을 위해 재분류하지 않았습니다.
2. **기존 상태 정규화:** `개발 완료 (Dev Done)`는 기존 summary/funnel에서 종료로 분류되지만 프로젝트 상세는 미검증으로 구분합니다. 이번에는 기존 집계를 보존했습니다. 향후 원본 상태 기준 통합 시 별도 승인된 지표 마이그레이션이 필요합니다.
3. **기존 필드 매핑:** 실제 담당자는 `조치 담당자`, 고유 ID는 `ID ISSUE-2272`인데 기존 FIELD_MAP과 맞지 않는 부분이 있습니다. 기존 통계·렌더링을 유지하고 범위 밖 매핑 변경은 하지 않았습니다.
4. **QA 입력 완전성:** 예정 4건은 일정 미정이며, 담당자 relation이 없는 업무가 있습니다. 미래 시작일인데 완료로 표시된 업무 1건은 화면에서 확인 필요로 표시합니다.
5. **Release Risk 근거:** 업무↔릴리즈↔결함 연결과 확정 배포 예정일, 실제 검증 완료 정보가 확보되면 Risk 정책을 확장할 수 있습니다.
6. **크롤링 범위:** QA 페이지 탐색은 최대 3단계이며, 발견한 모든 TC·장애 DB의 상세 행을 통계화하지 않았습니다. 문서 링크가 있다는 것과 해당 문서 내용의 지표 검증은 구분합니다.
7. **배포 반영:** 상위 workflow는 원격 Bug_Dashboard/main을 가져옵니다. 생성 HTML만 수동 업로드하고 새 Python/JS/CSS를 반영하지 않으면 다음 자동 실행에 새 구조가 유지되지 않습니다.

## 12. 실행 및 배포 방법

`Bug_Dashboard` 디렉터리에서:

```bash
# 로컬 갱신: 기존 .env / NOTION_TOKEN 재사용
python3 generate_defect_dashboard.py --no-publish

# 로컬 확인
python3 -m http.server 8765 --bind 127.0.0.1
# http://127.0.0.1:8765/defect_dashboard_embed.html

# 단위 테스트
python3 -m unittest discover -s tests -v

# Playwright/Chromium이 있는 개발 환경의 브라우저 검증
python3 tests/browser_dashboard.py

# 검토 후 기존 Pages 게시 방식 사용
python3 generate_defect_dashboard.py --publish
```

자동화에 적용하려면 수정 생성기와 `qa_dashboard.py`, `qa_dashboard.js`, `qa_dashboard.css`, 문서·테스트를 Bug_Dashboard 원격 저장소에 반영한 뒤 기존 통합 실행 workflow를 실행합니다. Secrets 이름과 HTML 경로는 그대로입니다. 이번 작업에서는 원격 커밋·푸시·배포를 하지 않았습니다.

## 후속 UI 개선: 스크롤 없는 컴팩트 화면

- 상단의 반복 설명과 빈 동기화 메시지 공간을 제거했습니다. 초기 축소가 과도하다는 피드백을 반영해 기본 본문 13px·패널 제목 15px·KPI 28px로 복원하고 보조 정보는 11~12px로 표시합니다.
- QA 업무를 현재 업무/예정 업무 2열 카드로 구성했습니다. 완료·중지·단계 완료 등의 반복 목록은 상태 Select로 조회하며, Timeline은 별도 화면으로 전환합니다.
- 품질 탭의 중복 QA 업무·TC 표는 업무 탭 연결로 대체했습니다. 품질 요약/미해결/장기 미처리/문서를 Select로 분리했습니다.
- 프로젝트 상세의 처리 현황/유형별 심각도/누적 그래프/유형 분포를 Select로 분리하고, 차트 화면의 중복 KPI를 줄였습니다.
- 긴 표·버전 목록·문서·업무 카드·Timeline은 가용 화면 높이에 맞게 페이지를 나눕니다. PC의 2열 패널은 작은 화면에서 패널 선택으로 전환합니다.
- 본문 스크롤과 표 내부 스크롤을 실제 높이·너비로 검사합니다. `overflow:hidden`으로 내용을 잘라 스크롤만 감추지 않습니다. 줄여 표시한 긴 제목과 셀은 전체 텍스트 tooltip 및 원본 링크로 확인할 수 있습니다.
- UI 수정 전후의 내장 JSON 전체가 동일함을 비교했으며, 기존 결함·업무 집계는 변경하지 않았습니다. 이 후속 작업은 데이터 재동기화 없이 기존 검증 스냅샷을 재사용합니다.
- 자동 브라우저 검사에서 9개 화면 크기와 모든 하위 분석 화면을 검사하고, 긴 목록의 모든 행이 페이지 전환으로 정확히 한 번씩 조회되는지 검증합니다. 상세 결과는 `validation/browser_results.json`에 기록합니다.

### 노션 임베드 가독성 보정

사용자가 첨부한 노션 화면의 임베드 영역(약 1390×860)을 기준으로 검증합니다. 공간이 부족하면 행·목록을 나누며, 화면 전체의 글자를 9~10px로 축소하지 않습니다. PC·태블릿·모바일 9개 화면과 실제 iframe 안에서 탭을 전환해 넘침을 검사하고, 폰트 크기도 자동 검증합니다. 데이터와 집계는 수정 전 내장 JSON과 동일합니다.
