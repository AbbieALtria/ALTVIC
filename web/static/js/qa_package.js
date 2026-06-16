// ─── Client QA Package ───────────────────────────────────────────────────────

let _qaJobId      = null;
let _qaJobPoll    = null;
let _qaZipFile    = null;

// ── Init ─────────────────────────────────────────────────────────────────────

async function loadQaCampaigns() {
    const list = document.getElementById('qaCampList');
    if (!list || list.dataset.loaded) return;
    try {
        const d = await apiFetch('/api/qa-package/campaigns');
        const camps = d.campaigns || [];
        list.innerHTML = camps.map(c =>
            '<label style="display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer;font-size:13px;">' +
            '<input type="checkbox" class="qa-camp-cb" value="' + esc(c) + '" checked style="width:14px;height:14px;accent-color:#6366f1;">' +
            esc(c) + '</label>'
        ).join('');
        list.dataset.loaded = '1';
    } catch(e) {
        list.innerHTML = '<span style="color:red;font-size:13px">' + esc(e.message) + '</span>';
    }
}

function qaSelectAll()  { document.querySelectorAll('.qa-camp-cb').forEach(c => c.checked = true); }
function qaSelectNone() { document.querySelectorAll('.qa-camp-cb').forEach(c => c.checked = false); }

function qaDatePreset(p) {
    const today     = new Date().toISOString().slice(0, 10);
    const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
    document.getElementById('qaDate').value = p === 'today' ? today : yesterday;
    document.querySelectorAll('#qa-package-page .apt-preset').forEach(b => {
        b.classList.toggle('active', b.getAttribute('onclick').includes("'" + p + "'"));
    });
}

// ── Start job ─────────────────────────────────────────────────────────────────

