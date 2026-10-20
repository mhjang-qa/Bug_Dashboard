from playwright.sync_api import sync_playwright
from pathlib import Path
import json
import os
import re
root=Path(__file__).resolve().parents[1]
out=root/'validation';out.mkdir(exist_ok=True)
url=os.getenv('QA_DASHBOARD_URL','http://127.0.0.1:8765/defect_dashboard_embed.html')
with sync_playwright() as p:
 browser=p.chromium.launch()
 page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(url);page.wait_for_selector('#summary .card')
 expected=page.evaluate('Object.fromEntries(Object.entries(DATA.domains).map(([k,v])=>[k,String(v.summary.total)]))')
 assert page.locator('.global-tab').count()==3
 assert page.locator('.tab').count()==0
 assert page.locator('#summary strong').first.inner_text()==expected['ALL']
 for domain,count in expected.items():
  page.locator(f'[data-domain="{domain}"]').click();assert page.locator('#summary strong').first.inner_text()==count
  for view,target in [('overview','#funnel'),('trend','#dailyChart'),('version','#versions'),('recent','#recentList'),('project','#projectProgressTable')]:
   page.select_option('#analysisSelect',view);assert page.locator('#'+view).is_visible();assert len(page.locator(target).inner_text())>0
  options=page.locator('#projectVersionSelect option').all_text_contents()
  assert options
  values=page.locator('#projectVersionSelect option').evaluate_all('(nodes)=>nodes.map(n=>n.value)')
  page.select_option('#projectVersionSelect',values[-1]);assert page.locator('#projectVersionSelect').input_value()==values[-1]
  page.locator('#excludeCompletedProjectVersions').check();page.locator('#excludeCompletedProjectVersions').uncheck()
 page.select_option('#analysisSelect','trend');page.locator('[data-days="7"]').click();page.locator('[data-domain="한패스"]').click()
 assert page.locator('#dailyChart .day').count()==7
 page.locator('[data-domain="ALL"]').click();page.select_option('#analysisSelect','overview')
 page.screenshot(path=str(out/'defects.png'),full_page=True)
 page.select_option('#analysisSelect','recent')
 assert page.locator('#recentList a').count()>0
 assert page.locator('#recentList a').evaluate_all('(a)=>a.map(n=>n.href)') == page.evaluate('DATA.domains.ALL.recent.map(r=>r.url)')
 # Count network requests after initial page load to detect navigation-induced API calls.
 requests=[];page.on('request',lambda r:requests.append(r.url))
 page.locator('[data-section="tasks"]').click();assert page.locator('#qaTasksPanel').is_visible();assert page.locator('#summary').is_hidden()
 for state in ['진행중','예정','완료','지연/주의','단계 완료','중지','전체']:
  page.locator(f'[data-task-filter="{state}"]').click()
 assert page.locator('.qa-timeline-bar').count()>0
 page.screenshot(path=str(out/'tasks.png'),full_page=True)
 page.select_option('#taskRange','7');page.select_option('#taskRange','ALL')
 page.locator('[data-section="quality"]').click();assert page.locator('#qaQualityPanel').is_visible()
 for domain in ['한패스','GoHanpass','ALL']:
  page.select_option('#qualityDomain',domain)
 page.screenshot(path=str(out/'quality.png'),full_page=True)
 page.set_viewport_size({'width':768,'height':1024});page.screenshot(path=str(out/'tablet.png'),full_page=True)
 assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Tablet horizontal overflow'
 page.set_viewport_size({'width':390,'height':844})
 for section in ['tasks','defects','quality']:
  page.locator(f'[data-section="{section}"]').click()
  assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), section+' mobile horizontal overflow'
 page.screenshot(path=str(out/'mobile.png'),full_page=True)
 assert not requests,requests
 switch_requests=list(requests)
 assert not errors,errors
 # Simulate a failed QA quality source using the real generated snapshot.
 html=(root/'defect_dashboard_embed.html').read_text()
 match=re.search(r'(<script id="dashboard-data" type="application/json">)(.*?)(</script>)',html,re.S)
 snapshot=json.loads(match[2]);snapshot['qaQuality']={'status':'error','data':None,'syncedAt':None};snapshot['sources']['quality']={'status':'error','syncedAt':None}
 failed_html=html[:match.start(2)]+json.dumps(snapshot,ensure_ascii=False).replace('<',r'\u003c')+html[match.end(2):]
 failure_url=url.rsplit('/',1)[0]+'/failed-source.html'
 page.route('**/failed-source.html',lambda route:route.fulfill(status=200,content_type='text/html',body=failed_html))
 page.goto(failure_url)
 assert page.locator('#summary strong').first.inner_text()==expected['ALL']
 page.locator('[data-section="tasks"]').click();assert page.locator('#qaTasksPanel tbody tr').count()==len(snapshot['qaTasks']['data']['rows'])
 page.locator('[data-section="quality"]').click();assert page.locator('#qaQualityPanel').is_visible();assert '데이터를 조회하지 못했습니다' in page.locator('#qaQualityPanel').inner_text()
 assert not errors,errors
 result={'browser':'Chromium','consoleErrors':errors,'tabSwitchRequests':switch_requests,'sourceFailureIsolation':'PASS','viewports':[1440,768,390],'result':'PASS'}
 (out/'browser_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps(result,ensure_ascii=False))
 browser.close()
