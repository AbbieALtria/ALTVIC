// ─── APT Download ────────────────────────────────────────────────────────────

function aptToggleParams() {
    const body = document.getElementById('aptParamsBody');
    const chevron = document.getElementById('aptParamsChevron');
    const open = body.style.display === '';
    body.style.display = open ? 'none' : '';
    chevron.style.transform = open ? '' : 'rotate(180deg)';
}

function aptToggleHours() {
    const enabled = document.getElementById('aptHoursEnable').checked;
    document.getElementById('aptHoursInputs').style.display = enabled ? '' : 'none';
    document.getElementById('aptHoursOff').style.display    = enabled ? 'none' : '';
}

function aptSetHours(start, end) {
    document.getElementById('aptHoursStart').value = start;
    document.getElementById('aptHoursEnd').value   = end;
}

function aptResetExclusions() {
    document.querySelectorAll('.apt-excl-cb').forEach(cb => { cb.checked = true; });
}

function aptGetParams() {
    const excluded = [...document.querySelectorAll('.apt-excl-cb:checked')].map(c => c.value);
    const minSec   = parseInt(document.getElementById('aptMinSec')?.value || '5', 10);
    const hoursOn  = document.getElementById('aptHoursEnable')?.checked || false;
    const hStart   = hoursOn ? (document.getElementById('aptHoursStart')?.value || '') : '';
    const hEnd     = hoursOn ? (document.getElementById('aptHoursEnd')?.value   || '') : '';
    return { excluded_statuses: excluded, min_answered_sec: minSec, hours_start: hStart, hours_end: hEnd };
}

let _aptRows = [];
let _aptPreset = 'today';

function aptPreset(p) {
    _aptPreset = p;
    document.querySelectorAll('.apt-preset').forEach(b => {
        b.classList.toggle('active', b.getAttribute('onclick').includes("'" + p + "'"));
    });
    const today = new Date().toISOString().slice(0, 10);
    const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
    const start = document.getElementById('aptStartDate');
    const end   = document.getElementById('aptEndDate');
    if (p === 'today')     { start.value = today;     end.style.display = 'none'; }
    if (p === 'yesterday') { start.value = yesterday; end.style.display = 'none'; }
    if (p === 'range')     { start.value = today;     end.style.display = ''; end.value = today; }
}

async function aptLoadCampaigns() {
    const list = document.getElementById('aptCampList');
    if (!list) return;
    try {
        const d = await apiFetch('/api/apt/campaigns');
        const camps = d.campaigns || [];
        list.innerHTML = camps.map(c =>
            '<label style="display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer;font-size:13px;">' +
            '<input type="checkbox" class="apt-camp-cb" value="' + esc(c) + '" checked style="width:14px;height:14px;accent-color:#6366f1;">' +
            esc(c) + '</label>'
        ).join('');
    } catch(e) {
        list.innerHTML = '<span style="color:red;font-size:13px">' + esc(e.message) + '</span>';
    }
}

function aptSelectAll()  { document.querySelectorAll('.apt-camp-cb').forEach(c => c.checked = true); }
function aptSelectNone() { document.querySelectorAll('.apt-camp-cb').forEach(c => c.checked = false); }

async function runAptDownload() {
    const btn = document.getElementById('aptRunBtn');
    const campaigns = [...document.querySelectorAll('.apt-camp-cb:checked')].map(c => c.value);
    if (!campaigns.length) { alert('Select at least one campaign'); return; }
    const start = document.getElementById('aptStartDate').value;
    const end   = _aptPreset === 'range' ? document.getElementById('aptEndDate').value : start;
    const tz    = document.getElementById('aptTimezone').value;
    if (!start) { alert('Select a date'); return; }

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
    ['aptKpis','aptRemovedCard','aptCampBreakdown','aptCallsCard'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });

    try {
        const params = aptGetParams();
        const resp = await fetch('/api/apt/download', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ campaigns, start_date: start, end_date: end, timezone: tz, ...params })
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const d = await resp.json();

        _aptRows = d.rows || [];
        const s  = d.summary || {};
        renderAptParamsUsed(s);
        renderAptKpis(s);
        renderAptRemoved(s.removed || {});
        renderAptCampBreakdown(s.campaigns || []);
        renderAptCalls(_aptRows);

    } catch(e) {
        alert('Error: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-download"></i> Download & Analyze';
    }
}

