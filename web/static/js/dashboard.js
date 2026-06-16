// ============================================================
//  Altria Ops Dashboard — dashboard.js v2.0
//  All data comes from real API endpoints. No mock data.
// ============================================================

let volumeChart, statusChart, weekChart, emailTrendChart, emailTypeChart;
let autoRefreshTimer;
const API = '';  // same origin

// ── Init ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initCharts();
    startClock();
    checkHealth();
    setInterval(checkHealth, 60000);

    // Load dashboard immediately
    loadPageData('dashboard');
    startAutoRefresh(30);

    // Buttons
    document.getElementById('refreshAllBtn')?.addEventListener('click', () => {
        const page = currentPage();
        if (MANUAL_PAGES.has(page)) {
            // For manual pages, just update the timestamp — don't re-run heavy reports
            document.getElementById('lastUpdated').textContent = 'Updated ' + new Date().toLocaleTimeString();
        } else {
            loadPageData(page, true);
        }
    });
    document.getElementById('generateReportBtn')?.addEventListener('click', generateReport);
    document.getElementById('refreshAlertsBtn')?.addEventListener('click', fetchAlerts);
    document.getElementById('emailLoadBtn')?.addEventListener('click', loadEmailPage);

    document.getElementById('reportDate')?.addEventListener('change', function () {
        document.getElementById('customDate').style.display = this.value === 'custom' ? 'inline-block' : 'none';
    });
    document.getElementById('emailDateSelect')?.addEventListener('change', function () {
        document.getElementById('emailCustomDate').style.display = this.value === 'custom' ? 'inline-block' : 'none';
    });

    // Top agents period tabs
    document.querySelectorAll('.tab-pill[data-period]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-pill[data-period]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            fetchTopAgents(btn.dataset.period);
        });
    });
});

// ── Navigation ────────────────────────────────────────────
function currentPage() {
    const active = document.querySelector('.nav-item.active');
    return active ? active.dataset.page : 'dashboard';
}

function initNavigation() {
    // Hide nav items not allowed for this user's role (server injects window.ALTRIA_ALLOWED_PAGES)
    const allowed = window.ALTRIA_ALLOWED_PAGES || null;
    let firstAllowedPage = 'dashboard';
    document.querySelectorAll('.nav-item').forEach((item, idx) => {
        const page = item.dataset.page;
        if (allowed && !allowed.includes(page)) {
            item.style.display = 'none';
        } else if (idx === 0 || firstAllowedPage === 'dashboard') {
            // track the first visible item as fallback landing page
        }
    });
    if (allowed && allowed.length && !allowed.includes('dashboard')) {
        firstAllowedPage = allowed[0];
    }

    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', e => {
            e.preventDefault();
            const page = item.dataset.page;
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            item.classList.add('active');
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            const tp = document.getElementById(page + '-page');
            if (tp) tp.classList.add('active');
            const titles = { dashboard:'Dashboard', agents:'Live Agents',
                             campaigns:'Campaigns', email:'Email Channel',
                             reports:'EOD Report', alerts:'Alerts',
                             'vicidial-reports':'Reports', quality:'QC Scoring',
                             mapping:'Agent Mapping', 'agent-mgmt':'Agent Management',
                             forecast:'Predictive Analytics', schedule:'Schedule',
                             anomaly:'Anomaly Detection', dids:'DID Inspector',
                             'query-monitor':'Query Monitor', apt:'API Services',
                             'qa-package':'Client QA Package', 'user-mgmt':'User Management' };
            document.getElementById('pageTitle').textContent = titles[page] || page;
            loadPageData(page, true); // force=true on explicit nav click
            closeMobileSidebar();
        });
    });

    // If the default "dashboard" page isn't allowed for this role, jump to first allowed page
    if (allowed && allowed.length && !allowed.includes('dashboard')) {
        const target = document.querySelector(`.nav-item[data-page="${firstAllowedPage}"]`);
        if (target) target.click();
    }

    // ── Mobile hamburger / overlay ──────────────────────────
    const toggleBtn = document.getElementById('mobileNavToggle');
    const overlay   = document.getElementById('sidebarOverlay');
    const sidebar   = document.querySelector('.sidebar');
    toggleBtn?.addEventListener('click', () => {
        sidebar?.classList.toggle('open');
        overlay?.classList.toggle('open');
    });
    overlay?.addEventListener('click', closeMobileSidebar);
}

function closeMobileSidebar() {
    document.querySelector('.sidebar')?.classList.remove('open');
    document.getElementById('sidebarOverlay')?.classList.remove('open');
}

// Pages that should NOT auto-refresh (user controls when to reload)
const MANUAL_PAGES = new Set(['reports', 'vicidial-reports', 'quality', 'mapping', 'email', 'agent-mgmt', 'forecast', 'schedule', 'dids', 'query-monitor', 'user-mgmt']);

function loadPageData(page, force = false) {
    // For manual pages, only load on explicit navigation (not auto-refresh or visibility change)
    if (MANUAL_PAGES.has(page) && !force) return;

    switch (page) {
        case 'dashboard':        fetchDashboard(); break;
        case 'agents':           fetchAgentStatus(); break;
        case 'campaigns':        fetchCampaignPerformance(); break;
        case 'email':            loadEmailPage(); break;
        case 'reports':          /* user clicks Generate manually */ break;
        case 'alerts':           fetchAlerts(); break;
        case 'vicidial-reports': initVicidialReports(); break;
        case 'quality':          initQualityPage(); break;
        case 'agent-mgmt':       initAgentMgmt(); break;
        case 'mapping':          loadMappingPage(); break;
        case 'forecast':         initForecastPage(); break;
        case 'schedule':         initSchedulePage(); break;
        case 'anomaly':          runAnomalyDetect(); break;
        case 'dids':             fetchDids(); break;
        case 'query-monitor':    loadQueryMonitor(); break;
        case 'user-mgmt':        loadUserMgmtPage(); break;
    }
    document.getElementById('lastUpdated').textContent = 'Updated ' + new Date().toLocaleTimeString();
}

function startAutoRefresh(secs) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = setInterval(() => {
        if (currentPage() === 'dashboard') fetchDashboard();
        if (currentPage() === 'agents')    fetchAgentStatus();
    }, secs * 1000);
}

// ── Clock ─────────────────────────────────────────────────
function startClock() {
    function tick() {
        const el = document.getElementById('serverTime');
        if (el) el.textContent = new Date().toLocaleString('en-US', { month:'short', day:'numeric', hour:'numeric', minute:'2-digit', second:'2-digit' });
    }
    tick(); setInterval(tick, 1000);
}

// ── Health check ──────────────────────────────────────────
async function checkHealth() {
    try {
        const h = await apiFetch('/api/health');
        setDot('vicidialDot', h.vicidial_db);
        setDot('emailDot',    h.email_db);
    } catch(e) {
        setDot('vicidialDot', false); setDot('emailDot', false);
    }
}
function setDot(id, ok) {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = 'dot ' + (ok ? 'ok' : 'err');
    el.title = ok ? 'Connected' : 'Disconnected';
}

