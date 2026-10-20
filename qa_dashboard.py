"""QA extensions. Property names below were verified with Notion API on 2026-10-20.

Keep legacy defect normalization and aggregates in generate_defect_dashboard.py.
No title-based guessing of task service, owner, percentage or release risk.
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

TASK_DB = '7ab73fbd195182da9862015f449308d5'
QUALITY_PAGE = '1fa73fbd195180a59f39d3ae80362936'
TASK_RELATION = '❤️‍🔥 QA 업무 진행 현황'
TASK_STATES = {
    '테스트 진행중': '진행중',
    '테스트 예정': '예정',
    '태스트 완료': '완료',  # Actual Notion option spelling.
    '1차 테스트 완료': '단계 완료',
    '테스트 중지': '중지',
}
KST = ZoneInfo('Asia/Seoul')
AGING_DAYS = 30


def now():
    return datetime.now(KST).isoformat(timespec='seconds')


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def sync_source(path, fetch):
    """A failure retains only this source's previous successful snapshot."""
    try:
        data = fetch()
        result = {'status': 'ok', 'syncedAt': now(), 'attemptedAt': now(), 'data': data}
        atomic_json(path, result)
        return result
    except Exception as exc:
        previous = {}
        try:
            previous = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
        result = {
            'status': 'stale' if 'data' in previous else 'error',
            'syncedAt': previous.get('syncedAt'), 'attemptedAt': now(),
            'error': '동기화 실패 · 권한, 연결 및 서버 로그 확인',
            'data': previous.get('data'),
        }
        # Only the exception class is logged; API responses need not be public.
        print(f'[qa-dashboard] {path.stem}: {type(exc).__name__}', flush=True)
        return result


def validate_schema(schema, fields):
    props = schema.get('properties', {})
    for name, kind in fields.items():
        if props.get(name, {}).get('type') != kind:
            raise ValueError(f'Notion schema changed: {name} ({kind})')


def day(value):
    if not value:
        return ''
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo:
            parsed = parsed.astimezone(KST)
        return parsed.date().isoformat()
    except ValueError:
        return ''


def normalize_tasks(pages, text, related=None, today=None):
    today = today or datetime.now(KST).date()
    related = related or {}
    tasks = []
    for page in pages:
        props = page.get('properties', {})
        status = text(props.get('선택'))
        state = TASK_STATES.get(status, '분류 미확인')
        dates = props.get('날짜', {}).get('date') or {}
        start, end = day(dates.get('start')), day(dates.get('end'))
        # A start-only date is NOT an implied target completion date.
        overdue = bool(end and end < today.isoformat() and state in {'진행중', '예정', '단계 완료'})
        relation_ids = [v['id'] for v in props.get(TASK_RELATION, {}).get('relation', [])]
        parents = [related[i] for i in relation_ids if i in related]
        owners = sorted({n for p in parents for n in p.get('owners', [])})
        tasks.append({
            'id': page['id'], 'title': text(props.get('이름')) or '제목 없음',
            'url': page.get('url', ''), 'status': status or '미지정', 'state': state,
            'overdue': overdue, 'start': start, 'end': end,
            'dday': (date.fromisoformat(start) - today).days if start else None,
            'tcState': text(props.get('TC 개발 유/무')) or '미지정',
            'tcCount': props.get('TC 개수', {}).get('number'),
            'priority': text(props.get('우선순위')), 'owners': owners,
            'ownerSource': '연결된 QA 업무의 담당자' if owners else '담당자 정보 없음',
            'relations': [{'id': i, 'url': 'https://www.notion.so/' + i.replace('-', '')} for i in relation_ids],
            'predecessors': [v['id'] for v in props.get('선행 작업', {}).get('relation', [])],
            'warnings': ['완료 상태와 미래 시작일 확인 필요'] if state == '완료' and start > today.isoformat() else [],
        })
    return sorted(tasks, key=lambda r: (r['start'] or '9999', r['title']))


def fetch_tasks(api):
    db = os.getenv('NOTION_QA_TASK_DB_ID', TASK_DB)
    schema = api.notion_request('/databases/' + db)
    validate_schema(schema, {'이름': 'title', '선택': 'select', '날짜': 'date', 'TC 개발 유/무': 'select', 'TC 개수': 'number', TASK_RELATION: 'relation'})
    pages = api.fetch_database_pages(db, 'qa-tasks')
    parents, parent_errors = {}, []
    ids = {r['id'] for p in pages for r in p['properties'].get(TASK_RELATION, {}).get('relation', [])}
    for pid in sorted(ids):
        try:
            p = api.notion_request('/pages/' + pid)
            owners = p.get('properties', {}).get('담당자', {})
            if owners.get('type') == 'people':
                parents[pid] = {'owners': [v['name'] for v in owners.get('people', []) if v.get('name')]}
        except Exception:
            parent_errors.append(pid)
        time.sleep(.35)
    # Save normalized input with dates/states; derived date flags are recalculated per sync.
    return {'rows': normalize_tasks(pages, api.plain_text, parents),
            'sourceUrl': 'https://www.notion.so/' + db.replace('-', ''),
            'ownerLookupFailures': len(parent_errors),
            'fields': {n: p['type'] for n, p in schema['properties'].items()},
            'stateOptions': [x['name'] for x in schema['properties']['선택']['select']['options']]}