function renderAptParamsUsed(s) {
    const el = document.getElementById('aptParamsUsed');
    if (!el) return;
    const p = s.params_used || {};
    const excl = (p.excluded_statuses || []).join(', ') || '—';
    const hours = (p.hours_start && p.hours_start !== 'any')
        ? p.hours_start + ' → ' + p.hours_end
        : 'All hours (no filter)';

    const pill = (label, value, icon) =>
        '<div style="display:flex;align-items:flex-start;gap:10px;padding:12px 16px;background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0;">' +
        '<div style="width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;color:white;font-size:13px;flex-shrink:0;">' + icon + '</div>' +
        '<div>' +
        '<div style="font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px;">' + esc(label) + '</div>' +
        '<div style="font-size:13px;font-weight:600;color:#0f172a;font-family:monospace;">' + esc(String(value)) + '</div>' +
        '</div></div>';

    el.innerHTML =
        '<div style="background:white;border-radius:12px;border:1px solid #e2e8f0;padding:16px 20px;">' +
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">' +
        '<i class="fas fa-circle-check" style="color:#22c55e;font-size:15px;"></i>' +
        '<span style="font-size:13px;font-weight:700;color:#374151;">Parameters Used for This Run</span>' +
        '<span style="font-size:12px;color:#94a3b8;margin-left:4px;">· ' + esc(s.date_range || '') + ' · ' + esc(s.timezone || '') + '</span>' +
        '</div>' +
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;">' +
        pill('Formula',           p.formula || 'Call Time = length_in_sec − dispo_sec', 'ƒ') +
        pill('Min Answered (sec)', p.min_answered_sec || 5, '≥') +
        pill('Excluded Statuses', excl, '⊘') +
        pill('Working Hours',     hours, '🕐') +
        pill('Timezone',          s.timezone || '—', '🌍') +
        pill('Date Range',        s.date_range || '—', '📅') +
        '</div></div>';
    el.style.display = '';
}

function renderAptKpis(s) {
    const el = document.getElementById('aptKpis');
    if (!el) return;
    const ansColor = s.answer_rate >= 80 ? '#22c55e' : s.answer_rate >= 60 ? '#f59e0b' : '#ef4444';
    const abdColor = s.abandon_rate <= 5  ? '#22c55e' : s.abandon_rate <= 10 ? '#f59e0b' : '#ef4444';
    el.innerHTML =
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;">' +
        kpiBox('Total Calls',     fmt(s.total_processed),         '#0f172a') +
        kpiBox('Answered',        fmt(s.answered) + ' (' + s.answer_rate + '%)', ansColor) +
        kpiBox('Abandoned',       fmt(s.abandoned) + ' (' + s.abandon_rate + '%)', abdColor) +
        kpiBox('Total Talk',      s.total_talk_hms,               '#6366f1') +
        kpiBox('Total Call Time', s.total_calltime_hms,           '#8b5cf6') +
        kpiBox('Avg Talk',        s.avg_talk_hms,                 '#64748b') +
        kpiBox('Avg Call Time',   s.avg_calltime_hms,             '#64748b') +
        kpiBox('Raw Records',     fmt(s.total_raw),               '#94a3b8') +
        '</div>';
    el.style.display = '';
}

function kpiBox(label, value, color) {
    return '<div style="background:white;border:1px solid #e2e8f0;border-radius:12px;padding:14px 18px;">' +
        '<div style="font-size:20px;font-weight:800;color:' + color + '">' + esc(String(value)) + '</div>' +
        '<div style="font-size:11px;color:#94a3b8;margin-top:3px;font-weight:600;text-transform:uppercase;letter-spacing:.05em">' + esc(label) + '</div>' +
        '</div>';
}