// ── Generic fetch helper ──────────────────────────────────
async function apiFetch(url) {
    const r = await fetch(API + url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
}

// ── Dashboard ─────────────────────────────────────────────
async function fetchDashboard() {
    try {
        const [kpi, vol, status] = await Promise.all([
            apiFetch('/api/dashboard/kpi'),
            apiFetch('/api/call/volume/today'),
            apiFetch('/api/agent/status')
        ]);

        // KPI cards
        setText('kpiTotalCalls', fmt(kpi.calls.total));
        setText('kpiAnswerRate', `${kpi.calls.answer_rate}% answer rate`);
        setText('kpiAgents', fmt(kpi.agents.online));
        setText('kpiInCall', `${kpi.agents.incall} in call · ${kpi.agents.ready} ready`);
        setText('kpiQueue', fmt(kpi.queue.waiting));
        const abdColor = kpi.calls.abandon_rate > 15 ? '#ef4444' : kpi.calls.abandon_rate > 8 ? '#f59e0b' : '#22c55e';
        setHtml('kpiAbandon', `<span style="color:${abdColor}">${kpi.calls.abandon_rate}%</span>`);

        // Email KPI
        try {
            const em = await apiFetch('/api/email/summary');
            setText('kpiEmails', fmt(em.data.total_emails));
            setText('kpiEmailSub', `${em.data.agents_active} agents · $${em.data.refund_total.toFixed(2)} refunds`);
            const badge = document.getElementById('emailBadge');
            if (badge && em.data.cancellations > 0) { badge.textContent = em.data.cancellations + ' cancel'; badge.style.display='inline'; }
        } catch(e) {
            setText('kpiEmails', '—'); setText('kpiEmailSub', 'Email DB offline');
        }

        // Volume chart
        updateVolumeChart(vol.data);

        // Status donut
        const c = status.counts;
        updateStatusChart(c);

        // Top agents
        fetchTopAgents('today');

        // Week chart
        fetchWeekChart();

    } catch(e) { console.error('Dashboard fetch error', e); }
}

// ── Volume Chart ──────────────────────────────────────────
function updateVolumeChart(hours) {
    if (!volumeChart) return;
    const labels = hours.map(h => h.label);
    const data   = hours.map(h => h.calls);
    volumeChart.data.labels = labels;
    volumeChart.data.datasets[0].data = data;
    volumeChart.update();
}

// ── Status Chart ──────────────────────────────────────────
function updateStatusChart(counts) {
    if (!statusChart) return;
    const vals = [counts.INCALL||0, counts.READY||0, counts.PAUSE||0, counts.RING||0];
    statusChart.data.datasets[0].data = vals;
    statusChart.update();
    const total = vals.reduce((a,b) => a+b, 0);
    const labels = ['In Call','Ready','Paused','Ring'];
    const colors = ['#3b82f6','#22c55e','#f59e0b','#a855f7'];
    const legend = document.getElementById('statusLegend');
    if (legend) {
        legend.innerHTML = labels.map((l,i) => `
            <div style="display:inline-flex;align-items:center;gap:5px;margin-right:14px;">
                <span style="width:10px;height:10px;border-radius:50%;background:${colors[i]};display:inline-block"></span>
                <span style="color:#475569">${l}: <b>${vals[i]}</b></span>
            </div>`).join('');
    }
}

// ── Week Chart ────────────────────────────────────────────
async function fetchWeekChart() {
    try {
        const [calls, emails] = await Promise.all([
            apiFetch('/api/call/volume/week'),
            apiFetch('/api/email/trend').catch(() => ({ data: [] }))
        ]);
        if (!weekChart) return;
        const dates = calls.data.map(d => d.day);
        const callData  = calls.data.map(d => d.calls);
        const emailMap  = {};
        (emails.data || []).forEach(e => { emailMap[e.date] = e.total; });
        const emailData = calls.data.map(d => emailMap[d.date] || 0);

        weekChart.data.labels = dates;
        weekChart.data.datasets[0].data = callData;
        weekChart.data.datasets[1].data = emailData;
        weekChart.update();
    } catch(e) {}
}

// ── Top Agents ────────────────────────────────────────────
async function fetchTopAgents(period) {
    const el = document.getElementById('topAgentsList');
    if (!el) return;
    try {
        const res = await apiFetch(`/api/top/agents/${period}`);
        const agents = res.data || [];
        if (!agents.length) { el.innerHTML = '<p style="color:#94a3b8;padding:20px">No data</p>'; return; }
        const rankClass = i => i===0?'gold':i===1?'silver':i===2?'bronze':'';
        el.innerHTML = agents.map((a,i) => `
            <div class="agent-rank-item">
                <div style="display:flex;align-items:center;gap:10px;">
                    <div class="rank-num ${rankClass(i)}">${i+1}</div>
                    <span style="font-weight:600">${esc(a.name)}</span>
                </div>
                <div style="display:flex;gap:14px;align-items:center;">
                    <span style="color:#64748b;font-size:13px">${fmt(a.calls)} calls</span>
                    <span style="color:#64748b;font-size:13px">${a.talk_time}</span>
                </div>
            </div>`).join('');
    } catch(e) { el.innerHTML = '<p style="color:#ef4444;padding:20px">Error loading agents</p>'; }
}

// ── Live Agents ───────────────────────────────────────────
async function fetchAgentStatus() {
    const tbody = document.getElementById('agentsTableBody');
    const summary = document.getElementById('agentStatusSummary');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="6" class="loading-cell"><i class="fas fa-spinner fa-spin"></i> Loading...</td></tr>`;
    try {
        const res = await apiFetch('/api/agent/status');
        const agents = res.agents || [];
        if (!agents.length) { tbody.innerHTML = `<tr><td colspan="6" class="loading-cell">No active agents</td></tr>`; return; }

        const statusBadge = s => {
            const map = { INCALL:'badge-incall',READY:'badge-ready',PAUSE:'badge-pause',RING:'badge-ring',QUEUE:'badge-queue' };
            return `<span class="badge ${map[s]||'badge-default'}">${s}</span>`;
        };
        tbody.innerHTML = agents.map(a => `
            <tr>
                <td style="font-weight:600">${esc(a.user)}</td>
                <td>${esc(a.name)}</td>
                <td>${statusBadge(a.status)}</td>
                <td>${esc(a.campaign)}</td>
                <td>${minutesBadge(a.minutes)}</td>
                <td style="color:#64748b">${esc(a.last_call)}</td>
            </tr>`).join('');

        if (summary) {
            const c = res.counts;
            summary.innerHTML = [['INCALL',c.INCALL,'badge-incall'],['READY',c.READY,'badge-ready'],
                                  ['PAUSE',c.PAUSE,'badge-pause']].map(([l,n,cls]) =>
                `<span class="status-pill ${cls}" style="padding:4px 12px">${l}: ${n}</span>`).join('');
        }
    } catch(e) { tbody.innerHTML = `<tr><td colspan="6" class="loading-cell" style="color:#ef4444">Error: ${esc(e.message)}</td></tr>`; }
}

function minutesBadge(mins) {
    if (!mins && mins !== 0) return '—';
    const color = mins > 30 ? '#ef4444' : mins > 15 ? '#f59e0b' : '#64748b';
    return `<span style="color:${color};font-weight:${mins>15?'600':'400'}">${mins}m</span>`;
}

// ── Campaigns ─────────────────────────────────────────────
function renderCampTable(tbody, campaigns, extraCol, extraTotalFn) {
    if (!campaigns.length) {
        const filterActive = _appliedTime.start || _appliedTime.end;
        tbody.innerHTML = filterActive
            ? `<tr><td colspan="9" style="padding:32px;text-align:center;">
                <div style="color:#f59e0b;font-size:28px;margin-bottom:12px;">⏱</div>
                <div style="font-weight:700;color:#374151;margin-bottom:6px;">No calls found in time window <strong>${esc(_appliedTime.start||'00:00')} – ${esc(_appliedTime.end||'23:59')}</strong></div>
                <div style="color:#64748b;font-size:13px;margin-bottom:16px;">Your database likely stores times in a different timezone. Try adjusting the window or check the actual call hours below.</div>
                <button class="btn-primary" onclick="detectPeakHours(this)" style="margin-right:8px;"><i class="fas fa-magnifying-glass"></i> Detect Peak Hours</button>
                <button onclick="clearCampTime()" style="padding:8px 16px;border-radius:9px;border:1px solid #e2e8f0;background:white;cursor:pointer;font-size:13px;font-weight:600;color:#374151;">Show All Day</button>
                <div id="peakHoursResult" style="margin-top:16px;"></div>
               </td></tr>`
            : `<tr><td colspan="9" class="loading-cell">No data for this period</td></tr>`;
        return;
    }
    _campLastData = campaigns;
    const rows = campaigns.map(c => campRow(c, extraCol ? extraCol(c) : '')).join('');
    tbody.innerHTML = rows + campTotalsRow(campaigns, extraTotalFn);
    // make header sortable
    const thead = tbody.closest('table')?.querySelector('thead');
    if (thead) makeSortable(thead, campaigns, (sorted) => {
        _campLastData = sorted;
        tbody.innerHTML = sorted.map(c => campRow(c, extraCol ? extraCol(c) : '')).join('')
            + campTotalsRow(sorted, extraTotalFn);
    });
}

async function detectPeakHours(btn) {
    const out = document.getElementById('peakHoursResult');
    if (!out) return;
    if (btn) btn.disabled = true;
    out.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Scanning call hours from last 7 days…';
    try {
        const d = await apiFetch('/api/campaigns/hourly');
        const rows = d.data || [];
        if (!rows.length) { out.innerHTML = '<span style="color:#94a3b8">No hourly data found.</span>'; return; }
        const max = Math.max(...rows.map(r => r.total_calls));
        out.innerHTML = `<div style="margin-top:8px;font-weight:700;color:#374151;margin-bottom:10px;">Call volume by hour (DB time):</div>
            <div style="display:flex;gap:3px;align-items:flex-end;height:60px;flex-wrap:nowrap;overflow-x:auto;padding-bottom:4px;">
            ${Array.from({length:24}, (_,h) => {
                const row = rows.find(r => r.hour_of_day === h);
                const cnt = row?.total_calls || 0;
                const pct = max ? Math.max(4, Math.round(cnt/max*56)) : 4;
                const color = cnt > 0 ? '#6366f1' : '#e2e8f0';
                return `<div style="display:flex;flex-direction:column;align-items:center;gap:2px;min-width:22px;">
                    <div style="width:18px;height:${pct}px;background:${color};border-radius:3px 3px 0 0;" title="${h}:00 – ${cnt} calls"></div>
                    <span style="font-size:9px;color:#94a3b8">${String(h).padStart(2,'0')}</span>
                </div>`;
            }).join('')}
            </div>
            <div style="margin-top:12px;font-size:12px;color:#64748b;">
                Peak hours (DB time): <strong style="color:#6366f1">${rows.sort((a,b)=>b.total_calls-a.total_calls).slice(0,3).map(r=>`${String(r.hour_of_day).padStart(2,'0')}:00`).join(', ')}</strong>
                &nbsp;·&nbsp; Set your time window to match these hours and click Apply.
            </div>`;
    } catch(e) {
        out.innerHTML = `<span style="color:#ef4444">Error: ${esc(e.message)}</span>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchCampaignPerformance() {
    const tbody = document.getElementById('campaignsTableBody');
    const totels = document.getElementById('campaignTotals');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="8" class="loading-cell"><i class="fas fa-spinner fa-spin"></i> Loading...</td></tr>`;
    try {
        const res = await apiFetch('/api/campaigns/performance' + campTimeParams(true));
        const campaigns = res.data || [];
        if (!campaigns.length) { renderCampTable(tbody, [], null, null); return; }

        renderCampTable(tbody, campaigns, null, null);

        if (totels && res.totals) {
            const t = res.totals;
            const rc = (r,g,w) => r>=g?'#22c55e':r>=w?'#f59e0b':'#ef4444';
            totels.innerHTML = `
                <span class="status-pill">${fmt(t.calls)} total</span>
                <span class="status-pill" style="color:${rc(t.answer_rate,80,60)}">${t.answer_rate}% ans</span>
                <span class="status-pill" style="color:${t.abandon_rate>20?'#ef4444':'inherit'}">${t.abandon_rate}% abd</span>`;
        }
        // Populate campaign selects for sub-tabs (only once)
        const ids = ['campSpecificSelect','campCmp1','campCmp2','campHourlySelect'];
        ids.forEach(id => {
            const sel = document.getElementById(id);
            if (!sel || sel.options.length > 1) return;
            campaigns.forEach(c => {
                const o = document.createElement('option');
                o.value = c.campaign_id || c.campaign;
                o.textContent = c.campaign_id || c.campaign;
                sel.appendChild(o);
            });
        });
    } catch(e) { tbody.innerHTML = `<tr><td colspan="8" class="loading-cell" style="color:#ef4444">Error: ${esc(e.message)}</td></tr>`; }
}

// ── Email Channel ─────────────────────────────────────────
async function loadEmailPage() {
    const spinner = document.getElementById('emailLoadingSpinner');
    if (spinner) spinner.style.display = 'inline';

    const sel = document.getElementById('emailDateSelect')?.value;
    let dateStr;
    if (sel === 'today') {
        dateStr = toDateStr(new Date());
    } else if (sel === 'yesterday') {
        const d = new Date(); d.setDate(d.getDate()-1); dateStr = toDateStr(d);
    } else {
        dateStr = document.getElementById('emailCustomDate')?.value;
    }
    if (!dateStr) { if (spinner) spinner.style.display='none'; return; }

    try {
        const [sum, agents, trend] = await Promise.all([
            apiFetch(`/api/email/summary/${dateStr}`),
            apiFetch(`/api/email/agents/${dateStr}`),
            apiFetch('/api/email/trend').catch(() => ({ data:[] }))
        ]);

        const s = sum.data;
        setText('ekTotal',   fmt(s.total_emails));
        setText('ekAgents',  `${s.agents_active} agents active`);
        setText('ekCancels', fmt(s.cancellations));
        setText('ekFullRef', fmt(s.full_refunds));
        setText('ekPartRef', fmt(s.partial_refunds));
        setText('ekRefVal',  `$${s.refund_total.toFixed(2)}`);
        setText('ekOrderSt', fmt(s.order_status));
        setText('ekGenInq',  fmt(s.gen_inquiry));

        // Subtitle
        const sub = document.getElementById('emailTableSubtitle');
        if (sub) sub.textContent = `${dateStr} — ${s.total_emails} emails, ${s.agents_active} agents`;

        // Unmapped warning
        const unmapped = (agents.data || []).filter(a => !a.altria_username).length;
        const warn = document.getElementById('unmappedWarning');
        if (warn) {
            if (unmapped > 0) { warn.textContent = `⚠ ${unmapped} agent(s) not linked to VICIdial`; warn.style.display='inline'; }
            else warn.style.display = 'none';
        }

        // Agent table
        renderEmailAgents(agents.data || []);

        // Trend chart
        updateEmailTrendChart(trend.data || []);

        // Type donut for selected day
        updateEmailTypeChart(s);

    } catch(e) {
        console.error('Email page error', e);
        document.getElementById('emailAgentsBody').innerHTML =
            `<tr><td colspan="8" class="loading-cell" style="color:#ef4444">Error: ${esc(e.message)}</td></tr>`;
    }
    if (spinner) spinner.style.display = 'none';
}

function renderEmailAgents(agents) {
    const tbody = document.getElementById('emailAgentsBody');
    if (!tbody) return;
    if (!agents.length) { tbody.innerHTML = `<tr><td colspan="8" class="loading-cell">No email data for this date</td></tr>`; return; }

    tbody.innerHTML = agents.map(a => {
        const linked = a.altria_username
            ? `<span style="color:#22c55e;font-weight:600">${esc(a.altria_username)}</span>`
            : `<span style="color:#f59e0b;font-style:italic">⚠ Unlinked</span>`;
        const topType = a.by_type ? Object.entries(a.by_type).sort((x,y)=>y[1]-x[1])[0]?.[0] || '—' : '—';
        return `<tr>
            <td style="font-weight:600">${esc(a.pinktools_name)}</td>
            <td>${linked}</td>
            <td class="num">${fmt(a.total_emails)}</td>
            <td class="num">${fmt(a.cancellations)}</td>
            <td class="num">${fmt(a.by_type?.['FULL REFUND']||0)}</td>
            <td class="num">${fmt(a.by_type?.['PARTIAL REFUND']||0)}</td>
            <td class="num">$${a.refund_total.toFixed(2)}</td>
            <td style="font-size:12px;color:#64748b">${esc(topType)}</td>
        </tr>`;
    }).join('');
}

function updateEmailTrendChart(data) {
    if (!emailTrendChart || !data.length) return;
    emailTrendChart.data.labels = data.map(d => d.date.slice(5));
    emailTrendChart.data.datasets[0].data = data.map(d => d.total);
    emailTrendChart.data.datasets[1].data = data.map(d => d.cancels);
    emailTrendChart.data.datasets[2].data = data.map(d => (d.full_ref||0) + (d.part_ref||0));
    emailTrendChart.update();
}

function updateEmailTypeChart(s) {
    if (!emailTypeChart) return;
    emailTypeChart.data.datasets[0].data = [
        s.cancellations, s.full_refunds, s.partial_refunds,
        s.order_status, s.gen_inquiry, s.reshipments
    ];
    emailTypeChart.update();
}

// ── EOD Report ────────────────────────────────────────────
let eodDateStr = '';

async function generateReport() {
    const sel = document.getElementById('reportDate')?.value;
    if (sel === 'today') eodDateStr = toDateStr(new Date());
    else if (sel === 'yesterday') { const d=new Date(); d.setDate(d.getDate()-1); eodDateStr=toDateStr(d); }
    else eodDateStr = document.getElementById('customDate')?.value;

    const content = document.getElementById('reportContent');
    if (!content) return;
    if (!eodDateStr) { content.innerHTML = '<p style="color:#ef4444;padding:40px">Please select a valid date</p>'; return; }

    // Load campaign list for filter
    await loadCampaignFilter(eodDateStr);

    // Run the actual report
    await runEodReport();
}

async function loadCampaignFilter(dateStr) {
    try {
        const res = await apiFetch(`/api/campaigns/list?date=${dateStr}`);
        const campaigns = res.data || [];
        const wrap = document.getElementById('campaignFilterWrap');
        const box  = document.getElementById('campaignCheckboxes');
        if (!wrap || !box) return;

        wrap.style.display = campaigns.length ? 'block' : 'none';
        box.innerHTML = campaigns.map(c => `
            <label style="display:inline-flex;align-items:center;gap:6px;padding:5px 12px;background:white;
                          border:1px solid #e2e8f0;border-radius:20px;cursor:pointer;font-size:13px;font-weight:500;
                          transition:all 0.15s;" class="camp-chip">
                <input type="checkbox" value="${esc(c)}" checked
                       style="accent-color:#3b82f6;cursor:pointer;"
                       onchange="updateChipStyle(this)">
                ${esc(c)}
            </label>`).join('');

        document.getElementById('applyFilterBtn')?.addEventListener('click', runEodReport);

    // Clear preset active state when custom time is typed
    ['timeStart','timeEnd'].forEach(id => {
        document.getElementById(id)?.addEventListener('input', () => {
            document.querySelectorAll('.time-preset').forEach(b => b.classList.remove('active'));
        });
    });
    } catch(e) {}
}

function updateChipStyle(cb) {
    const label = cb.closest('label');
    if (!label) return;
    label.style.background    = cb.checked ? '#eff6ff' : 'white';
    label.style.borderColor   = cb.checked ? '#3b82f6' : '#e2e8f0';
    label.style.color         = cb.checked ? '#1d4ed8' : '#64748b';
}

function selectAllCampaigns(checked) {
    document.querySelectorAll('#campaignCheckboxes input[type=checkbox]').forEach(cb => {
        cb.checked = checked;
        updateChipStyle(cb);
    });
}

async function runEodReport() {
    const content = document.getElementById('reportContent');
    if (!content || !eodDateStr) return;

    // Collect selected campaigns
    const checked = [...document.querySelectorAll('#campaignCheckboxes input[type=checkbox]:checked')]
                        .map(cb => cb.value);
    const allCamps = [...document.querySelectorAll('#campaignCheckboxes input[type=checkbox]')]
                        .map(cb => cb.value);
    const isAll = checked.length === allCamps.length || checked.length === 0;
    const campParam = isAll ? '' : `campaigns=${checked.join(',')}`;

    // Time range from picker
    const timeStart = document.getElementById('timeStart')?.value || '';
    const timeEnd   = document.getElementById('timeEnd')?.value   || '';
    const timeParam = timeStart ? `time_start=${timeStart}${timeEnd ? '&time_end='+timeEnd : ''}` : '';
    const queryStr  = [campParam, timeParam].filter(Boolean).join('&');

    const timeLabel = timeStart ? ` · ⏰ ${timeStart}${timeEnd?' – '+timeEnd:''}` : '';

    _billingData = null; // reset cache for new report
    content.innerHTML = `<div class="loading-cell"><i class="fas fa-spinner fa-spin" style="font-size:28px"></i>
        <p style="margin-top:12px">Loading report for ${eodDateStr}${isAll?'':` — ${checked.length} campaigns`}${timeLabel}…</p></div>`;
    try {
        const res = await apiFetch(`/api/eod/${eodDateStr}${queryStr ? '?' + queryStr : ''}`);
        renderEODReport(res.data, content, checked, isAll);
    } catch(e) {
        content.innerHTML = `<p style="color:#ef4444;padding:40px">Error: ${esc(e.message)}</p>`;
    }
}

function renderEODReport(r, container, selectedCamps=[], isAll=true) {
    const timeRangeLabel = r.time_range && r.time_range !== 'All Day'
        ? `<span style="background:#f0f0ff;color:#6366f1;font-size:12px;font-weight:600;padding:3px 10px;border-radius:20px;margin-left:8px">⏰ ${esc(r.time_range)}</span>`
        : '';
    const filterLabel = (isAll
        ? '<span style="color:#64748b;font-size:14px;font-weight:400">— All Campaigns</span>'
        : `<span style="background:#eff6ff;color:#1d4ed8;font-size:13px;font-weight:600;padding:3px 10px;border-radius:20px;margin-left:8px">${selectedCamps.length} campaigns selected</span>`)
        + timeRangeLabel;
    const totalMins = r.total_minutes || 0;
    const cards = [
        {title:'Total Calls',   val:fmt(r.total_calls),  color:'#0f172a'},
        {title:'Valid Calls',   val:fmt(r.valid_calls),  color:'#0f172a', sub:`${r.ghost_pct}% ghost`},
        {title:'Answered',      val:fmt(r.answered),     color:'#22c55e', sub:`${r.answer_rate}%`},
        {title:'Abandoned',     val:fmt(r.abandoned),    color:'#ef4444', sub:`${r.abandon_rate}%`},
        {title:'Total Minutes', val:`${Math.floor(totalMins).toLocaleString()}`,
         color:'#6366f1', sub:`${r.total_talk_fmt || ''} talk time`, icon:'⏱️'},
    ];
    let html = `<div style="margin-bottom:24px"><h3 style="margin-bottom:16px;color:#0f172a">📊 ${r.date} ${filterLabel}</h3>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:28px">`;

    cards.forEach(c => { html += `
        <div style="background:#f8fafc;border-radius:12px;padding:20px;text-align:center">
            <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.5px">${c.title}</div>
            <div style="font-size:34px;font-weight:800;color:${c.color};margin:6px 0">${c.val}</div>
            ${c.sub ? `<div style="font-size:13px;color:${c.color}">${c.sub}</div>` : ''}
        </div>`; });
    html += `</div>`;

    // Campaigns table — calls + emails side by side
    if (r.campaigns?.length) {
        const hasEmail = r.campaigns.some(c => c.email);
        html += `<h3 style="margin-bottom:12px">Campaign Breakdown</h3>
        <div style="overflow-x:auto;border-radius:10px;border:1px solid #e2e8f0">
        <table style="width:100%;border-collapse:collapse;font-size:14px">
        <thead>
            <tr style="background:#f8fafc;border-bottom:1px solid #e2e8f0">
                <th style="padding:10px 16px;text-align:left;font-weight:600;color:#475569" rowspan="2">Campaign</th>
                <th colspan="5" style="padding:8px 16px;text-align:center;font-weight:700;color:#3b82f6;border-left:2px solid #e2e8f0;border-right:${hasEmail?'1px':'2px'} solid #e2e8f0">
                    📞 Calls</th>
                ${hasEmail ? `<th colspan="5" style="padding:8px 16px;text-align:center;font-weight:700;color:#a855f7;border-right:2px solid #e2e8f0">📧 Emails</th>` : ''}
            </tr>
            <tr style="background:#f8fafc;border-bottom:2px solid #e2e8f0">
                <th style="padding:8px 16px;text-align:right;font-weight:600;color:#475569;font-size:12px;border-left:2px solid #e2e8f0">Total</th>
                <th style="padding:8px 16px;text-align:right;font-weight:600;color:#475569;font-size:12px">Valid</th>
                <th style="padding:8px 16px;text-align:right;font-weight:600;color:#475569;font-size:12px">Ans %</th>
                <th style="padding:8px 16px;text-align:right;font-weight:600;color:#475569;font-size:12px">Abd %</th>
                <th style="padding:8px 16px;text-align:right;font-weight:600;color:#475569;font-size:12px">Avg Talk</th>
                <th style="padding:8px 16px;text-align:right;font-weight:600;color:#6366f1;font-size:12px;border-right:${hasEmail?'1px':'2px'} solid #e2e8f0">⏱ Minutes</th>
                ${hasEmail ? `
                <th style="padding:8px 16px;text-align:right;font-weight:600;color:#475569;font-size:12px">Emails</th>
                <th style="padding:8px 16px;text-align:right;font-weight:600;color:#475569;font-size:12px">Cancels</th>
                <th style="padding:8px 16px;text-align:right;font-weight:600;color:#475569;font-size:12px">Refunds</th>
                <th style="padding:8px 16px;text-align:right;font-weight:600;color:#475569;font-size:12px">Refund $</th>
                <th style="padding:8px 16px;text-align:right;font-weight:600;color:#475569;font-size:12px;border-right:2px solid #e2e8f0">Agents</th>` : ''}
            </tr>
        </thead><tbody>`;

        r.campaigns.forEach(c => {
            const em = c.email;
            const emailCells = hasEmail ? (em ? `
                <td style="padding:12px 16px;text-align:right;font-weight:600;color:#a855f7">${fmt(em.total)}</td>
                <td style="padding:12px 16px;text-align:right;color:${em.cancels>0?'#ef4444':'#64748b'}">${em.cancels}</td>
                <td style="padding:12px 16px;text-align:right;color:${(em.full_ref+em.part_ref)>0?'#f97316':'#64748b'}">${em.full_ref+em.part_ref}</td>
                <td style="padding:12px 16px;text-align:right;color:${em.refund_val>0?'#22c55e':'#64748b'}">$${em.refund_val.toFixed(2)}</td>
                <td style="padding:12px 16px;text-align:right;color:#64748b;border-right:2px solid #e2e8f0">${em.agents}</td>` :
                `<td colspan="5" style="padding:12px 16px;text-align:center;color:#cbd5e1;font-size:12px;border-right:2px solid #e2e8f0">no emails</td>`)
                : '';
            html += `<tr style="border-bottom:1px solid #f1f5f9">
                <td style="padding:12px 16px;font-weight:600">${esc(c.campaign)}</td>
                <td style="padding:12px 16px;text-align:right;border-left:2px solid #f1f5f9">${fmt(c.calls)}</td>
                <td style="padding:12px 16px;text-align:right">${fmt(c.valid)}</td>
                <td style="padding:12px 16px;text-align:right;color:${c.answer_rate>=80?'#22c55e':c.answer_rate>=60?'#f59e0b':'#ef4444'};font-weight:600">${c.answer_rate}%</td>
                <td style="padding:12px 16px;text-align:right;color:${c.abandon_rate>20?'#ef4444':c.abandon_rate>10?'#f59e0b':'#64748b'}">${c.abandon_rate}%</td>
                <td style="padding:12px 16px;text-align:right">${c.avg_talk}</td>
                <td style="padding:12px 16px;text-align:right;font-weight:700;color:#6366f1">${c.minutes ? c.minutes.toLocaleString(undefined,{minimumFractionDigits:1,maximumFractionDigits:1}) : '0'}</td>
                ${emailCells}
            </tr>`;
        });
        html += `</tbody></table></div>`;
    }

    // ── Billing minutes summary ──────────────────────────────────────────────
    html += `<div id="billingSection" style="margin-top:28px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;flex-wrap:wrap;gap:10px;">
            <h3 style="margin:0">⏱️ Billing Minutes Summary</h3>
            <div style="display:flex;gap:8px;">
                <button onclick="loadBillingReport('today')" class="bill-tab active" style="padding:5px 14px;border-radius:8px;border:1px solid #6366f1;background:#6366f1;color:white;font-size:12px;font-weight:600;cursor:pointer;">Today</button>
                <button onclick="loadBillingReport('week')"  class="bill-tab" style="padding:5px 14px;border-radius:8px;border:1px solid #e2e8f0;background:white;color:#64748b;font-size:12px;font-weight:600;cursor:pointer;">7 Days</button>
                <button onclick="loadBillingReport('month')" class="bill-tab" style="padding:5px 14px;border-radius:8px;border:1px solid #e2e8f0;background:white;color:#64748b;font-size:12px;font-weight:600;cursor:pointer;">This Month</button>
                <button onclick="loadBillingReport('last_month')" class="bill-tab" style="padding:5px 14px;border-radius:8px;border:1px solid #e2e8f0;background:white;color:#64748b;font-size:12px;font-weight:600;cursor:pointer;">Last Month</button>
            </div>
        </div>
        <div id="billingContent"><div style="text-align:center;padding:30px;color:#94a3b8"><i class="fas fa-spinner fa-spin"></i> Loading billing data…</div></div>
    </div>`;

    // Trigger billing load after render
    setTimeout(() => loadBillingReport('today', campParam), 100);

    // Email channel section
    if (r.email?.summary && r.email.summary.total_emails > 0) {
        const es = r.email.summary;
        html += `<h3 style="margin:28px 0 12px">📧 Email Channel</h3>
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px">`;
        [['Total Emails',es.total_emails,'#3b82f6'],['Cancellations',es.cancellations,'#ef4444'],
         ['Full Refunds',es.full_refunds,'#f97316'],['Partial Refunds',es.partial_refunds,'#f59e0b'],
         ['Refund Value','$'+es.refund_total.toFixed(2),'#22c55e'],
         ['Order Status',es.order_status,'#06b6d4'],['Gen Inquiry',es.gen_inquiry,'#a855f7']
        ].forEach(([l,v,c]) => { html += `<div style="background:#f8fafc;padding:14px 18px;border-radius:10px;text-align:center;min-width:110px">
            <div style="font-size:11px;color:#64748b;font-weight:600">${l}</div>
            <div style="font-size:24px;font-weight:800;color:${c};margin-top:4px">${v}</div></div>`; });
        html += `</div>`;

        if (r.email.agents?.length) {
            html += `<div style="overflow-x:auto;border-radius:10px;border:1px solid #e2e8f0">
            <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead style="background:#f8fafc"><tr>
                <th style="padding:10px 16px;text-align:left">Agent</th>
                <th style="padding:10px 16px;text-align:left">VICIdial</th>
                <th style="padding:10px 16px;text-align:right">Emails</th>
                <th style="padding:10px 16px;text-align:right">Cancels</th>
                <th style="padding:10px 16px;text-align:right">Refunds</th>
                <th style="padding:10px 16px;text-align:right">Refund $</th>
            </tr></thead><tbody>`;
            r.email.agents.slice(0,15).forEach(a => { html += `<tr style="border-bottom:1px solid #f1f5f9">
                <td style="padding:10px 16px;font-weight:600">${esc(a.pinktools_name)}</td>
                <td style="padding:10px 16px;color:${a.altria_username?'#22c55e':'#f59e0b'}">${a.altria_username||'⚠ Unlinked'}</td>
                <td style="padding:10px 16px;text-align:right">${a.total_emails}</td>
                <td style="padding:10px 16px;text-align:right">${a.cancellations}</td>
                <td style="padding:10px 16px;text-align:right">${a.refund_count}</td>
                <td style="padding:10px 16px;text-align:right">$${a.refund_total.toFixed(2)}</td>
            </tr>`; });
            html += `</tbody></table></div>`;
        }
    }
    html += `</div>`;
    container.innerHTML = html;
}

// ── Alerts ────────────────────────────────────────────────
async function fetchAlerts() {
    const list = document.getElementById('alertsList');
    if (!list) return;
    list.innerHTML = `<div class="loading-cell"><i class="fas fa-spinner fa-spin"></i> Loading...</div>`;
    try {
        const res = await apiFetch('/api/alerts/active');
        const alerts = res.alerts || [];
        const badge = document.getElementById('alertBadge');
        if (badge) { if (alerts.length>0) { badge.textContent=alerts.length; badge.style.display='inline'; } else badge.style.display='none'; }

        if (!alerts.length) {
            list.innerHTML = `<div class="no-alerts"><i class="fas fa-check-circle" style="font-size:40px;color:#22c55e;margin-bottom:12px;display:block"></i>No active alerts — system operating normally</div>`;
            return;
        }
        list.innerHTML = alerts.map(a => `
            <div class="alert-item ${a.severity}">
                <div>
                    <div class="alert-msg">${esc(a.message)}</div>
                    <div style="font-size:12px;color:#64748b;margin-top:4px">${a.type}</div>
                </div>
                <div class="alert-time">${new Date(a.time).toLocaleTimeString()}</div>
            </div>`).join('');
    } catch(e) {
        list.innerHTML = `<div class="loading-cell" style="color:#ef4444">Error loading alerts: ${esc(e.message)}</div>`;
    }
}

// ── Chart Init ────────────────────────────────────────────
function initCharts() {
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
    const gridColor = '#f1f5f9';

    // Volume (line)
    const vCtx = document.getElementById('volumeChart')?.getContext('2d');
    if (vCtx) {
        volumeChart = new Chart(vCtx, {
            type: 'line',
            data: { labels: [], datasets: [{ label:'Calls', data:[], borderColor:'#3b82f6',
                backgroundColor:'rgba(59,130,246,0.08)', tension:0.35, fill:true,
                pointBackgroundColor:'#3b82f6', pointBorderColor:'white', pointBorderWidth:2, pointRadius:4 }] },
            options: { responsive:true, maintainAspectRatio:false,
                plugins:{legend:{display:false}, tooltip:{backgroundColor:'#1e293b'}},
                scales:{y:{beginAtZero:true, grid:{color:gridColor}}, x:{grid:{display:false}}} }
        });
    }

    // Status (doughnut)
    const sCtx = document.getElementById('statusChart')?.getContext('2d');
    if (sCtx) {
        statusChart = new Chart(sCtx, {
            type: 'doughnut',
            data: { labels:['In Call','Ready','Paused','Ring'],
                    datasets:[{data:[0,0,0,0], backgroundColor:['#3b82f6','#22c55e','#f59e0b','#a855f7'], borderWidth:0, hoverOffset:4}] },
            options: { responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, cutout:'72%' }
        });
    }

    // Week (bar with email overlay)
    const wCtx = document.getElementById('weekChart')?.getContext('2d');
    if (wCtx) {
        weekChart = new Chart(wCtx, {
            type: 'bar',
            data: { labels:[], datasets:[
                { label:'Calls', data:[], backgroundColor:'#3b82f6', borderRadius:6, barPercentage:0.6 },
                { label:'Emails', data:[], backgroundColor:'#a855f7', borderRadius:6, barPercentage:0.6 }
            ]},
            options: { responsive:true, maintainAspectRatio:false,
                plugins:{ legend:{ position:'top', labels:{ usePointStyle:true, font:{size:12} } }, tooltip:{backgroundColor:'#1e293b'} },
                scales:{ y:{beginAtZero:true, grid:{color:gridColor}}, x:{grid:{display:false}} } }
        });
    }

    // Email trend (line)
    const etCtx = document.getElementById('emailTrendChart')?.getContext('2d');
    if (etCtx) {
        emailTrendChart = new Chart(etCtx, {
            type: 'line',
            data: { labels:[], datasets:[
                { label:'Total', data:[], borderColor:'#3b82f6', backgroundColor:'rgba(59,130,246,0.08)', tension:0.35, fill:true },
                { label:'Cancels', data:[], borderColor:'#ef4444', tension:0.35 },
                { label:'Refunds', data:[], borderColor:'#f97316', tension:0.35 }
            ]},
            options: { responsive:true, maintainAspectRatio:false,
                plugins:{ legend:{ position:'top', labels:{usePointStyle:true,font:{size:12}} }, tooltip:{backgroundColor:'#1e293b'} },
                scales:{ y:{beginAtZero:true, grid:{color:gridColor}}, x:{grid:{display:false}} } }
        });
    }

    // Email type (doughnut)
    const ecCtx = document.getElementById('emailTypeChart')?.getContext('2d');
    if (ecCtx) {
        emailTypeChart = new Chart(ecCtx, {
            type: 'doughnut',
            data: { labels:['Cancellations','Full Refunds','Partial Refunds','Order Status','Gen Inquiry','Reshipment'],
                    datasets:[{data:[0,0,0,0,0,0],
                        backgroundColor:['#ef4444','#f97316','#f59e0b','#06b6d4','#a855f7','#3b82f6'], borderWidth:0, hoverOffset:4}] },
            options:{ responsive:true, maintainAspectRatio:false,
                plugins:{ legend:{position:'bottom', labels:{usePointStyle:true, font:{size:11}, padding:12}}, tooltip:{backgroundColor:'#1e293b'} }, cutout:'65%' }
        });
    }
}

// ══════════════════════════════════════════════════════════
// VICIDIAL REPORTS
// ══════════════════════════════════════════════════════════

let trendChart;

function initVicidialReports() {
    // Tab switching
    document.querySelectorAll('.tab-pill[data-report]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-pill[data-report]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.report-section').forEach(s => s.style.display='none');
            const sec = document.getElementById('report-' + btn.dataset.report);
            if (sec) sec.style.display='block';
        });
    });
    // Default dates
    const today = toDateStr(new Date());
    const week  = toDateStr(new Date(Date.now() - 6*864e5));
    const s = document.getElementById('agentPerfStart');
    const e = document.getElementById('agentPerfEnd');
    if (s && !s.value) s.value = week;
    if (e && !e.value) e.value = today;

    document.getElementById('agentPerfLoadBtn')?.addEventListener('click', loadAgentPerf);
    document.getElementById('trendLoadBtn')?.addEventListener('click', loadCampaignTrend);
    document.getElementById('heatmapLoadBtn')?.addEventListener('click', loadHeatmap);
    document.getElementById('dispLoadBtn')?.addEventListener('click', loadDispositionReport);

    // Pre-fill disposition dates
    const dS = document.getElementById('dispDateStart');
    const dE = document.getElementById('dispDateEnd');
    if (dS && !dS.value) dS.value = today;
    if (dE && !dE.value) dE.value = today;

    // Populate disposition agent/campaign dropdowns
    _populateDispDropdowns();

    // Init trend chart
    if (!trendChart) {
        const ctx = document.getElementById('trendChart')?.getContext('2d');
        if (ctx) trendChart = new Chart(ctx, {
            type: 'line',
            data: { labels:[], datasets:[
                { label:'Calls', data:[], borderColor:'#3b82f6', backgroundColor:'rgba(59,130,246,0.08)', tension:0.3, fill:true, yAxisID:'y' },
                { label:'Ans %', data:[], borderColor:'#22c55e', tension:0.3, yAxisID:'y1' }
            ]},
            options:{ responsive:true, maintainAspectRatio:false,
                plugins:{ legend:{position:'top',labels:{usePointStyle:true}} },
                scales:{ y:{beginAtZero:true,grid:{color:'#f1f5f9'},title:{display:true,text:'Calls'}},
                         y1:{beginAtZero:true,max:100,position:'right',grid:{display:false},title:{display:true,text:'Ans %'}} } }
        });
    }
    loadAgentPerf();
}

async function loadAgentPerf() {
    const start = document.getElementById('agentPerfStart')?.value;
    const end   = document.getElementById('agentPerfEnd')?.value;
    const tbody = document.getElementById('agentPerfBody');
    if (!tbody || !start || !end) return;
    tbody.innerHTML = `<tr><td colspan="8" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>`;
    try {
        const res = await apiFetch(`/api/reports/agent-performance?start=${start}&end=${end}`);
        const meta = document.getElementById('agentPerfMeta');
        if (meta) meta.innerHTML = `<span class="status-pill">${res.data.length} agents</span>`;
        if (!res.data.length) { tbody.innerHTML = `<tr><td colspan="8" class="loading-cell">No data</td></tr>`; return; }
        tbody.innerHTML = res.data.map(a => `<tr>
            <td style="font-weight:600">${esc(a.user)}</td>
            <td>${esc(a.name)}</td>
            <td class="num">${fmt(a.total_calls)}</td>
            <td class="num">${fmt(a.valid_calls)}</td>
            <td class="num" style="color:${a.ghost_calls>0?'#f59e0b':'#64748b'}">${fmt(a.ghost_calls)}</td>
            <td class="num" style="color:${a.answer_rate>=80?'#22c55e':a.answer_rate>=60?'#f59e0b':'#ef4444'};font-weight:600">${a.answer_rate}%</td>
            <td class="num">${a.total_talk}</td>
            <td class="num">${a.avg_talk}</td>
        </tr>`).join('');
    } catch(e) { tbody.innerHTML = `<tr><td colspan="8" class="loading-cell" style="color:#ef4444">${esc(e.message)}</td></tr>`; }
}

async function loadCampaignTrend() {
    const days  = document.getElementById('trendDays')?.value || 30;
    const tbody = document.getElementById('trendBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="6" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>`;
    try {
        const res = await apiFetch(`/api/reports/campaign-trend?days=${days}`);
        if (trendChart) {
            trendChart.data.labels = res.data.map(d => d.date.slice(5));
            trendChart.data.datasets[0].data = res.data.map(d => d.calls);
            trendChart.data.datasets[1].data = res.data.map(d => d.answer_rate);
            trendChart.update();
        }
        tbody.innerHTML = res.data.map(d => `<tr>
            <td>${d.date}</td>
            <td class="num">${fmt(d.calls)}</td>
            <td class="num">${fmt(d.answered)}</td>
            <td class="num" style="color:${d.answer_rate>=80?'#22c55e':d.answer_rate>=60?'#f59e0b':'#ef4444'};font-weight:600">${d.answer_rate}%</td>
            <td class="num">${fmt(d.abandoned)}</td>
            <td class="num">${d.avg_queue}s</td>
        </tr>`).join('');
    } catch(e) { tbody.innerHTML = `<tr><td colspan="6" class="loading-cell" style="color:#ef4444">${esc(e.message)}</td></tr>`; }
}

async function loadHeatmap() {
    const container = document.getElementById('heatmapContainer');
    if (!container) return;
    container.innerHTML = `<div class="loading-cell"><i class="fas fa-spinner fa-spin"></i></div>`;
    try {
        const res = await apiFetch('/api/reports/hourly-heatmap');
        const data = res.data;
        // Build date/hour matrix
        const dates = [...new Set(data.map(d => d.date))].sort();
        const maxCalls = Math.max(...data.map(d => d.calls), 1);
        const cell = (date, hour) => {
            const found = data.find(d => d.date===date && d.hour===hour);
            const calls = found ? found.calls : 0;
            const intensity = calls / maxCalls;
            const bg = calls === 0 ? '#f1f5f9' :
                       intensity < 0.3 ? `rgba(59,130,246,${0.2+intensity*0.5})` :
                       intensity < 0.7 ? `rgba(34,197,94,${0.3+intensity*0.4})` :
                                         `rgba(239,68,68,${0.4+intensity*0.6})`;
            return `<div class="heatmap-cell" style="background:${bg}" title="${date} ${hour}:00 — ${calls} calls">${calls||''}</div>`;
        };
        let html = `<div style="display:flex;gap:16px;align-items:flex-start;overflow-x:auto;padding-bottom:8px;">`;
        // Hour labels col
        html += `<div style="display:grid;grid-template-rows:repeat(24,39px);gap:3px;padding-top:30px;">`;
        for (let h=0;h<24;h++) html += `<div style="height:36px;display:flex;align-items:center;font-size:11px;color:#94a3b8;white-space:nowrap">${h}:00</div>`;
        html += `</div>`;
        // Date columns
        dates.forEach(d => {
            html += `<div><div style="font-size:11px;font-weight:600;color:#475569;text-align:center;margin-bottom:6px;white-space:nowrap">${d.slice(5)}</div>`;
            html += `<div style="display:grid;grid-template-rows:repeat(24,1fr);gap:3px;">`;
            for (let h=0;h<24;h++) html += cell(d,h);
            html += `</div></div>`;
        });
        html += `</div>`;
        container.innerHTML = html;
    } catch(e) { container.innerHTML = `<div class="loading-cell" style="color:#ef4444">${esc(e.message)}</div>`; }
}

// ══════════════════════════════════════════════════════════
// QUALITY SCORING
// ══════════════════════════════════════════════════════════

let qcTrendChart, qcDistChart;
let qcCheckpointsData = [];
let qcSelectedUID = '';

function initQualityPage() {
    // Tab switching
    document.querySelectorAll('.tab-pill[data-qtab]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-pill[data-qtab]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.qc-section').forEach(s => s.style.display='none');
            const sec = document.getElementById(btn.dataset.qtab);
            if (sec) sec.style.display='block';
        });
    });

    document.getElementById('qcTrendDays')?.addEventListener('change', loadQcTrend);
    initAiTab();
    document.getElementById('qcEvalLoadBtn')?.addEventListener('click', loadQcEvaluations);
    document.getElementById('qcTopLoadBtn')?.addEventListener('click', loadQcTopPerformers);
    document.getElementById('qcCoachLoadBtn')?.addEventListener('click', loadQcCoaching);
    document.getElementById('qcCallLoadBtn')?.addEventListener('click', loadQcRecentCalls);
    document.getElementById('qcSubmitBtn')?.addEventListener('click', submitQcEvaluation);

    if (!qcTrendChart) {
        const ctx = document.getElementById('qcTrendChart')?.getContext('2d');
        if (ctx) qcTrendChart = new Chart(ctx, {
            type: 'line',
            data: { labels:[], datasets:[
                { label:'Avg Score', data:[], borderColor:'#6366f1', backgroundColor:'rgba(99,102,241,0.08)', tension:0.35, fill:true },
                { label:'Evaluations', data:[], borderColor:'#94a3b8', tension:0.3, yAxisID:'y1' }
            ]},
            options:{ responsive:true, maintainAspectRatio:false,
                plugins:{ legend:{position:'top',labels:{usePointStyle:true}} },
                scales:{ y:{min:0,max:100,grid:{color:'#f1f5f9'}},
                         y1:{beginAtZero:true,position:'right',grid:{display:false}} } }
        });
    }
    if (!qcDistChart) {
        const ctx = document.getElementById('qcDistChart')?.getContext('2d');
        if (ctx) qcDistChart = new Chart(ctx, {
            type: 'doughnut',
            data: { labels:['Excellent 90+','Good 80-90','Average 70-80','Needs Work <70'],
                    datasets:[{data:[0,0,0,0], backgroundColor:['#22c55e','#3b82f6','#f59e0b','#ef4444'], borderWidth:0}] },
            options:{ responsive:true, maintainAspectRatio:false,
                plugins:{ legend:{position:'bottom',labels:{usePointStyle:true,padding:12}} }, cutout:'65%' }
        });
    }

    loadQcDashboard();
    loadQcAgentFilter();
    loadQcCheckpoints();
}

