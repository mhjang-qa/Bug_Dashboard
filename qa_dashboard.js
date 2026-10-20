// All screens use the generated snapshot. No Notion requests are made here.
(() => {
  const main = document.querySelector('main');
  const tasksPanel = document.createElement('section');
  tasksPanel.id = 'qaTasksPanel'; tasksPanel.hidden = true; tasksPanel.className = 'qa-stack';
  const qualityPanel = document.createElement('section');
  qualityPanel.id = 'qaQualityPanel'; qualityPanel.hidden = true; qualityPanel.className = 'qa-stack';
  main.append(tasksPanel, qualityPanel);
  let section = 'defects', taskFilter = '전체', taskRange = 'ALL', qualityDomain = 'ALL';
  const today = new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Seoul'}).format(new Date());
  const dateNum = s => Date.parse(s + 'T00:00:00Z') / 86400000;
  const offset = (s, n) => new Date((dateNum(s) + n) * 86400000).toISOString().slice(0,10);
  const safeUrl = value => {
    try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) ? esc(u.href) : '#'; }
    catch { return '#'; }
  };
  const link = (title, url) => `<a href="${safeUrl(url)}" target="_blank" rel="noopener noreferrer">${esc(title)}</a>`;
  const card = (label,value,note='') => `<article class="card"><span>${esc(label)}</span><strong>${esc(value)}</strong><em>${esc(note)}</em></article>`;
  const sourceNotice = source => {
    if (!source || source.status === 'error') return '<div class="empty">데이터를 조회하지 못했습니다. Notion 접근 권한과 동기화 상태를 확인해 주세요.</div>';
    if (source.status === 'stale') return `<p class="qa-warning">동기화 실패 · 마지막 성공 데이터 표시 (${esc(formatKstDateTime(source.syncedAt))})</p>`;
    return '';
  };
  const labels = {defects:'결함 데이터',tasks:'QA 업무',quality:'QA 품질', 'report-한패스':'Hanpass 제보', 'report-GoHanpass':'Gohanpass 제보'};
  $('sourceStatus').innerHTML = Object.entries(DATA.sources || {}).map(([key,s]) => `<span class="source-badge ${esc(s.status)}" title="마지막 성공: ${esc(s.syncedAt ? formatKstDateTime(s.syncedAt) : '없음')} · 최근 시도: ${esc(s.attemptedAt ? formatKstDateTime(s.attemptedAt) : '-')} ">${esc(labels[key] || key)} · ${s.status === 'ok' ? '정상' : s.status === 'stale' ? '갱신 실패 · 이전 데이터' : '조회 실패'}</span>`).join('');

  const mappingNote = document.createElement('p');
  mappingNote.className = 'qa-note'; mappingNote.style.flexBasis = '100%';
  mappingNote.textContent = '서비스는 기존 목표버전·제목 기반 분류를 유지합니다. 서비스 속성이 없어 버전 누락·불명확 항목은 기존처럼 Hanpass에 포함될 수 있습니다.';
  $('defectControls').append(mappingNote);

  function showSection() {
    const defects = section === 'defects';
    $('defectControls').hidden = !defects;
    $('summary').hidden = !defects || DATA.sources?.defects?.status === 'error';
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
  function taskTable(rows) {
    if (!rows.length) return '<div class="empty">해당 업무가 없습니다.</div>';
    return `<div class="table-wrap"><table class="qa-table qa-task-table"><thead><tr><th>업무명</th><th>담당자</th><th>진행 상태</th><th>시작일</th><th>목표 완료일</th><th>TC 준비 / 개수</th><th>D-Day</th></tr></thead><tbody>${rows.map(t => `<tr>
      <td>${link(t.title,t.url)}${t.warnings.map(w => `<small class="qa-warning">${esc(w)}</small>`).join('')}${t.predecessors.length ? `<small>선행 작업 ${t.predecessors.map((id,i) => link(String(i+1),'https://www.notion.so/'+id.replaceAll('-',''))).join(', ')}</small>` : ''}</td>
      <td>${esc(t.owners.length ? t.owners.join(', ') : '정보 없음')}${t.owners.length ? '<small>연결된 QA 업무의 담당자</small>' : ''}</td>
      <td>${esc(t.status)}${t.overdue ? '<small class="qa-warning">일정 초과 · 확인 필요</small>' : ''}</td>
      <td>${esc(t.start || '미정')}</td><td>${esc(t.end || '미정')}</td><td>${esc(t.tcState)}<small>${t.tcCount === null ? '개수 미입력' : esc(t.tcCount)+'건'}</small></td>
      <td>${t.start && t.state === '예정' ? `D${dateNum(t.start)-dateNum(today)>0 ? '-' : '+'}${Math.abs(dateNum(t.start)-dateNum(today))}` : '—'}</td>
    </tr>`).join('')}</tbody></table></div>`;
  }
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
  function renderTasks() {
    const source = DATA.qaTasks, all = tasks();
    const categories = ['전체','진행중','예정','완료','지연/주의','단계 완료','중지','분류 미확인'];
    const matches = (t,c) => c === '전체' || (c === '지연/주의' ? t.overdue : t.state === c);
    let rows = all.filter(t => matches(t,taskFilter));
    if (taskRange !== 'ALL') {
      const end = offset(today,Number(taskRange)-1);
      rows = rows.filter(t => t.start && t.start <= end && (t.end || t.start) >= today);
    }
    tasksPanel.innerHTML = `${sourceNotice(source)}<article class="panel"><div class="qa-section-head"><h2>QA 업무 진행 현황</h2><span class="subtle">기준일 ${today} · ${all.length}건</span></div>
      <div class="qa-stat-grid">${['진행중','예정','완료','지연/주의'].map(c => card(c,source?.data ? all.filter(t => matches(t,c)).length : '—',c==='지연/주의' ? '진행·예정·단계 완료 중 종료일 초과' : '원본 상태 기준')).join('')}</div>
      <div class="qa-filter-row" style="margin-top:16px">${categories.map(c => `<button class="qa-chip ${taskFilter===c ? 'active' : ''}" data-task-filter="${esc(c)}">${esc(c)} ${all.filter(t => matches(t,c)).length}</button>`).join('')}</div>
      <label class="qa-note" for="taskRange">목록 일정 범위 <select id="taskRange" class="qa-chip"><option value="ALL">전체 일정</option><option value="7">오늘부터 7일</option><option value="14">오늘부터 14일</option><option value="30">오늘부터 30일</option></select></label>
      <p class="qa-note">원본의 ‘태스트 완료’를 완료로 표시하며 ‘1차 테스트 완료’는 단계 완료로 구분합니다. 지연은 별도 주의 표시로 중복 집계합니다. 서비스·진행률 속성이 없어 해당 지표는 제공하지 않습니다.</p>
      ${source?.data?.ownerLookupFailures ? `<p class="qa-warning">연결 업무 ${source.data.ownerLookupFailures}건의 담당자 조회 실패</p>` : ''}
      </article>
      ${taskFilter==='전체' ? ['진행중','예정','단계 완료','완료','중지','분류 미확인'].map(c => `<article class="panel"><h2>${esc(c==='진행중' ? '현재 진행 업무' : c==='예정' ? '예정 업무' : c)} · ${rows.filter(t=>t.state===c).length}</h2>${taskTable(rows.filter(t=>t.state===c))}</article>`).join('') : `<article class="panel"><h2>${esc(taskFilter)} · ${rows.length}건</h2>${taskTable(rows)}</article>`}
      <article class="panel"><h2>QA 업무 Timeline</h2>${renderTimeline(rows)}</article>`;
    tasksPanel.querySelectorAll('[data-task-filter]').forEach(b=>b.addEventListener('click',()=>{taskFilter=b.dataset.taskFilter;renderTasks();}));
    $('taskRange').value=taskRange;
    $('taskRange').addEventListener('change',e=>{taskRange=e.target.value;renderTasks();});
  }
  function defectTable(rows) {
    if (!rows.length) return '<div class="empty">해당 결함이 없습니다.</div>';
    return `<div class="table-wrap"><table class="qa-table"><thead><tr><th>결함</th><th>상태</th><th>심각도</th><th>Target Version</th><th>등록 후 경과</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${link(r.title,r.url)}</td><td>${esc(r.status)}</td><td>${esc(r.severity)}</td><td>${esc(r.version)}</td><td>${r.ageDays ?? '—'}일</td></tr>`).join('')}</tbody></table></div>`;
  }
  function renderQuality() {
    const q = DATA.domains[qualityDomain].quality;
    const all = tasks(), taskAvailable = Boolean(DATA.qaTasks?.data), defectAvailable = DATA.sources?.defects?.status !== 'error';
    const docs = DATA.qaQuality?.data?.documents || [];
    qualityPanel.innerHTML = `<article class="panel"><div class="qa-section-head"><h2>QA QUALITY SUMMARY</h2><label>결함 서비스 <select id="qualityDomain" class="qa-chip"><option value="ALL">전체</option><option value="한패스">Hanpass</option><option value="GoHanpass">Gohanpass</option></select></label></div>
      <div class="qa-stat-grid">${card('진행 QA',taskAvailable ? all.filter(t=>t.state==='진행중').length : '—','전체 QA 업무')}${card('예정 QA',taskAvailable ? all.filter(t=>t.state==='예정').length : '—','전체 QA 업무')}${card('미해결 Critical',defectAvailable?q.unresolvedCritical:'—')}${card('미해결 Major',defectAvailable?q.unresolvedMajor:'—')}${card('지연 업무',taskAvailable?all.filter(t=>t.overdue).length:'—','전체 QA 업무')}${card('개발 완료 · 미검증',defectAvailable?q.awaitingVerification:'—')}</div>
      <p class="qa-note">Release Risk: ${esc(q.risk.reason)}. 서비스 선택은 결함 지표에 적용하며, 서비스 속성이 없는 QA 업무는 전체 기준입니다.</p>${sourceNotice(DATA.qaTasks)}${sourceNotice(DATA.sources?.defects)}
      <details class="qa-note"><summary>집계 기준</summary>미해결: 기존 프로젝트 상세의 최종 완료·백로그 이관 판정을 제외한 결함. 개발 완료는 미검증으로 포함합니다. 장기 미처리는 등록 후 ${q.agingDays}일 이상이며, 상태 체류 시간과는 다릅니다. 기존 결함 요약의 종료 집계 기준은 그대로 유지합니다.</details></article>
      <article class="panel"><h2>미해결 Critical / Major · ${defectAvailable?q.highCount:'—'}건</h2>${defectAvailable?defectTable(q.high):sourceNotice(DATA.sources?.defects)}${q.highCount>50?'<p class="qa-note">Critical 우선, 오래된 등록 순 최대 50건 표시</p>':''}</article>
      <article class="panel"><h2>장기 미처리 결함 · ${defectAvailable?q.agingCount:'—'}건</h2>${defectAvailable?defectTable(q.aging):sourceNotice(DATA.sources?.defects)}${q.agingCount>50?'<p class="qa-note">등록일이 오래된 순 최대 50건 표시</p>':''}</article>
      <article class="panel"><h2>QA 일정 / TC 준비 상태</h2>${sourceNotice(DATA.qaTasks)}${taskTable(all.filter(t=>['진행중','예정','단계 완료'].includes(t.state)))}<p class="qa-note">TC 개수는 테스트 규모이며 수행률·통과율이 아닙니다.</p></article>
      <article class="panel"><h2>QA 주요 문서 / 링크</h2>${sourceNotice(DATA.qaQuality)}<ul class="qa-documents">${docs.map(d=>`<li>${link(d.title,d.url)}</li>`).join('')}</ul>${!docs.length?'<div class="empty">조회된 주요 문서가 없습니다.</div>':''}<p class="qa-note">QA 페이지에서 확인한 하위 문서·DB 링크입니다. 최대 ${DATA.qaQuality?.data?.depthLimit ?? 3}단계 탐색${DATA.qaQuality?.data?.partialFailures ? ` · 하위 컨테이너 ${DATA.qaQuality.data.partialFailures}건 조회 실패` : ''}.</p></article>`;
    $('qualityDomain').value=qualityDomain;
    $('qualityDomain').addEventListener('change',e=>{qualityDomain=e.target.value;renderQuality();});
  }
  if (DATA.sources?.defects?.status === 'error') {
    $('defectControls').insertAdjacentHTML('afterend', '<p class="qa-warning">결함 데이터를 조회하지 못했습니다. 아래 빈 차트의 0건은 실제 결함 건수가 아닙니다.</p>');
  }
  showSection();
})();