function renderAptRemoved(removed) {
    const el = document.getElementById('aptRemovedCard');
    if (!el) return;
    const total = (removed.before||0) + (removed.after||0) + (removed.status||0);
    if (!total) { el.style.display = 'none'; return; }
    const byType = removed.by_type || {};
    const typeRows = Object.entries(byType).filter(function(e) { return e[1] > 0; })
        .map(function(e) {
            return '<span style="background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:6px;font-size:12px;font-weight:600;">' + esc(e[0]) + ': ' + e[1] + '</span>';
        }).join(' ');
    el.style.cssText = 'display:block;margin-bottom:20px;background:white;border-radius:12px;border:1px solid #fecaca;';
    el.innerHTML =
        '<div style="padding:16px 24px;">' +
        '<div style="font-size:13px;font-weight:700;color:#ef4444;margin-bottom:8px;">Excluded Records: ' + total + '</div>' +
        '<div style="display:flex;gap:12px;flex-wrap:wrap;font-size:13px;color:#64748b;">' +
        (removed.before ? '<span>Before range: <b>' + removed.before + '</b></span>' : '') +
        (removed.after  ? '<span>After range: <b>'  + removed.after  + '</b></span>' : '') +
        (removed.status ? '<span>Status filtered: <b>' + removed.status + '</b></span>' : '') +
        ' ' + typeRows +
        '</div></div>';
}

function renderAptCampBreakdown(camps) {
    const card  = document.getElementById('aptCampBreakdown');
    const tbody = document.getElementById('aptCampBreakBody');
    if (!tbody) return;
    tbody.innerHTML = camps.map(function(c) {
        return '<tr>' +
            '<td style="font-weight:600">' + esc(c.campaign) + '</td>' +
            '<td class="num">' + fmt(c.calls) + '</td>' +
            '<td class="num">' + esc(c.talk_hms) + '</td>' +
            '<td class="num">' + esc(c.call_time_hms) + '</td>' +
            '<td class="num">' + esc(c.avg_call_hms) + '</td>' +
            '</tr>';
    }).join('');
    if (card) card.style.display = '';
}

function renderAptCalls(rows) {
    const card  = document.getElementById('aptCallsCard');
    const tbody = document.getElementById('aptCallsBody');
    const count = document.getElementById('aptCallsCount');
    if (!tbody) return;
    if (count) count.textContent = fmt(rows.length) + ' records (showing up to 5,000)';

    function dispColor(d) {
        d = (d||'').toUpperCase();
        if (['DROP','ABAND','AFAIL','QUEUETIMEOUT','ABANDON'].indexOf(d) >= 0) return '#ef4444';
        if (d === 'SALE') return '#22c55e';
        return '#374151';
    }

    tbody.innerHTML = rows.map(function(r) {
        var ls = r.length_sec || 0, ts = r.talk_sec || 0;
        return '<tr>' +
            '<td style="white-space:nowrap;font-size:12px;color:#64748b">' + esc(r.call_date_local) + '</td>' +
            '<td style="font-weight:600">' + esc(r.campaign_id) + '</td>' +
            '<td>' + esc(r.agent_name || r.agent) + '</td>' +
            '<td style="font-family:monospace;font-size:12px">' + esc(r.phone_number) + '</td>' +
            '<td style="color:' + dispColor(r.term_reason) + ';font-weight:600;font-size:12px">' + esc(r.term_reason) + '</td>' +
            '<td class="num">' + Math.floor(ls/60) + ':' + String(ls%60).padStart(2,'0') + '</td>' +
            '<td class="num">' + Math.floor(ts/60) + ':' + String(ts%60).padStart(2,'0') + '</td>' +
            '<td class="num" style="font-weight:700;color:#6366f1">' + esc(r.call_time_hms) + '</td>' +
            '</tr>';
    }).join('');
    if (card) card.style.display = '';
}

function aptExportCSV() {
    if (!_aptRows.length) { alert('No data to export'); return; }
    const tz   = document.getElementById('aptTimezone').value;
    const date = document.getElementById('aptStartDate').value;
    const fn   = 'APT_Report_' + date + '_' + tz + '.csv';
    fetch('/api/apt/export/csv', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({rows: _aptRows, filename: fn})
    }).then(function(r) { return r.blob(); }).then(function(blob) {
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = fn;
        a.click();
    });
}

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.nav-item[data-page="apt"]').forEach(function(link) {
        link.addEventListener('click', function() {
            var list = document.getElementById('aptCampList');
            if (list && !list.children.length) {
                aptLoadCampaigns();
                aptPreset('today');
            }
        });
    });
});