async function loadQcDashboard() {
    try {
        const [dash, trend] = await Promise.all([
            apiFetch('/api/qc/dashboard'),
            apiFetch('/api/qc/score-trend?days=30')
        ]);
        if (!dash.available) {
            document.getElementById('qcKpiGrid').innerHTML = `<div style="color:#94a3b8;padding:20px;grid-column:1/-1">QC tables not found in VICIdial database. Run evaluations from the CLI first.</div>`;
            return;
        }
        const s = dash.stats;
        document.getElementById('qcKpiGrid').innerHTML = `
            <div class="kpi-card kpi-purple"><div class="kpi-icon"><i class="fas fa-clipboard-check"></i></div>
                <div class="kpi-body"><div class="kpi-label">Total Evaluations</div><div class="kpi-value">${fmt(s.total)}</div><div class="kpi-sub">${s.agents} agents</div></div></div>
            <div class="kpi-card kpi-blue"><div class="kpi-icon"><i class="fas fa-star"></i></div>
                <div class="kpi-body"><div class="kpi-label">Avg QC Score</div><div class="kpi-value">${s.avg_score}%</div><div class="kpi-sub">${s.min_score}% – ${s.max_score}%</div></div></div>
            <div class="kpi-card kpi-green"><div class="kpi-icon"><i class="fas fa-trophy"></i></div>
                <div class="kpi-body"><div class="kpi-label">Excellent (90+)</div><div class="kpi-value">${fmt(s.distribution.excellent)}</div></div></div>
            <div class="kpi-card kpi-red"><div class="kpi-icon"><i class="fas fa-exclamation-triangle"></i></div>
                <div class="kpi-body"><div class="kpi-label">Needs Work</div><div class="kpi-value">${fmt(s.distribution.needs_work)}</div></div></div>`;

        if (qcDistChart) {
            const d = s.distribution;
            qcDistChart.data.datasets[0].data = [d.excellent, d.good, d.average, d.needs_work];
            qcDistChart.update();
        }
        if (qcTrendChart && trend.data?.length) {
            qcTrendChart.data.labels = trend.data.map(d => d.date.slice(5));
            qcTrendChart.data.datasets[0].data = trend.data.map(d => d.avg_score);
            qcTrendChart.data.datasets[1].data = trend.data.map(d => d.evals);
            qcTrendChart.update();
        }
    } catch(e) { console.error('QC dashboard error', e); }
}

async function loadQcTrend() {
    const days = document.getElementById('qcTrendDays')?.value || 30;
    try {
        const trend = await apiFetch(`/api/qc/score-trend?days=${days}`);
        if (qcTrendChart && trend.data?.length) {
            qcTrendChart.data.labels = trend.data.map(d => d.date.slice(5));
            qcTrendChart.data.datasets[0].data = trend.data.map(d => d.avg_score);
            qcTrendChart.data.datasets[1].data = trend.data.map(d => d.evals);
            qcTrendChart.update();
        }
    } catch(e) {}
}

async function loadQcAgentFilter() {
    try {
        const res = await apiFetch('/api/qc/evaluations?limit=1');
        if (!res.available) return;
        const agents = await apiFetch('/api/reports/agent-performance?start=2020-01-01&end=2099-01-01');
        ['qcEvalAgent','qcCallAgent'].forEach(id => {
            const sel = document.getElementById(id);
            if (!sel) return;
            sel.innerHTML = '<option value="">All Agents</option>';
            (agents.data||[]).forEach(a => {
                sel.innerHTML += `<option value="${esc(a.user)}">${esc(a.name)} (${esc(a.user)})</option>`;
            });
        });
    } catch(e) {}
}

async function loadQcEvaluations() {
    const agent = document.getElementById('qcEvalAgent')?.value || '';
    const days  = document.getElementById('qcEvalDays')?.value || 30;
    const tbody = document.getElementById('qcEvalBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="9" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>`;
    try {
        const res = await apiFetch(`/api/qc/evaluations?agent=${agent}&days=${days}`);
        if (!res.available) { tbody.innerHTML = `<tr><td colspan="9" class="loading-cell">QC not available</td></tr>`; return; }
        const meta = document.getElementById('qcEvalMeta');
        if (meta) meta.innerHTML = `<span class="status-pill">${res.data.length} evaluations</span>`;
        tbody.innerHTML = res.data.map(r => {
            const sc = scoreBadge(r.score);
            const ai = r.ai_score ? `<span class="score-badge ${scoreClass(r.ai_score)}">${r.ai_score}%</span>` : '—';
            return `<tr>
                <td style="font-weight:600">#${r.id}</td>
                <td>${r.date}</td>
                <td>${esc(r.agent_name)}</td>
                <td>${esc(r.campaign)}</td>
                <td class="num">${r.duration}</td>
                <td class="num">${sc}</td>
                <td class="num">${ai}</td>
                <td><span style="font-size:12px;color:#64748b">${r.source}</span></td>
                <td><button onclick="loadEvalDetail(${r.id})" style="background:none;border:1px solid #e2e8f0;padding:4px 10px;border-radius:6px;cursor:pointer;font-size:12px;color:#3b82f6">View</button></td>
            </tr>`;
        }).join('') || `<tr><td colspan="9" class="loading-cell">No evaluations found</td></tr>`;
    } catch(e) { tbody.innerHTML = `<tr><td colspan="9" class="loading-cell" style="color:#ef4444">${esc(e.message)}</td></tr>`; }
}

async function loadEvalDetail(id) {
    const drawer = document.getElementById('qcDetailDrawer');
    const content = document.getElementById('qcDetailContent');
    const title = document.getElementById('qcDetailTitle');
    if (!drawer || !content) return;
    drawer.style.display='block';
    content.innerHTML = `<div class="loading-cell"><i class="fas fa-spinner fa-spin"></i></div>`;
    try {
        const res = await apiFetch(`/api/qc/evaluation/${id}`);
        const r = res.data;
        if (title) title.textContent = `Evaluation #${id} — ${r.agent_name} — ${r.date}`;
        const aiLine = r.ai_score ? `<div>AI Score: <strong>${r.ai_score}%</strong> (confidence ${r.ai_confidence}%)</div>` : '';
        content.innerHTML = `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px;background:#f8fafc;border-radius:10px;padding:16px;">
                <div><div style="font-size:12px;color:#64748b">Agent</div><div style="font-weight:600">${esc(r.agent_name)} (${esc(r.agent)})</div></div>
                <div><div style="font-size:12px;color:#64748b">Campaign</div><div style="font-weight:600">${esc(r.campaign)}</div></div>
                <div><div style="font-size:12px;color:#64748b">Duration</div><div style="font-weight:600">${r.duration}</div></div>
                <div><div style="font-size:12px;color:#64748b">Source</div><div style="font-weight:600">${r.source}</div></div>
                <div><div style="font-size:12px;color:#64748b">QC Score</div><div style="font-size:22px;font-weight:800">${scoreBadge(r.score)}</div></div>
                <div><div style="font-size:12px;color:#64748b">AI Score</div>${aiLine||'<div style="color:#94a3b8">—</div>'}</div>
            </div>
            ${r.comments ? `<div style="background:#fffbeb;border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:14px"><strong>Notes:</strong> ${esc(r.comments)}</div>` : ''}
            <h4 style="margin-bottom:12px">Checkpoints</h4>
            ${r.checkpoints.map(cp => `
                <div class="checkpoint-row">
                    <span class="checkpoint-text">${cp.order}. ${esc(cp.text)}</span>
                    <div class="checkpoint-bar"><div class="checkpoint-bar-fill" style="width:${cp.pct}%;background:${cp.pct>=80?'#22c55e':cp.pct>=60?'#f59e0b':'#ef4444'}"></div></div>
                    <span style="font-weight:700;color:${cp.pct>=80?'#22c55e':cp.pct>=60?'#f59e0b':'#ef4444'}">${cp.score}/${cp.max}</span>
                    <span style="font-size:12px;color:#94a3b8">${cp.pct}%</span>
                </div>`).join('')}`;
    } catch(e) { content.innerHTML = `<div style="color:#ef4444">${esc(e.message)}</div>`; }
    drawer.scrollIntoView({ behavior:'smooth' });
}

async function loadQcTopPerformers() {
    const days = document.getElementById('qcTopDays')?.value || 30;
    const tbody = document.getElementById('qcTopBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="8" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>`;
    try {
        const res = await apiFetch(`/api/qc/top-performers?days=${days}`);
        if (!res.available) { tbody.innerHTML = `<tr><td colspan="8" class="loading-cell">QC not available</td></tr>`; return; }
        const medals = ['🥇','🥈','🥉'];
        tbody.innerHTML = res.data.map((r,i) => {
            const stability = r.stddev < 5 ? '🌟 Very Stable' : r.stddev < 10 ? '📊 Stable' : '⚠️ Variable';
            return `<tr>
                <td style="font-size:18px">${medals[i]||i+1}</td>
                <td style="font-weight:600">${esc(r.user)}</td>
                <td>${esc(r.name)}</td>
                <td class="num">${r.evals}</td>
                <td class="num">${scoreBadge(r.avg_score)}</td>
                <td class="num" style="font-size:12px;color:#64748b">${r.min_score}% – ${r.max_score}%</td>
                <td>${stability}</td>
                <td style="font-size:12px;color:#64748b">${r.ai_count>0?'🤖 AI+QA':'👤 Manual'}</td>
            </tr>`;
        }).join('') || `<tr><td colspan="8" class="loading-cell">No data</td></tr>`;
    } catch(e) { tbody.innerHTML = `<tr><td colspan="8" class="loading-cell" style="color:#ef4444">${esc(e.message)}</td></tr>`; }
}

async function loadQcCoaching() {
    const days = document.getElementById('qcCoachDays')?.value || 30;
    const tbody = document.getElementById('qcCoachBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="7" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>`;
    try {
        const res = await apiFetch(`/api/qc/coaching?days=${days}`);
        if (!res.available) { tbody.innerHTML = `<tr><td colspan="7" class="loading-cell">QC not available</td></tr>`; return; }
        tbody.innerHTML = res.data.map(r => {
            const priority = r.avg_score < 60 ? '<span style="color:#ef4444;font-weight:700">🔴 High</span>' :
                             r.avg_score < 70 ? '<span style="color:#f59e0b;font-weight:700">🟡 Medium</span>' :
                             '<span style="color:#3b82f6;font-weight:700">🔵 Low</span>';
            return `<tr>
                <td style="font-weight:600">${esc(r.user)}</td>
                <td>${esc(r.name)}</td>
                <td class="num">${r.evals}</td>
                <td class="num">${scoreBadge(r.avg_score)}</td>
                <td class="num">${scoreBadge(r.min_score)}</td>
                <td class="num">${r.below_threshold}</td>
                <td>${priority}</td>
            </tr>`;
        }).join('') || `<tr><td colspan="7" class="loading-cell">No agents need coaching</td></tr>`;
    } catch(e) { tbody.innerHTML = `<tr><td colspan="7" class="loading-cell" style="color:#ef4444">${esc(e.message)}</td></tr>`; }
}

async function loadQcCheckpoints() {
    try {
        const res = await apiFetch('/api/qc/checkpoints');
        if (!res.available) return;
        qcCheckpointsData = res.data;
    } catch(e) {}
}

async function loadQcRecentCalls() {
    const agent = document.getElementById('qcCallAgent')?.value || '';
    const tbody = document.getElementById('qcRecentCallsBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="6" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>`;
    try {
        const res = await apiFetch(`/api/qc/recent-calls?agent=${agent}&limit=30`);
        tbody.innerHTML = res.data.map(r => `<tr>
            <td style="font-size:12px;color:#64748b">${r.uniqueid}</td>
            <td>${r.date}</td>
            <td>${esc(r.agent_name)}</td>
            <td>${esc(r.campaign)}</td>
            <td class="num">${r.duration}</td>
            <td><button onclick="selectCall('${r.uniqueid}','${esc(r.agent_name)}','${r.duration}')"
                style="background:#3b82f6;color:white;border:none;padding:4px 12px;border-radius:6px;cursor:pointer;font-size:12px">Select</button></td>
        </tr>`).join('') || `<tr><td colspan="6" class="loading-cell">No unevaluated calls found</td></tr>`;
    } catch(e) { tbody.innerHTML = `<tr><td colspan="6" class="loading-cell" style="color:#ef4444">${esc(e.message)}</td></tr>`; }
}

function selectCall(uid, agentName, duration) {
    qcSelectedUID = uid;
    document.getElementById('qcSelectedUID').textContent = uid;
    document.getElementById('qcSelectedAgent').textContent = agentName;
    document.getElementById('qcSelectedDuration').textContent = duration;
    document.getElementById('qcSelectedCall').style.display='block';
    renderCheckpointsForm();
}

function renderCheckpointsForm() {
    const container = document.getElementById('qcCheckpointsList');
    const form = document.getElementById('qcCheckpointsForm');
    if (!container || !form) return;
    if (!qcCheckpointsData.length) { form.style.display='block'; container.innerHTML='<p style="color:#94a3b8">No checkpoints configured</p>'; return; }
    container.innerHTML = qcCheckpointsData.map(cp => `
        <div class="checkpoint-row">
            <span class="checkpoint-text">${cp.order}. ${esc(cp.text)}</span>
            <div class="checkpoint-bar"><div class="checkpoint-bar-fill" id="bar_${cp.id}" style="width:0%"></div></div>
            <input type="number" class="checkpoint-score-input" id="score_${cp.id}"
                   min="0" max="${cp.max_points}" step="0.5" value="0"
                   oninput="updateCheckpointBar(${cp.id},${cp.max_points})">
            <span class="checkpoint-max">/ ${cp.max_points}</span>
        </div>`).join('');
    form.style.display='block';
    updateLiveScore();
}

function updateCheckpointBar(id, max) {
    const input = document.getElementById(`score_${id}`);
    const bar   = document.getElementById(`bar_${id}`);
    if (!input || !bar) return;
    const pct = Math.min(parseFloat(input.value)||0, max) / max * 100;
    bar.style.width = pct + '%';
    bar.style.background = pct>=80?'#22c55e':pct>=60?'#f59e0b':'#ef4444';
    updateLiveScore();
}

function updateLiveScore() {
    if (!qcCheckpointsData.length) return;
    let total=0, possible=0;
    qcCheckpointsData.forEach(cp => {
        const input = document.getElementById(`score_${cp.id}`);
        total    += Math.min(parseFloat(input?.value||0), cp.max_points);
        possible += cp.max_points;
    });
    const pct = possible ? (total/possible*100).toFixed(1) : 0;
    const el = document.getElementById('qcLiveScore');
    if (el) { el.textContent = `Score: ${pct}%`; el.style.color = pct>=80?'#22c55e':pct>=70?'#f59e0b':'#ef4444'; }
}

async function submitQcEvaluation() {
    const uid = qcSelectedUID || document.getElementById('qcManualUID')?.value?.trim();
    if (!uid) { alert('Please select a call or enter a UniqueID'); return; }
    if (!qcCheckpointsData.length) { alert('No checkpoints loaded'); return; }
    const scores = {};
    qcCheckpointsData.forEach(cp => {
        const input = document.getElementById(`score_${cp.id}`);
        scores[cp.id] = parseFloat(input?.value||0);
    });
    const comments = document.getElementById('qcComments')?.value || '';
    const result = document.getElementById('qcSubmitResult');
    if (result) result.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Saving...`;
    try {
        const res = await fetch('/api/qc/add-evaluation', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ uniqueid: uid, scores, comments })
        });
        const data = await res.json();
        if (data.success) {
            if (result) result.innerHTML = `<div style="color:#22c55e;font-weight:700">✅ Saved! Score: ${data.total_score}% (ID #${data.result_id})</div>`;
            qcSelectedUID = '';
            document.getElementById('qcSelectedCall').style.display='none';
            document.getElementById('qcCheckpointsForm').style.display='none';
        } else {
            if (result) result.innerHTML = `<div style="color:#ef4444">Error: ${esc(data.error)}</div>`;
        }
    } catch(e) { if (result) result.innerHTML = `<div style="color:#ef4444">${esc(e.message)}</div>`; }
}

// ══════════════════════════════════════════════════════════
// AGENT MAPPING
// ══════════════════════════════════════════════════════════

let vicidialUsers = [];
let mappingChanges = {};

async function loadMappingPage() {
    const tbody = document.getElementById('mappingTableBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="5" class="loading-cell"><i class="fas fa-spinner fa-spin"></i> Loading...</td></tr>`;
    try {
        const [agents, users] = await Promise.all([
            apiFetch('/api/mapping/agents'),
            apiFetch('/api/mapping/vicidial-users')
        ]);
        vicidialUsers = users.data || [];
        mappingChanges = {};

        const stats = document.getElementById('mappingStats');
        if (stats) stats.innerHTML = `
            <span class="status-pill" style="color:#22c55e">${agents.linked} linked</span>
            <span class="status-pill" style="color:#f59e0b">${agents.unlinked} unlinked</span>`;

        const badge = document.getElementById('mappingBadge');
        if (badge) { if (agents.unlinked>0) { badge.textContent=agents.unlinked; badge.style.display='inline'; } else badge.style.display='none'; }

        tbody.innerHTML = agents.data.map(a => {
            const opts = `<option value="">— Not linked —</option>` +
                vicidialUsers.map(u => `<option value="${esc(u.user)}" ${a.altria_username===u.user?'selected':''}>${esc(u.full_name)} (${esc(u.user)})</option>`).join('');
            const linked = a.altria_username ? 'linked' : 'unlinked';
            return `<tr id="mrow_${CSS.escape(a.pinktools_name)}">
                <td style="font-weight:600">${esc(a.pinktools_name)}</td>
                <td class="num">${fmt(a.total_emails)}</td>
                <td style="color:#94a3b8;font-size:13px">${a.last_seen||'—'}</td>
                <td>
                    <select class="mapping-select ${linked}" id="msel_${esc(a.pinktools_name)}"
                        onchange="onMappingChange('${esc(a.pinktools_name)}',this)">
                        ${opts}
                    </select>
                </td>
                <td id="mstatus_${esc(a.pinktools_name)}">
                    ${a.altria_username
                        ? `<span style="color:#22c55e;font-weight:600">✓ Linked</span>`
                        : `<span style="color:#f59e0b;font-weight:600">⚠ Unlinked</span>`}
                </td>
            </tr>`;
        }).join('');

        document.getElementById('mappingSaveAllBtn')?.addEventListener('click', saveAllMappings);

    } catch(e) { tbody.innerHTML = `<tr><td colspan="5" class="loading-cell" style="color:#ef4444">${esc(e.message)}</td></tr>`; }
}

function onMappingChange(ptName, sel) {
    mappingChanges[ptName] = sel.value;
    sel.className = 'mapping-select ' + (sel.value ? 'linked' : 'unlinked');
    const status = document.getElementById(`mstatus_${ptName}`);
    if (status) status.innerHTML = sel.value
        ? `<span style="color:#3b82f6;font-weight:600">● Changed</span>`
        : `<span style="color:#f59e0b;font-weight:600">⚠ Unlinked</span>`;
}

async function saveAllMappings() {
    const msg = document.getElementById('mappingSaveMsg');
    if (!Object.keys(mappingChanges).length) {
        if (msg) { msg.style.display='block'; msg.style.background='#fef9c3'; msg.style.color='#92400e'; msg.textContent='No changes to save.'; }
        return;
    }
    const payload = Object.entries(mappingChanges).map(([pt, al]) => ({ pinktools_name: pt, altria_username: al }));
    try {
        const res = await fetch('/api/mapping/save', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            if (msg) { msg.style.display='block'; msg.style.background='#dcfce7'; msg.style.color='#15803d'; msg.textContent=`✅ ${data.saved} mapping(s) saved successfully!`; }
            mappingChanges = {};
            setTimeout(() => loadMappingPage(), 1000);
        }
    } catch(e) {
        if (msg) { msg.style.display='block'; msg.style.background='#fee2e2'; msg.style.color='#b91c1c'; msg.textContent=`Error: ${e.message}`; }
    }
}

// ══════════════════════════════════════════════════════════
// AI AUTO-SCORE
// ══════════════════════════════════════════════════════════

let aiJobId = null;
let aiPollTimer = null;

function initAiTab() {
    document.getElementById('aiCallsLoadBtn')?.addEventListener('click', loadAiCalls);

    // Populate campaign + agent dropdowns from existing selects
    const campSrc = document.getElementById('qcCallAgent');
    const aiCamp  = document.getElementById('aiCampaign');
    const aiAgent = document.getElementById('aiAgent');
    if (aiCamp) {
        apiFetch('/api/campaigns/performance?days=30').then(res => {
            (res.data||[]).forEach(c => {
                const id = c.campaign_id || c.campaign;
                aiCamp.innerHTML += `<option value="${esc(id)}">${esc(id)}</option>`;
            });
        }).catch(()=>{});
    }
    if (aiAgent && campSrc) {
        aiAgent.innerHTML = campSrc.innerHTML;
    }
}

async function loadAiCalls() {
    const campaign = document.getElementById('aiCampaign')?.value || '';
    const agent    = document.getElementById('aiAgent')?.value    || '';
    const days     = document.getElementById('aiDays')?.value     || 7;
    const tbody    = document.getElementById('aiCallsBody');
    const count    = document.getElementById('aiCallsCount');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="6" class="loading-cell"><i class="fas fa-spinner fa-spin"></i> Searching for recordings…</td></tr>`;
    try {
        const res = await apiFetch(`/api/ai/calls?campaign=${campaign}&agent=${agent}&days=${days}`);
        const calls = res.data || [];
        if (count) count.innerHTML = `<span class="status-pill">${calls.length} calls with recordings</span>`;

        if (!calls.length) {
            tbody.innerHTML = `<tr><td colspan="6" class="loading-cell">No unevaluated recordings found for this filter</td></tr>`;
            return;
        }

        tbody.innerHTML = calls.map(c => `<tr>
            <td style="font-size:13px">${c.date.slice(0,16)}</td>
            <td>${esc(c.agent_name)}</td>
            <td>${esc(c.campaign)}</td>
            <td class="num">${c.duration_fmt}</td>
            <td style="font-size:12px;color:#64748b">${esc(c.phone)}</td>
            <td>
                <button class="btn-primary" style="padding:5px 12px;font-size:12px;"
                    onclick="startAiScore('${esc(c.uniqueid)}','${esc(c.phone)}','${esc(c.date)}','${esc(c.agent)}','${esc(c.campaign)}',${c.duration},'${esc(c.agent_name)}')">
                    <i class="fas fa-robot"></i> Score
                </button>
            </td>
        </tr>`).join('');
    } catch(e) {
        tbody.innerHTML = `<tr><td colspan="6" class="loading-cell" style="color:#ef4444">${esc(e.message)}</td></tr>`;
    }
}

async function startAiScore(uniqueid, phone, callDate, agent, campaign, duration, agentName) {
    // Show & reset progress panel
    const panel    = document.getElementById('aiProgressPanel');
    const info     = document.getElementById('aiProgressInfo');
    const bar      = document.getElementById('aiProgressBar');
    const logEl    = document.getElementById('aiLog');
    const resultEl = document.getElementById('aiResultPanel');

    if (resultEl) resultEl.style.display = 'none';
    if (panel)    panel.style.display    = 'block';
    if (info)     info.textContent       = `Scoring: ${agentName} — ${campaign} — ${callDate.slice(0,10)}`;
    if (bar)      bar.style.width        = '0%';
    if (logEl)    logEl.innerHTML        = '';
    panel?.scrollIntoView({ behavior:'smooth' });

    // Clear any existing poll
    if (aiPollTimer) clearInterval(aiPollTimer);

    try {
        const res = await fetch('/api/ai/score', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uniqueid, phone, call_date: callDate,
                                   agent, agent_name: agentName, campaign, duration })
        });
        const data = await res.json();
        if (!data.success) throw new Error(data.error);
        aiJobId = data.job_id;
        // Start polling every 2 seconds
        aiPollTimer = setInterval(pollAiJob, 2000);
    } catch(e) {
        if (logEl) logEl.innerHTML += `<div style="color:#ef4444">❌ ${esc(e.message)}</div>`;
    }
}

async function pollAiJob() {
    if (!aiJobId) return;
    try {
        const res  = await apiFetch(`/api/ai/status/${aiJobId}`);
        const bar  = document.getElementById('aiProgressBar');
        const logEl= document.getElementById('aiLog');

        if (bar)   bar.style.width = res.progress + '%';
        if (logEl) {
            logEl.innerHTML = (res.log||[]).map(l =>
                `<div style="color:${l.startsWith('ERROR')?'#ef4444':l==='Done!'?'#22c55e':'#94a3b8'}">» ${esc(l)}</div>`
            ).join('');
            logEl.scrollTop = logEl.scrollHeight;
        }

        if (res.status === 'complete') {
            clearInterval(aiPollTimer);
            aiPollTimer = null;
            showAiResult(res.result);
        } else if (res.status === 'error') {
            clearInterval(aiPollTimer);
            aiPollTimer = null;
            if (logEl) logEl.innerHTML += `<div style="color:#ef4444;margin-top:8px">❌ ${esc(res.error)}</div>`;
        }
    } catch(e) {}
}

function cancelAiJob() {
    clearInterval(aiPollTimer);
    aiPollTimer = null;
    aiJobId = null;
    document.getElementById('aiProgressPanel').style.display = 'none';
}

function showAiResult(r) {
    // Hide progress panel
    const panel = document.getElementById('aiProgressPanel');
    if (panel) panel.style.display = 'none';

    const scoreColor = r.score>=90?'#22c55e':r.score>=80?'#3b82f6':r.score>=70?'#f59e0b':'#ef4444';
    const bgColor    = r.score>=90?'#f0fdf4':r.score>=80?'#eff6ff':r.score>=70?'#fffbeb':'#fef2f2';
    const isNormal   = r.call_type === 'NORMAL';

    // Subtitle — Evaluation # + timestamp
    const sub = document.getElementById('aiModalSubtitle');
    if (sub) sub.textContent = `Evaluation #${r.result_id} · ${new Date().toLocaleString()}`;

    // Score banner — call info strip + scores
    document.getElementById('aiModalBanner').innerHTML = `
        <!-- ── Call info strip ── -->
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;
                    padding:10px 0 14px;border-bottom:1px solid #f1f5f9;margin-bottom:16px;">
            <div style="display:flex;align-items:center;gap:8px;
                        background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:8px 14px;">
                <div style="width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#3b82f6,#6366f1);
                            display:flex;align-items:center;justify-content:center;color:white;font-size:15px;flex-shrink:0;">👤</div>
                <div>
                    <div style="font-size:14px;font-weight:700;color:#0f172a;">${esc(r.agent_name || r.agent || '—')}</div>
                    <div style="font-size:11px;color:#64748b;margin-top:1px;">@${esc(r.agent||'—')}</div>
                </div>
            </div>
            <div style="display:flex;align-items:center;gap:6px;
                        background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:8px 14px;">
                <span style="font-size:16px;">📞</span>
                <div>
                    <div style="font-size:13px;font-weight:600;color:#1e293b;font-family:monospace;">${esc(r.phone || '—')}</div>
                    <div style="font-size:11px;color:#64748b;">Phone number</div>
                </div>
            </div>
            <div style="display:flex;align-items:center;gap:6px;
                        background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:8px 14px;">
                <span style="font-size:16px;">📢</span>
                <div>
                    <div style="font-size:13px;font-weight:600;color:#1e293b;">${esc(r.campaign || '—')}</div>
                    <div style="font-size:11px;color:#64748b;">Campaign</div>
                </div>
            </div>
            <div style="display:flex;align-items:center;gap:6px;
                        background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:8px 14px;">
                <span style="font-size:16px;">🕐</span>
                <div>
                    <div style="font-size:13px;font-weight:600;color:#1e293b;">${esc(r.duration_fmt || '—')}</div>
                    <div style="font-size:11px;color:#64748b;">${r.call_date ? r.call_date.slice(0,10) : '—'}</div>
                </div>
            </div>
        </div>
        <!-- ── Score cards ── -->
        <div style="display:flex; gap:20px; flex-wrap:wrap; align-items:stretch;">
            <div style="flex:1; min-width:140px; background:${bgColor}; border-radius:14px; padding:20px 24px; text-align:center; border:2px solid ${scoreColor}20;">
                <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">AI Score</div>
                <div style="font-size:52px;font-weight:900;color:${scoreColor};line-height:1.1;margin:6px 0;">${r.score}%</div>
                ${!isNormal ? `<span style="display:inline-block;background:#fef3c7;color:#92400e;padding:3px 12px;border-radius:20px;font-size:12px;font-weight:700;margin-top:4px;">⚠ ${esc(r.call_type)}</span>` : `<span style="display:inline-block;background:#dcfce7;color:#15803d;padding:3px 12px;border-radius:20px;font-size:12px;font-weight:700;margin-top:4px;">✓ NORMAL</span>`}
            </div>
            <div style="flex:1; min-width:140px; background:#faf5ff; border-radius:14px; padding:20px 24px; text-align:center; border:2px solid #a855f720;">
                <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Confidence</div>
                <div style="font-size:52px;font-weight:900;color:#6366f1;line-height:1.1;margin:6px 0;">${r.confidence}%</div>
                <span style="font-size:12px;color:#64748b">${r.confidence>=85?'High':r.confidence>=70?'Medium':'Low'} confidence</span>
            </div>
            <div style="flex:2; min-width:220px; background:#f8fafc; border-radius:14px; padding:20px 24px; border:1px solid #e2e8f0;">
                <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;">AI Notes</div>
                <div style="font-size:14px;color:#1e293b;line-height:1.6;">${esc(r.notes)}</div>
                ${r.ghost_reason ? `<div style="margin-top:8px;padding:8px 12px;background:#fef3c7;border-radius:8px;font-size:12px;color:#92400e;line-height:1.5;">⚠ ${esc(r.ghost_reason)}</div>` : ''}
            </div>
        </div>
    `;

    // Checkpoints tab
    document.getElementById('tab-checkpoints').innerHTML = (r.checkpoints||[]).map(cp => {
        const pct = cp.max > 0 ? Math.round(cp.score/cp.max*100) : 0;
        const col = pct>=80?'#22c55e':pct>=60?'#f59e0b':'#ef4444';
        return `<div class="cp-row">
            <span class="cp-label">${esc(cp.text)}</span>
            <div class="cp-bar-wrap"><div class="cp-bar-fill" style="width:${pct}%;background:${col}"></div></div>
            <span class="cp-score" style="color:${col}">${cp.score}/${cp.max}</span>
        </div>`;
    }).join('') || '<p style="color:#94a3b8">No checkpoint data</p>';

    // Transcript tab
    document.getElementById('tab-transcript').innerHTML = r.transcript_preview
        ? `<div style="background:#0f172a;border-radius:12px;padding:20px;color:#94a3b8;font-family:monospace;font-size:13px;line-height:1.8;max-height:320px;overflow-y:auto;">
            <div style="color:#22c55e;font-size:11px;font-weight:700;margin-bottom:12px;text-transform:uppercase;">Whisper Transcript Preview</div>
            ${esc(r.transcript_preview)}
           </div>`
        : '<p style="color:#94a3b8;padding:20px">No transcript available</p>';

    // Analysis tab
    document.getElementById('tab-analysis').innerHTML = `
        <div style="display:grid;gap:12px;">
            <div style="background:#f8fafc;border-radius:10px;padding:16px;">
                <div style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;margin-bottom:8px;">Call Classification</div>
                <div style="font-size:15px;font-weight:600;color:${isNormal?'#22c55e':'#f59e0b'}">${r.call_type}</div>
                ${r.ghost_reason ? `<div style="font-size:13px;color:#475569;margin-top:4px;">${esc(r.ghost_reason)}</div>` : ''}
            </div>
            <div style="background:#f8fafc;border-radius:10px;padding:16px;">
                <div style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;margin-bottom:8px;">Score Breakdown</div>
                ${(r.checkpoints||[]).map(cp => {
                    const pct = cp.max > 0 ? Math.round(cp.score/cp.max*100) : 0;
                    const col = pct>=80?'#22c55e':pct>=60?'#f59e0b':'#ef4444';
                    return `<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:13px;border-bottom:1px solid #f1f5f9;">
                        <span style="color:#475569">${esc(cp.text)}</span>
                        <span style="font-weight:700;color:${col}">${pct}%</span>
                    </div>`;
                }).join('')}
            </div>
        </div>`;

    // Save info
    document.getElementById('aiModalSaveInfo').innerHTML = `✅ Saved as Evaluation #${r.result_id}`;

    // Reset to first tab
    document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
    document.querySelector('.modal-tab[data-tab="checkpoints"]')?.classList.add('active');
    document.querySelectorAll('[id^="tab-"]').forEach(t => t.style.display='none');
    document.getElementById('tab-checkpoints').style.display='block';

    // Show modal
    document.getElementById('aiModal').style.display = 'block';
    document.body.style.overflow = 'hidden';

    // Refresh calls list
    loadAiCalls();
}

function closeAiModal() {
    document.getElementById('aiModal').style.display = 'none';
    document.body.style.overflow = '';
}

function switchModalTab(tab, btn) {
    document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('[id^="tab-"]').forEach(t => t.style.display='none');
    document.getElementById('tab-' + tab).style.display = 'block';
}

function switchToEvaluations() {
    closeAiModal();
    // Navigate to QC Evaluations tab
    document.querySelector('.nav-item[data-page="quality"]')?.click();
    setTimeout(() => {
        document.querySelector('.tab-pill[data-qtab="qc-evaluations"]')?.click();
    }, 200);
}

// Close modal on backdrop click
document.addEventListener('click', e => {
    const modal = document.getElementById('aiModal');
    if (e.target === modal) closeAiModal();
});

// ══════════════════════════════════════════════════════════
// AGENT MANAGEMENT
// ══════════════════════════════════════════════════════════

let agentsList = [];

function initAgentMgmt() {
    // Tab switching
    document.querySelectorAll('.tab-pill[data-atab]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-pill[data-atab]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.ag-section').forEach(s => s.style.display='none');
            const sec = document.getElementById(btn.dataset.atab);
            if (sec) sec.style.display = 'block';
            // Auto-load on first visit
            const tab = btn.dataset.atab;
            if (tab === 'ag-realtime')  loadAgentRealtime();
            if (tab === 'ag-inbound')   loadInboundGroups();
            if (tab === 'ag-outbound')  loadOutboundMonitor();
        });
    });

    // Load agents list for dropdowns
    _loadAgentDropdowns();

    // Button handlers
    document.getElementById('agLookupBtn')?.addEventListener('click', loadAgentLookup);
    document.getElementById('agPerfBtn')?.addEventListener('click', loadAgentPerformance);
    document.getElementById('agLoginBtn')?.addEventListener('click', loadAgentLoginHistory);
    document.getElementById('agNotesLoadBtn')?.addEventListener('click', loadAgentNotes);
    document.getElementById('agNoteSaveBtn')?.addEventListener('click', saveAgentNote);
    document.getElementById('agTopBtn')?.addEventListener('click', loadAgentTopPerformers);
    document.getElementById('agSalesBtn')?.addEventListener('click', loadAgentSalesDashboard);
}