def fetch_quality(api):
    root = os.getenv('NOTION_QA_QUALITY_PAGE_ID', QUALITY_PAGE)
    queue, visited, links, databases, failures = [(root, 0)], set(), {}, [], []
    while queue:
        bid, depth = queue.pop(0)
        if bid in visited:
            continue
        visited.add(bid)
        cursor = ''
        try:
            while True:
                data = api.notion_request('/blocks/' + bid + '/children?page_size=100' + ('&start_cursor=' + cursor if cursor else ''))
                for b in data['results']:
                    kind = b['type']; value = b[kind]
                    if kind in {'child_page', 'child_database'}:
                        title = value.get('title', '')
                        links[b['id']] = {'title': title, 'url': 'https://www.notion.so/' + b['id'].replace('-', ''), 'kind': kind}
                        if kind == 'child_database':
                            databases.append({'id': b['id'], 'title': title})
                    if kind in {'embed', 'bookmark', 'link_preview'}:
                        url = value.get('url', '')
                        if url.startswith('https://'):
                            links[url] = {'title': url.split('//', 1)[1], 'url': url, 'kind': kind}
                    if depth < 3 and kind != 'child_database' and (b.get('has_children') or kind == 'child_page'):
                        queue.append((b['id'], depth + 1))
                if not data.get('has_more'):
                    break
                cursor = data['next_cursor']
        except Exception:
            if depth == 0:
                raise
            failures.append(bid)
        time.sleep(.35)
    # Document sections are selected from actual accessible page titles, not fabricated metrics.
    words = ('테스트 계획', '테스트 결과', '장애', 'Test Design', '운영 배포', 'Release', '출시', 'TC 진행', 'QA 업무')
    selected = [v for v in links.values() if any(w in v['title'] for w in words)]
    return {'sourceUrl': 'https://www.notion.so/' + root.replace('-', ''),
            'documents': selected, 'databases': databases, 'visitedContainers': len(visited),
            'partialFailures': len(failures), 'depthLimit': 3}


def quality_metrics(rows, api, today=None):
    today = today or datetime.now(KST).date()
    unresolved = [r for r in rows if not api.is_done_row(r) and not api.is_backlog_transfer_row(r)]
    high = [r for r in unresolved if r['severity'] in {'Critical', 'Major'}]
    aging = [r for r in unresolved if r.get('createdDate') and (today - date.fromisoformat(r['createdDate'])).days >= AGING_DAYS]
    def items(records):
        return [{**{k: r.get(k) for k in ('title', 'url', 'status', 'severity', 'version', 'domain')},
                 'ageDays': (today - date.fromisoformat(r['createdDate'])).days if r.get('createdDate') else None}
                for r in records]
    return {'unresolvedCritical': sum(r['severity'] == 'Critical' for r in unresolved),
            'unresolvedMajor': sum(r['severity'] == 'Major' for r in unresolved),
            'awaitingVerification': sum(api.is_dev_done_row(r) for r in unresolved),
            'highCount': len(high), 'high': items(sorted(high, key=lambda r: (r['severity'] != 'Critical', r['createdDate']))[:50]),
            'agingCount': len(aging), 'aging': items(sorted(aging, key=lambda r: r['createdDate'])[:50]),
            'agingDays': AGING_DAYS,
            'risk': release_risk()}


def release_risk():
    """No scoring until a verified release relation and release deadline exist."""
    return {'level': None, 'reason': '릴리즈별 결함·QA 업무 연결 및 배포 예정일 근거 부족으로 등급 미산출'}


def extend_payload(payload, rows, api):
    cache = api.SCRIPT_DIR / 'data'
    tasks = sync_source(cache / 'qa_tasks.json', lambda: fetch_tasks(api))
    quality = sync_source(cache / 'qa_quality.json', lambda: fetch_quality(api))
    if tasks.get('data'):
        today = datetime.now(KST).date().isoformat()
        for task in tasks['data']['rows']:
            task['overdue'] = bool(task['end'] and task['end'] < today and task['state'] in {'진행중', '예정', '단계 완료'})
    payload['qaTasks'] = tasks
    payload['qaQuality'] = quality
    payload['sources'] = {'defects': payload.get('defectSource', {'status': 'ok', 'syncedAt': payload['generatedAt']}),
                          'tasks': {k: v for k, v in tasks.items() if k != 'data'},
                          'quality': {k: v for k, v in quality.items() if k != 'data'}}
    for domain, scope in payload['domains'].items():
        subset = rows if domain == 'ALL' else [r for r in rows if r['domain'] == domain]
        scope['quality'] = quality_metrics(subset, api)
        scope['summary']['critical'] = sum(r['severity'] == 'Critical' for r in subset)
        scope['summary']['todayClosed'] = sum(r['closedDate'] == datetime.now().date().isoformat() for r in subset)
    return payload


def integrate_html(html, api):
    css = (api.SCRIPT_DIR / 'qa_dashboard.css').read_text(encoding='utf-8')
    js = (api.SCRIPT_DIR / 'qa_dashboard.js').read_text(encoding='utf-8')
    return html.replace('</head>', '<style>' + css + '</style></head>').replace('</body>', '<script>' + js + '</script></body>')
