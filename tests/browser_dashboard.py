"""Verify compact navigation, accessible pagination, and real snapshot invariants."""
from playwright.sync_api import sync_playwright
from pathlib import Path
import json
import os
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'validation'
OUT.mkdir(exist_ok=True)
URL = os.getenv('QA_DASHBOARD_URL', 'http://127.0.0.1:8765/defect_dashboard_embed.html')
PROFILES = [(1440, 900), (1280, 720), (1024, 768), (768, 1024),
            (390, 844), (1366, 600), (1024, 600), (390, 667), (1390, 860)]

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    errors, requests, checked = [], [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(URL)
    page.wait_for_selector('#summary .card')
    snapshot = page.evaluate('DATA')
    if all(s['status']=='ok' for s in snapshot['sources'].values()):
        assert page.locator('#sourceStatus').is_hidden()
    typography=page.evaluate('''()=>({body:parseFloat(getComputedStyle(document.body).fontSize),heading:parseFloat(getComputedStyle(document.querySelector('.panel h2')).fontSize),kpi:parseFloat(getComputedStyle(document.querySelector('.card strong')).fontSize)})''')
    assert typography['body']>=13 and typography['heading']>=15 and typography['kpi']>=28,typography
    page.on('request', lambda request: requests.append(request.url))

    def fit_check(label):
        page.wait_for_timeout(70)
        actual = page.evaluate('''() => ({width: innerWidth, height: innerHeight,
            documentWidth: document.documentElement.scrollWidth,
            documentHeight: document.documentElement.scrollHeight,
            scrollContainers: Array.from(document.querySelectorAll('main *')).filter(n => {
                if (!n.getClientRects().length || /^(SELECT|OPTION)$/.test(n.tagName)) return false;
                const s=getComputedStyle(n);
                return (/auto|scroll/.test(s.overflowY) && n.scrollHeight>n.clientHeight+1) ||
                    (/auto|scroll/.test(s.overflowX) && n.scrollWidth>n.clientWidth+1);
            }).map(n => n.id || n.className)})''')
        assert actual['documentWidth'] <= actual['width'], (label, actual)
        assert actual['documentHeight'] <= actual['height'] + 1, (label, actual)
        assert not actual['scrollContainers'], (label, actual)
        checked.append(label)

    def all_pages(container, selector):
        """Each original item must remain reachable once, without clipping or loss."""
        fit_check('before pagination ' + container)
        locator = page.locator(container)
        total = locator.locator(selector).count()
        locator.locator(selector).evaluate_all('(nodes)=>nodes.forEach((n,i)=>n.dataset.testIndex=String(i))')
        seen = []
        for _ in range(total + 1):
            visible = locator.locator(selector).evaluate_all('(nodes)=>nodes.filter(n=>n.getClientRects().length).map(n=>Number(n.dataset.testIndex))')
            seen.extend(visible)
            fit_check('pagination ' + container)
            pager = locator.locator('xpath=preceding-sibling::*[contains(@class,"qa-pager")][1]')
            if not pager.count() or not pager.is_visible() or pager.locator('button').last.is_disabled():
                break
            pager.locator('button').last.click()
            page.wait_for_timeout(70)
        assert sorted(seen) == list(range(total)), (container, total, seen)

    assert page.locator('.global-tab').count() == 3
    for domain, scope in snapshot['domains'].items():
        page.locator(f'[data-domain="{domain}"]').click()
        assert page.locator('#summary strong').first.inner_text() == str(scope['summary']['total'])
        for view in ('overview', 'trend', 'version', 'recent', 'project'):
            page.select_option('#analysisSelect', view)
            fit_check(domain + ' ' + view)
        values = page.locator('#projectVersionSelect option').evaluate_all('(nodes)=>nodes.map(n=>n.value)')
        assert values
        page.select_option('#projectVersionSelect', values[-1])
        page.locator('#excludeCompletedProjectVersions').check()
        page.locator('#excludeCompletedProjectVersions').uncheck()
    page.select_option('#analysisSelect', 'trend')
    page.locator('[data-days="7"]').click()
    page.locator('[data-domain="ALL"]').click()
    assert page.locator('#dailyChart .day').count() == 7

    for width, height in PROFILES:
        page.set_viewport_size({'width': width, 'height': height})
        page.locator('[data-section="defects"]').click()
        for view in ('overview', 'trend', 'version', 'recent', 'project'):
            page.select_option('#analysisSelect', view)
            fit_check(f'{width}x{height} defects/{view}')
            if view in ('overview', 'version') and width < 900:
                nav = page.locator(f'#{view} > .qa-panel-nav button')
                for index in range(nav.count()):
                    nav.nth(index).click()
                    fit_check(f'{width}x{height} {view}/panel{index}')
            if view == 'overview' and width < 900 and height < 750:
                for detail in ('heatmap','reports'):
                    page.select_option('#overviewDetailSelect',detail)
                    fit_check(f'{width}x{height} overview/{detail}')
            if view == 'version':
                if width < 900:
                    page.locator('#version > .qa-panel-nav button').first.click()
                page.locator('[data-version-mode="ALL"]').click()
                fit_check(f'{width}x{height} all versions')
                if width < 900:
                    page.locator('#version > .qa-panel-nav button').last.click()
                for distribution in ('0', '1', '2'):
                    page.select_option('#distributionSelect', distribution)
                    fit_check(f'{width}x{height} distribution/{distribution}')
            if view == 'project':
                for detail in ('status', 'severity', 'daily', 'type'):
                    page.select_option('#projectDetailSelect', detail)
                    fit_check(f'{width}x{height} project/{detail}')
        page.locator('[data-section="tasks"]').click()
        page.select_option('#taskView', 'list')
        if width < 900:
            page.locator('.qa-work-columns').locator('xpath=preceding-sibling::*[1]').locator('button').first.click()
        for state in ('진행중', '단계 완료', '완료', '중지', '지연/주의', '전체', '분류 미확인'):
            page.select_option('#taskState', state)
            fit_check(f'{width}x{height} tasks/{state}')
        if width < 900:
            page.locator('.qa-work-columns').locator('xpath=preceding-sibling::*[1]').locator('button').last.click()
            fit_check(f'{width}x{height} upcoming')
        page.select_option('#taskView', 'timeline')
        fit_check(f'{width}x{height} timeline')
        page.locator('[data-section="quality"]').click()
        for detail in ('summary', 'high', 'aging', 'documents'):
            page.select_option('#qualityView', detail)
            fit_check(f'{width}x{height} quality/{detail}')
        if width == 1440:
            page.locator('[data-section="tasks"]').click()
            page.select_option('#taskView', 'list')
            page.select_option('#taskState', '진행중')
            page.screenshot(path=str(OUT / 'tasks.png'))
            page.locator('[data-section="defects"]').click()
            page.select_option('#analysisSelect', 'overview')
            page.screenshot(path=str(OUT / 'defects.png'))

    # Traverse complete long lists on a short screen; no rows may be discarded.
    page.set_viewport_size({'width': 1280, 'height': 600})
    page.locator('[data-section="quality"]').click()
    for detail in ('high', 'aging'):
        page.select_option('#qualityView', detail)
        all_pages('#qaQualityPanel table', 'tbody > tr')
    page.select_option('#qualityView', 'documents')
    all_pages('#qualityDocuments', 'li')
    page.locator('[data-section="tasks"]').click()
    page.select_option('#taskView', 'list')
    page.select_option('#taskState', '완료')
    all_pages('#taskCurrentList', '.qa-task-card')
    page.locator('[data-section="defects"]').click()
    page.select_option('#analysisSelect', 'recent')
    all_pages('#recentList table', 'tbody > tr')
    assert page.locator('#recentList a').evaluate_all('(a)=>a.map(n=>n.href)') == [r['url'] for r in snapshot['domains']['ALL']['recent']]
    page.select_option('#analysisSelect', 'version')
    page.locator('[data-version-mode="ALL"]').click()
    all_pages('#versions', '.version-item')
    assert not requests, requests
    assert not errors, errors
    switch_requests = list(requests)

    # Test inside an actual iframe, using the approximate Notion embed bounds supplied by the user.
    embed_page=browser.new_page(viewport={'width':1540,'height':1020})
    embed_page.set_content('<iframe title="QA Dashboard" src="'+URL+'" style="border:0;width:1390px;height:860px"></iframe>')
    frame=embed_page.frames[-1]
    frame.wait_for_selector('#summary .card')
    for name in ('defects','tasks','quality'):
        frame.locator('[data-section="'+name+'"]').click()
        frame.wait_for_timeout(100)
        size=frame.evaluate('''()=>({w:innerWidth,h:innerHeight,sw:document.documentElement.scrollWidth,sh:document.documentElement.scrollHeight})''')
        assert size['sw']<=size['w'] and size['sh']<=size['h']+1,(name,size)
    embed_page.close()

    # Failed QA source must not remove the healthy defect and task screens.
    html = (ROOT / 'defect_dashboard_embed.html').read_text()
    match = re.search(r'(<script id="dashboard-data" type="application/json">)(.*?)(</script>)', html, re.S)
    failed = json.loads(match[2])
    failed['qaQuality'] = {'status': 'error', 'data': None, 'syncedAt': None}
    failed['sources']['quality'] = {'status': 'error', 'syncedAt': None}
    failed_html = html[:match.start(2)] + json.dumps(failed, ensure_ascii=False).replace('<', r'\u003c') + html[match.end(2):]
    failure_url = URL.rsplit('/', 1)[0] + '/failed-source.html'
    page.route('**/failed-source.html', lambda route: route.fulfill(status=200, content_type='text/html', body=failed_html))
    page.goto(failure_url)
    assert page.locator('#sourceStatus .source-badge.error').is_visible()
    assert page.locator('#sourceStatus .source-badge').count()==1
    assert page.locator('#summary strong').first.inner_text() == str(failed['domains']['ALL']['summary']['total'])
    page.locator('[data-section="tasks"]').click()
    assert page.locator('#taskUpcomingList .qa-task-card').count() == sum(t['state'] == '예정' for t in failed['qaTasks']['data']['rows'])
    page.locator('[data-section="quality"]').click()
    page.select_option('#qualityView', 'documents')
    assert '데이터를 조회하지 못했습니다' in page.locator('#qaQualityPanel').inner_text()
    fit_check('failed source')
    assert not errors, errors
    result = {'browser': 'Chromium', 'consoleErrors': errors, 'tabSwitchRequests': switch_requests,
              'sourceFailureIsolation': 'PASS', 'scrollFreeScreensChecked': len(checked),
              'paginationCompleteness': 'PASS', 'notionSizedIframe': [1390,860], 'typography': typography, 'viewports': PROFILES, 'result': 'PASS'}
    (OUT / 'browser_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))
    browser.close()