// ── Agent dropdown loader (shared across all tabs) ────────
async function _loadAgentDropdowns() {
    // Show loading state in all selects
    ['agLookupSelect','agLoginSelect','agNotesSelect'].forEach(id => {
        const sel = document.getElementById(id);
        if (sel) sel.innerHTML = '<option value="">Loading agents…</option>';
    });

    try {
        const res = await apiFetch('/api/agents/list');
        agentsList = res.data || [];

        if (agentsList.length === 0) {
            ['agLookupSelect','agLoginSelect','agNotesSelect'].forEach(id => {
                const sel = document.getElementById(id);
                if (sel) sel.innerHTML = '<option value="">No agents found</option>';
            });
            return;
        }

        const opts = '<option value="">— Select Agent —</option>' +
            agentsList.map(a =>
                `<option value="${esc(a.user)}">${esc(a.name)} (${esc(a.user)})</option>`
            ).join('');

        ['agLookupSelect','agLoginSelect','agNotesSelect'].forEach(id => {
            const sel = document.getElementById(id);
            if (sel) sel.innerHTML = opts;
        });

        // Campaign filter for performance tab
        try {
            const cr = await apiFetch('/api/campaigns/performance?days=30');
            const sel = document.getElementById('agPerfCampaign');
            if (sel && cr.data) {
                cr.data.forEach(c => {
                    const id = c.campaign_id || c.campaign;
                    sel.innerHTML += `<option value="${esc(id)}">${esc(id)}</option>`;
                });
            }
        } catch(e) { /* campaigns filter optional */ }

    } catch(e) {
        console.error('Failed to load agents:', e);
        ['agLookupSelect','agLoginSelect','agNotesSelect'].forEach(id => {
            const sel = document.getElementById(id);
            if (sel) sel.innerHTML = `<option value="">Error: ${esc(e.message)}</option>`;
        });
    }
}

// ── 1. Agent Lookup ───────────────────────────────────────
async function loadAgentLookup() {
    const username = document.getElementById('agLookupSelect')?.value;
    const result   = document.getElementById('agLookupResult');
    if (!username || !result) return;
    result.innerHTML = `<div class="loading-cell"><i class="fas fa-spinner fa-spin"></i></div>`;
    try {
        const res = await apiFetch(`/api/agents/lookup/${username}`);
        const a   = res.data;
        result.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 2fr;gap:20px;">
            <!-- Profile card -->
            <div class="card">
                <div style="text-align:center;padding:20px 0;">
                    <div style="width:70px;height:70px;border-radius:50%;background:linear-gradient(135deg,#3b82f6,#8b5cf6);color:white;font-size:28px;font-weight:800;display:flex;align-items:center;justify-content:center;margin:0 auto 14px;">
                        ${esc(a.name.charAt(0).toUpperCase())}
                    </div>
                    <div style="font-size:18px;font-weight:700">${esc(a.name)}</div>
                    <div style="color:#64748b;font-size:13px;margin-top:4px">@${esc(a.user)}</div>
                    <div style="margin-top:8px"><span class="badge ${a.active==='Y'?'badge-ready':'badge-default'}">${a.active==='Y'?'Active':'Inactive'}</span></div>
                </div>
                <div style="border-top:1px solid #f1f5f9;padding-top:14px;">
                    ${[['Campaign',a.campaign],['Level','Level '+a.level],['Email',a.email||'—']].map(([l,v])=>`
                    <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:13px;border-bottom:1px solid #f8fafc;">
                        <span style="color:#64748b">${l}</span><strong>${esc(v||'—')}</strong>
                    </div>`).join('')}
                </div>
                <div style="margin-top:16px;display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                    ${[['Calls (30d)',a.total_calls_30d],['Talk (30d)',a.total_talk_30d],['Avg Call',a.avg_talk_30d],['Last Active',a.last_active?.slice(0,10)||'—']].map(([l,v])=>`
                    <div style="background:#f8fafc;border-radius:8px;padding:10px;text-align:center;">
                        <div style="font-size:10px;color:#64748b;font-weight:700;text-transform:uppercase">${l}</div>
                        <div style="font-size:16px;font-weight:800;color:#0f172a;margin-top:4px">${v}</div>
                    </div>`).join('')}
                </div>
            </div>

            <!-- Activity + Recent calls -->
            <div>
                <div class="card" style="margin-bottom:16px;">
                    <h3 style="margin-bottom:14px">Last 7 Days Activity</h3>
                    ${a.daily.length ? `
                    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:10px;">
                        ${a.daily.map(d=>`
                        <div style="background:#f8fafc;border-radius:8px;padding:10px;text-align:center;">
                            <div style="font-size:11px;color:#64748b">${d.date.slice(5)}</div>
                            <div style="font-size:20px;font-weight:800;color:#3b82f6">${d.calls}</div>
                            <div style="font-size:11px;color:#94a3b8">${d.talk}</div>
                        </div>`).join('')}
                    </div>` : '<p style="color:#94a3b8">No activity in last 7 days</p>'}
                </div>
                <div class="card">
                    <h3 style="margin-bottom:14px">Recent Calls</h3>
                    <div class="table-wrap">
                    <table class="data-table">
                        <thead><tr><th>Date/Time</th><th>Campaign</th><th>Phone</th><th class="num">Duration</th><th>Result</th></tr></thead>
                        <tbody>${a.recent_calls.map(c=>`
                        <tr><td style="font-size:12px">${c.date}</td><td>${esc(c.campaign)}</td>
                            <td style="font-size:12px;color:#64748b">${esc(c.phone)}</td>
                            <td class="num">${c.duration}</td>
                            <td><span style="font-size:11px;color:#64748b">${esc(c.result)}</span></td>
                        </tr>`).join('') || '<tr><td colspan="5" class="loading-cell">No recent calls</td></tr>'}
                        </tbody>
                    </table></div>
                </div>
            </div>
        </div>`;
    } catch(e) { result.innerHTML = `<div class="loading-cell" style="color:#ef4444">${esc(e.message)}</div>`; }
}

// ── 2. Agent Performance ──────────────────────────────────
async function loadAgentPerformance() {
    const days     = document.getElementById('agPerfDays')?.value || 7;
    const campaign = document.getElementById('agPerfCampaign')?.value || '';
    const tbody    = document.getElementById('agPerfBody');
    const meta     = document.getElementById('agPerfMeta');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="8" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>`;
    try {
        const res = await apiFetch(`/api/agents/performance?days=${days}&campaign=${campaign}`);
        if (meta) meta.innerHTML = `<span class="status-pill">${res.data.length} agents · ${days} days</span>`;
        const medals = ['🥇','🥈','🥉'];
        tbody.innerHTML = res.data.map((a,i) => `<tr>
            <td style="font-weight:600">${esc(a.user)}</td>
            <td>${esc(a.name)}</td>
            <td class="num">${fmt(a.calls)}</td>
            <td class="num">${fmt(a.valid)}</td>
            <td class="num">${a.days_active}</td>
            <td class="num">${a.talk_time}</td>
            <td class="num">${a.avg_call}</td>
            <td class="num" style="font-weight:700;color:#6366f1">${a.minutes}</td>
        </tr>`).join('') || `<tr><td colspan="8" class="loading-cell">No data</td></tr>`;
    } catch(e) { tbody.innerHTML = `<tr><td colspan="8" class="loading-cell" style="color:#ef4444">${esc(e.message)}</td></tr>`; }
}

// ── 3. Real-time ──────────────────────────────────────────
async function loadAgentRealtime() {
    const grid = document.getElementById('agRealtimeGrid');
    if (!grid) return;
    try {
        const res = await apiFetch('/api/agent/status');
        const agents = res.agents || [];
        if (!agents.length) { grid.innerHTML = '<p style="color:#94a3b8;padding:20px">No active agents</p>'; return; }
        const statusStyle = {
            INCALL:  {bg:'#dbeafe',col:'#1d4ed8',icon:'📞'},
            READY:   {bg:'#dcfce7',col:'#15803d',icon:'✅'},
            PAUSE:   {bg:'#fef9c3',col:'#92400e',icon:'⏸️'},
            RING:    {bg:'#e0e7ff',col:'#4338ca',icon:'🔔'},
            QUEUE:   {bg:'#fce7f3',col:'#9d174d',icon:'⏳'},
            CLOSER:  {bg:'#f3e8ff',col:'#7e22ce',icon:'🎯'}
        };
        grid.innerHTML = agents.map(a => {
            const s = statusStyle[a.status] || {bg:'#f1f5f9',col:'#475569',icon:'👤'};
            return `<div style="background:${s.bg};border-radius:14px;padding:16px;border:1px solid ${s.col}20;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                    <div>
                        <div style="font-weight:700;font-size:14px;color:#0f172a">${esc(a.name)}</div>
                        <div style="font-size:12px;color:#64748b;margin-top:2px">@${esc(a.user)}</div>
                    </div>
                    <span style="font-size:18px">${s.icon}</span>
                </div>
                <div style="margin-top:10px;display:flex;justify-content:space-between;align-items:center;">
                    <span style="background:${s.col};color:white;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700">${a.status}</span>
                    <span style="font-size:12px;color:${a.minutes>30?'#ef4444':a.minutes>15?'#f59e0b':'#64748b'};font-weight:600">${a.minutes}m</span>
                </div>
                <div style="margin-top:6px;font-size:11px;color:#64748b">${esc(a.campaign)} · ${a.last_call}</div>
            </div>`;
        }).join('');
    } catch(e) { grid.innerHTML = `<div style="color:#ef4444">${esc(e.message)}</div>`; }
}

// ── 4. Login History ──────────────────────────────────────
async function loadAgentLoginHistory() {
    const username = document.getElementById('agLoginSelect')?.value;
    const days     = document.getElementById('agLoginDays')?.value || 7;
    const result   = document.getElementById('agLoginResult');
    if (!username || !result) return;
    result.innerHTML = `<div class="loading-cell"><i class="fas fa-spinner fa-spin"></i></div>`;
    try {
        const res = await apiFetch(`/api/agents/login-history/${username}?days=${days}`);
        const days_data = res.data || [];
        if (!days_data.length) { result.innerHTML = '<div class="card"><p style="color:#94a3b8;padding:20px">No login data found</p></div>'; return; }
        result.innerHTML = days_data.map(d => `
            <div class="card" style="margin-bottom:14px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                    <h3 style="margin:0">${d.date}</h3>
                    <div style="display:flex;gap:10px;">
                        <span class="status-pill">${d.event_count} events</span>
                        <span class="status-pill" style="color:#6366f1">🕐 ${d.total_talk}</span>
                    </div>
                </div>
                <div style="max-height:200px;overflow-y:auto;">
                <table class="data-table">
                    <thead><tr><th>Time</th><th>Status</th><th>Campaign</th><th class="num">Talk</th><th class="num">Wait</th></tr></thead>
                    <tbody>${d.events.slice(0,30).map(e => {
                        const sc = {INCALL:'badge-incall',READY:'badge-ready',PAUSE:'badge-pause'}[e.status]||'badge-default';
                        return `<tr>
                            <td style="font-size:12px">${e.time.slice(11,19)}</td>
                            <td><span class="badge ${sc}">${e.status}</span></td>
                            <td style="font-size:12px">${esc(e.campaign)}</td>
                            <td class="num" style="font-size:12px">${e.talk_sec}s</td>
                            <td class="num" style="font-size:12px">${e.wait_sec}s</td>
                        </tr>`;
                    }).join('')}</tbody>
                </table></div>
            </div>`).join('');
    } catch(e) { result.innerHTML = `<div style="color:#ef4444;padding:20px">${esc(e.message)}</div>`; }
}

// ── 5. Notes ──────────────────────────────────────────────
async function loadAgentNotes() {
    const username = document.getElementById('agNotesSelect')?.value;
    const list     = document.getElementById('agNotesList');
    if (!username || !list) return;
    list.innerHTML = `<div class="loading-cell"><i class="fas fa-spinner fa-spin"></i></div>`;
    try {
        const res   = await apiFetch(`/api/agents/notes/${username}`);
        const notes = res.data || [];
        const typeStyle = {coaching:'#3b82f6',warning:'#ef4444',achievement:'#22c55e',feedback:'#a855f7',general:'#64748b'};
        list.innerHTML = notes.length ? notes.map(n => `
            <div style="padding:12px;border-radius:10px;background:#f8fafc;margin-bottom:10px;border-left:4px solid ${typeStyle[n.type]||'#64748b'};">
                <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                    <span style="font-size:12px;font-weight:700;color:${typeStyle[n.type]||'#64748b'};text-transform:uppercase">${n.type}</span>
                    <span style="font-size:11px;color:#94a3b8">${n.created_at?.slice(0,16)||''}</span>
                </div>
                <div style="font-size:14px;color:#1e293b">${esc(n.content)}</div>
            </div>`).join('')
            : '<p style="color:#94a3b8;text-align:center;padding:20px">No notes for this agent</p>';
    } catch(e) { list.innerHTML = `<div style="color:#ef4444">${esc(e.message)}</div>`; }
}

async function saveAgentNote() {
    const username = document.getElementById('agNotesSelect')?.value;
    const type     = document.getElementById('agNoteType')?.value;
    const content  = document.getElementById('agNoteContent')?.value?.trim();
    const msg      = document.getElementById('agNoteSaveMsg');
    if (!username) { if(msg) msg.innerHTML='<span style="color:#f59e0b">Select an agent first</span>'; return; }
    if (!content)  { if(msg) msg.innerHTML='<span style="color:#f59e0b">Enter a note</span>'; return; }
    try {
        const res = await fetch(`/api/agents/notes/${username}`, {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({type, content})
        });
        const data = await res.json();
        if (data.success) {
            if(msg) msg.innerHTML='<span style="color:#22c55e">✅ Note saved!</span>';
            document.getElementById('agNoteContent').value = '';
            loadAgentNotes();
        }
    } catch(e) { if(msg) msg.innerHTML=`<span style="color:#ef4444">${esc(e.message)}</span>`; }
}

// ── 6. Top Performers ─────────────────────────────────────
async function loadAgentTopPerformers() {
    const days  = document.getElementById('agTopDays')?.value || 30;
    const tbody = document.getElementById('agTopBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="9" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>`;
    try {
        const res = await apiFetch(`/api/agents/performance?days=${days}`);
        const medals = ['🥇','🥈','🥉'];
        tbody.innerHTML = res.data.map((a,i) => {
            const minPerDay = a.days_active > 0 ? (a.minutes/a.days_active).toFixed(1) : '0';
            return `<tr>
                <td style="font-size:18px;text-align:center">${medals[i]||i+1}</td>
                <td style="font-weight:600">${esc(a.user)}</td>
                <td>${esc(a.name)}</td>
                <td class="num">${fmt(a.calls)}</td>
                <td class="num">${fmt(a.valid)}</td>
                <td class="num">${a.days_active}</td>
                <td class="num">${a.talk_time}</td>
                <td class="num">${a.avg_call}</td>
                <td class="num" style="color:#6366f1;font-weight:600">${minPerDay}</td>
            </tr>`;
        }).join('') || `<tr><td colspan="9" class="loading-cell">No data</td></tr>`;
    } catch(e) { tbody.innerHTML = `<tr><td colspan="9" class="loading-cell" style="color:#ef4444">${esc(e.message)}</td></tr>`; }
}

