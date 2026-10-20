// All screens use the generated snapshot. No Notion requests are made here.
(() => {
  const main = document.querySelector('main');
  const tasksPanel = document.createElement('section');
  tasksPanel.id = 'qaTasksPanel'; tasksPanel.hidden = true; tasksPanel.className = 'qa-stack';
  const qualityPanel = document.createElement('section');
  qualityPanel.id = 'qaQualityPanel'; qualityPanel.hidden = true; qualityPanel.className = 'qa-stack';
  main.append(tasksPanel, qualityPanel);
  let section = 'defects', taskFilter = '진행중', taskRange = 'ALL', taskView = 'list', qualityDomain = 'ALL', qualityView = 'summary';
  const today = new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Seoul'}).format(new Date());
  const dateNum = s => Date.parse(s + 'T00:00:00Z') / 86400000;
  const offset = (s, n) => new Date((dateNum(s) + n) * 86400000).toISOString().slice(0,10);
  const safeUrl = value => {
    try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) ? esc(u.href) : '#'; }
    catch { return '#'; }
  };
  const link = (title, url) => `<a href="${safeUrl(url)}" title="${esc(title)}" target="_blank" rel="noopener noreferrer">${esc(title)}</a>`;
  const card = (label,value,note='') => `<article class="card"><span>${esc(label)}</span><strong>${esc(value)}</strong><em>${esc(note)}</em></article>`;
  const sourceNotice = source => {
    if (!source || source.status === 'error') return '<div class="empty">데이터를 조회하지 못했습니다. Notion 접근 권한과 동기화 상태를 확인해 주세요.</div>';
    if (source.status === 'stale') return `<p class="qa-warning">동기화 실패 · 마지막 성공 데이터 표시 (${esc(formatKstDateTime(source.syncedAt))})</p>`;
    return '';
  };
  const labels = {defects:'결함 데이터',tasks:'QA 업무',quality:'QA 품질', 'report-한패스':'Hanpass 제보', 'report-GoHanpass':'Gohanpass 제보'};
  $('sourceStatus').innerHTML = Object.entries(DATA.sources || {}).map(([key,s]) => `<span class="source-badge ${esc(s.status)}" title="마지막 성공: ${esc(s.syncedAt ? formatKstDateTime(s.syncedAt) : '없음')} · 최근 시도: ${esc(s.attemptedAt ? formatKstDateTime(s.attemptedAt) : '-')} ">${esc(labels[key] || key)} · ${s.status === 'ok' ? '정상' : s.status === 'stale' ? '갱신 실패 · 이전 데이터' : '조회 실패'}</span>`).join('');

  const mappingNote = document.createElement('span');
  mappingNote.className = 'qa-help';
  mappingNote.textContent = '분류 기준 ⓘ';
  mappingNote.title = '서비스는 기존 목표버전·제목 기반 분류를 유지합니다. 버전 누락·불명확 항목은 기존처럼 Hanpass에 포함될 수 있습니다.';
  $('defectControls').append(mappingNote);

  function showSection() {
    const defects = section === 'defects';
    $('defectControls').hidden = !defects;
    $('summary').hidden = !defects || $('analysisSelect').value === 'project' || DATA.sources?.defects?.status === 'error';
    document.querySelectorAll('main > .view').forEach(v => {
      v.classList.toggle('active', defects && v.id === $('analysisSelect').value);
    });
    tasksPanel.hidden = section !== 'tasks'; qualityPanel.hidden = section !== 'quality';
    document.querySelectorAll('.global-tab').forEach(b => {
      b.classList.toggle('active', b.dataset.section === section);
      b.setAttribute('aria-selected', String(b.dataset.section === section));
    });
    if (defects && $('analysisSelect').value === 'project') renderProjectProgress();
    if (section === 'tasks') renderTasks();
    if (section === 'quality') renderQuality();
    scheduleFit();
  }
  document.querySelectorAll('.global-tab').forEach(b => b.addEventListener('click', () => { section = b.dataset.section; showSection(); }));
  $('analysisSelect').addEventListener('change', showSection);
  // Arrow keys move through the persistent global navigation.
  document.querySelector('.global-tabs').setAttribute('role', 'tablist');
  document.querySelectorAll('.global-tab').forEach((b,i,all) => {
    b.setAttribute('role','tab');
    b.addEventListener('keydown', e => {
      if (!['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) return;
      e.preventDefault();
      const j = e.key === 'Home' ? 0 : e.key === 'End' ? all.length-1 : (i + (e.key === 'ArrowRight' ? 1 : -1) + all.length) % all.length;
      all[j].focus(); all[j].click();
    });
  });

  const tasks = () => (DATA.qaTasks?.data?.rows || []).map(t => ({...t,
    overdue: Boolean(t.end && t.end < today && ['진행중','예정','단계 완료'].includes(t.state))}));
  function renderTimeline(rows) {
    const eligible = rows.filter(t => ['진행중','예정','단계 완료'].includes(t.state) && t.start);
    if (!eligible.length) return '<p class="qa-note">날짜가 있는 진행·예정 업무가 없어 타임라인을 표시하지 않습니다.</p>';
    const start = offset(today,-14), end = offset(today,30), span = dateNum(end)-dateNum(start)+1;
    const pos = s => Math.max(0,Math.min(100,(dateNum(s)-dateNum(start))/span*100));
    const visible = eligible.filter(t => (t.end || t.start)>=start && t.start<=end);
    return `<div class="table-wrap"><div class="qa-timeline"><div class="qa-timeline-head"><strong>진행·예정 업무</strong><div class="qa-timeline-axis"><span>${start}</span><span style="position:absolute;left:${pos(today)}%;transform:translateX(-50%)">오늘 ${today}</span><span>${end}</span></div></div>${visible.map(t => {
      const left = pos(t.start), right = pos(offset(t.end || t.start,1));
      return `<div class="qa-timeline-row"><span>${link(t.title,t.url)}</span><div class="qa-timeline-track"><span class="qa-timeline-today" style="left:${pos(today)}%"></span><a class="qa-timeline-bar ${t.overdue ? 'late' : ''}" href="${safeUrl(t.url)}" target="_blank" rel="noopener noreferrer" style="left:${left}%;width:${Math.max(.6,right-left)}%" aria-label="${esc(t.title)} · ${esc(t.start)} ~ ${esc(t.end || '종료일 미정')}" title="${esc(t.start)} ~ ${esc(t.end || '종료일 미정')}"></a></div></div>`;
    }).join('')}</div></div><p class="qa-note">오늘 기준 −14일 ~ +30일 · 종료일이 없으면 시작일만 표시합니다. 기간 밖 ${eligible.length-visible.length}건, 날짜 미정 ${rows.filter(t => !t.start && ['진행중','예정','단계 완료'].includes(t.state)).length}건은 목록에서 확인하세요.</p>`;
  }
  function taskCards(rows, id) {
    return `<div id="${id}" class="qa-task-list">${rows.length ? rows.map(t => {
      const owners = t.owners.length ? t.owners.join(', ') : '담당자 미지정';
      const dates = `${t.start || '일정 미정'}${t.end ? ' ~ '+t.end : ''}`;
      return `<article class="qa-task-card">
        <div class="qa-task-title">${link(t.title,t.url)}<span class="qa-task-state ${t.overdue ? 'qa-warning' : ''}" title="${esc(t.status)}">${t.overdue ? '일정 초과' : esc(t.state)}</span></div>
        <div class="qa-task-meta"><span title="${esc(owners)} · ${esc(t.ownerSource)}">${esc(owners)}</span><span>${esc(dates)}</span></div>
        <div class="qa-task-meta"><span>${esc(t.tcState)} · TC ${t.tcCount === null ? '미입력' : esc(t.tcCount)+'건'}</span><span>${t.start && t.state==='예정' ? `D${dateNum(t.start)>dateNum(today)?'-':'+'}${Math.abs(dateNum(t.start)-dateNum(today))}` : ''}${t.predecessors.length ? ' · 선행 '+t.predecessors.map((id,i)=>link(String(i+1),'https://www.notion.so/'+id.replaceAll('-',''))).join(', ') : ''}</span></div>
        ${t.warnings.length ? `<small class="qa-warning">${esc(t.warnings.join(' · '))}</small>` : ''}
      </article>`;
    }).join('') : '<div class="empty">해당 업무가 없습니다.</div>'}</div>`;
  }
  function renderTasks() {
    const source = DATA.qaTasks, all = tasks();
    const matches = (t,c) => c==='전체' ? t.state!=='예정' : c==='지연/주의' ? t.overdue && t.state!=='예정' : t.state===c;
    let rows = all;
    if (taskRange !== 'ALL') {
      const end = offset(today,Number(taskRange)-1);
      rows = rows.filter(t => t.start && t.start <= end && (t.end || t.start) >= today);
    }
    const selected = rows.filter(t=>matches(t,taskFilter));
    const upcoming = rows.filter(t=>t.state==='예정');
    tasksPanel.innerHTML = `${sourceNotice(source)}<article class="panel qa-task-toolbar">
      <div class="qa-section-head"><h2>QA 업무 진행 현황</h2><div class="qa-inline-controls">
        <label>화면 <select id="taskView"><option value="list">업무 목록</option><option value="timeline">Timeline</option></select></label>
        <label>일정 <select id="taskRange"><option value="ALL">전체</option><option value="7">7일</option><option value="14">14일</option><option value="30">30일</option></select></label>
        <span class="qa-help" title="원본 상태 기준입니다. 단계 완료는 최종 완료가 아닙니다. 일정 초과는 실제 종료일이 지난 진행·예정·단계 완료 업무에 중복 표시합니다. TC 개수는 수행률이 아닙니다.">집계 기준 ⓘ</span>
      </div></div>
      <div class="qa-stat-grid">${['진행중','예정','완료','지연/주의'].map(c=>card(c,source?.data ? all.filter(t=>c==='지연/주의'?t.overdue:t.state===c).length : '—')).join('')}</div>
      ${source?.data?.ownerLookupFailures ? `<span class="qa-warning">연결 업무 ${source.data.ownerLookupFailures}건 담당자 조회 실패</span>` : ''}
      </article>
      ${taskView==='timeline' ? `<article class="panel"><h2>QA 업무 Timeline</h2>${renderTimeline(rows)}</article>` : `<div class="qa-work-columns compact-focus-group">
        <article class="panel"><div class="qa-section-head"><h2>${taskFilter==='진행중'?'현재 진행 업무':'업무 현황'} · ${selected.length}</h2><label class="qa-inline-controls">상태 <select id="taskState">${['진행중','단계 완료','완료','중지','지연/주의','전체','분류 미확인'].map(c=>`<option value="${esc(c)}">${esc(c==='전체'?'전체 (예정 제외)':c)}</option>`).join('')}</select></label></div>${taskCards(selected,'taskCurrentList')}</article>
        <article class="panel"><h2>예정 업무 · ${upcoming.length}</h2>${taskCards(upcoming,'taskUpcomingList')}</article>
      </div>`}`;
    $('taskRange').value=taskRange; $('taskView').value=taskView;
    $('taskRange').addEventListener('change',e=>{taskRange=e.target.value;resetPages();renderTasks();});
    $('taskView').addEventListener('change',e=>{taskView=e.target.value;resetPages();renderTasks();});
    if ($('taskState')) {
      $('taskState').value=taskFilter;
      $('taskState').addEventListener('change',e=>{taskFilter=e.target.value;resetPages();renderTasks();});
    }
    scheduleFit();
  }
  function defectTable(rows) {
    if (!rows.length) return '<div class="empty">해당 결함이 없습니다.</div>';
    return `<div class="table-wrap"><table class="qa-table"><thead><tr><th>결함</th><th>상태</th><th>심각도</th><th>Target Version</th><th>등록 후 경과</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${link(r.title,r.url)}</td><td>${esc(r.status)}</td><td>${esc(r.severity)}</td><td>${esc(r.version)}</td><td>${r.ageDays ?? '—'}일</td></tr>`).join('')}</tbody></table></div>`;
  }
  function renderQuality() {
    const q = DATA.domains[qualityDomain].quality;
    const all = tasks(), taskAvailable = Boolean(DATA.qaTasks?.data), defectAvailable = DATA.sources?.defects?.status !== 'error';
    const docs = DATA.qaQuality?.data?.documents || [];
    let content = '';
    if (qualityView==='summary') content = `<article class="panel"><h2>QA QUALITY SUMMARY</h2>
      <div class="qa-stat-grid">${card('진행 QA',taskAvailable ? all.filter(t=>t.state==='진행중').length : '—')}${card('예정 QA',taskAvailable ? all.filter(t=>t.state==='예정').length : '—')}${card('미해결 Critical',defectAvailable?q.unresolvedCritical:'—')}${card('미해결 Major',defectAvailable?q.unresolvedMajor:'—')}${card('지연 업무',taskAvailable?all.filter(t=>t.overdue).length:'—')}${card('개발 완료 · 미검증',defectAvailable?q.awaitingVerification:'—')}</div>
      <p class="qa-note">Release Risk · ${esc(q.risk.reason)}</p>${sourceNotice(DATA.qaTasks)}${sourceNotice(DATA.sources?.defects)}
      <p class="qa-note">업무 일정·TC 준비 상태는 <button class="qa-text-button" id="goToTasks">QA 업무 진행 현황</button>에서 확인하세요.</p></article>`;
    if (qualityView==='high') content=`<article class="panel"><h2>미해결 Critical / Major · ${defectAvailable?q.highCount:'—'}건</h2>${defectAvailable?defectTable(q.high):sourceNotice(DATA.sources?.defects)}${q.highCount>50?'<p class="qa-note">Critical 우선 · 오래된 등록 순 상위 50건</p>':''}</article>`;
    if (qualityView==='aging') content=`<article class="panel"><h2>장기 미처리 · ${defectAvailable?q.agingCount:'—'}건</h2>${defectAvailable?defectTable(q.aging):sourceNotice(DATA.sources?.defects)}${q.agingCount>50?'<p class="qa-note">등록 후 30일 이상 · 오래된 등록 순 상위 50건</p>':''}</article>`;
    if (qualityView==='documents') content=`<article class="panel"><h2>QA 주요 문서 / 링크 · ${docs.length}</h2>${sourceNotice(DATA.qaQuality)}<ul id="qualityDocuments" class="qa-documents">${docs.map(d=>`<li>${link(d.title,d.url)}</li>`).join('')}</ul>${!docs.length?'<div class="empty">조회된 주요 문서가 없습니다.</div>':''}${DATA.qaQuality?.data?.partialFailures?`<p class="qa-warning">하위 컨테이너 ${DATA.qaQuality.data.partialFailures}건 조회 실패</p>`:''}</article>`;
    qualityPanel.innerHTML=`<article class="panel qa-controls"><label>분석 화면 <select id="qualityView"><option value="summary">품질 요약</option><option value="high">미해결 Critical / Major</option><option value="aging">장기 미처리 결함</option><option value="documents">주요 문서 / 링크</option></select></label>
      <label>결함 서비스 <select id="qualityDomain"><option value="ALL">전체</option><option value="한패스">Hanpass</option><option value="GoHanpass">Gohanpass</option></select></label>
      <span class="qa-help" title="미해결: 기존 프로젝트 상세의 최종 완료·백로그 이관 제외. 개발 완료는 미검증에 포함. 장기 미처리는 등록 후 30일 이상. 서비스 필터는 결함 지표에만 적용하며 QA 업무는 전체 기준입니다.">집계 기준 ⓘ</span></article>${content}`;
    $('qualityDomain').value=qualityDomain; $('qualityView').value=qualityView;
    $('qualityDomain').addEventListener('change',e=>{qualityDomain=e.target.value;resetPages();renderQuality();});
    $('qualityView').addEventListener('change',e=>{qualityView=e.target.value;resetPages();renderQuality();});
    $('goToTasks')?.addEventListener('click',()=>{section='tasks';showSection();});
    scheduleFit();
  }
  const pageState = new Map();
  let fitFrame = 0;
  function resetPages() { pageState.clear(); }
  function scheduleFit() {
    cancelAnimationFrame(fitFrame);
    fitFrame = requestAnimationFrame(fitViewport);
  }
  function paginateItems(container, items, key, columns=1) {
    if (!container || !items.length || !container.getClientRects().length) return;
    items.forEach(item=>{item.hidden=false;if(!item.title&&item.tagName!=='TR')item.title=item.textContent.trim();});
    let pager = container.parentElement.querySelector(`[data-pager="${key}"]`);
    if (!pager) {
      pager=document.createElement('div'); pager.className='qa-pager'; pager.dataset.pager=key;
      container.before(pager);
    }
    pager.hidden=false;
    pager.innerHTML='<span>페이지</span><button type="button" aria-label="이전 페이지">‹</button><span class="qa-page-label"></span><button type="button" aria-label="다음 페이지">›</button>';
    const rowHeight=Math.max(...items.map(item=>item.getBoundingClientRect().height));
    const style=getComputedStyle(container);
    const gap=parseFloat(style.rowGap)||0;
    const panel=container.closest('.panel');
    const after=panel ? Array.from(panel.children).filter(n=>n.compareDocumentPosition(container)&Node.DOCUMENT_POSITION_PRECEDING).reduce((sum,n)=>sum+(n===container||n.contains(container)?0:n.getBoundingClientRect().height+6),0) : 0;
    const headHeight=container.tagName==='TABLE' ? container.querySelector('thead')?.getBoundingClientRect().height||0 : container.querySelector('.qa-timeline-head')?.getBoundingClientRect().height||0;
    const available=innerHeight-container.getBoundingClientRect().top-22-after-headHeight;
    const take=Math.max(columns,Math.floor((available+gap)/(rowHeight+gap))*columns);
    const pages=Math.max(1,Math.ceil(items.length/take));
    const current=Math.min(pageState.get(key)||0,pages-1); pageState.set(key,current);
    items.forEach((item,i)=>{item.hidden=i<current*take||i>=(current+1)*take;});
    pager.querySelector('.qa-page-label').textContent=`${current+1} / ${pages} · ${items.length}개`;
    const buttons=pager.querySelectorAll('button');buttons[0].disabled=current===0;buttons[1].disabled=current===pages-1;
    buttons[0].onclick=()=>{pageState.set(key,current-1);scheduleFit();};
    buttons[1].onclick=()=>{pageState.set(key,current+1);scheduleFit();};
    if (pages===1) pager.hidden=true;
  }
  function focusPanels(group, key) {
    const panels=Array.from(group.children).filter(n=>n.classList.contains('panel')||n.classList.contains('dist-list'));
    if (!panels.length) return;
    let nav=group.previousElementSibling;
    if (!nav?.classList.contains('qa-panel-nav')) {
      nav=document.createElement('div');nav.className='qa-panel-nav';group.before(nav);
    }
    const narrow=innerWidth<900;
    const current=Math.min(pageState.get(key)||0,panels.length-1);
    nav.hidden=!narrow;
    nav.innerHTML=panels.map((n,i)=>`<button type="button" class="qa-chip ${i===current?'active':''}">${esc(n.querySelector('h2')?.textContent||String(i+1))}</button>`).join('');
    panels.forEach((n,i)=>{n.hidden=narrow&&i!==current;});
    nav.querySelectorAll('button').forEach((b,i)=>b.onclick=()=>{pageState.set(key,i);scheduleFit();});
  }
  function fitViewport() {
    observer.disconnect();
    if (section==='defects') {
      const view=$('analysisSelect').value;
      if (view==='overview'||view==='version') focusPanels($(view).querySelector('.grid'),'panels-'+view);
      if (view==='version') {
        const dist=$('distributions');
        const boxes=Array.from(dist.children);
        let selector=$('distributionSelect');
        if (!selector) {
          selector=document.createElement('select');selector.id='distributionSelect';selector.setAttribute('aria-label','분포 항목');
          selector.innerHTML='<option value="0">상태</option><option value="1">심각도</option><option value="2">우선순위</option>';
          dist.before(selector);selector.onchange=scheduleFit;
        }
        boxes.forEach((b,i)=>{b.hidden=i!==Number(selector.value);});
      }
      if(view==='project') {
        let selector=$('projectDetailSelect');
        if(!selector) {
          selector=document.createElement('select');selector.id='projectDetailSelect';selector.setAttribute('aria-label','프로젝트 상세 분석');
          selector.innerHTML='<option value="status">처리 현황</option><option value="severity">결함 유형별 심각도</option><option value="daily">일자별 누적 그래프</option><option value="type">결함 유형별 분포</option>';
          $('projectSummary').after(selector);selector.onchange=scheduleFit;
        }
        const mode=selector.value; $('projectSummary').hidden=['daily','type'].includes(mode);
        const tablePanel=$('projectProgressTable').closest('.panel'), chartPanel=$('projectCharts').closest('.panel');
        tablePanel.hidden=!['status','severity'].includes(mode);chartPanel.hidden=!['daily','type'].includes(mode);
        $('projectProgressTable').querySelectorAll('.project-detail-section').forEach((n,i)=>n.hidden=i!==(mode==='severity'?1:0));
        $('projectCharts').hidden=mode!=='daily';$('projectTypeChart').hidden=mode!=='type';
        chartPanel.querySelector('.legend').hidden=mode!=='daily';
        chartPanel.querySelector('.panel-head').hidden=mode!=='daily';
      }
    }
    document.querySelectorAll('main .line-chart, main .chart, main .project-pie').forEach(chart=>{
      if(!chart.getClientRects().length)return;
      chart.style.height='';
      const panel=chart.closest('.panel');
      const excess=Math.max(0,panel.getBoundingClientRect().bottom-innerHeight+12);
      if(excess)chart.style.height=Math.max(60,chart.getBoundingClientRect().height-excess)+'px';
    });
    if(section==='tasks'&&taskView==='list') focusPanels(tasksPanel.querySelector('.qa-work-columns'),'task-columns');
    const lists=[['versions','.version-item'],['reportList','.report-item'],['taskCurrentList','.qa-task-card'],['taskUpcomingList','.qa-task-card'],['qualityDocuments','li']];
    for(const [id,sel] of lists) {
      const node=$(id);
      if(node?.getClientRects().length) {
        const columns=id==='qualityDocuments'?getComputedStyle(node).gridTemplateColumns.split(' ').length:1;
        paginateItems(node,Array.from(node.querySelectorAll(sel)),id,columns);
      }
    }
    document.querySelectorAll('main table').forEach((table,i)=>{
      if(!table.getClientRects().length)return;
      table.querySelectorAll('td,th').forEach(cell=>{if(!cell.title)cell.title=cell.textContent.trim();});
      paginateItems(table,Array.from(table.querySelectorAll('tbody > tr')),table.closest('[id]')?.id+'-table-'+i);
    });
    document.querySelectorAll('.project-pie-legend').forEach(node=>paginateItems(node,Array.from(node.children),'project-pie-legend'));
    document.querySelectorAll('.qa-timeline').forEach(node=>paginateItems(node,Array.from(node.querySelectorAll('.qa-timeline-row')),'timeline'));
    observe();
  }
  const observer=new MutationObserver(scheduleFit);
  function observe() {observer.observe(main,{childList:true,subtree:true});}
  observe();
  addEventListener('resize',scheduleFit);
  document.addEventListener('click',e=>{if(e.target.closest('[data-domain],[data-version-mode]')){resetPages();scheduleFit();}});
  if (DATA.sources?.defects?.status === 'error') {
    $('defectControls').insertAdjacentHTML('afterend', '<p class="qa-warning">결함 데이터를 조회하지 못했습니다. 아래 빈 차트의 0건은 실제 결함 건수가 아닙니다.</p>');
  }
  showSection();
})();