async function startQaPackage() {
    const campaigns = [...document.querySelectorAll('.qa-camp-cb:checked')].map(c => c.value);
    if (!campaigns.length) { alert('Select at least one campaign'); return; }
    const date = document.getElementById('qaDate').value;
    if (!date) { alert('Select a date'); return; }
    const n = parseInt(document.getElementById('qaNPerAgent').value || '3', 10);

    // Reset UI
    document.getElementById('qaResultCard').style.display   = 'none';
    document.getElementById('qaHistoryCard').style.display  = 'none';
    document.getElementById('qaProgressCard').style.display = '';
    document.getElementById('qaLog').innerHTML = '';
    document.getElementById('qaStatusText').textContent = 'Starting…';
    document.getElementById('qaStatusSub').textContent  = 'Initialising job';
    setQaStatusIcon('spin');

    const btn = document.getElementById('qaRunBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running…';

    try {
        const resp = await fetch('/api/qa-package/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ campaigns, date, n_per_agent: n })
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const d = await resp.json();
        _qaJobId = d.job_id;
        _qaJobPoll = setInterval(pollQaJob, 2000);
    } catch(e) {
        alert('Failed to start: ' + e.message);
        resetQaBtn();
    }
}

// ── Polling ───────────────────────────────────────────────────────────────────

let _qaLogLen = 0;

async function pollQaJob() {
    if (!_qaJobId) return;
    try {
        const d = await apiFetch('/api/qa-package/status/' + _qaJobId);
        const log   = d.log   || [];
        const status = d.status || 'running';

        // Append new log lines
        const logEl = document.getElementById('qaLog');
        if (logEl && log.length > _qaLogLen) {
            for (let i = _qaLogLen; i < log.length; i++) {
                const e = log[i];
                const color = e.level === 'error' ? '#ef4444'
                            : e.level === 'ok'    ? '#22c55e'
                            : e.level === 'warn'  ? '#f59e0b'
                            : e.level === 'section' ? '#a78bfa'
                            : '#94a3b8';
                logEl.innerHTML +=
                    '<div><span style="color:#475569;">[' + esc(e.ts) + ']</span> ' +
                    '<span style="color:' + color + ';">' + esc(e.msg) + '</span></div>';
            }
            _qaLogLen = log.length;
            logEl.scrollTop = logEl.scrollHeight;

            // Update status text from last log line
            if (log.length) {
                const last = log[log.length - 1];
                document.getElementById('qaStatusText').textContent = last.msg.slice(0, 70);
            }
        }

        if (status === 'done') {
            clearInterval(_qaJobPoll); _qaJobPoll = null; _qaLogLen = 0;
            setQaStatusIcon('ok');
            document.getElementById('qaStatusText').textContent = 'Package complete!';
            document.getElementById('qaStatusSub').textContent  = '';
            renderQaResult(d.result || {});
            resetQaBtn();
        } else if (status === 'error') {
            clearInterval(_qaJobPoll); _qaJobPoll = null; _qaLogLen = 0;
            setQaStatusIcon('error');
            document.getElementById('qaStatusText').textContent = 'Error: ' + (d.error || 'Unknown error');
            document.getElementById('qaStatusSub').textContent  = 'Check log above';
            resetQaBtn();
        }
    } catch(e) {
        // network hiccup — keep polling
    }
}

// ── Result ────────────────────────────────────────────────────────────────────

function renderQaResult(r) {
    _qaZipFile = r.zip_filename || '';
    const card = document.getElementById('qaResultCard');
    const sub  = document.getElementById('qaResultSub');
    if (sub) sub.textContent = r.zip_filename + ' · ' + (r.zip_size_mb || 0) + ' MB';

    // KPIs
    const kpis = document.getElementById('qaResultKpis');
    function kbox(label, val, color) {
        return '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px 18px;text-align:center;">' +
            '<div style="font-size:22px;font-weight:800;color:' + color + ';">' + val + '</div>' +
            '<div style="font-size:11px;color:#94a3b8;margin-top:2px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;">' + label + '</div>' +
            '</div>';
    }
    if (kpis) kpis.innerHTML =
        kbox('Agents',        r.total_agents  || 0, '#6366f1') +
        kbox('Calls Scored',  r.total_calls   || 0, '#22c55e') +
        kbox('Ghost/Skipped', r.ghost_skipped || 0, '#f59e0b') +
        kbox('ZIP Size',      (r.zip_size_mb  || 0) + ' MB', '#0f172a');

    // Calls table
    const calls = r.calls || [];
    const tbl = document.getElementById('qaResultTable');
    if (tbl && calls.length) {
        tbl.innerHTML =
            '<div style="font-size:13px;font-weight:700;color:#374151;margin-bottom:10px;">Scored Calls</div>' +
            '<div class="table-wrap"><table class="data-table"><thead><tr>' +
            '<th>Agent</th><th>Campaign</th><th>Phone</th><th>Type</th><th class="num">Score</th><th class="num">%</th>' +
            '</tr></thead><tbody>' +
            calls.map(function(c) {
                var pct  = c.pct || 0;
                var col  = pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444';
                var type = c.call_type || '';
                return '<tr>' +
                    '<td style="font-weight:600;">' + esc(c.agent) + '</td>' +
                    '<td>' + esc(c.campaign) + '</td>' +
                    '<td style="font-family:monospace;font-size:12px;">' + esc(c.phone) + '</td>' +
                    '<td><span style="font-size:11px;padding:2px 7px;border-radius:6px;background:' +
                        (type === 'SHORT_REVIEW' ? '#fef3c7' : '#dcfce7') + ';color:' +
                        (type === 'SHORT_REVIEW' ? '#92400e' : '#166534') + ';">' + esc(type || 'NORMAL') + '</span></td>' +
                    '<td class="num" style="font-weight:700;">' + esc(c.score) + '</td>' +
                    '<td class="num" style="font-weight:800;color:' + col + ';">' + pct + '%</td>' +
                    '</tr>';
            }).join('') +
            '</tbody></table></div>';
    }

    if (card) card.style.display = '';
}

function qaDownload() {
    if (!_qaZipFile) return;
    window.location.href = '/api/qa-package/download/' + encodeURIComponent(_qaZipFile);
}

// ── History ───────────────────────────────────────────────────────────────────

async function loadQaHistory() {
    const card  = document.getElementById('qaHistoryCard');
    const tbody = document.getElementById('qaHistoryBody');
    if (!card || !tbody) return;
    card.style.display = '';
    tbody.innerHTML = '<tr><td colspan="7" class="loading-cell"><i class="fas fa-spinner fa-spin"></i></td></tr>';
    try {
        const d = await apiFetch('/api/qa-package/history');
        const rows = d.history || [];
        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">No packages generated yet</td></tr>';
            return;
        }
        tbody.innerHTML = rows.map(function(r) {
            var statusColor = r.status === 'COMPLETE' ? '#22c55e' : '#ef4444';
            return '<tr>' +
                '<td style="font-weight:600;">' + esc(r.request_date || '') + '</td>' +
                '<td>' + esc(r.campaign_ids || '') + '</td>' +
                '<td class="num">' + (r.total_agents || 0) + '</td>' +
                '<td class="num">' + (r.total_calls  || 0) + '</td>' +
                '<td class="num">' + (r.zip_size_mb  || 0) + ' MB</td>' +
                '<td><span style="color:' + statusColor + ';font-weight:700;">' + esc(r.status || '') + '</span></td>' +
                '<td>' + (r.zip_filename ?
                    '<button onclick="qaDownloadFile(\'' + esc(r.zip_filename) + '\')" style="font-size:11px;padding:3px 10px;border-radius:6px;border:1px solid #6366f1;background:white;color:#6366f1;cursor:pointer;font-weight:600;"><i class="fas fa-download"></i> Download</button>'
                    : '—') + '</td>' +
                '</tr>';
        }).join('');
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="7" style="color:red;padding:12px;">' + esc(e.message) + '</td></tr>';
    }
}

function qaDownloadFile(filename) {
    window.location.href = '/api/qa-package/download/' + encodeURIComponent(filename);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function setQaStatusIcon(state) {
    var el = document.getElementById('qaStatusIcon');
    if (!el) return;
    if (state === 'spin') {
        el.style.background = '#6366f1';
        el.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    } else if (state === 'ok') {
        el.style.background = '#22c55e';
        el.innerHTML = '<i class="fas fa-check"></i>';
    } else {
        el.style.background = '#ef4444';
        el.innerHTML = '<i class="fas fa-xmark"></i>';
    }
}

function resetQaBtn() {
    var btn = document.getElementById('qaRunBtn');
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-box-open"></i> Generate Package'; }
}

// ── Page init ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.nav-item[data-page="qa-package"]').forEach(function(link) {
        link.addEventListener('click', function() {
            loadQaCampaigns();
            qaDatePreset('yesterday');
        });
    });

    // Add title mapping
    var titles = { 'qa-package': 'Client QA Package' };
    // handled by existing nav click logic via titles object — just ensure page shown
});