// ── 7. Sales Dashboard ────────────────────────────────────
async function loadAgentSalesDashboard() {
    const days  = document.getElementById('agSalesDays')?.value || 7;
    const tbody = document.getElementById('agSalesBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="9" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>`;
    try {
        const res = await apiFetch(`/api/agents/sales-dashboard?days=${days}`);
        const medals = ['🥇','🥈','🥉'];
        tbody.innerHTML = res.data.map((a,i) => `<tr>
            <td style="font-size:18px;text-align:center">${medals[i]||i+1}</td>
            <td style="font-weight:600">${esc(a.user)}</td>
            <td>${esc(a.name)}</td>
            <td class="num">${fmt(a.dials)}</td>
            <td class="num">${fmt(a.contacts)}</td>
            <td class="num" style="color:${a.contact_rate>=20?'#22c55e':a.contact_rate>=10?'#f59e0b':'#ef4444'};font-weight:600">${a.contact_rate}%</td>
            <td class="num">${a.talk_time}</td>
            <td class="num">${a.avg_call}</td>
            <td class="num">${a.days_worked}</td>
        </tr>`).join('') || `<tr><td colspan="9" class="loading-cell">No sales data</td></tr>`;
    } catch(e) { tbody.innerHTML = `<tr><td colspan="9" class="loading-cell" style="color:#ef4444">${esc(e.message)}</td></tr>`; }
}

// ── Outbound Dialer Monitor ───────────────────────────────
async function loadOutboundMonitor() {
    const grid    = document.getElementById('outboundLiveGrid');
    const meta    = document.getElementById('outboundLiveMeta');
    const summary = document.getElementById('outboundCampSummary');
    const tbody   = document.getElementById('outboundRecentBody');
    if (!grid) return;
    grid.innerHTML = `<div class="loading-cell"><i class="fas fa-spinner fa-spin"></i></div>`;
    try {
        const res = await apiFetch('/api/agents/outbound-monitor');

        // Live agents grid
        if (meta) meta.innerHTML = `<span class="status-pill">${res.total_live} on call now</span>`;
        grid.innerHTML = res.live_agents.length
            ? res.live_agents.map(a => `
            <div style="background:#dbeafe;border-radius:12px;padding:14px;border:1px solid #bfdbfe;">
                <div style="font-weight:700;font-size:14px">${esc(a.name)}</div>
                <div style="font-size:12px;color:#64748b;margin:2px 0">@${esc(a.user)}</div>
                <div style="margin-top:8px;display:flex;justify-content:space-between;align-items:center;">
                    <span style="background:#1d4ed8;color:white;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700">📞 ${esc(a.campaign)}</span>
                    <span style="font-size:13px;font-weight:700;color:${a.duration>300?'#ef4444':a.duration>120?'#f59e0b':'#1d4ed8'}">${a.duration_fmt}</span>
                </div>
            </div>`).join('')
            : '<p style="color:#94a3b8;padding:20px;grid-column:1/-1">No agents on outbound calls right now</p>';

        // Campaign summary pills
        if (summary) summary.innerHTML = res.campaign_summary.map(c =>
            `<div style="background:#f0f4ff;border-radius:10px;padding:10px 18px;text-align:center;border:1px solid #c7d2fe;">
                <div style="font-weight:700;color:#1d4ed8;font-size:18px">${c.count}</div>
                <div style="font-size:12px;color:#475569;margin-top:2px">${esc(c.campaign)}</div>
            </div>`).join('') || '<p style="color:#94a3b8">No live campaigns</p>';

        // Recent activity table
        if (tbody) tbody.innerHTML = res.recent.map(r => `<tr>
            <td style="font-size:12px">${r.time.slice(11,19)}</td>
            <td>${esc(r.name||r.agent)}</td>
            <td>${esc(r.campaign)}</td>
            <td style="font-size:12px;color:#64748b">${esc(r.phone)}</td>
            <td class="num">${r.duration}</td>
            <td style="font-size:11px;color:#64748b">${esc(r.result)}</td>
        </tr>`).join('') || `<tr><td colspan="6" class="loading-cell">No recent activity</td></tr>`;

    } catch(e) {
        grid.innerHTML = `<div style="color:#ef4444;padding:20px">${esc(e.message)}</div>`;
    }
}

// ── 8. Inbound Groups ─────────────────────────────────────
async function loadInboundGroups() {
    const tbody = document.getElementById('agInboundBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="6" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>`;
    try {
        const res = await apiFetch('/api/agents/inbound-groups');
        tbody.innerHTML = res.data.map(g => `<tr>
            <td style="font-weight:600;font-family:monospace">${esc(g.id)}</td>
            <td>${esc(g.name)}</td>
            <td><span class="badge ${g.active==='Y'?'badge-ready':'badge-default'}">${g.active==='Y'?'Active':'Inactive'}</span></td>
            <td class="num">${fmt(g.calls_today)}</td>
            <td class="num" style="color:${g.waiting>5?'#ef4444':g.waiting>0?'#f59e0b':'#22c55e'};font-weight:600">${g.waiting}</td>
            <td style="font-size:12px;color:#64748b">${g.oldest_wait||'—'}</td>
        </tr>`).join('') || `<tr><td colspan="6" class="loading-cell">No inbound groups found</td></tr>`;
    } catch(e) { tbody.innerHTML = `<tr><td colspan="6" class="loading-cell" style="color:#ef4444">${esc(e.message)}</td></tr>`; }
}

// ══════════════════════════════════════════════════════════
// DISPOSITION REPORT
// ══════════════════════════════════════════════════════════

let _dispLastData  = null;   // cache for CSV/print
let _dispAllAgents = [];     // all agents in current campaign+date

async function _populateDispDropdowns() {
    try {
        // Use performance data (last 30 days) so dropdown matches what's actually active
        const campRes = await apiFetch('/api/campaigns/performance?days=30');
        const campSel = document.getElementById('dispCampaign');
        if (campSel) {
            const camps = (campRes.data || []).map(c => c.campaign_id || c.campaign);
            campSel.innerHTML = `<option value="">All Campaigns</option>` +
                camps.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
        }
    } catch(e) { /* keep default */ }
}

async function onDispCampaignChange() {
    const campaign  = document.getElementById('dispCampaign')?.value || '';
    const dateStart = document.getElementById('dispDateStart')?.value || '';
    const dateEnd   = document.getElementById('dispDateEnd')?.value   || dateStart;
    const box       = document.getElementById('dispAgentCheckboxes');
    const countEl   = document.getElementById('dispAgentCount');
    if (!box) return;

    if (!campaign) {
        box.innerHTML = `<span style="color:#94a3b8;font-size:13px;align-self:center;">Select a campaign to filter agents, or leave blank for all</span>`;
        if (countEl) countEl.textContent = '';
        _dispAllAgents = [];
        return;
    }

    box.innerHTML = `<i class="fas fa-spinner fa-spin" style="color:#94a3b8"></i>`;
    try {
        let qs = `campaign=${encodeURIComponent(campaign)}`;
        if (dateStart) qs += `&date_start=${dateStart}&date_end=${dateEnd||dateStart}`;
        const res = await apiFetch(`/api/reports/campaign-agents?${qs}`);
        _dispAllAgents = res.data || [];

        if (countEl) countEl.textContent = `${_dispAllAgents.length} agents worked this campaign`;

        if (!_dispAllAgents.length) {
            box.innerHTML = `<span style="color:#f59e0b;font-size:13px">No agents found for this campaign & date range</span>`;
            return;
        }
        _renderAgentCheckboxes(_dispAllAgents);
    } catch(e) {
        box.innerHTML = `<span style="color:#ef4444;font-size:13px">${esc(e.message)}</span>`;
    }
}

function _renderAgentCheckboxes(agents) {
    const box = document.getElementById('dispAgentCheckboxes');
    if (!box) return;
    box.innerHTML = agents.map(a => `
        <label style="display:inline-flex;align-items:center;gap:6px;padding:5px 12px;background:white;
                      border:1px solid #e2e8f0;border-radius:20px;cursor:pointer;font-size:13px;font-weight:500;
                      transition:all 0.15s;user-select:none;" class="agent-chip">
            <input type="checkbox" value="${esc(a.user)}" checked
                   style="accent-color:#3b82f6;cursor:pointer;" onchange="updateAgentChipStyle(this)">
            ${esc(a.name)}
            <span style="font-size:11px;color:#94a3b8;margin-left:2px">(${fmt(a.calls)})</span>
        </label>`).join('');
}

function updateAgentChipStyle(cb) {
    const label = cb.closest('label');
    if (!label) return;
    label.style.background  = cb.checked ? '#eff6ff' : 'white';
    label.style.borderColor = cb.checked ? '#3b82f6' : '#e2e8f0';
    label.style.color       = cb.checked ? '#1d4ed8' : '#64748b';
}

function dispSelectAllAgents(checked) {
    document.querySelectorAll('#dispAgentCheckboxes input[type=checkbox]').forEach(cb => {
        cb.checked = checked;
        updateAgentChipStyle(cb);
    });
}

async function loadDispositionReport() {
    const dateStart  = document.getElementById('dispDateStart')?.value;
    const dateEnd    = document.getElementById('dispDateEnd')?.value || dateStart;
    const campaign   = document.getElementById('dispCampaign')?.value || '';
    const out        = document.getElementById('dispReportOut');
    const expBtn     = document.getElementById('dispExportBtn');
    const printBtn   = document.getElementById('dispPrintBtn');

    if (!out) return;
    if (!dateStart) { alert('Please select a date range'); return; }

    // Collect checked agents
    const checkedCbs   = [...document.querySelectorAll('#dispAgentCheckboxes input[type=checkbox]:checked')];
    const allCbs       = [...document.querySelectorAll('#dispAgentCheckboxes input[type=checkbox]')];
    const agentsParam  = (allCbs.length > 0 && checkedCbs.length < allCbs.length)
                         ? checkedCbs.map(cb => cb.value).join(',') : '';

    out.innerHTML = `<div style="text-align:center;padding:60px;color:#94a3b8">
        <i class="fas fa-spinner fa-spin" style="font-size:28px"></i>
        <p style="margin-top:12px">Generating report…</p></div>`;
    if (expBtn)   expBtn.style.display   = 'none';
    if (printBtn) printBtn.style.display = 'none';
    _dispLastData = null;

    try {
        let qs = `date_start=${dateStart}&date_end=${dateEnd}`;
        if (campaign)   qs += `&campaign=${encodeURIComponent(campaign)}`;
        if (agentsParam) qs += `&agents=${encodeURIComponent(agentsParam)}`;

        const res = await apiFetch(`/api/reports/dispositions?${qs}`);
        _dispLastData = res;

        const statuses   = res.statuses || [];
        const agents     = res.agents   || [];
        const campLabel  = campaign || 'All Campaigns';
        const rangeLabel = dateStart === dateEnd ? dateStart : `${dateStart} → ${dateEnd}`;

        if (!agents.length) {
            out.innerHTML = `<div class="card" style="text-align:center;padding:60px;color:#94a3b8">No calls found for this period</div>`;
            return;
        }

        // ── Colour map ────────────────────────────────────
        const DC = {
            YPVM:'#3b82f6', SALE:'#22c55e', DNC:'#ef4444',  DROP:'#ef4444',
            YPNA:'#f59e0b', YPNI:'#8b5cf6', YPCBCK:'#06b6d4', INCALL:'#3b82f6',
            NI:'#94a3b8',   NA:'#94a3b8',   B:'#94a3b8',    DNCL:'#ef4444',
            YPDNC:'#ef4444', YPDUP:'#f97316', PDROP:'#f97316', ADC:'#06b6d4',
            AB:'#f97316',   TEST:'#94a3b8'
        };

        // ── KPI pills ─────────────────────────────────────
        const kpiHtml = statuses.slice(0, 8).map(s => {
            const cnt = res.col_totals[s] || 0;
            const pct = res.grand_total ? ((cnt / res.grand_total) * 100).toFixed(1) : '0.0';
            const col = DC[s] || '#6366f1';
            return `<div style="background:white;border:1px solid #e2e8f0;border-radius:14px;padding:14px 20px;
                                min-width:110px;flex:1;border-top:4px solid ${col};">
                <div style="font-size:24px;font-weight:800;color:${col}">${fmt(cnt)}</div>
                <div style="font-size:13px;font-weight:700;color:#1e293b;margin-top:2px">${esc(s)}</div>
                <div style="font-size:11px;color:#94a3b8;margin-top:2px">${pct}% of total</div>
            </div>`;
        }).join('');

        // ── Pivot table ───────────────────────────────────
        const thCols = statuses.map(s =>
            `<th class="num" style="color:${DC[s]||'#475569'};font-weight:700;font-size:12px">${esc(s)}</th>`
        ).join('');

        const agentRows = agents.map(a => {
            const tds = statuses.map(s => {
                const cnt = a.dispositions[s] || 0;
                const col = DC[s];
                return `<td class="num" style="${cnt>0&&col?`color:${col};font-weight:600`:'color:#cbd5e1'}">${cnt>0?fmt(cnt):'—'}</td>`;
            }).join('');
            const vm      = a.dispositions['YPVM'] || 0;
            const sales   = a.dispositions['SALE'] || 0;
            const vmRate  = a.total ? (vm/a.total*100).toFixed(1)   : '0.0';
            const salRate = a.total ? (sales/a.total*100).toFixed(1) : '0.0';
            return `<tr>
                <td style="font-weight:600;white-space:nowrap">${esc(a.name)}</td>
                <td style="font-family:monospace;font-size:12px;color:#475569">${esc(a.campaign_id||'—')}</td>
                ${tds}
                <td class="num" style="font-weight:800;color:#1e293b">${fmt(a.total)}</td>
                <td class="num" style="color:#64748b;font-size:12px">${esc(a.talk_time)}</td>
                <td class="num" style="color:${parseFloat(vmRate)>=70?'#22c55e':parseFloat(vmRate)>=50?'#f59e0b':'#ef4444'};font-weight:700">${vmRate}%</td>
                <td class="num" style="color:${parseFloat(salRate)>0?'#22c55e':'#94a3b8'};font-weight:700">${salRate}%</td>
            </tr>`;
        }).join('');

        const totalTds = statuses.map(s => {
            const c = res.col_totals[s] || 0;
            return `<td class="num" style="font-weight:700">${c>0?fmt(c):'—'}</td>`;
        }).join('');

        // ── Suggestions ───────────────────────────────────
        const suggestions = _buildSuggestions(agents, statuses, res.col_totals, res.grand_total);
        const suggestHtml = suggestions.length
            ? suggestions.map(s => `
                <div style="display:flex;gap:12px;align-items:flex-start;padding:12px 0;border-bottom:1px solid #f1f5f9;">
                    <div style="width:32px;height:32px;border-radius:10px;background:${s.bg};display:flex;align-items:center;
                                justify-content:center;font-size:16px;flex-shrink:0;">${s.icon}</div>
                    <div style="flex:1">
                        <div style="font-weight:700;color:#1e293b;font-size:14px">${esc(s.title)}</div>
                        <div style="font-size:13px;color:#475569;margin-top:3px">${esc(s.body)}</div>
                    </div>
                    <span style="flex-shrink:0;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;
                                 background:${s.tagBg};color:${s.tagCol}">${esc(s.tag)}</span>
                </div>`).join('')
            : `<p style="color:#94a3b8;font-size:13px;padding:12px 0">No notable patterns detected.</p>`;

        // ── Assemble report ───────────────────────────────
        out.innerHTML = `
        <div id="dispPrintArea">
            <div class="card" style="margin-bottom:16px;padding:20px 28px;
                 background:linear-gradient(135deg,#0f172a,#1e3a5f);color:white;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;">
                    <div>
                        <div style="font-size:11px;font-weight:600;color:#94a3b8;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px">
                            Disposition Report
                        </div>
                        <div style="font-size:22px;font-weight:800;margin-bottom:4px">📢 ${esc(campLabel)}</div>
                        <div style="font-size:14px;color:#94a3b8">
                            📅 ${esc(rangeLabel)} &nbsp;·&nbsp;
                            ${agents.length} agent${agents.length!==1?'s':''} &nbsp;·&nbsp;
                            ${fmt(res.grand_total)} total calls
                        </div>
                    </div>
                    <div style="text-align:right;font-size:12px;color:#64748b;">
                        Generated: ${new Date().toLocaleString()}<br>Altria Ops v2.0
                    </div>
                </div>
            </div>

            <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;">${kpiHtml}</div>

            <div class="card" style="margin-bottom:16px;">
                <div class="card-header">
                    <h2>📊 Agent Disposition Breakdown</h2>
                    <div class="status-pills">
                        <span class="status-pill">VM% = voicemail rate</span>
                        <span class="status-pill">Sale% = conversion rate</span>
                    </div>
                </div>
                <div class="table-wrap" style="overflow-x:auto;">
                    <table class="data-table">
                        <thead><tr>
                            <th>Agent</th><th>Campaign</th>${thCols}
                            <th class="num" style="font-weight:800">Total</th>
                            <th class="num">Talk Time</th>
                            <th class="num" style="color:#3b82f6">VM%</th>
                            <th class="num" style="color:#22c55e">Sale%</th>
                        </tr></thead>
                        <tbody>
                            ${agentRows}
                            <tr style="background:#f8fafc;border-top:2px solid #e2e8f0;font-weight:800;">
                                <td colspan="2">TOTAL</td>${totalTds}
                                <td class="num">${fmt(res.grand_total)}</td>
                                <td></td><td></td><td></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2>💡 Insights &amp; Suggestions</h2>
                    <span style="font-size:12px;color:#94a3b8">Auto-generated from call patterns</span>
                </div>
                <div style="padding:0 4px;">${suggestHtml}</div>
            </div>
        </div>`;

        if (expBtn)   expBtn.style.display   = 'inline-flex';
        if (printBtn) printBtn.style.display = 'inline-flex';

    } catch(e) {
        out.innerHTML = `<div class="card" style="color:#ef4444;padding:30px">Error: ${esc(e.message)}</div>`;
    }
}

function _buildSuggestions(agents, statuses, totals, grand) {
    const tips = [];
    if (!agents.length) return tips;

    // ① High voicemail rate
    const vmTotal = totals['YPVM'] || 0;
    const vmRate  = grand ? vmTotal / grand * 100 : 0;
    if (vmRate > 70) tips.push({
        icon:'📞', bg:'#dbeafe', tag:'High VM', tagBg:'#dbeafe', tagCol:'#1d4ed8',
        title:`${vmRate.toFixed(1)}% of all calls went to voicemail`,
        body:'Consider dialing during peak contact hours (10am–12pm, 6pm–8pm EST) or refining your contact list quality.'
    });

    // ② Top seller
    const ranked = [...agents].sort((a,b)=>(b.dispositions['SALE']||0)-(a.dispositions['SALE']||0));
    const top = ranked[0];
    if ((top?.dispositions['SALE']||0) > 0) {
        const ts = top.dispositions['SALE'];
        const tr2 = top.total ? (ts/top.total*100).toFixed(1) : '0';
        tips.push({
            icon:'🏆', bg:'#dcfce7', tag:'Top Performer', tagBg:'#dcfce7', tagCol:'#15803d',
            title:`${top.name} leads with ${ts} sale${ts!==1?'s':''} (${tr2}% conversion)`,
            body:'Consider having this agent mentor others. Analyze their call handling for best practices.'
        });
    }

    // ③ High-volume, zero sales
    const noSale = agents.filter(a => a.total >= 50 && !(a.dispositions['SALE']));
    if (noSale.length) {
        const names = noSale.slice(0,3).map(a=>a.name.split(' ')[0]).join(', ');
        tips.push({
            icon:'🎯', bg:'#fef9c3', tag:'Coaching Needed', tagBg:'#fef9c3', tagCol:'#92400e',
            title:`${noSale.length} high-volume agent${noSale.length!==1?'s':''} with no sales: ${names}`,
            body:'These agents are making significant calls but not converting. Schedule script coaching and objection-handling training.'
        });
    }

    // ④ High callback rate
    const cbRate = grand ? (totals['YPCBCK']||0)/grand*100 : 0;
    if (cbRate > 5) tips.push({
        icon:'🔄', bg:'#f0f9ff', tag:'Callbacks', tagBg:'#e0f2fe', tagCol:'#0369a1',
        title:`${cbRate.toFixed(1)}% callback rate — ${fmt(totals['YPCBCK']||0)} pending`,
        body:'Ensure agents follow up on all callbacks within 24 hours. Consider dedicated callback blocks in the schedule.'
    });

    // ⑤ Low-volume agents
    const avgCalls = grand / agents.length;
    const lowVol   = agents.filter(a => a.total < avgCalls * 0.5);
    if (lowVol.length && agents.length > 2) {
        tips.push({
            icon:'⚠️', bg:'#fff7ed', tag:'Low Volume', tagBg:'#fed7aa', tagCol:'#c2410c',
            title:`${lowVol.length} agent${lowVol.length!==1?'s':''} below 50% of team average (${Math.round(avgCalls)} calls)`,
            body:`${lowVol.map(a=>a.name.split(' ')[0]).join(', ')} — check login hours, breaks, and system availability.`
        });
    }

    // ⑥ DNC / list quality
    const dncTotal = (totals['DNC']||0)+(totals['YPDNC']||0)+(totals['DNCL']||0);
    const dncRate  = grand ? dncTotal/grand*100 : 0;
    if (dncRate > 3) tips.push({
        icon:'🚫', bg:'#fef2f2', tag:'List Quality', tagBg:'#fecaca', tagCol:'#b91c1c',
        title:`${dncRate.toFixed(1)}% DNC rate — ${fmt(dncTotal)} do-not-call hits`,
        body:'Consider scrubbing against the national DNC registry and refreshing list sourcing.'
    });

    // ⑦ Drop rate
    const dropTotal = (totals['DROP']||0)+(totals['PDROP']||0);
    const dropRate  = grand ? dropTotal/grand*100 : 0;
    if (dropRate > 5) tips.push({
        icon:'📶', bg:'#f5f3ff', tag:'System Issue', tagBg:'#ede9fe', tagCol:'#6d28d9',
        title:`${dropRate.toFixed(1)}% drop rate — ${fmt(dropTotal)} dropped calls`,
        body:'Elevated call drop rate may signal bandwidth/server issues. Check VICIdial server load and carrier trunk stability.'
    });

    return tips;
}

function exportDispositionCSV() {
    if (!_dispLastData) return;
    const { agents, statuses, col_totals, grand_total, date_start, date_end } = _dispLastData;
    const campaign = document.getElementById('dispCampaign')?.value || 'AllCampaigns';

    const headers = ['Agent','Username','Campaign',...statuses,'Total','Talk Time','VM%','Sale%'];
    const rows = agents.map(a => {
        const vm = a.dispositions['YPVM']||0, sale = a.dispositions['SALE']||0;
        return [`"${a.name}"`, a.user, a.campaign_id||'',
                ...statuses.map(s=>a.dispositions[s]||0),
                a.total, `"${a.talk_time}"`,
                a.total?(vm/a.total*100).toFixed(1)+'%':'0%',
                a.total?(sale/a.total*100).toFixed(1)+'%':'0%'];
    });
    rows.push(['"TOTAL"','','',...statuses.map(s=>col_totals[s]||0),grand_total,'','','']);

    const csv  = [headers.join(','),...rows.map(r=>r.join(','))].join('\n');
    const blob = new Blob([csv],{type:'text/csv'});
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href=url; a.download=`dispositions_${campaign}_${date_start}_${date_end}.csv`;
    a.click(); URL.revokeObjectURL(url);
}

function printDispositionReport() {
    const area = document.getElementById('dispPrintArea');
    if (!area) return;
    const win = window.open('','_blank','width=1100,height=800');
    win.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Disposition Report</title>
<style>
body{font-family:Arial,sans-serif;font-size:13px;color:#1e293b;margin:0;padding:20px;}
h2{font-size:16px;font-weight:800;margin:0 0 4px;}
table{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:16px;}
th{background:#f8fafc;padding:8px;text-align:left;font-weight:700;border-bottom:2px solid #e2e8f0;}
td{padding:7px 8px;border-bottom:1px solid #f1f5f9;}
.num{text-align:right;}
.kpi-wrap{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;}
.kpi{border:1px solid #e2e8f0;border-radius:8px;padding:10px 14px;min-width:90px;}
.card{border:1px solid #e2e8f0;border-radius:10px;padding:16px;margin-bottom:16px;}
.hdr{background:#0f172a;color:white;padding:18px;border-radius:10px;margin-bottom:16px;}
@media print{.hdr{-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
</style></head><body>
${area.innerHTML}
<p style="font-size:11px;color:#94a3b8;text-align:right;border-top:1px solid #e2e8f0;padding-top:10px;">
Generated by Altria Ops &nbsp;·&nbsp; ${new Date().toLocaleString()}
</p>
</body></html>`);
    win.document.close(); win.focus();
    setTimeout(()=>win.print(), 600);
}

// ── Time preset picker ────────────────────────────────────
function setTimePreset(btn, start, end) {
    document.querySelectorAll('.time-preset').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const sEl = document.getElementById('timeStart');
    const eEl = document.getElementById('timeEnd');
    if (sEl) sEl.value = start;
    if (eEl) eEl.value = end;
}

// ── Billing Report ────────────────────────────────────────
let _billingData = null;

async function loadBillingReport(period, campParam) {
    const box = document.getElementById('billingContent');
    if (!box) return;

    // Tab styling
    document.querySelectorAll('.bill-tab').forEach(b => {
        b.style.background = 'white';
        b.style.color = '#64748b';
        b.style.borderColor = '#e2e8f0';
    });
    const activeBtn = document.querySelector(`.bill-tab[onclick*="'${period}'"]`);
    if (activeBtn) { activeBtn.style.background='#6366f1'; activeBtn.style.color='white'; activeBtn.style.borderColor='#6366f1'; }

    try {
        // Fetch if not cached or different filter
        const url = campParam ? `/api/billing/summary?campaigns=${campParam}` : '/api/billing/summary';
        if (!_billingData) {
            box.innerHTML = `<div style="text-align:center;padding:30px;color:#94a3b8"><i class="fas fa-spinner fa-spin"></i> Loading…</div>`;
            const res = await apiFetch(url);
            _billingData = res;
        }
        const d = _billingData[period];
        if (!d) return;

        const totalMins = d.total_minutes;
        const h = Math.floor(totalMins / 60);
        const m = Math.floor(totalMins % 60);
        const s = Math.round((totalMins * 60) % 60);
        const periodLabel = {today:'Today',week:'Last 7 Days',month:'This Month',last_month:'Last Month'}[period];

        box.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:20px;">
            <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:14px;padding:20px;color:white;text-align:center;">
                <div style="font-size:11px;font-weight:700;opacity:0.8;text-transform:uppercase;letter-spacing:0.5px;">${periodLabel} — Total Minutes</div>
                <div style="font-size:44px;font-weight:900;margin:8px 0;">${Math.floor(totalMins).toLocaleString()}</div>
                <div style="font-size:13px;opacity:0.85;">${h}h ${m}m ${s}s</div>
            </div>
            <div style="background:#f8fafc;border-radius:14px;padding:20px;text-align:center;border:1px solid #e2e8f0;">
                <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;">Total Calls</div>
                <div style="font-size:36px;font-weight:800;color:#0f172a;margin:8px 0;">${fmt(d.total_calls)}</div>
            </div>
            <div style="background:#f0fdf4;border-radius:14px;padding:20px;text-align:center;border:1px solid #bbf7d0;">
                <div style="font-size:11px;font-weight:700;color:#15803d;text-transform:uppercase;">Avg Min / Call</div>
                <div style="font-size:36px;font-weight:800;color:#15803d;margin:8px 0;">${d.total_calls > 0 ? (totalMins/d.total_calls).toFixed(1) : '0'}</div>
            </div>
        </div>

        <div style="overflow-x:auto;border-radius:10px;border:1px solid #e2e8f0;">
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead style="background:#f8fafc;">
            <tr>
                <th style="padding:10px 16px;text-align:left;font-weight:700;color:#475569;">Campaign</th>
                <th style="padding:10px 16px;text-align:right;font-weight:700;color:#475569;">Calls</th>
                <th style="padding:10px 16px;text-align:right;font-weight:700;color:#475569;">Valid</th>
                <th style="padding:10px 16px;text-align:right;font-weight:700;color:#6366f1;">Minutes</th>
                <th style="padding:10px 16px;text-align:right;font-weight:700;color:#475569;">H:M:S</th>
                <th style="padding:10px 16px;text-align:right;font-weight:700;color:#475569;">% of Total</th>
                <th style="padding:10px 16px;font-weight:700;color:#475569;">Share</th>
            </tr>
        </thead>
        <tbody>
        ${d.by_campaign.map(c => {
            const pct = totalMins > 0 ? (c.minutes/totalMins*100) : 0;
            const barW = Math.round(pct);
            return `<tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:11px 16px;font-weight:600;">${esc(c.campaign)}</td>
                <td style="padding:11px 16px;text-align:right;">${fmt(c.calls)}</td>
                <td style="padding:11px 16px;text-align:right;">${fmt(c.valid_calls)}</td>
                <td style="padding:11px 16px;text-align:right;font-weight:800;color:#6366f1;font-size:15px;">${Math.floor(c.minutes).toLocaleString()}<span style="font-size:11px;color:#94a3b8;font-weight:400"> min</span></td>
                <td style="padding:11px 16px;text-align:right;color:#64748b;">${c.minutes_fmt}</td>
                <td style="padding:11px 16px;text-align:right;font-weight:600;">${pct.toFixed(1)}%</td>
                <td style="padding:11px 16px;min-width:100px;">
                    <div style="background:#e0e7ff;border-radius:4px;height:8px;overflow:hidden;">
                        <div style="background:#6366f1;height:100%;width:${barW}%;border-radius:4px;transition:width 0.5s;"></div>
                    </div>
                </td>
            </tr>`;
        }).join('')}
        <tr style="background:#f8fafc;font-weight:700;border-top:2px solid #e2e8f0;">
            <td style="padding:12px 16px;">TOTAL</td>
            <td style="padding:12px 16px;text-align:right;">${fmt(d.total_calls)}</td>
            <td style="padding:12px 16px;text-align:right;"></td>
            <td style="padding:12px 16px;text-align:right;color:#6366f1;font-size:15px;">${Math.floor(totalMins).toLocaleString()} min</td>
            <td style="padding:12px 16px;text-align:right;">${h}h ${m}m</td>
            <td style="padding:12px 16px;text-align:right;">100%</td>
            <td></td>
        </tr>
        </tbody></table></div>`;

    } catch(e) {
        if (box) box.innerHTML = `<div style="color:#ef4444;padding:20px">Error: ${esc(e.message)}</div>`;
    }
}

// ── Campaign row helper (matches terminal output) ─────────
function campRow(c, extraCols) {
    const rc  = (r,g,w) => r>=g?'#22c55e':r>=w?'#f59e0b':'#ef4444';
    const ans = c.answer_rate ?? 0;
    const abn = c.abandon_rate ?? 0;
    const campId = esc(c.campaign_id || c.campaign);
    // Row background: subtle tint based on answer rate
    const rowBg = ans >= 80 ? 'rgba(34,197,94,0.04)' : ans >= 60 ? 'rgba(245,158,11,0.05)' : 'rgba(239,68,68,0.05)';
    return `<tr class="camp-row" style="cursor:pointer;background:${rowBg};" onclick="openCampDetail('${campId}')" title="Click for daily breakdown">
        <td style="font-weight:700;color:#6366f1;">${campId} <i class="fas fa-external-link-alt" style="font-size:9px;opacity:.4;margin-left:4px;"></i></td>
        <td class="num" style="font-weight:600">${fmt(c.total_calls??c.calls)}</td>
        <td class="num">${fmt(c.answered)}</td>
        <td class="num" style="color:${rc(ans,80,60)};font-weight:800;font-size:15px">${ans.toFixed(1)}%</td>
        <td class="num">${fmt(c.abandoned)}</td>
        <td class="num" style="color:${abn>20?'#ef4444':abn>10?'#f59e0b':'#64748b'};font-weight:600">${abn.toFixed(1)}%</td>
        <td class="num" style="font-family:monospace">${esc(c.avg_talk||'—')}</td>
        <td class="num" style="color:#94a3b8;font-size:12px">${esc(c.last_call||'—')}</td>
        ${extraCols||''}
    </tr>`;
}

function campTotalsRow(data, extraColsFn) {
    const tc  = data.reduce((s,r) => s+(r.total_calls??r.calls??0), 0);
    const ta  = data.reduce((s,r) => s+(r.answered??0), 0);
    const tb  = data.reduce((s,r) => s+(r.abandoned??0), 0);
    const tm  = data.reduce((s,r) => s+(r.talk_time_mins??0), 0);
    const ansr = tc ? (ta/tc*100).toFixed(1) : 0;
    const abdr = tc ? (tb/tc*100).toFixed(1) : 0;
    const rc = (r,g,w) => r>=g?'#22c55e':r>=w?'#f59e0b':'#ef4444';
    return `<tr style="background:#f1f5f9;font-weight:700;border-top:2px solid #e2e8f0;">
        <td style="color:#374151">TOTAL (${data.length})</td>
        <td class="num" style="color:#0f172a">${fmt(tc)}</td>
        <td class="num" style="color:#0f172a">${fmt(ta)}</td>
        <td class="num" style="color:${rc(parseFloat(ansr),80,60)};font-size:15px">${ansr}%</td>
        <td class="num" style="color:#0f172a">${fmt(tb)}</td>
        <td class="num" style="color:${abdr>20?'#ef4444':abdr>10?'#f59e0b':'#22c55e'}">${abdr}%</td>
        <td class="num">—</td><td class="num">—</td>
        ${extraColsFn ? extraColsFn(data, tm) : ''}
    </tr>`;
}

// ── Campaign Detail Modal ─────────────────────────────────
let _currentDetailCamp = '';

function _activeCampDays() {
    // Return the days value matching the currently active campaign tab
    const tab = document.querySelector('.tab-pill[data-ctab].active')?.dataset.ctab;
    if (tab === 'camp-today')  return 0;
    if (tab === 'camp-7d')     return 7;
    if (tab === 'camp-30d')    return 30;
    return 30;
}

function openCampDetail(campId) {
    _currentDetailCamp = campId;
    const modal = document.getElementById('campDetailModal');
    const title = document.getElementById('campDetailTitle');
    const sub   = document.getElementById('campDetailSub');
    if (!modal) return;
    if (title) title.textContent = campId;
    if (sub)   sub.textContent   = 'Loading…';
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';
    // Sync the days selector in the modal to match the active tab
    const days = _activeCampDays();
    const sel = document.getElementById('campDetailDays');
    if (sel) sel.value = days;
    loadCampDetail(campId, days);
    loadCampCalls(campId, days);
}

function closeCampDetail() {
    const modal = document.getElementById('campDetailModal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('campDetailModal')?.addEventListener('click', function(e) {
        if (e.target === this) closeCampDetail();
    });
    document.getElementById('campDetailDays')?.addEventListener('change', function() {
        if (_currentDetailCamp) {
            loadCampDetail(_currentDetailCamp, this.value);
            loadCampCalls(_currentDetailCamp, this.value);
        }
    });
});

function switchCampDetailTab(tab) {
    document.querySelectorAll('.cd-tab').forEach(b => {
        const active = b.dataset.cdtab === tab;
        b.style.color = active ? '#6366f1' : '#94a3b8';
        b.style.borderBottom = active ? '2px solid #6366f1' : '2px solid transparent';
        b.classList.toggle('active', active);
    });
    document.getElementById('cdPanelSummary').style.display = tab === 'summary' ? '' : 'none';
    document.getElementById('cdPanelCalls').style.display   = tab === 'calls'   ? '' : 'none';
    if (tab === 'calls' && _currentDetailCamp) {
        const days = document.getElementById('campDetailDays')?.value || 0;
        loadCampCalls(_currentDetailCamp, days);
    }
}

// Stores last-loaded calls for CSV export
let _campCallsData = { before: [], within: [], after: [], all: [] };

async function loadCampCalls(campId, days) {
    const container = document.getElementById('campCallsBody');
    if (!container) return;
    container.innerHTML = `<tr><td colspan="7" class="loading-cell"><i class="fas fa-spinner fa-spin"></i> Loading calls…</td></tr>`;

    const ts = _appliedTime.start || document.getElementById('campTimeStart')?.value || '';
    const te = _appliedTime.end   || document.getElementById('campTimeEnd')?.value   || '';
    let url = `/api/campaigns/calls?campaign=${encodeURIComponent(campId)}&days=${days}&limit=2000`;
    if (ts) url += `&time_start=${encodeURIComponent(ts)}`;
    if (te) url += `&time_end=${encodeURIComponent(te)}`;

    try {
        const d = await apiFetch(url);
        const within = d.data         || [];
        const before = d.before_hours || [];
        const after  = d.after_hours  || [];
        const hasFilter = ts || te;
        _campCallsData = { before, within, after, all: d.all || within };

        // ── helpers ──────────────────────────────────────────────────────────
        const dispColor = disp => {
            const v = (disp||'').toUpperCase();
            if (['DROP','ABAND','AFAIL','QUEUETIMEOUT','ABANDON','AFTERHOURS'].includes(v)) return '#ef4444';
            if (['SALE','ANSWERED','CONNECT'].includes(v)) return '#22c55e';
            return '#374151';
        };

        const durationSec = dur => {
            // dur is like "5:43" (m:ss) or "0:01"
            const p = String(dur||'0:00').split(':');
            return parseInt(p[0]||0)*60 + parseInt(p[1]||0);
        };

        const agentTally = rows => {
            const counts = {};
            rows.forEach(r => { const a = r.agent||'Unknown'; counts[a] = (counts[a]||0)+1; });
            return Object.entries(counts)
                .sort((a,b) => b[1]-a[1])
                .map(([a,n]) =>
                    `<span style="display:inline-block;background:#e0e7ff;color:#3730a3;border-radius:20px;padding:1px 8px;font-size:11px;font-weight:600;margin:1px 2px;">${esc(a)} ${n}</span>`)
                .join('');
        };

        const ABANDON_DISPS = ['DROP','ABAND','AFAIL','QUEUETIMEOUT','ABANDON','AFTERHOURS'];
        const sectionTotals = rows => {
            if (!rows.length) return '';
            const totalSec  = rows.reduce((s,r) => s + durationSec(r.duration), 0);
            const short     = rows.filter(r => durationSec(r.duration) < 30).length;
            const avgSec    = Math.round(totalSec / rows.length);
            const abandoned = rows.filter(r => ABANDON_DISPS.includes((r.disposition||'').toUpperCase())).length;
            const answered  = rows.length - abandoned;
            const fmt = s => `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
            return `<tr style="background:#f1f5f9;border-top:2px solid #e2e8f0;">
                <td colspan="2" style="padding:7px 12px;font-size:12px;font-weight:700;color:#475569;">
                    Total: ${rows.length} calls
                </td>
                <td colspan="2" style="padding:7px 12px;font-size:12px;color:#475569;">
                    <span style="color:#22c55e;font-weight:700;">✓ ${answered} answered</span>
                    &nbsp;·&nbsp;
                    <span style="color:#ef4444;font-weight:700;">✕ ${abandoned} abandoned</span>
                </td>
                <td style="padding:7px 12px;font-size:12px;color:#475569;">
                    Talk: <b>${fmt(totalSec)}</b> &nbsp;·&nbsp; Avg: <b>${fmt(avgSec)}</b>
                </td>
                <td colspan="2" style="padding:7px 12px;font-size:12px;color:${short?'#f59e0b':'#94a3b8'};">
                    ${short ? `⚠ ${short} short call${short!==1?'s':''} (&lt;30s)` : '✓ No short calls'}
                </td>
            </tr>`;
        };

        const makeRows = (rows, startNum) => {
            if (!rows.length) return `<tr><td colspan="7" style="padding:8px 12px;color:#94a3b8;font-size:12px;font-style:italic;">None</td></tr>`;
            return rows.map((r, i) => {
                const sec     = durationSec(r.duration);
                const isShort = sec > 0 && sec < 30;
                const rowBg   = isShort ? '#fffbeb' : (i%2===0 ? '' : '#f8fafc');
                const shortTag = isShort
                    ? `<span style="font-size:10px;background:#fef3c7;color:#92400e;border-radius:4px;padding:1px 5px;margin-left:4px;">SHORT</span>`
                    : '';
                return `<tr style="background:${rowBg};">
                    <td style="color:#94a3b8;font-size:11px;text-align:center;width:32px;">${startNum + i}</td>
                    <td style="white-space:nowrap;color:#64748b;font-size:12px;">${String(r.time||'').replace('T',' ').substring(11,19)}</td>
                    <td style="font-weight:600;font-size:13px;">${esc(r.agent)}</td>
                    <td><span style="font-size:11px;padding:2px 7px;border-radius:10px;background:${r.direction==='inbound'?'#dbeafe':'#fef3c7'};color:${r.direction==='inbound'?'#1d4ed8':'#92400e'};">${r.direction}</span></td>
                    <td style="color:${dispColor(r.disposition)};font-weight:600;font-size:12px;">${esc(r.disposition)}${shortTag}</td>
                    <td class="num" style="font-family:monospace;">${r.duration}</td>
                    <td class="num" style="color:#94a3b8;">${r.queue_sec ? r.queue_sec+'s' : '—'}</td>
                </tr>`;
            }).join('') + sectionTotals(rows);
        };

        const sectionHeader = (label, rows, color, bg) => {
            const tally = rows.length ? agentTally(rows) : '';
            return `<tr>
                <td colspan="7" style="padding:8px 12px 6px;background:${bg};border-top:2px solid ${color}33;">
                    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                        <span style="font-size:12px;font-weight:700;color:${color};">${label}</span>
                        <span style="font-size:11px;font-weight:600;background:${color}22;color:${color};border-radius:20px;padding:1px 8px;">${rows.length}</span>
                        ${tally}
                    </div>
                </td>
            </tr>`;
        };

        // ── no filter: single flat list ───────────────────────────────────────
        if (!hasFilter) {
            const all = d.all || within;
            if (!all.length) {
                container.innerHTML = `<tr><td colspan="7" class="empty-cell">No calls for this period</td></tr>`;
                return;
            }
            container.innerHTML = makeRows(all, 1);
            return;
        }

        // ── three sections ────────────────────────────────────────────────────
        container.innerHTML =
            sectionHeader(`⏰ Before Hours  (before ${ts})`, before, '#f59e0b', '#fffbeb') +
            makeRows(before, 1) +
            sectionHeader(`✅ Within Hours  (${ts} – ${te})`, within, '#22c55e', '#f0fdf4') +
            makeRows(within, 1) +
            sectionHeader(`🌙 After Hours  (after ${te})`, after, '#6366f1', '#f5f3ff') +
            makeRows(after, 1);

    } catch(e) {
        container.innerHTML = `<tr><td colspan="7" class="empty-cell">Error: ${esc(e.message)}</td></tr>`;
    }
}

function exportCampCallsCSV() {
    const ts = _appliedTime.start || document.getElementById('campTimeStart')?.value || '';
    const te = _appliedTime.end   || document.getElementById('campTimeEnd')?.value   || '';
    const hasFilter = ts || te;

    const toRow = (section, num, r) =>
        [num, section, String(r.time||'').replace('T',' ').substring(0,19),
         r.agent, r.direction, r.disposition, r.duration,
         r.queue_sec||''].map(v => `"${String(v).replace(/"/g,'""')}"`).join(',');

    let lines = ['"#","Section","Time","Agent","Direction","Disposition","Duration","Queue (s)"'];
    if (hasFilter) {
        _campCallsData.before.forEach((r,i) => lines.push(toRow('Before Hours', i+1, r)));
        _campCallsData.within.forEach((r,i) => lines.push(toRow('Within Hours', i+1, r)));
        _campCallsData.after.forEach((r,i)  => lines.push(toRow('After Hours',  i+1, r)));
    } else {
        _campCallsData.all.forEach((r,i) => lines.push(toRow('All', i+1, r)));
    }

    const blob = new Blob([lines.join('\n')], {type:'text/csv'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `calls_${_currentDetailCamp}_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
}

function exportCampCallsPDF() {
    const ts = _appliedTime.start || document.getElementById('campTimeStart')?.value || '';
    const te = _appliedTime.end   || document.getElementById('campTimeEnd')?.value   || '';
    const hasFilter = ts || te;
    const camp  = _currentDetailCamp || 'Campaign';
    const today = new Date().toLocaleString('en-US', {dateStyle:'long', timeStyle:'short'});

    const ABANDON_DISPS = ['DROP','ABAND','AFAIL','QUEUETIMEOUT','ABANDON','AFTERHOURS'];
    const durationSec = dur => { const p = String(dur||'0:00').split(':'); return parseInt(p[0]||0)*60+parseInt(p[1]||0); };
    const fmtSec = s => `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;

    const sectionColor = { 'Before Hours': '#f59e0b', 'Within Hours': '#22c55e', 'After Hours': '#6366f1', 'All Calls': '#374151' };

    const buildSection = (label, rows) => {
        if (!rows.length) return '';
        const totalSec  = rows.reduce((s,r) => s + durationSec(r.duration), 0);
        const abandoned = rows.filter(r => ABANDON_DISPS.includes((r.disposition||'').toUpperCase())).length;
        const answered  = rows.length - abandoned;
        const avgSec    = Math.round(totalSec / rows.length);
        const short     = rows.filter(r => { const s = durationSec(r.duration); return s > 0 && s < 30; }).length;
        const color     = sectionColor[label] || '#374151';

        const rowsHtml = rows.map((r, i) => {
            const sec = durationSec(r.duration);
            const isShort = sec > 0 && sec < 30;
            const isAband = ABANDON_DISPS.includes((r.disposition||'').toUpperCase());
            return `<tr style="background:${i%2===0?'#fff':'#f8fafc'}${isShort?';background:#fffbeb':''};">
                <td style="text-align:center;color:#94a3b8;font-size:11px;">${i+1}</td>
                <td style="white-space:nowrap;">${String(r.time||'').replace('T',' ').substring(11,19)}</td>
                <td style="font-weight:600;">${r.agent||''}</td>
                <td>${r.direction||''}</td>
                <td style="font-weight:600;color:${isAband?'#ef4444':'#16a34a'};">${r.disposition||''}${isShort?' ⚠':''}</td>
                <td style="text-align:right;font-family:monospace;">${r.duration||''}</td>
                <td style="text-align:right;color:#64748b;">${r.queue_sec ? r.queue_sec+'s' : '—'}</td>
            </tr>`;
        }).join('');

        return `
        <div style="margin-bottom:28px;page-break-inside:avoid;">
            <div style="background:${color}18;border-left:4px solid ${color};padding:8px 14px;border-radius:0 6px 6px 0;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
                <span style="font-weight:700;color:${color};font-size:13px;">${label}</span>
                <span style="font-size:12px;color:#475569;">
                    <b>${rows.length}</b> calls &nbsp;·&nbsp;
                    <span style="color:#16a34a;font-weight:600;">✓ ${answered} answered</span> &nbsp;·&nbsp;
                    <span style="color:#ef4444;font-weight:600;">✕ ${abandoned} abandoned</span> &nbsp;·&nbsp;
                    Talk: <b>${fmtSec(totalSec)}</b> &nbsp;·&nbsp; Avg: <b>${fmtSec(avgSec)}</b>
                    ${short ? `&nbsp;·&nbsp; <span style="color:#f59e0b;font-weight:600;">⚠ ${short} short</span>` : ''}
                </span>
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:12px;">
                <thead><tr style="background:#f1f5f9;">
                    <th style="width:30px;padding:5px 6px;text-align:center;border-bottom:2px solid #e2e8f0;color:#64748b;">#</th>
                    <th style="padding:5px 8px;text-align:left;border-bottom:2px solid #e2e8f0;color:#64748b;">Time</th>
                    <th style="padding:5px 8px;text-align:left;border-bottom:2px solid #e2e8f0;color:#64748b;">Agent</th>
                    <th style="padding:5px 8px;text-align:left;border-bottom:2px solid #e2e8f0;color:#64748b;">Direction</th>
                    <th style="padding:5px 8px;text-align:left;border-bottom:2px solid #e2e8f0;color:#64748b;">Disposition</th>
                    <th style="padding:5px 8px;text-align:right;border-bottom:2px solid #e2e8f0;color:#64748b;">Talk</th>
                    <th style="padding:5px 8px;text-align:right;border-bottom:2px solid #e2e8f0;color:#64748b;">Queue</th>
                </tr></thead>
                <tbody>${rowsHtml}</tbody>
            </table>
        </div>`;
    };

    // Agent summary table
    const allRows = hasFilter
        ? [..._campCallsData.before, ..._campCallsData.within, ..._campCallsData.after]
        : _campCallsData.all;
    const agentMap = {};
    allRows.forEach(r => {
        const a = r.agent || 'Unknown';
        if (!agentMap[a]) agentMap[a] = {calls:0, talk:0, aband:0};
        agentMap[a].calls++;
        agentMap[a].talk += durationSec(r.duration);
        if (ABANDON_DISPS.includes((r.disposition||'').toUpperCase())) agentMap[a].aband++;
    });
    const agentRows = Object.entries(agentMap).sort((a,b)=>b[1].calls-a[1].calls).map(([name,s], i) =>
        `<tr style="background:${i%2===0?'#fff':'#f8fafc'};">
            <td style="padding:5px 8px;font-weight:600;">${name}</td>
            <td style="padding:5px 8px;text-align:center;">${s.calls}</td>
            <td style="padding:5px 8px;text-align:center;color:#16a34a;font-weight:600;">${s.calls - s.aband}</td>
            <td style="padding:5px 8px;text-align:center;color:#ef4444;font-weight:600;">${s.aband}</td>
            <td style="padding:5px 8px;text-align:right;font-family:monospace;">${fmtSec(s.talk)}</td>
            <td style="padding:5px 8px;text-align:right;font-family:monospace;">${fmtSec(Math.round(s.talk/s.calls))}</td>
        </tr>`).join('');

    const grandTotal = allRows.length;
    const grandAband = allRows.filter(r => ABANDON_DISPS.includes((r.disposition||'').toUpperCase())).length;
    const grandTalk  = allRows.reduce((s,r) => s + durationSec(r.duration), 0);
    const timeLabel  = hasFilter ? `${ts} – ${te}` : 'All Day';

    const html = `<!DOCTYPE html><html><head><meta charset="utf-8">
    <title>${camp} — Call Report</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', Arial, sans-serif; color: #1e293b; background: #fff; padding: 32px 40px; font-size: 13px; }
        @media print {
            body { padding: 16px 20px; }
            .no-print { display: none !important; }
            @page { margin: 1.5cm; size: A4; }
        }
    </style>
    </head><body>

    <!-- Print button (hidden on print) -->
    <div class="no-print" style="margin-bottom:20px;display:flex;gap:10px;">
        <button onclick="window.print()" style="padding:8px 22px;background:#6366f1;color:white;border:none;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;">
            🖨 Print / Save as PDF
        </button>
        <button onclick="window.close()" style="padding:8px 18px;background:#f1f5f9;color:#374151;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;cursor:pointer;">
            ✕ Close
        </button>
    </div>

    <!-- Header -->
    <div style="border-bottom:3px solid #6366f1;padding-bottom:16px;margin-bottom:24px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
                <div style="font-size:22px;font-weight:800;color:#6366f1;letter-spacing:-.5px;">${camp}</div>
                <div style="font-size:13px;color:#64748b;margin-top:4px;">Call Detail Report &nbsp;·&nbsp; Working Hours: <b>${timeLabel}</b></div>
            </div>
            <div style="text-align:right;font-size:12px;color:#94a3b8;">
                <div>Generated: ${today}</div>
                <div style="margin-top:2px;">Altria Operations</div>
            </div>
        </div>
    </div>

    <!-- Grand summary KPIs -->
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:28px;">
        ${[
            ['Total Calls', grandTotal, '#6366f1'],
            ['Answered',    grandTotal - grandAband, '#16a34a'],
            ['Abandoned',   grandAband, '#ef4444'],
            ['Total Talk',  fmtSec(grandTalk), '#0f172a'],
        ].map(([l,v,c]) => `<div style="border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;text-align:center;">
            <div style="font-size:22px;font-weight:800;color:${c};">${v}</div>
            <div style="font-size:11px;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:.06em;margin-top:3px;">${l}</div>
        </div>`).join('')}
    </div>

    <!-- Agent summary -->
    <div style="margin-bottom:28px;">
        <div style="font-size:13px;font-weight:700;color:#374151;margin-bottom:8px;text-transform:uppercase;letter-spacing:.05em;">Agent Summary</div>
        <table style="width:100%;border-collapse:collapse;font-size:12px;">
            <thead><tr style="background:#f1f5f9;">
                <th style="padding:6px 8px;text-align:left;border-bottom:2px solid #e2e8f0;color:#64748b;">Agent</th>
                <th style="padding:6px 8px;text-align:center;border-bottom:2px solid #e2e8f0;color:#64748b;">Total</th>
                <th style="padding:6px 8px;text-align:center;border-bottom:2px solid #e2e8f0;color:#64748b;">Answered</th>
                <th style="padding:6px 8px;text-align:center;border-bottom:2px solid #e2e8f0;color:#64748b;">Abandoned</th>
                <th style="padding:6px 8px;text-align:right;border-bottom:2px solid #e2e8f0;color:#64748b;">Total Talk</th>
                <th style="padding:6px 8px;text-align:right;border-bottom:2px solid #e2e8f0;color:#64748b;">Avg Talk</th>
            </tr></thead>
            <tbody>${agentRows}</tbody>
        </table>
    </div>

    <!-- Call sections -->
    <div style="font-size:13px;font-weight:700;color:#374151;margin-bottom:12px;text-transform:uppercase;letter-spacing:.05em;">Call Detail</div>
    ${hasFilter
        ? buildSection('Before Hours', _campCallsData.before) +
          buildSection('Within Hours', _campCallsData.within) +
          buildSection('After Hours',  _campCallsData.after)
        : buildSection('All Calls', _campCallsData.all)
    }

    </body></html>`;

    const w = window.open('', '_blank', 'width=900,height=800');
    w.document.write(html);
    w.document.close();
}

async function loadCampDetail(campId, days) {
    const tbody = document.getElementById('campDetailBody');
    const kpis  = document.getElementById('campDetailKpis');
    const sub   = document.getElementById('campDetailSub');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="8" class="loading-cell"><i class="fas fa-spinner fa-spin"></i> Loading ${esc(campId)}…</td></tr>`;
    if (kpis) kpis.innerHTML = '';
    try {
        const _ts2 = _appliedTime.start || document.getElementById('campTimeStart')?.value || '';
        const _te2 = _appliedTime.end   || document.getElementById('campTimeEnd')?.value   || '';
        let detailUrl = `/api/campaigns/detail?campaign=${encodeURIComponent(campId)}&days=${days}`;
        if (_ts2) detailUrl += `&time_start=${encodeURIComponent(_ts2)}`;
        if (_te2) detailUrl += `&time_end=${encodeURIComponent(_te2)}`;
        const d = await apiFetch(detailUrl);
        const rows = d.data || [];

        // Summary totals
        const totCalls = rows.reduce((s, r) => s + r.total_calls, 0);
        const totAns   = rows.reduce((s, r) => s + r.answered, 0);
        const totAbd   = rows.reduce((s, r) => s + r.abandoned, 0);
        const totMins  = rows.reduce((s, r) => s + r.talk_time_mins, 0);
        const ansRate  = totCalls ? (totAns / totCalls * 100).toFixed(1) : 0;
        const abdRate  = totCalls ? (totAbd / totCalls * 100).toFixed(1) : 0;

        const periodLabel = days == 0 ? 'Today' : `Last ${days} days`;
        if (sub) sub.textContent = `${periodLabel} · ${rows.length} active days · ${fmt(totCalls)} calls`;

        const rc = (r,g,w) => r>=g?'#22c55e':r>=w?'#f59e0b':'#ef4444';
        if (kpis) kpis.innerHTML = `
            <div style="background:#f8fafc;border-radius:12px;padding:12px 20px;min-width:120px;text-align:center;">
                <div style="font-size:22px;font-weight:800;color:#0f172a">${fmt(totCalls)}</div>
                <div style="font-size:12px;color:#64748b;margin-top:2px">Total Calls</div>
            </div>
            <div style="background:#f8fafc;border-radius:12px;padding:12px 20px;min-width:120px;text-align:center;">
                <div style="font-size:22px;font-weight:800;color:${rc(parseFloat(ansRate),80,60)}">${ansRate}%</div>
                <div style="font-size:12px;color:#64748b;margin-top:2px">Answer Rate</div>
            </div>
            <div style="background:#f8fafc;border-radius:12px;padding:12px 20px;min-width:120px;text-align:center;">
                <div style="font-size:22px;font-weight:800;color:${abdRate>20?'#ef4444':abdRate>10?'#f59e0b':'#22c55e'}">${abdRate}%</div>
                <div style="font-size:12px;color:#64748b;margin-top:2px">Abandon Rate</div>
            </div>
            <div style="background:#f8fafc;border-radius:12px;padding:12px 20px;min-width:120px;text-align:center;">
                <div style="font-size:22px;font-weight:800;color:#6366f1">${Math.round(totMins).toLocaleString()}</div>
                <div style="font-size:12px;color:#64748b;margin-top:2px">Total Mins</div>
            </div>
            <div style="background:#f8fafc;border-radius:12px;padding:12px 20px;min-width:120px;text-align:center;">
                <div style="font-size:22px;font-weight:800;color:#0f172a">${rows.length}</div>
                <div style="font-size:12px;color:#64748b;margin-top:2px">Active Days</div>
            </div>`;

        if (!rows.length) {
            tbody.innerHTML = `<tr><td colspan="8" class="loading-cell">No data for this period</td></tr>`;
            return;
        }

        tbody.innerHTML = rows.map(r => {
            const ans = r.answer_rate ?? 0;
            const abn = r.abandon_rate ?? 0;
            return `<tr>
                <td style="font-weight:600">${esc(r.call_date)}</td>
                <td class="num">${fmt(r.total_calls)}</td>
                <td class="num">${fmt(r.answered)}</td>
                <td class="num" style="color:${rc(ans,80,60)};font-weight:700">${ans.toFixed(1)}%</td>
                <td class="num">${fmt(r.abandoned)}</td>
                <td class="num" style="color:${abn>20?'#ef4444':abn>10?'#f59e0b':'#64748b'}">${abn.toFixed(1)}%</td>
                <td class="num">${esc(r.avg_talk||'—')}</td>
                <td class="num" style="color:#94a3b8">${r.talk_time_mins} min</td>
            </tr>`;
        }).join('');
    } catch(e) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" style="color:red;padding:16px">Error: ${esc(e.message)}</td></tr>`;
    }
}

// ── Score helpers ─────────────────────────────────────────
function scoreClass(s) { return s>=90?'score-excellent':s>=80?'score-good':s>=70?'score-average':'score-poor'; }
function scoreBadge(s) { return `<span class="score-badge ${scoreClass(s)}">${s}%</span>`; }

// ── Utils ─────────────────────────────────────────────────
function setText(id, val) { const e=document.getElementById(id); if(e) e.textContent=val; }
function setHtml(id, val) { const e=document.getElementById(id); if(e) e.innerHTML=val; }
function fmt(n)  { return n != null ? Number(n).toLocaleString() : '0'; }
function esc(s)  { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function toDateStr(d) { return d.toISOString().slice(0,10); }

window.addEventListener('resize', () => {
    [volumeChart, statusChart, weekChart, emailTrendChart, emailTypeChart].forEach(c => c?.resize());
});
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        const page = currentPage();
        // Only auto-refresh live data pages — never re-run reports/QC/mapping
        if (!MANUAL_PAGES.has(page)) loadPageData(page, true);
    }
});

// ═══════════════════════════════════════════════════════════
//  CAMPAIGN TIME FILTER + SORT + CSV
// ═══════════════════════════════════════════════════════════

function setCampTime(start, end) {
    const s = document.getElementById('campTimeStart');
    const e = document.getElementById('campTimeEnd');
    if (s) s.value = start;
    if (e) e.value = end;
    // highlight active preset
    document.querySelectorAll('.time-preset').forEach(b => {
        b.classList.toggle('active',
            b.getAttribute('onclick') === `setCampTime('${start}','${end}')`);
    });
}

// _appliedTime holds the COMMITTED filter (empty = All Day, show everything)
let _appliedTime = { start: '', end: '' };
// DB stores call_date in local business time — no offset needed
const CAMP_TZ_OFFSET = 0;

function campTimeParams(first = false) {
    const parts = [];
    if (_appliedTime.start) parts.push(`time_start=${encodeURIComponent(_appliedTime.start)}`);
    if (_appliedTime.end)   parts.push(`time_end=${encodeURIComponent(_appliedTime.end)}`);
    if (CAMP_TZ_OFFSET !== 0) parts.push(`tz_offset=${CAMP_TZ_OFFSET}`);
    if (!parts.length) return '';
    return (first ? '?' : '&') + parts.join('&');
}

async function checkDbTimezone() {
    const btn = document.getElementById('campTzCheckBtn');
    const out = document.getElementById('campTzCheckOut');
    if (btn) { btn.disabled = true; btn.textContent = 'Checking…'; }
    if (out) { out.style.display = 'none'; out.innerHTML = ''; }
    try {
        const d = await apiFetch('/api/debug/time');
        // jsonify_ok spreads fields at top level; success=true on OK
        if (!d.success) throw new Error(d.error || 'API error');
        const dbNow   = d.db_now   || '';
        const tz      = d.global_tz || d.session_tz || 'unknown';
        const samples = [...(d.vicidial_closer_log_recent || []),
                         ...(d.vicidial_log_recent        || [])].slice(0, 6);
        const sampleHtml = samples.length
            ? samples.map(s => `<li><code>${esc(s.call_date)}</code> &mdash; ${esc(s.campaign_id)}</li>`).join('')
            : '<li>No recent calls found</li>';

        // Rough offset hint: compare DB clock to browser clock
        const jsNow   = new Date();
        const dbParse = new Date(dbNow.replace(' ', 'T'));   // parse as local time
        const diffH   = Math.round((jsNow - dbParse) / 3600000);
        // diffH = jsNow - dbParse; positive means browser is ahead (DB is behind)
        const suggestedOffset = diffH;  // add this many hours to DB time to get local time
        let hint = '';
        if (Math.abs(diffH) >= 1 && Math.abs(diffH) <= 14) {
            const dir = diffH > 0 ? 'behind' : 'ahead of';
            hint = `<br><b style="color:#4338ca">💡 Suggested offset: ${suggestedOffset > 0 ? '+' : ''}${suggestedOffset} h</b>
                    (DB clock is ~${Math.abs(diffH)}h ${dir} your browser — select this from the dropdown)`;
        } else if (Math.abs(diffH) < 1) {
            hint = `<br><b style="color:#16a34a">✅ DB clock matches your browser — no offset needed.</b>`;
        }

        if (out) {
            out.innerHTML = `<div style="background:#f0f4ff;border:1px solid #c7d2fe;border-radius:8px;padding:12px 16px;font-size:13px;line-height:1.9;">
                <b>DB NOW():</b> ${esc(dbNow)} &nbsp;|&nbsp; <b>DB Timezone:</b> ${esc(tz)}<br>
                <b>Your browser:</b> ${jsNow.toLocaleString()}${hint}
                <hr style="border:0;border-top:1px solid #c7d2fe;margin:8px 0">
                <b>Recent call_dates from DB:</b>
                <ul style="margin:4px 0 0 16px;">${sampleHtml}</ul>
                <hr style="border:0;border-top:1px solid #c7d2fe;margin:8px 0">
                <span style="color:#64748b;font-size:12px;">If call_dates are 4–5 h ahead of EST, your DB stores UTC.
                Select <b>-5 h (DB=UTC, EST)</b> from the offset dropdown above.</span>
            </div>`;
            out.style.display = 'block';
        }
    } catch(e) {
        if (out) { out.textContent = 'Error: ' + e.message; out.style.display = 'block'; }
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '🔍 Check DB Time'; }
    }
}

function applyTzOffset() {
    const sel = document.getElementById('campTzOffset');
    _tzOffset = sel ? parseInt(sel.value) : 0;
    reloadActiveCampTab();
}

function campTimeLabel() {
    if (!_appliedTime.start && !_appliedTime.end) return '';
    const s = _appliedTime.start || '00:00';
    const e = _appliedTime.end   || '23:59';
    return `${s} – ${e}`;
}

function updateCampTimeIndicator() {
    const bar = document.getElementById('campActiveFilter');
    if (!bar) return;
    const label = campTimeLabel();
    if (label) {
        bar.style.display = 'flex';
        bar.innerHTML = `<i class="fas fa-clock" style="color:#6366f1"></i> <strong>Active filter:</strong> ${esc(label)}
            <button onclick="clearCampTime()" style="margin-left:8px;padding:2px 10px;border-radius:20px;border:1px solid #e2e8f0;background:white;cursor:pointer;font-size:12px;color:#ef4444;font-weight:700;">✕ Clear</button>`;
    } else {
        bar.style.display = 'none';
    }
}

function clearCampTime() {
    _appliedTime = { start: '', end: '' };
    const s = document.getElementById('campTimeStart');
    const e = document.getElementById('campTimeEnd');
    if (s) s.value = '';
    if (e) e.value = '';
    document.querySelectorAll('.time-preset').forEach(b => b.classList.remove('active'));
    updateCampTimeIndicator();
    reloadActiveCampTab();
}

function reloadActiveCampTab() {
    const activeTab = document.querySelector('.tab-pill[data-ctab].active')?.dataset.ctab;
    if (!activeTab) return;
    if (activeTab === 'camp-today')         fetchCampaignPerformance();
    else if (activeTab === 'camp-7d')       fetchCamp7d();
    else if (activeTab === 'camp-30d')      fetchCamp30d();
    else if (activeTab === 'camp-specific') fetchCampSpecific();
}

// Apply button commits the selected time and re-runs the active tab
document.addEventListener('DOMContentLoaded', () => {
    updateCampTimeIndicator();  // starts as All Day (no filter)

    document.getElementById('campTimeApplyBtn')?.addEventListener('click', () => {
        _appliedTime.start = document.getElementById('campTimeStart')?.value || '';
        _appliedTime.end   = document.getElementById('campTimeEnd')?.value   || '';
        updateCampTimeIndicator();
        reloadActiveCampTab();
    });
});

// ── Sortable table columns ────────────────────────────────
let _campSortCol = null, _campSortAsc = true;
let _campLastData = [];   // cache last loaded rows for sort + CSV

function makeSortable(thead, data, renderFn) {
    thead.querySelectorAll('th').forEach((th, idx) => {
        th.style.cursor = 'pointer';
        th.style.userSelect = 'none';
        th.addEventListener('click', () => {
            if (_campSortCol === idx) _campSortAsc = !_campSortAsc;
            else { _campSortCol = idx; _campSortAsc = true; }
            const sorted = [...data].sort((a, b) => {
                const av = Object.values(a)[idx] ?? '';
                const bv = Object.values(b)[idx] ?? '';
                const n = (v) => isNaN(parseFloat(v)) ? String(v).toLowerCase() : parseFloat(v);
                return _campSortAsc ? (n(av) > n(bv) ? 1 : -1) : (n(av) < n(bv) ? 1 : -1);
            });
            renderFn(sorted);
            thead.querySelectorAll('th').forEach((t, i) => {
                t.textContent = t.textContent.replace(/ [▲▼]$/, '');
                if (i === idx) t.textContent += _campSortAsc ? ' ▲' : ' ▼';
            });
        });
    });
}

// ── CSV export ────────────────────────────────────────────
function exportCampCSV() {
    if (!_campLastData.length) { alert('Load data first.'); return; }
    const headers = ['Campaign','Calls','Answered','Ans%','Abandoned','Abd%','Avg Talk','Last Call','Total Mins'];
    const rows = _campLastData.map(r => [
        r.campaign_id||r.campaign, r.total_calls||r.calls, r.answered,
        (r.answer_rate??0).toFixed(1)+'%', r.abandoned,
        (r.abandon_rate??0).toFixed(1)+'%', r.avg_talk||'',
        r.last_call||'', r.talk_time_mins||''
    ]);
    const csv = [headers, ...rows].map(r => r.map(v => `"${String(v).replace(/"/g,'""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url  = URL.createObjectURL(blob);
    const a    = Object.assign(document.createElement('a'), { href: url, download: `campaigns_${new Date().toISOString().slice(0,10)}.csv` });
    a.click(); URL.revokeObjectURL(url);
}

// ═══════════════════════════════════════════════════════════
//  CAMPAIGNS EXTENDED TABS
// ═══════════════════════════════════════════════════════════

// ── Camp tab router ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Campaign sub-tabs
    document.querySelectorAll('.tab-pill[data-ctab]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-pill[data-ctab]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.camp-section').forEach(s => s.style.display = 'none');
            const sec = document.getElementById(btn.dataset.ctab);
            if (sec) sec.style.display = '';
            onCampTabSwitch(btn.dataset.ctab);
        });
    });

    // Service Level inner sub-tabs
    document.querySelectorAll('.tab-pill[data-sltab]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-pill[data-sltab]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.sl-section').forEach(s => s.style.display = 'none');
            const sec = document.getElementById(btn.dataset.sltab);
            if (sec) sec.style.display = '';
            onSlTabSwitch(btn.dataset.sltab);
        });
    });

    // Forecast sub-tabs
    document.querySelectorAll('.tab-pill[data-ftab]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-pill[data-ftab]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.fc-section').forEach(s => s.style.display = 'none');
            const sec = document.getElementById(btn.dataset.ftab);
            if (sec) sec.style.display = '';
        });
    });

    // Schedule sub-tabs
    document.querySelectorAll('.tab-pill[data-schtab]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-pill[data-schtab]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.sch-section').forEach(s => s.style.display = 'none');
            const sec = document.getElementById(btn.dataset.schtab);
            if (sec) sec.style.display = '';
        });
    });

    // DID sub-tabs removed — single-table design

    // Manual load buttons
    document.getElementById('camp7dLoadBtn')?.addEventListener('click', fetchCamp7d);
    document.getElementById('camp30dLoadBtn')?.addEventListener('click', fetchCamp30d);
    document.getElementById('campSpecificLoadBtn')?.addEventListener('click', fetchCampSpecific);
    document.getElementById('campCmpLoadBtn')?.addEventListener('click', fetchCampCompare);
    document.getElementById('campHourlyLoadBtn')?.addEventListener('click', fetchCampHourly);
    document.getElementById('campQueueRefreshBtn')?.addEventListener('click', fetchQueueData);
    document.getElementById('fcVolumeLoadBtn')?.addEventListener('click', fetchFcVolume);
    document.getElementById('fcStaffLoadBtn')?.addEventListener('click', fetchFcStaff);
    document.getElementById('schTodayLoadBtn')?.addEventListener('click', fetchSchToday);
    document.getElementById('schAdhLoadBtn')?.addEventListener('click', fetchSchAdherence);
    document.getElementById('anomalyRunBtn')?.addEventListener('click', runAnomalyDetect);
    document.getElementById('qmRefreshBtn')?.addEventListener('click', loadQueryMonitor);
    document.getElementById('didProbRefreshBtn')?.addEventListener('click', fetchDidProblematic);
    document.getElementById('didSearchBtn')?.addEventListener('click', fetchDidSearch);
    document.getElementById('didSearchInput')?.addEventListener('keydown', e => { if (e.key === 'Enter') fetchDidSearch(); });
});

let campHourlyChart = null;

function onCampTabSwitch(tab) {
    if      (tab === 'camp-today')    fetchCampaignPerformance();
    else if (tab === 'camp-7d')       fetchCamp7d();
    else if (tab === 'camp-30d')      fetchCamp30d();
    else if (tab === 'camp-queue')    fetchQueueData();
    else if (tab === 'camp-sl-current' || tab === 'camp-sl') fetchSlCurrent();
}

async function fetchCamp7d() {
    const tbody = document.getElementById('camp7dBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="9" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>';
    try {
        const d = await apiFetch('/api/campaigns/performance?days=7' + campTimeParams());
        if (!d.success) throw new Error(d.error || 'API error');
        if (!d.data || !d.data.length) { tbody.innerHTML = '<tr><td colspan="9" class="loading-cell" style="color:#94a3b8">No data for the last 7 days</td></tr>'; return; }
        renderCampTable(tbody, d.data,
            r => `<td class="num" style="color:#94a3b8">${fmt(r.talk_time_mins)} min</td>`,
            (data, tm) => `<td class="num" style="color:#94a3b8">${Math.round(tm)} min</td>`
        );
        updateCampTotals('camp7dTotals', d.totals);
    } catch(e) { tbody.innerHTML = `<tr><td colspan="9" style="color:red;padding:12px">Error: ${esc(e.message)}</td></tr>`; }
}

async function fetchCamp30d() {
    const tbody = document.getElementById('camp30dBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="9" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>';
    try {
        const d = await apiFetch('/api/campaigns/performance?days=30' + campTimeParams());
        if (!d.success) throw new Error(d.error || 'API error');
        if (!d.data || !d.data.length) { tbody.innerHTML = '<tr><td colspan="9" class="loading-cell" style="color:#94a3b8">No data for the last 30 days</td></tr>'; return; }
        renderCampTable(tbody, d.data,
            r => `<td class="num" style="color:#94a3b8">${fmt(r.active_days)} days</td>`,
            (data) => `<td class="num" style="color:#94a3b8">${data.length} camps</td>`
        );
        updateCampTotals('camp30dTotals', d.totals);
    } catch(e) { tbody.innerHTML = `<tr><td colspan="9" style="color:red;padding:12px">Error: ${esc(e.message)}</td></tr>`; }
}

function updateCampTotals(id, t) {
    if (!t) return;
    const el = document.getElementById(id);
    if (!el) return;
    const rc = (r,g,w) => r>=g?'#22c55e':r>=w?'#f59e0b':'#ef4444';
    el.innerHTML = `<span class="status-pill">${fmt(t.calls)} total</span>
        <span class="status-pill" style="color:${rc(t.answer_rate,80,60)}">${t.answer_rate}% ans</span>
        <span class="status-pill" style="color:${t.abandon_rate>20?'#ef4444':'inherit'}">${t.abandon_rate}% abd</span>`;
}

async function fetchCampSpecific() {
    const camp = document.getElementById('campSpecificSelect')?.value.trim();
    const days  = document.getElementById('campSpecificDays')?.value || 30;
    const out   = document.getElementById('campSpecificOut');
    if (!out) return;
    out.innerHTML = '<p style="padding:20px;color:#94a3b8"><i class="fas fa-spinner fa-spin"></i> Loading…</p>';
    try {
        const url = `/api/campaigns/performance?days=${days}${camp ? '&campaign='+encodeURIComponent(camp) : ''}` + campTimeParams();
        const d = await apiFetch(url);
        if (!d.data || !d.data.length) { out.innerHTML = '<p style="padding:20px;color:#94a3b8">No data found.</p>'; return; }
        out.innerHTML = `<div class="table-wrap"><table class="data-table">
            <thead><tr>
                <th>Campaign</th><th class="num">Calls</th><th class="num">Answered</th>
                <th class="num">Ans %</th><th class="num">Abandoned</th><th class="num">Abd %</th>
                <th class="num">Avg Talk</th><th class="num">Last Call</th><th class="num">Total Mins</th>
            </tr></thead>
            <tbody id="campSpecificTbody">${d.data.map(r => campRow(r, `<td class="num" style="color:#94a3b8">${fmt(r.talk_time_mins)} min</td>`)).join('')}
            ${campTotalsRow(d.data, (data,tm) => `<td class="num">${Math.round(tm)} min</td>`)}
            </tbody>
        </table></div>`;
        _campLastData = d.data;
    } catch(e) { out.innerHTML = `<p style="color:red;padding:20px">Error: ${esc(e.message)}</p>`; }
}

async function fetchCampCompare() {
    const a    = document.getElementById('campCmp1')?.value.trim();
    const b    = document.getElementById('campCmp2')?.value.trim();
    const days = document.getElementById('campCmpDays')?.value || 7;
    const out  = document.getElementById('campCmpOut');
    if (!out || !a || !b) { if(out) out.innerHTML='<p style="padding:20px;color:#f59e0b">Select both campaigns first.</p>'; return; }
    out.innerHTML = '<p style="padding:20px;color:#94a3b8"><i class="fas fa-spinner fa-spin"></i> Loading…</p>';
    try {
        const d = await apiFetch(`/api/campaigns/compare?campaigns=${encodeURIComponent(a)},${encodeURIComponent(b)}&days=${days}`);
        if (!d.data || !d.data.length) { out.innerHTML='<p style="padding:20px;color:#94a3b8">No data.</p>'; return; }
        out.innerHTML = `<div class="table-wrap"><table class="data-table">
            <thead><tr>
                <th>Campaign</th><th class="num">Calls</th><th class="num">Answered</th>
                <th class="num">Ans %</th><th class="num">Abandoned</th><th class="num">Abd %</th>
                <th class="num">Avg Talk</th><th class="num">Last Call</th>
            </tr></thead>
            <tbody>${d.data.map(r => campRow(r)).join('')}</tbody>
        </table></div>`;
    } catch(e) { out.innerHTML=`<p style="color:red;padding:20px">Error: ${esc(e.message)}</p>`; }
}

async function fetchCampHourly() {
    const camp  = document.getElementById('campHourlySelect')?.value.trim();
    const tbody = document.getElementById('campHourlyBody');
    if (!camp) { alert('Enter a campaign ID.'); return; }
    if (tbody) tbody.innerHTML = '<tr><td colspan="4" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>';
    try {
        const d = await apiFetch(`/api/campaigns/hourly?campaign=${encodeURIComponent(camp)}`);
        const rows = d.data || [];

        // Chart
        const canvas = document.getElementById('campHourlyChart');
        if (canvas) {
            if (campHourlyChart) campHourlyChart.destroy();
            campHourlyChart = new Chart(canvas.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: rows.map(r => `${String(r.hour||r.hour_of_day).padStart(2,'0')}:00`),
                    datasets: [{
                        label: 'Calls',
                        data: rows.map(r => r.total_calls),
                        backgroundColor: '#6366f1',
                        borderRadius: 4
                    }]
                },
                options: { responsive: true, plugins: { legend: { display: false } } }
            });
        }

        if (tbody) {
            tbody.innerHTML = rows.length ? rows.map(r => `<tr>
                <td>${String(r.hour||r.hour_of_day).padStart(2,'0')}:00</td>
                <td class="num">${fmt(r.total_calls)}</td>
                <td class="num">${fmt(r.answered)}</td>
                <td class="num">${(r.avg_handle_time||0).toFixed(0)}s</td>
            </tr>`).join('') : '<tr><td colspan="4" class="loading-cell">No data</td></tr>';
        }
    } catch(e) { if(tbody) tbody.innerHTML=`<tr><td colspan="4" style="color:red;padding:12px">${esc(e.message)}</td></tr>`; }
}

async function fetchQueueData() {
    const out = document.getElementById('campQueueContent');
    const tbody = document.getElementById('campInboundBody');
    if (out) out.innerHTML = '<p style="padding:16px;color:#94a3b8"><i class="fas fa-spinner fa-spin"></i> Loading live queue…</p>';
    try {
        const d = await apiFetch('/api/queue/status');
        const q = d.data || {};
        if (out) out.innerHTML = `
            <div class="kpi-grid" style="margin-bottom:16px;">
                <div class="kpi-card"><div class="kpi-label">Calls Waiting</div><div class="kpi-value">${fmt(q.calls_waiting)}</div></div>
                <div class="kpi-card"><div class="kpi-label">Agents Ready</div><div class="kpi-value">${fmt(q.agents_ready)}</div></div>
                <div class="kpi-card"><div class="kpi-label">In Call</div><div class="kpi-value">${fmt(q.agents_incall)}</div></div>
                <div class="kpi-card"><div class="kpi-label">Avg Wait</div><div class="kpi-value">${q.avg_wait||'—'}s</div></div>
            </div>`;
    } catch(e) { if(out) out.innerHTML=`<p style="color:red;padding:16px">${esc(e.message)}</p>`; }

    try {
        const d2 = await apiFetch('/api/agent/inbound-groups');
        const groups = d2.data || [];
        if (tbody) tbody.innerHTML = groups.length ? groups.map(g => `<tr>
            <td>${esc(g.group_id)}</td>
            <td>${esc(g.group_name)}</td>
            <td class="num">${fmt(g.calls_today)}</td>
            <td class="num">${fmt(g.agents_logged)}</td>
        </tr>`).join('') : '<tr><td colspan="4" class="loading-cell">No groups</td></tr>';
    } catch(e) { if(tbody) tbody.innerHTML=`<tr><td colspan="4" style="color:red;padding:12px">${esc(e.message)}</td></tr>`; }
}

// ── Service Level sub-tabs ────────────────────────────────
const _slLoaded = new Set();
function onSlTabSwitch(tab) {
    if (_slLoaded.has(tab)) return;
    _slLoaded.add(tab);
    if (tab === 'sl-current') fetchSlCurrent();
    else if (tab === 'sl-trend') fetchSlTrend(7);
    else if (tab === 'sl-hourly') fetchSlHourly();
    else if (tab === 'sl-breaches') fetchSlBreaches();
}

async function fetchSlCurrent() {
    const tbody = document.getElementById('slCurrentBody');
    if (!tbody) return;
    try {
        const d = await apiFetch('/api/service-level/current');
        const rows = d.data || [];
        tbody.innerHTML = rows.length ? rows.map(r => {
            const pct = r.sl_pct || 0;
            const color = pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444';
            return `<tr>
                <td>${esc(r.campaign_id)}</td>
                <td class="num">${fmt(r.total_calls)}</td>
                <td class="num">${fmt(r.answered_in_sla)}</td>
                <td class="num" style="color:${color};font-weight:700">${pct.toFixed(1)}%</td>
                <td class="num">${(r.avg_wait_sec||0).toFixed(0)}s</td>
                <td class="num">${fmt(r.abandoned)}</td>
            </tr>`;
        }).join('') : '<tr><td colspan="6" class="loading-cell">No data today</td></tr>';
    } catch(e) { tbody.innerHTML=`<tr><td colspan="6" style="color:red;padding:12px">${esc(e.message)}</td></tr>`; }
}

async function fetchSlTrend(days) {
    const tbody = document.getElementById('slTrendBody');
    if (!tbody) return;
    try {
        const d = await apiFetch(`/api/service-level/trend?days=${days}`);
        const rows = d.data || [];
        tbody.innerHTML = rows.length ? rows.map(r => {
            const pct = r.sl_pct || 0;
            const color = pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444';
            return `<tr>
                <td>${esc(r.call_day)}</td>
                <td class="num">${fmt(r.total_calls)}</td>
                <td class="num">${fmt(r.answered_in_sla)}</td>
                <td class="num" style="color:${color};font-weight:700">${pct.toFixed(1)}%</td>
                <td class="num">${(r.avg_wait_sec||0).toFixed(0)}s</td>
            </tr>`;
        }).join('') : '<tr><td colspan="5" class="loading-cell">No data</td></tr>';
    } catch(e) { tbody.innerHTML=`<tr><td colspan="5" style="color:red;padding:12px">${esc(e.message)}</td></tr>`; }
}

async function fetchSlHourly() {
    const tbody = document.getElementById('slHourlyBody');
    if (!tbody) return;
    try {
        const d = await apiFetch('/api/service-level/hourly');
        const rows = d.data || [];
        tbody.innerHTML = rows.length ? rows.map(r => {
            const pct = r.sl_pct || 0;
            const color = pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444';
            return `<tr>
                <td>${String(r.hour_of_day).padStart(2,'0')}:00</td>
                <td class="num">${fmt(r.total_calls)}</td>
                <td class="num">${fmt(r.answered_in_sla)}</td>
                <td class="num" style="color:${color};font-weight:700">${pct.toFixed(1)}%</td>
                <td class="num">${(r.avg_wait_sec||0).toFixed(0)}s</td>
            </tr>`;
        }).join('') : '<tr><td colspan="5" class="loading-cell">No data today</td></tr>';
    } catch(e) { tbody.innerHTML=`<tr><td colspan="5" style="color:red;padding:12px">${esc(e.message)}</td></tr>`; }
}

async function fetchSlBreaches() {
    const tbody = document.getElementById('slBreachBody');
    if (!tbody) return;
    try {
        const d = await apiFetch('/api/service-level/breaches');
        const rows = d.data || [];
        tbody.innerHTML = rows.length ? rows.map(r => `<tr>
            <td>${esc(r.call_day)}</td>
            <td>${esc(r.campaign_id)}</td>
            <td class="num">${fmt(r.total_calls)}</td>
            <td class="num" style="color:#ef4444;font-weight:700">${(r.sl_pct||0).toFixed(1)}%</td>
            <td class="num">${(r.avg_wait_sec||0).toFixed(0)}s</td>
            <td class="num">${(r.max_wait_sec||0).toFixed(0)}s</td>
        </tr>`).join('') : '<tr><td colspan="6" class="loading-cell" style="color:#22c55e">No SLA breaches in last 7 days</td></tr>';
    } catch(e) { tbody.innerHTML=`<tr><td colspan="6" style="color:red;padding:12px">${esc(e.message)}</td></tr>`; }
}

// ═══════════════════════════════════════════════════════════
//  PREDICTIVE ANALYTICS (FORECAST)
// ═══════════════════════════════════════════════════════════
let fcVolumeChart = null, fcStaffChart = null;

function initForecastPage() {
    fetchFcVolume();
    populateFcCampaigns();
}

async function fetchFcVolume() {
    const days  = document.getElementById('fcDaysAhead')?.value || 7;
    const tbody = document.getElementById('fcVolumeBody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="loading-cell"><i class="fas fa-spinner fa-spin"></i> Generating forecast…</td></tr>';
    try {
        const d = await apiFetch(`/api/forecast/volume?days_ahead=${days}`);
        const rows = d.data || [];
        const label = document.getElementById('fcModelLabel');
        if (label) label.textContent = `Model: ${d.model || 'Linear Regression'} · ${rows.length} days`;

        const canvas = document.getElementById('fcVolumeChart');
        if (canvas) {
            if (fcVolumeChart) fcVolumeChart.destroy();
            fcVolumeChart = new Chart(canvas.getContext('2d'), {
                type: 'line',
                data: {
                    labels: rows.map(r => r.date),
                    datasets: [
                        { label: 'Predicted', data: rows.map(r => r.predicted_calls), borderColor: '#6366f1', backgroundColor: 'rgba(99,102,241,0.08)', tension: 0.3, fill: true },
                        { label: 'Low',  data: rows.map(r => r.low),  borderColor: '#94a3b8', borderDash: [4,4], tension: 0.3, fill: false },
                        { label: 'High', data: rows.map(r => r.high), borderColor: '#94a3b8', borderDash: [4,4], tension: 0.3, fill: false }
                    ]
                },
                options: { responsive: true, plugins: { legend: { position: 'top' } } }
            });
        }

        if (tbody) tbody.innerHTML = rows.length ? rows.map(r => `<tr>
            <td>${esc(r.date)}</td>
            <td>${esc(r.day_name||'')}</td>
            <td class="num" style="font-weight:700">${fmt(r.predicted_calls)}</td>
            <td class="num" style="color:#94a3b8">${fmt(r.low)}</td>
            <td class="num" style="color:#94a3b8">${fmt(r.high)}</td>
            <td class="num">${fmt(r.recommended_agents)}</td>
        </tr>`).join('') : '<tr><td colspan="6" class="loading-cell">No forecast data</td></tr>';
    } catch(e) { if(tbody) tbody.innerHTML=`<tr><td colspan="6" style="color:red;padding:12px">Error: ${esc(e.message)}</td></tr>`; }
}

async function populateFcCampaigns() {
    const sel = document.getElementById('fcStaffCampaign');
    if (!sel) return;
    try {
        const d = await apiFetch('/api/campaigns/performance');
        (d.data || []).forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.campaign_id; opt.textContent = c.campaign_id;
            sel.appendChild(opt);
        });
    } catch(e) {}
}

async function fetchFcStaff() {
    const camp  = document.getElementById('fcStaffCampaign')?.value || '';
    const tbody = document.getElementById('fcStaffBody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="3" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>';
    try {
        const url = `/api/forecast/staffing${camp ? '?campaign='+encodeURIComponent(camp) : ''}`;
        const d = await apiFetch(url);
        const rows = d.data || [];

        const canvas = document.getElementById('fcStaffChart');
        if (canvas) {
            if (fcStaffChart) fcStaffChart.destroy();
            fcStaffChart = new Chart(canvas.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: rows.map(r => `${String(r.hour).padStart(2,'0')}:00`),
                    datasets: [{
                        label: 'Recommended Agents',
                        data: rows.map(r => r.recommended_agents),
                        backgroundColor: '#6366f1',
                        borderRadius: 4
                    }]
                },
                options: { responsive: true, plugins: { legend: { display: false } } }
            });
        }

        if (tbody) tbody.innerHTML = rows.length ? rows.map(r => `<tr>
            <td>${String(r.hour).padStart(2,'0')}:00</td>
            <td class="num">${fmt(r.avg_calls)}</td>
            <td class="num" style="font-weight:700;color:#6366f1">${fmt(r.recommended_agents)}</td>
        </tr>`).join('') : '<tr><td colspan="3" class="loading-cell">No staffing data</td></tr>';
    } catch(e) { if(tbody) tbody.innerHTML=`<tr><td colspan="3" style="color:red;padding:12px">${esc(e.message)}</td></tr>`; }
}

// ═══════════════════════════════════════════════════════════
//  SCHEDULE
// ═══════════════════════════════════════════════════════════
function initSchedulePage() {
    fetchSchToday();
}

async function fetchSchToday() {
    const tbody = document.getElementById('schTodayBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>';
    try {
        const d = await apiFetch('/api/schedule/agents');
        const rows = d.data || [];
        tbody.innerHTML = rows.length ? rows.map(r => `<tr>
            <td>${esc(r.agent_user)}</td>
            <td>${esc(r.agent_name||'')}</td>
            <td>${esc(r.first_login||'—')}</td>
            <td>${esc(r.last_activity||'—')}</td>
            <td class="num">${fmt(r.talk_time_mins)} min</td>
            <td class="num">${fmt(r.calls)}</td>
        </tr>`).join('') : '<tr><td colspan="6" class="loading-cell">No activity today</td></tr>';
    } catch(e) { tbody.innerHTML=`<tr><td colspan="6" style="color:red;padding:12px">${esc(e.message)}</td></tr>`; }
}

async function fetchSchAdherence() {
    const tbody = document.getElementById('schAdhBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>';
    try {
        const d = await apiFetch('/api/schedule/adherence');
        const rows = d.data || [];
        tbody.innerHTML = rows.length ? rows.map(r => `<tr>
            <td>${esc(r.agent_user)}</td>
            <td>${esc(r.agent_name||'')}</td>
            <td>${esc(r.work_date||'')}</td>
            <td>${esc(r.clock_in||'—')}</td>
            <td>${esc(r.clock_out||'—')}</td>
            <td class="num">${(r.active_hours||0).toFixed(1)}h</td>
        </tr>`).join('') : '<tr><td colspan="6" class="loading-cell">No adherence data</td></tr>';
    } catch(e) { tbody.innerHTML=`<tr><td colspan="6" style="color:red;padding:12px">${esc(e.message)}</td></tr>`; }
}

// ═══════════════════════════════════════════════════════════
//  ANOMALY DETECTION
// ═══════════════════════════════════════════════════════════
async function runAnomalyDetect() {
    const hours   = document.getElementById('anomalyWindow')?.value || 1;
    const out     = document.getElementById('anomalyResults');
    const checked = document.getElementById('anomalyCheckedAt');
    const badge   = document.getElementById('anomalyBadge');
    if (out) out.innerHTML = '<div style="text-align:center;padding:40px;color:#94a3b8"><i class="fas fa-spinner fa-spin" style="font-size:28px"></i><p style="margin-top:12px">Scanning…</p></div>';
    try {
        const d = await apiFetch(`/api/anomaly/detect?hours=${hours}`);
        const anomalies = d.data || [];
        if (checked) checked.textContent = 'Checked at ' + new Date().toLocaleTimeString();
        if (badge) { badge.textContent = anomalies.length || ''; badge.style.display = anomalies.length ? 'inline' : 'none'; }

        if (!anomalies.length) {
            out.innerHTML = `<div class="card" style="text-align:center;padding:50px;">
                <i class="fas fa-circle-check" style="font-size:40px;color:#22c55e;display:block;margin-bottom:12px;"></i>
                <h3 style="color:#22c55e;margin:0 0 8px">No Anomalies Detected</h3>
                <p style="color:#94a3b8;margin:0">System looks normal for the last ${hours} hour(s)</p>
            </div>`;
            return;
        }

        const sevColor = { HIGH:'#ef4444', MEDIUM:'#f59e0b', LOW:'#94a3b8' };
        out.innerHTML = `<div class="card">
            <div class="card-header"><h2>${anomalies.length} Anomaly${anomalies.length>1?'s':''} Detected</h2></div>
            ${anomalies.map(a => `
            <div style="border-left:4px solid ${sevColor[a.severity]||'#94a3b8'};padding:16px 20px;margin-bottom:12px;background:#fafafa;border-radius:0 10px 10px 0;">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
                    <span style="font-weight:700;color:${sevColor[a.severity]||'#94a3b8'};font-size:12px;background:${sevColor[a.severity]||'#94a3b8'}22;padding:2px 8px;border-radius:20px;">${esc(a.severity)}</span>
                    <strong>${esc(a.type||a.anomaly_type||'Anomaly')}</strong>
                </div>
                <p style="margin:0 0 4px;color:#374151;">${esc(a.description||a.detail||'')}</p>
                <small style="color:#94a3b8;">${esc(a.campaign||'')} ${a.value!=null?'· Value: '+a.value:''}</small>
            </div>`).join('')}
        </div>`;
    } catch(e) { if(out) out.innerHTML=`<div class="card" style="color:red;padding:20px">Error: ${esc(e.message)}</div>`; }
}

// ═══════════════════════════════════════════════════════════
//  DID INSPECTOR
// ═══════════════════════════════════════════════════════════
let _didAllRows   = [];
let _didSortCol   = 'calls_period';
let _didSortAsc   = false;

async function fetchDids() {
    const tbody = document.getElementById('didAllBody');
    if (!tbody) return;
    const days = document.getElementById('didPeriod')?.value || 30;
    tbody.innerHTML = `<tr><td colspan="10" class="loading-cell"><i class="fas fa-spinner fa-spin"></i> Loading…</td></tr>`;
    try {
        const d = await apiFetch(`/api/dids/list?days=${days}`);
        _didAllRows = d.data || [];
        renderDidKpis(d);
        didApplyFilters();
    } catch(e) {
        tbody.innerHTML = `<tr><td colspan="10" style="color:red;padding:12px">${esc(e.message)}</td></tr>`;
    }
}

function renderDidKpis(d) {
    const el = document.getElementById('didKpis');
    if (!el) return;
    const rows = d.data || [];
    const withCalls  = rows.filter(r => r.calls_period > 0).length;
    const zeroCalls  = rows.filter(r => r.calls_period === 0).length;
    const totalCalls = rows.reduce((s,r) => s + r.calls_period, 0);
    const groups     = new Set(rows.map(r => r.group).filter(Boolean)).size;
    function kpi(label, val, color) {
        return `<div style="background:white;border:1px solid #e2e8f0;border-radius:12px;padding:14px 18px;text-align:center;">
            <div style="font-size:22px;font-weight:800;color:${color}">${val}</div>
            <div style="font-size:11px;color:#94a3b8;margin-top:2px;font-weight:600;text-transform:uppercase;letter-spacing:.05em">${label}</div>
        </div>`;
    }
    el.innerHTML =
        kpi('Total DIDs',    rows.length,  '#0f172a') +
        kpi('Active',        d.active||0,  '#22c55e') +
        kpi('Inactive',      d.inactive||0,'#ef4444') +
        kpi('With Calls',    withCalls,    '#6366f1') +
        kpi('Zero Calls',    zeroCalls,    '#f59e0b') +
        kpi('Total Calls',   fmt(totalCalls),'#0f172a') +
        kpi('Groups',        groups,       '#64748b');
}

function didApplyFilters() {
    const text   = (document.getElementById('didFilterText')?.value  || '').toLowerCase();
    const status = document.getElementById('didFilterStatus')?.value || 'all';
    const calls  = document.getElementById('didFilterCalls')?.value  || 'all';

    let rows = _didAllRows.filter(r => {
        if (text && !`${r.did} ${r.description} ${r.group} ${r.route} ${r.carrier}`.toLowerCase().includes(text)) return false;
        if (status === 'active'   && r.active !== 'Y') return false;
        if (status === 'inactive' && r.active === 'Y') return false;
        if (calls === 'active_calls' && r.calls_period === 0) return false;
        if (calls === 'zero'         && r.calls_period >  0) return false;
        return true;
    });

    // Sort
    rows = rows.slice().sort((a, b) => {
        let av = a[_didSortCol], bv = b[_didSortCol];
        if (typeof av === 'number') return _didSortAsc ? av - bv : bv - av;
        av = String(av||'').toLowerCase(); bv = String(bv||'').toLowerCase();
        return _didSortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
    });

    const sub  = document.getElementById('didTableSub');
    if (sub) sub.textContent = `${rows.length} of ${_didAllRows.length} DIDs · Last ${document.getElementById('didPeriod')?.value||30} days`;

    const tbody = document.getElementById('didAllBody');
    if (!tbody) return;
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="10" class="loading-cell">No DIDs match filters</td></tr>'; return; }

    tbody.innerHTML = rows.map(r => {
        const isActive = r.active === 'Y';
        const hasCall  = r.calls_period > 0;
        const callColor = hasCall ? '#22c55e' : '#94a3b8';
        const issue = !isActive ? 'Inactive' : !hasCall ? 'No calls' : '';
        const issueTag = issue ? `<span style="font-size:10px;background:#fef3c7;color:#92400e;padding:1px 6px;border-radius:5px;margin-left:4px;">${issue}</span>` : '';
        return `<tr style="${!isActive ? 'opacity:.75;' : ''}">
            <td style="font-family:monospace;font-weight:700;font-size:13px;">${esc(r.did)}<span style="font-size:10px;color:#94a3b8;margin-left:4px;">#${r.did_id}</span></td>
            <td>${esc(r.description||'—')}</td>
            <td>${r.group && r.group !== '---NONE---' ? `<span style="background:#ede9fe;color:#6d28d9;padding:2px 8px;border-radius:6px;font-size:12px;font-weight:600;">${esc(r.group)}</span>` : '<span style="color:#cbd5e1">—</span>'}</td>
            <td style="font-size:12px;color:#64748b;">${esc(r.route||'—')}</td>
            <td>${issueTag}<span class="status-pill ${isActive?'ok':'err'}" style="font-size:11px;">${isActive?'Active':'Inactive'}</span></td>
            <td class="num" style="font-weight:700;color:${callColor};">${fmt(r.calls_period)}</td>
            <td class="num" style="color:#64748b;">${r.avg_talk ? Math.floor(r.avg_talk/60)+':'+String(Math.round(r.avg_talk%60)).padStart(2,'0') : '—'}</td>
            <td class="num" style="color:#64748b;">${r.total_talk_min ? r.total_talk_min+' min' : '—'}</td>
            <td style="font-size:12px;color:${r.last_call==='Never'?'#94a3b8':'#374151'};">${esc(r.last_call)}</td>
            <td style="font-size:12px;color:#94a3b8;">${esc(r.modified||'—')}</td>
        </tr>`;
    }).join('');
}

function didExportCSV() {
    if (!_didAllRows.length) return;
    const cols = ['did','description','group','route','active','calls_period','avg_talk','total_talk_min','last_call','modified','carrier','campaign'];
    const header = 'DID,Description,Group,Route,Status,Calls,Avg Talk(s),Total Mins,Last Call,Modified,Carrier,Campaign';
    const lines  = [header, ..._didAllRows.map(r => cols.map(c => `"${(r[c]||'').toString().replace(/"/g,'""')}"`).join(','))];
    const blob = new Blob([lines.join('\n')], {type:'text/csv'});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = `DIDs_${new Date().toISOString().slice(0,10)}.csv`; a.click();
}

document.addEventListener('DOMContentLoaded', () => {
    // Column sort click
    document.getElementById('didTable')?.addEventListener('click', e => {
        const th = e.target.closest('.did-sort');
        if (!th) return;
        const col = th.dataset.col;
        if (_didSortCol === col) _didSortAsc = !_didSortAsc;
        else { _didSortCol = col; _didSortAsc = false; }
        document.querySelectorAll('.did-sort').forEach(h => h.textContent = h.textContent.replace(/ [↑↓]$/,'') + ' ↕');
        th.textContent = th.textContent.replace(/ [↕↑↓]$/,'') + (_didSortAsc ? ' ↑' : ' ↓');
        didApplyFilters();
    });
});

// ═══════════════════════════════════════════════════════════
//  QUERY MONITOR
// ═══════════════════════════════════════════════════════════
async function loadQueryMonitor() {
    const checked = document.getElementById('qmCheckedAt');
    const kpiGrid = document.getElementById('qmKpiGrid');
    const tbody   = document.getElementById('qmActiveBody');
    const tblBody = document.getElementById('qmTablesBody');
    if (checked) checked.textContent = 'Refreshing…';
    try {
        const d = await apiFetch('/api/query-monitor/status');
        if (checked) checked.textContent = 'Updated ' + new Date().toLocaleTimeString();
        const s = d.data || {};

        if (kpiGrid) kpiGrid.innerHTML = `
            <div class="kpi-card"><div class="kpi-label">Active Queries</div><div class="kpi-value" style="color:${(s.active_count||0)>5?'#ef4444':'#22c55e'}">${s.active_count||0}</div></div>
            <div class="kpi-card"><div class="kpi-label">Total Processes</div><div class="kpi-value">${fmt(s.total_processes)}</div></div>
            <div class="kpi-card"><div class="kpi-label">Longest Query</div><div class="kpi-value">${(s.longest_query_sec||0)}s</div></div>
            <div class="kpi-card"><div class="kpi-label">DB Uptime</div><div class="kpi-value" style="font-size:14px">${esc(s.uptime||'—')}</div></div>`;

        const active = s.active_queries || [];
        if (tbody) tbody.innerHTML = active.length ? active.map(r => `<tr>
            <td>${esc(r.Id)}</td>
            <td>${esc(r.User)}</td>
            <td>${esc(r.Command)}</td>
            <td class="num" style="${(r.Time||0)>30?'color:#ef4444;font-weight:700':''}">${r.Time||0}</td>
            <td>${esc(r.State||'')}</td>
            <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:monospace;font-size:12px">${esc((r.Info||'').slice(0,120))}</td>
        </tr>`).join('') : '<tr><td colspan="6" class="loading-cell" style="color:#22c55e">No active queries</td></tr>';

        const tables = s.table_sizes || [];
        if (tblBody) tblBody.innerHTML = tables.length ? tables.map(t => `<tr>
            <td>${esc(t.table_name)}</td>
            <td class="num">${(t.data_mb||0).toFixed(2)}</td>
            <td class="num">${(t.index_mb||0).toFixed(2)}</td>
            <td class="num">${fmt(t.row_estimate)}</td>
        </tr>`).join('') : '<tr><td colspan="4" class="loading-cell">No table data</td></tr>';

    } catch(e) {
        if (checked) checked.textContent = 'Error';
        if (tbody) tbody.innerHTML=`<tr><td colspan="6" style="color:red;padding:12px">${esc(e.message)}</td></tr>`;
    }
}
