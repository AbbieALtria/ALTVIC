#!/usr/bin/env python3
# =============================================================================
# File:         app.py
# Version:      2.0.0
# Date:         2026-06-05
# Description:  Flask Web Dashboard for Altria Ops — Full real-data version
#               All endpoints use live DB data. Email channel integrated.
# =============================================================================

from flask import Flask, render_template, jsonify, request, send_from_directory, send_file, redirect, url_for, session
from flask_cors import CORS
import sys, os, threading, uuid, json
from datetime import datetime, timedelta, date as date_type
from pathlib import Path
from decimal import Decimal
import pytz

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import db
from utils.colors import Colors, print_color
from utils.formatter import sec_to_hms, time_ago
from auth import (
    verify_login, current_user, login_required_guard, ROLE_PAGES, can_write,
    role_required, list_users, create_user, update_user, delete_user, VALID_ROLES,
)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'altria-ops-2026-change-in-production')
CORS(app)


@app.before_request
def _enforce_login():
    return login_required_guard()

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_est_time():
    utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)
    return utc_now.astimezone(pytz.timezone('America/New_York'))

def safe_int(v):
    if v is None: return 0
    if isinstance(v, Decimal): return int(v)
    try: return int(v)
    except: return 0

def safe_float(v):
    if v is None: return 0.0
    if isinstance(v, Decimal): return float(v)
    try: return float(v)
    except: return 0.0

def jsonify_ok(data):
    return jsonify({'success': True, **data})

def jsonify_err(msg, code=500):
    return jsonify({'success': False, 'error': str(msg)}), code

# ──────────────────────────────────────────────────────────────────────────────
# Static / Pages
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@app.route('/sw.js')
def service_worker():
    # Must be served from root scope (not /static/...) so it can control the whole app
    resp = send_from_directory('static', 'sw.js', mimetype='application/javascript')
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = verify_login(username, password)
        if user:
            session['username']     = user['username']
            session['role']         = user['role']
            session['display_name'] = user['display_name']
            next_url = request.args.get('next') or '/'
            return redirect(next_url)
        error = 'Invalid username or password'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/')
def index():
    user = current_user()
    allowed_pages = ROLE_PAGES.get(user['role'], [])
    return render_template(
        'dashboard.html',
        current_user=user,
        allowed_pages=allowed_pages,
        allowed_pages_json=json.dumps(allowed_pages),
        can_write=can_write(),
    )

# ──────────────────────────────────────────────────────────────────────────────
# User Management (admin only)
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/admin/users', methods=['GET'])
@role_required('admin')
def admin_list_users():
    return jsonify({'success': True, 'users': list_users(), 'roles': sorted(VALID_ROLES)})

@app.route('/api/admin/users', methods=['POST'])
@role_required('admin')
def admin_create_user():
    data = request.get_json(silent=True) or {}
    try:
        create_user(
            username=data.get('username', ''),
            password=data.get('password', ''),
            role=data.get('role', ''),
            display_name=data.get('display_name', ''),
        )
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify_err(str(e), 400)

@app.route('/api/admin/users/<username>', methods=['PUT'])
@role_required('admin')
def admin_update_user(username):
    data = request.get_json(silent=True) or {}
    try:
        update_user(
            username,
            role=data.get('role'),
            display_name=data.get('display_name'),
            password=data.get('password') or None,
        )
        # Keep the editing admin's own session in sync if they changed their own account
        me = current_user()
        if me and me['username'] == username:
            if data.get('role'):
                session['role'] = data['role']
            if data.get('display_name'):
                session['display_name'] = data['display_name']
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify_err(str(e), 400)

@app.route('/api/admin/users/<username>', methods=['DELETE'])
@role_required('admin')
def admin_delete_user(username):
    me = current_user()
    if me and me['username'] == username:
        return jsonify_err('You cannot delete your own account while logged in as it', 400)
    try:
        delete_user(username)
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify_err(str(e), 400)

# ──────────────────────────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/health')
def api_health():
    vicidial_ok = bool(db.execute_query("SELECT 1 AS ok"))
    email_ok = False
    try:
        from core.email_database import email_db
        email_ok = email_db.test_connection()
    except Exception:
        pass
    return jsonify({
        'success': True,
        'version': '2.0.0',
        'timestamp': datetime.now().isoformat(),
        'vicidial_db': vicidial_ok,
        'email_db': email_ok
    })

# ──────────────────────────────────────────────────────────────────────────────
# Dashboard KPI — single call for all top-bar numbers
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/dashboard/kpi')
def dashboard_kpi():
    """One-shot endpoint: calls today, agents live, queue, abandon rate."""
    try:
        # Call stats today
        call_row = db.execute_query("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS answered,
                SUM(CASE WHEN term_reason IN ('ABANDON','QUEUETIMEOUT','NOAGENT')
                         OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) AS abandoned,
                SUM(CASE WHEN length_in_sec = 0 AND queue_seconds IS NULL THEN 1 ELSE 0 END) AS ghost
            FROM vicidial_closer_log
            WHERE DATE(call_date) = CURDATE()
        """) or [{}]
        cr = call_row[0]
        total    = safe_int(cr.get('total'))
        answered = safe_int(cr.get('answered'))
        abandoned= safe_int(cr.get('abandoned'))
        ghost    = safe_int(cr.get('ghost'))
        valid    = total - ghost
        ans_rate = round(answered / valid * 100, 1) if valid else 0
        abd_rate = round(abandoned / valid * 100, 1) if valid else 0

        # Live agents
        agent_row = db.execute_query("""
            SELECT
                COUNT(*) AS online,
                SUM(status='INCALL') AS incall,
                SUM(status='READY')  AS ready,
                SUM(status='PAUSE')  AS paused
            FROM vicidial_live_agents
            WHERE status IN ('READY','INCALL','PAUSE','QUEUE','RING','CLOSER')
        """) or [{}]
        ar = agent_row[0]

        # Queue waiting (last 10 min, no agent answered yet)
        queue_row = db.execute_query("""
            SELECT COUNT(*) AS waiting
            FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(NOW(), INTERVAL 10 MINUTE)
              AND length_in_sec = 0 AND queue_seconds > 0
        """) or [{}]

        return jsonify_ok({
            'calls': {
                'total': total, 'answered': answered,
                'abandoned': abandoned, 'ghost': ghost,
                'answer_rate': ans_rate, 'abandon_rate': abd_rate
            },
            'agents': {
                'online': safe_int(ar.get('online')),
                'incall': safe_int(ar.get('incall')),
                'ready':  safe_int(ar.get('ready')),
                'paused': safe_int(ar.get('paused'))
            },
            'queue': { 'waiting': safe_int((queue_row[0] or {}).get('waiting')) },
            'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# Agent Status (live)
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/agent/status')
def agent_status():
    try:
        agents = db.execute_query("""
            SELECT l.user, u.full_name, l.status, l.campaign_id,
                   l.last_call_time,
                   TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) AS minutes_in_status
            FROM vicidial_live_agents l
            LEFT JOIN vicidial_users u ON l.user = u.user
            WHERE l.status IN ('READY','INCALL','PAUSE','QUEUE','CLOSER','RING')
            ORDER BY FIELD(l.status,'INCALL','RING','QUEUE','READY','CLOSER','PAUSE')
        """) or []

        counts = {s: 0 for s in ('INCALL','READY','PAUSE','QUEUE','RING','CLOSER')}
        result = []
        for a in agents:
            s = a['status']
            if s in counts: counts[s] += 1
            lc = 'Never'
            if a['last_call_time']:
                lc = time_ago(a['last_call_time']) if hasattr(a['last_call_time'], 'strftime') else str(a['last_call_time'])
            result.append({
                'user': a['user'], 'name': a.get('full_name') or a['user'],
                'status': s, 'campaign': a['campaign_id'] or 'N/A',
                'minutes': safe_int(a['minutes_in_status']), 'last_call': lc
            })
        return jsonify_ok({'agents': result, 'counts': counts, 'total': len(result)})
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# Call Volume
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/call/volume/today')
def call_volume_today():
    try:
        rows = db.execute_query("""
            SELECT HOUR(call_date) AS hour, COUNT(*) AS calls
            FROM vicidial_closer_log
            WHERE DATE(call_date) = CURDATE()
            GROUP BY HOUR(call_date) ORDER BY hour
        """) or []
        by_hour = {r['hour']: safe_int(r['calls']) for r in rows}
        hours = [{'hour': h, 'label': f"{h:02d}:00", 'calls': by_hour.get(h, 0)} for h in range(24)]
        return jsonify_ok({'data': hours, 'total': sum(h['calls'] for h in hours),
                           'max_calls': max((h['calls'] for h in hours), default=0)})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/call/volume/week')
def call_volume_week():
    try:
        rows = db.execute_query("""
            SELECT DATE(call_date) AS d, DAYNAME(call_date) AS day, COUNT(*) AS calls
            FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
            GROUP BY DATE(call_date) ORDER BY d
        """) or []
        return jsonify_ok({'data': [{'date': r['d'].strftime('%Y-%m-%d'),
                                     'day': r['day'][:3], 'calls': safe_int(r['calls'])} for r in rows]})
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# Top Agents
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/top/agents/<period>')
def top_agents(period='today'):
    try:
        flt = {"today": "DATE(a.event_time) = CURDATE()",
               "week":  "a.event_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
               "month": "a.event_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)"}.get(period, "DATE(a.event_time) = CURDATE()")
        rows = db.execute_query(f"""
            SELECT a.user, u.full_name, COUNT(*) AS calls, SUM(a.talk_sec) AS talk_time
            FROM vicidial_agent_log a
            LEFT JOIN vicidial_users u ON a.user = u.user
            WHERE {flt} GROUP BY a.user ORDER BY calls DESC LIMIT 10
        """) or []
        return jsonify_ok({'data': [{'user': r['user'], 'name': r.get('full_name') or r['user'],
                                      'calls': safe_int(r['calls']),
                                      'talk_time': sec_to_hms(safe_int(r['talk_time']))} for r in rows]})
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# Campaigns
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/campaigns/performance')
def campaign_performance():
    """
    Unified outbound + inbound campaign performance.
    ?days=7          — last N days (0 = today only)
    ?campaign=X      — filter to one campaign
    ?time_start=06:00 — start of time window (HH:MM)
    ?time_end=18:00   — end of time window (HH:MM)
    """
    try:
        days       = int(request.args.get('days', 0))
        campaign   = request.args.get('campaign', '').strip()
        time_start = request.args.get('time_start', '').strip()
        time_end   = request.args.get('time_end', '').strip()
        exact_date = request.args.get('date', '').strip()  # 'yesterday' or 'YYYY-MM-DD'
        # tz_offset: hours to ADD to call_date before comparing (e.g. -5 = UTC→EST)
        tz_offset  = int(request.args.get('tz_offset', 0))

        def _ts_expr():
            """call_date expression with optional UTC offset applied."""
            if tz_offset:
                return f"DATE_ADD(call_date, INTERVAL {tz_offset} HOUR)"
            return "call_date"

        def _to_mins(t):
            """Convert 'HH:MM' or 'HH:MM:SS' to integer minutes since midnight."""
            parts = t.split(':')
            return int(parts[0]) * 60 + int(parts[1])

        def build_where(params):
            ts = _ts_expr()
            clauses = []
            if exact_date == 'yesterday':
                clauses.append(f"DATE({ts}) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)")
            elif exact_date:
                clauses.append(f"DATE({ts}) = %s")
                params.append(exact_date)
            elif days == 0:
                clauses.append(f"DATE({ts}) = CURDATE()")
            else:
                clauses.append("call_date >= DATE_SUB(NOW(), INTERVAL %s DAY)")
                params.append(days)
            if campaign:
                clauses.append("campaign_id = %s")
                params.append(campaign)
            if time_start:
                # Use integer minutes-since-midnight — avoids TIME() string comparison quirks
                params.append(_to_mins(time_start))
                clauses.append(f"(HOUR({ts})*60+MINUTE({ts})) >= %s")
            if time_end:
                params.append(_to_mins(time_end))
                clauses.append(f"(HOUR({ts})*60+MINUTE({ts})) <= %s")
            return ' AND '.join(clauses)

        def hms(sec):
            sec = int(sec or 0)
            return f"{sec//3600}:{(sec%3600)//60:02d}:{sec%60:02d}"

        # Build UNION of inbound (vicidial_closer_log) + outbound (vicidial_log)
        # Normalise outbound columns to match inbound schema
        p1, p2 = [], []
        w1 = build_where(p1)
        w2 = build_where(p2)

        union_query = f"""
            SELECT
                campaign_id,
                SUM(total_calls)   AS total_calls,
                SUM(answered)      AS answered,
                SUM(abandoned)     AS abandoned,
                SUM(total_talk_sec) AS total_talk_sec,
                SUM(answered_talk) AS answered_talk,
                SUM(answered_cnt)  AS answered_cnt,
                AVG(avg_queue)     AS avg_queue,
                MAX(last_call)     AS last_call,
                COUNT(DISTINCT call_day) AS active_days
            FROM (
                SELECT
                    campaign_id,
                    COUNT(*)          AS total_calls,
                    SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS answered,
                    SUM(CASE WHEN term_reason IN ('ABANDON','QUEUETIMEOUT','NOAGENT')
                             OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) AS abandoned,
                    SUM(length_in_sec) AS total_talk_sec,
                    SUM(CASE WHEN length_in_sec >= 5 THEN length_in_sec ELSE 0 END) AS answered_talk,
                    SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS answered_cnt,
                    AVG(queue_seconds) AS avg_queue,
                    MAX(call_date)     AS last_call,
                    DATE(call_date)    AS call_day
                FROM vicidial_closer_log
                WHERE {w1}
                GROUP BY campaign_id, DATE(call_date)

                UNION ALL

                SELECT
                    campaign_id,
                    COUNT(*)          AS total_calls,
                    SUM(CASE WHEN status NOT IN ('DROP','ABAND','AFAIL','QUEUETIMEOUT') AND length_in_sec >= 5 THEN 1 ELSE 0 END) AS answered,
                    SUM(CASE WHEN status IN ('DROP','ABAND','AFAIL','QUEUETIMEOUT') THEN 1 ELSE 0 END) AS abandoned,
                    SUM(length_in_sec) AS total_talk_sec,
                    SUM(CASE WHEN length_in_sec >= 5 THEN length_in_sec ELSE 0 END) AS answered_talk,
                    SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS answered_cnt,
                    0                  AS avg_queue,
                    MAX(call_date)     AS last_call,
                    DATE(call_date)    AS call_day
                FROM vicidial_log
                WHERE {w2}
                GROUP BY campaign_id, DATE(call_date)
            ) combined
            GROUP BY campaign_id
            HAVING total_calls > 0
            ORDER BY total_calls DESC
        """
        rows = db.execute_query(union_query, p1 + p2) or []

        result, tc, ta, tb = [], 0, 0, 0
        for r in rows:
            c = safe_int(r['total_calls'])
            a = safe_int(r['answered'])
            b = safe_int(r['abandoned'])
            tc += c; ta += a; tb += b
            avg_talk_sec = (safe_float(r['answered_talk']) / safe_float(r['answered_cnt'])
                           ) if safe_float(r['answered_cnt']) else 0
            talk_mins = round(safe_float(r['total_talk_sec']) / 60, 1)
            last_call = r['last_call'].strftime('%m-%d %H:%M') if r.get('last_call') else '—'
            result.append({
                'campaign_id':     r['campaign_id'],
                'campaign':        r['campaign_id'],
                'total_calls':     c,
                'calls':           c,
                'answered':        a,
                'abandoned':       b,
                'answer_rate':     round(a / c * 100, 1) if c else 0,
                'abandon_rate':    round(b / c * 100, 1) if c else 0,
                'avg_talk':        hms(avg_talk_sec),
                'avg_handle_time': round(avg_talk_sec, 0),
                'talk_time_mins':  talk_mins,
                'avg_queue':       round(safe_float(r['avg_queue']), 1),
                'last_call':       last_call,
                'active_days':     safe_int(r['active_days']),
            })
        return jsonify_ok({
            'data': result,
            'totals': {
                'calls': tc, 'answered': ta, 'abandoned': tb,
                'answer_rate':  round(ta / tc * 100, 1) if tc else 0,
                'abandon_rate': round(tb / tc * 100, 1) if tc else 0,
            }
        })
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# Queue
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/queue/status')
def queue_status():
    try:
        rows = db.execute_query("""
            SELECT campaign_id, COUNT(*) AS waiting, AVG(queue_seconds) AS avg_wait
            FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(NOW(), INTERVAL 10 MINUTE)
              AND length_in_sec = 0 AND queue_seconds > 0
            GROUP BY campaign_id HAVING waiting > 0 ORDER BY waiting DESC LIMIT 8
        """) or []
        queues = [{'campaign': r['campaign_id'], 'waiting': safe_int(r['waiting']),
                   'avg_wait': round(safe_float(r['avg_wait']),0)} for r in rows]
        return jsonify_ok({'total_waiting': sum(q['waiting'] for q in queues), 'queues': queues})
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# Debug / Timezone
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/debug/campaigns')
def debug_campaigns():
    """Quick sanity check — bypasses the UNION, hits each table directly."""
    try:
        def fmt_rows(rows):
            out = []
            for r in (rows or []):
                row = {}
                for k, v in r.items():
                    row[k] = str(v) if not isinstance(v, (int, float)) else v
                out.append(row)
            return out

        closer = db.execute_query(
            "SELECT campaign_id, COUNT(*) AS cnt, MAX(call_date) AS last "
            "FROM vicidial_closer_log "
            "WHERE call_date >= DATE_SUB(NOW(), INTERVAL 7 DAY) "
            "GROUP BY campaign_id ORDER BY cnt DESC LIMIT 15"
        )
        log = db.execute_query(
            "SELECT campaign_id, COUNT(*) AS cnt, MAX(call_date) AS last "
            "FROM vicidial_log "
            "WHERE call_date >= DATE_SUB(NOW(), INTERVAL 7 DAY) "
            "GROUP BY campaign_id ORDER BY cnt DESC LIMIT 15"
        )
        # also test the simple union
        union = db.execute_query(
            "SELECT campaign_id, COUNT(*) AS cnt FROM ("
            "  SELECT campaign_id FROM vicidial_closer_log WHERE call_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
            "  UNION ALL"
            "  SELECT campaign_id FROM vicidial_log WHERE call_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
            ") t GROUP BY campaign_id ORDER BY cnt DESC LIMIT 15"
        )
        # Check actual column names in both tables
        vcl_cols = [r['Field'] for r in (db.execute_query("SHOW COLUMNS FROM vicidial_closer_log") or [])]
        vl_cols  = [r['Field'] for r in (db.execute_query("SHOW COLUMNS FROM vicidial_log") or [])]
        return jsonify_ok({
            'vicidial_closer_log': fmt_rows(closer),
            'vicidial_log': fmt_rows(log),
            'union_test': fmt_rows(union),
            'closer_count': len(closer or []),
            'log_count': len(log or []),
            'vcl_columns': vcl_cols,
            'vl_columns': vl_cols,
        })
    except Exception as e:
        return jsonify_err(str(e))

@app.route('/api/debug/time')
def debug_time():
    """Returns DB timezone info + recent call samples so we can verify timezone handling."""
    try:
        tz_rows = db.execute_query(
            "SELECT NOW() AS db_now, @@global.time_zone AS global_tz, @@session.time_zone AS session_tz"
        ) or []
        tz = tz_rows[0] if tz_rows else {}

        # Sample most-recent 10 calls from vicidial_closer_log
        closer_rows = db.execute_query(
            "SELECT call_date, campaign_id FROM vicidial_closer_log ORDER BY call_date DESC LIMIT 10"
        ) or []
        # Sample most-recent 10 calls from vicidial_log
        log_rows = db.execute_query(
            "SELECT call_date, campaign_id FROM vicidial_log ORDER BY call_date DESC LIMIT 10"
        ) or []

        def fmt(r):
            cd = r.get('call_date')
            return {'call_date': str(cd), 'campaign_id': r.get('campaign_id')}

        return jsonify_ok({
            'db_now': str(tz.get('db_now', '')),
            'global_tz': tz.get('global_tz', ''),
            'session_tz': tz.get('session_tz', ''),
            'vicidial_closer_log_recent': [fmt(r) for r in closer_rows],
            'vicidial_log_recent': [fmt(r) for r in log_rows],
        })
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# Alerts
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/alerts/active')
def active_alerts():
    try:
        alerts = []
        try:
            from alerts.monitoring import get_active_alerts
            alerts = get_active_alerts() or []
        except ImportError:
            pass

        # Built-in: high queue wait
        q_rows = db.execute_query("""
            SELECT campaign_id, COUNT(*) AS waiting
            FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
              AND length_in_sec = 0 AND queue_seconds > 0
            GROUP BY campaign_id HAVING waiting > 5
        """) or []
        for q in q_rows:
            alerts.append({'type': 'queue_waiting', 'severity': 'warning',
                           'message': f"{q['waiting']} calls waiting in {q['campaign_id']}",
                           'time': datetime.now().isoformat()})

        # Built-in: high abandon rate last 30 min
        ab_row = db.execute_query("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN term_reason IN ('ABANDON','QUEUETIMEOUT') THEN 1 ELSE 0 END) AS abandoned
            FROM vicidial_closer_log WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)
        """) or [{}]
        ab = ab_row[0]
        if safe_int(ab.get('total')) > 0:
            rate = safe_int(ab.get('abandoned')) / safe_int(ab.get('total')) * 100
            if rate > 20:
                alerts.append({'type': 'high_abandon', 'severity': 'critical',
                               'message': f"Abandon rate {rate:.1f}% in last 30 min",
                               'time': datetime.now().isoformat()})

        return jsonify_ok({'alerts': [{'type': a.get('type','alert'),
                                       'severity': a.get('severity','info'),
                                       'message': a.get('message',''),
                                       'time': a.get('time', datetime.now().isoformat())} for a in alerts[:15]],
                           'count': len(alerts)})
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# EOD Report
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/campaigns/list')
def campaigns_list():
    """
    All campaigns that have data (inbound + outbound), optionally filtered by date.
    ?date=YYYY-MM-DD  — restrict to a single day
    ?source=outbound  — only vicidial_log (outbound)
    ?source=inbound   — only vicidial_closer_log (inbound/closer)
    Default: UNION of both tables.
    """
    try:
        date_str = request.args.get('date', '').strip()
        source   = request.args.get('source', 'all').strip().lower()

        def _q(table, date_col='call_date'):
            if date_str:
                return (f"SELECT DISTINCT campaign_id FROM {table}"
                        f" WHERE DATE({date_col}) = %s", [date_str])
            else:
                return (f"SELECT DISTINCT campaign_id FROM {table}"
                        f" WHERE {date_col} >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)", [])

        if source == 'outbound':
            if date_str:
                rows = db.execute_query(
                    "SELECT DISTINCT campaign_id FROM ("
                    "  SELECT campaign_id FROM vicidial_log WHERE DATE(call_date) = %s"
                    "  UNION"
                    "  SELECT campaign_id FROM vicidial_campaigns WHERE active='Y'"
                    ") t ORDER BY campaign_id", [date_str]
                ) or []
            else:
                rows = db.execute_query(
                    "SELECT DISTINCT campaign_id FROM ("
                    "  SELECT campaign_id FROM vicidial_log WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)"
                    "  UNION"
                    "  SELECT campaign_id FROM vicidial_campaigns WHERE active='Y'"
                    ") t ORDER BY campaign_id"
                ) or []
        elif source == 'inbound':
            sql, params = _q('vicidial_closer_log')
            rows = db.execute_query(sql, params) or []
        else:
            # UNION outbound + inbound + all active configured campaigns
            if date_str:
                rows = db.execute_query(
                    "SELECT DISTINCT campaign_id FROM ("
                    "  SELECT campaign_id FROM vicidial_log        WHERE DATE(call_date) = %s"
                    "  UNION"
                    "  SELECT campaign_id FROM vicidial_closer_log WHERE DATE(call_date) = %s"
                    "  UNION"
                    "  SELECT campaign_id FROM vicidial_campaigns  WHERE active='Y'"
                    ") t ORDER BY campaign_id",
                    [date_str, date_str]
                ) or []
            else:
                rows = db.execute_query(
                    "SELECT DISTINCT campaign_id FROM ("
                    "  SELECT campaign_id FROM vicidial_log        WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)"
                    "  UNION"
                    "  SELECT campaign_id FROM vicidial_closer_log WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)"
                    "  UNION"
                    "  SELECT campaign_id FROM vicidial_campaigns  WHERE active='Y'"
                    ") t ORDER BY campaign_id"
                ) or []

        campaigns = sorted(set(r['campaign_id'] for r in rows if r.get('campaign_id')))
        return jsonify_ok({'data': campaigns})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/reports/campaign-agents')
def report_campaign_agents():
    """
    Return agents who worked a specific campaign in a date range.
    ?campaign=YP2&date_start=YYYY-MM-DD&date_end=YYYY-MM-DD
    """
    try:
        campaign   = request.args.get('campaign', '').strip()
        est_today  = get_est_time().strftime('%Y-%m-%d')
        date_start = request.args.get('date_start') or est_today
        date_end   = request.args.get('date_end')   or date_start

        params = [date_start, date_end]
        camp_sql = ""
        if campaign:
            camp_sql = " AND vl.campaign_id = %s"
            params.append(campaign)

        rows = db.execute_query(
            "SELECT vl.user, COALESCE(u.full_name, vl.user) AS full_name,"
            "       COUNT(*) AS calls"
            " FROM vicidial_log vl"
            " LEFT JOIN vicidial_users u ON vl.user = u.user"
            " WHERE vl.call_date >= %s"
            "   AND vl.call_date < DATE_ADD(%s, INTERVAL 1 DAY)"
            + camp_sql +
            " GROUP BY vl.user, u.full_name"
            " ORDER BY full_name",
            params
        ) or []

        return jsonify_ok({
            'data': [{'user': r['user'],
                      'name': r['full_name'] or r['user'],
                      'calls': safe_int(r['calls'])} for r in rows]
        })
    except Exception as e:
        return jsonify_err(e)


@app.route('/api/eod/<date_str>')
def eod_report(date_str):
    try:
        target = datetime.strptime(date_str, '%Y-%m-%d').date()
        # Optional campaign filter — comma-separated in ?campaigns=A,B,C
        camp_param = request.args.get('campaigns', '').strip()
        camp_filter = ''
        camp_params = []
        if camp_param:
            selected = [c.strip() for c in camp_param.split(',') if c.strip()]
            if selected:
                placeholders = ','.join(['%s'] * len(selected))
                camp_filter = f" AND c.campaign_id IN ({placeholders})"
                camp_params = selected

        # Optional time range filter (EST) — ?time_start=08:00&time_end=20:00
        time_start = request.args.get('time_start', '').strip()  # HH:MM
        time_end   = request.args.get('time_end',   '').strip()
        time_filter = ''
        time_params = []
        if time_start and time_end:
            # Convert EST to server time (server is same tz as DB based on our check)
            # We store as TIME() comparison directly on call_date
            time_filter = " AND TIME(c.call_date) BETWEEN %s AND %s"
            time_params = [time_start + ':00', time_end + ':00']
        elif time_start:
            time_filter = " AND TIME(c.call_date) >= %s"
            time_params = [time_start + ':00']
        elif time_end:
            time_filter = " AND TIME(c.call_date) <= %s"
            time_params = [time_end + ':00']

        rows = db.execute_query(f"""
            SELECT c.campaign_id,
                COUNT(*) AS calls,
                SUM(CASE WHEN a.user IS NOT NULL AND c.length_in_sec>=5 THEN 1 ELSE 0 END) AS valid_calls,
                SUM(CASE WHEN a.user IS NULL AND c.length_in_sec=0 THEN 1 ELSE 0 END) AS ghost_calls,
                SUM(CASE WHEN a.talk_sec>=5 THEN 1 ELSE 0 END) AS answered,
                SUM(CASE WHEN c.term_reason IN ('ABANDON','QUEUETIMEOUT','NOAGENT') THEN 1 ELSE 0 END) AS abandoned,
                AVG(CASE WHEN a.user IS NOT NULL AND c.length_in_sec>=5 THEN c.length_in_sec END) AS avg_talk,
                SUM(CASE WHEN a.user IS NOT NULL AND c.length_in_sec>=5 THEN c.length_in_sec ELSE 0 END) AS total_talk_sec
            FROM vicidial_closer_log c
            LEFT JOIN vicidial_agent_log a ON c.uniqueid = a.uniqueid
            WHERE DATE(c.call_date) = %s {camp_filter} {time_filter}
            GROUP BY c.campaign_id ORDER BY calls DESC
        """, [target] + camp_params + time_params) or []

        tc     = sum(safe_int(r['calls'])       for r in rows)
        tvalid = sum(safe_int(r['valid_calls'])  for r in rows)
        tghost = sum(safe_int(r['ghost_calls'])  for r in rows)
        tans   = sum(safe_int(r['answered'])     for r in rows)
        tabd   = sum(safe_int(r['abandoned'])    for r in rows)
        ttalk  = sum(safe_int(r['total_talk_sec']) for r in rows)  # total seconds

        # Agent breakdown (filtered by same campaigns)
        agent_camp_filter = ''
        agent_camp_params = []
        if camp_params:
            placeholders = ','.join(['%s'] * len(camp_params))
            agent_camp_filter = f"""
                AND a.uniqueid IN (
                    SELECT uniqueid FROM vicidial_closer_log
                    WHERE DATE(call_date) = %s AND campaign_id IN ({placeholders})
                )"""
            agent_camp_params = [target] + camp_params
        # Build agent time filter using event_time instead of call_date
        agent_time_filter = ''
        if time_start and time_end:
            agent_time_filter = " AND TIME(a.event_time) BETWEEN %s AND %s"
        elif time_start:
            agent_time_filter = " AND TIME(a.event_time) >= %s"
        elif time_end:
            agent_time_filter = " AND TIME(a.event_time) <= %s"

        agent_rows = db.execute_query(f"""
            SELECT a.user, u.full_name, COUNT(*) AS calls, SUM(a.talk_sec) AS talk_sec
            FROM vicidial_agent_log a
            LEFT JOIN vicidial_users u ON a.user = u.user
            WHERE DATE(a.event_time) = %s {agent_camp_filter} {agent_time_filter}
            GROUP BY a.user ORDER BY calls DESC LIMIT 20
        """, [target] + agent_camp_params + time_params) or []

        # Email per campaign
        email_by_campaign = {}
        try:
            from core.email_database import email_db
            email_rows = email_db.execute_query("""
                SELECT campaign,
                    COUNT(*)                          AS total,
                    SUM(email_type='CANCELATION REQ') AS cancels,
                    SUM(email_type='FULL REFUND')      AS full_ref,
                    SUM(email_type='PARTIAL REFUND')   AS part_ref,
                    COALESCE(SUM(refund), 0)           AS refund_val,
                    COUNT(DISTINCT agent_name)         AS agents
                FROM tbl_email
                WHERE DATE(created_2) = %s
                GROUP BY campaign
            """, (target,)) or []
            for er in email_rows:
                email_by_campaign[er['campaign'] or 'UNKNOWN'] = {
                    'total':     safe_int(er['total']),
                    'cancels':   safe_int(er['cancels']),
                    'full_ref':  safe_int(er['full_ref']),
                    'part_ref':  safe_int(er['part_ref']),
                    'refund_val':safe_float(er['refund_val']),
                    'agents':    safe_int(er['agents'])
                }
        except Exception:
            pass

        # Email channel summary + agents
        email_data = None
        try:
            from core.email_integration import get_email_summary, get_email_stats_by_agent, ensure_mapping_table
            ensure_mapping_table()
            email_data = {
                'summary': get_email_summary(target),
                'agents': get_email_stats_by_agent(target)
            }
        except Exception:
            pass

        time_label = f"{time_start}–{time_end}" if time_start and time_end else \
                     f"from {time_start}" if time_start else \
                     f"until {time_end}" if time_end else "All Day"
        return jsonify_ok({'data': {
            'date': str(target),
            'time_range': time_label,
            'total_calls': tc, 'valid_calls': tvalid,
            'ghost_calls': tghost, 'ghost_pct': round(tghost/tc*100,1) if tc else 0,
            'answered': tans, 'abandoned': tabd,
            'answer_rate': round(tans/tvalid*100,1) if tvalid else 0,
            'abandon_rate': round(tabd/tvalid*100,1) if tvalid else 0,
            'total_talk_sec': ttalk,
            'total_minutes':  round(ttalk / 60, 2),
            'total_talk_fmt': sec_to_hms(ttalk),
            'campaigns': [{'campaign': r['campaign_id'],
                           'calls': safe_int(r['calls']),
                           'valid': safe_int(r['valid_calls']),
                           'ghost': safe_int(r['ghost_calls']),
                           'answered': safe_int(r['answered']),
                           'abandoned': safe_int(r['abandoned']),
                           'answer_rate': round(safe_int(r['answered'])/safe_int(r['valid_calls'])*100,1) if safe_int(r['valid_calls']) else 0,
                           'abandon_rate': round(safe_int(r['abandoned'])/safe_int(r['valid_calls'])*100,1) if safe_int(r['valid_calls']) else 0,
                           'avg_talk': sec_to_hms(safe_float(r['avg_talk'])),
                           'talk_sec': safe_int(r['total_talk_sec']),
                           'minutes': round(safe_int(r['total_talk_sec'])/60, 2),
                           'email': email_by_campaign.get(r['campaign_id'], None)} for r in rows],
            'agents': [{'user': r['user'], 'name': r.get('full_name') or r['user'],
                        'calls': safe_int(r['calls']),
                        'talk_time': sec_to_hms(safe_int(r['talk_sec']))} for r in agent_rows],
            'email': email_data
        }})
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# Email Channel API
# ──────────────────────────────────────────────────────────────────────────────

def _parse_date(date_str):
    if date_str:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    return get_est_time().date()

@app.route('/api/email/summary')
@app.route('/api/email/summary/<date_str>')
def email_summary_api(date_str=None):
    try:
        from core.email_integration import get_email_summary, ensure_mapping_table
        ensure_mapping_table()
        return jsonify_ok({'data': get_email_summary(_parse_date(date_str))})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/email/agents')
@app.route('/api/email/agents/<date_str>')
def email_agents_api(date_str=None):
    try:
        from core.email_integration import get_email_stats_by_agent, ensure_mapping_table
        ensure_mapping_table()
        target = _parse_date(date_str)
        agents = sorted(get_email_stats_by_agent(target), key=lambda x: x['total_emails'], reverse=True)
        return jsonify_ok({'data': agents, 'date': str(target)})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/email/trend')
def email_trend():
    """Email volume last 7 days by type for chart."""
    try:
        from core.email_database import email_db
        rows = email_db.execute_query("""
            SELECT DATE(created_2) AS d,
                   COUNT(*) AS total,
                   SUM(email_type='CANCELATION REQ') AS cancels,
                   SUM(email_type='FULL REFUND')      AS full_ref,
                   SUM(email_type='PARTIAL REFUND')   AS part_ref,
                   COALESCE(SUM(refund),0)             AS refund_val
            FROM tbl_email
            WHERE created_2 >= DATE_SUB(NOW(), INTERVAL 6 DAY)
            GROUP BY DATE(created_2) ORDER BY d
        """) or []
        return jsonify_ok({'data': [{'date': str(r['d']), 'total': safe_int(r['total']),
                                     'cancels': safe_int(r['cancels']),
                                     'full_ref': safe_int(r['full_ref']),
                                     'part_ref': safe_int(r['part_ref']),
                                     'refund_val': safe_float(r['refund_val'])} for r in rows]})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/email/mapping', methods=['GET'])
def email_mapping_list():
    try:
        from core.email_integration import get_all_mappings
        m = get_all_mappings()
        return jsonify_ok({'data': [{'pinktools_name': k, 'altria_username': v} for k, v in m.items()]})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/email/mapping', methods=['POST'])
def email_mapping_add():
    try:
        from core.email_integration import add_mapping, ensure_mapping_table
        ensure_mapping_table()
        body = request.get_json(force=True)
        pt = (body.get('pinktools_name') or '').strip()
        al = (body.get('altria_username') or '').strip()
        if not pt or not al:
            return jsonify_err('Both fields required', 400)
        add_mapping(pt, al)
        return jsonify_ok({'message': f'Mapped "{pt}" → "{al}"'})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/email/unmapped')
@app.route('/api/email/unmapped/<date_str>')
def email_unmapped_api(date_str=None):
    try:
        from core.email_integration import list_unmapped_agents, ensure_mapping_table
        ensure_mapping_table()
        target = _parse_date(date_str)
        names = list_unmapped_agents(target)
        return jsonify_ok({'data': names, 'count': len(names), 'date': str(target)})
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# AI Auto-Score API
# ──────────────────────────────────────────────────────────────────────────────
import threading, uuid
_ai_jobs = {}   # job_id → {status, progress, log, result, error}

def _run_ai_job(job_id, uniqueid, phone, call_date_str, agent, campaign, duration):
    """Run AI scoring in background thread — updates _ai_jobs[job_id] as it progresses."""
    job = _ai_jobs[job_id]
    log = []
    def progress(msg, pct=None):
        log.append(msg)
        job['log'] = log[:]
        if pct is not None:
            job['progress'] = pct

    try:
        from quality.ai_assistant import (
            download_recording, transcribe_audio,
            analyze_transcript, detect_ghost_call, get_checkpoints
        )
        from datetime import datetime as _dt

        progress("Loading AI model…", 5)
        # Parse call_date
        try:
            call_date = _dt.strptime(call_date_str[:19], '%Y-%m-%d %H:%M:%S')
        except Exception:
            call_date = _dt.now()

        progress("Downloading recording…", 15)
        audio_path = download_recording(uniqueid, phone, call_date)
        if not audio_path:
            raise ValueError("Recording not found — check recordings server")

        progress("Transcribing audio with Whisper…", 35)
        transcript = transcribe_audio(audio_path)
        if not transcript:
            raise ValueError("Transcription failed or empty")

        progress(f"Transcript ready ({len(transcript.split())} words). Analysing…", 60)

        ghost = detect_ghost_call(transcript, duration)
        call_type = ghost.get('call_type', 'NORMAL')

        analysis = analyze_transcript(transcript)
        analysis['call_type']   = call_type
        analysis['ghost_reason'] = ghost.get('reason', '')

        checkpoints = get_checkpoints()
        if not checkpoints:
            raise ValueError("No QC checkpoints configured")

        progress("Saving evaluation…", 80)
        scores    = analysis['scores']
        total_pos = sum(safe_float(cp['max_points']) for cp in checkpoints)
        total_giv = sum(safe_float(scores.get(cp['checkpoint_id'], 0)) for cp in checkpoints)
        pct_score = round(total_giv / total_pos * 100, 1) if total_pos else 0
        ai_conf   = round(analysis.get('confidence', 70), 1)

        db.execute_query("""
            INSERT INTO qc_results
                (uniqueid, evaluation_date, total_score, ai_total_score,
                 ai_confidence, source, comments, status)
            VALUES (%s, NOW(), %s, %s, %s, 'AI', %s, 'ACTIVE')
        """, (uniqueid, pct_score, pct_score, ai_conf,
              f"[AI] {analysis.get('notes','')} | {ghost.get('reason','')}"))

        rid_row = db.execute_query("SELECT LAST_INSERT_ID() AS id")
        result_id = safe_int((rid_row or [{'id': 0}])[0].get('id') or 0)
        if result_id == 0:
            # Fallback: get the actual inserted row
            rid_row2 = db.execute_query(
                "SELECT result_id FROM qc_results WHERE uniqueid=%s ORDER BY result_id DESC LIMIT 1",
                (uniqueid,))
            result_id = safe_int((rid_row2 or [{'result_id': 0}])[0].get('result_id') or 0)

        if result_id:
            for cp in checkpoints:
                cid = cp['checkpoint_id']
                db.execute_query("""
                    INSERT INTO qc_results_detail (result_id, checkpoint_id, score_given)
                    VALUES (%s, %s, %s)
                """, (result_id, cid, safe_float(scores.get(cid, 0))))

        progress("Done!", 100)
        # Resolve agent full name from DB if not provided
        agent_name_db = job.get('agent_name') or agent
        if not job.get('agent_name'):
            try:
                row = db.execute_query(
                    "SELECT full_name FROM vicidial_users WHERE user=%s LIMIT 1", (agent,))
                if row and row[0].get('full_name'):
                    agent_name_db = row[0]['full_name']
            except Exception:
                pass

        # Format duration nicely
        dur_min = duration // 60
        dur_sec = duration % 60
        dur_fmt = f"{dur_min}:{dur_sec:02d}"

        job['status'] = 'complete'
        job['result'] = {
            'result_id':    result_id,
            'score':        pct_score,
            'confidence':   ai_conf,
            'call_type':    call_type,
            'ghost_reason': ghost.get('reason',''),
            'notes':        analysis.get('notes',''),
            'transcript_preview': transcript[:400] + ('…' if len(transcript)>400 else ''),
            # Call metadata — shown in modal header
            'agent':        agent,
            'agent_name':   agent_name_db,
            'phone':        phone,
            'campaign':     campaign,
            'call_date':    call_date_str[:19] if call_date_str else '',
            'duration':     duration,
            'duration_fmt': dur_fmt,
            'checkpoints': [{'id': cp['checkpoint_id'],
                             'text': cp['checkpoint_text'],
                             'score': round(safe_float(scores.get(cp['checkpoint_id'],0)), 1),
                             'max':   safe_float(cp['max_points'])} for cp in checkpoints]
        }

    except Exception as e:
        import traceback
        job['status'] = 'error'
        job['error']  = str(e)
        job['log']    = log + [f"ERROR: {e}"]


@app.route('/api/ai/score', methods=['POST'])
def ai_score_start():
    """Start AI scoring for a call. Returns job_id to poll."""
    try:
        body       = request.get_json(force=True)
        uniqueid   = (body.get('uniqueid')   or '').strip()
        phone      = (body.get('phone')      or '').strip()
        call_date  = (body.get('call_date')  or '').strip()
        agent      = (body.get('agent')      or '').strip()
        agent_name = (body.get('agent_name') or '').strip()
        campaign   = (body.get('campaign')   or '').strip()
        duration   = safe_int(body.get('duration', 0))

        if not uniqueid:
            return jsonify_err('uniqueid required', 400)

        job_id = str(uuid.uuid4())[:8]
        _ai_jobs[job_id] = {
            'status': 'running', 'progress': 0,
            'log': ['Starting AI scoring…'], 'result': None, 'error': None,
            'agent_name': agent_name  # stored so _run_ai_job can use it
        }
        t = threading.Thread(
            target=_run_ai_job,
            args=(job_id, uniqueid, phone, call_date, agent, campaign, duration),
            daemon=True
        )
        t.start()
        return jsonify_ok({'job_id': job_id})
    except Exception as e:
        return jsonify_err(e)


@app.route('/api/ai/status/<job_id>')
def ai_score_status(job_id):
    """Poll AI scoring job status."""
    job = _ai_jobs.get(job_id)
    if not job:
        return jsonify_err('Job not found', 404)
    return jsonify_ok({
        'status':   job['status'],
        'progress': job['progress'],
        'log':      job['log'],
        'result':   job['result'],
        'error':    job['error']
    })


@app.route('/api/ai/calls')
def ai_available_calls():
    """Calls available for AI scoring (have recordings, not yet AI-scored).
       ?campaign=&agent=&days=7"""
    try:
        campaign = request.args.get('campaign', '')
        agent    = request.args.get('agent', '')
        days     = int(request.args.get('days', 7))

        # Check if recording_log table exists
        rec_table = db.execute_query("SHOW TABLES LIKE 'recording_log'")
        if not rec_table:
            return jsonify_ok({'data': [], 'message': 'recording_log table not found in VICIdial DB'})

        where_parts = [
            "c.call_date >= DATE_SUB(NOW(), INTERVAL %s DAY)",
            "c.length_in_sec >= 30",
        ]
        params = [days]

        # Exclude already AI-scored calls only if qc_results table exists
        if _qc_tables_exist():
            where_parts.append(
                "c.uniqueid NOT IN ("
                "  SELECT uniqueid FROM qc_results"
                "  WHERE source='AI' AND (status='ACTIVE' OR status IS NULL)"
                ")"
            )

        if campaign:
            where_parts.append("c.campaign_id = %s")
            params.append(campaign)
        if agent:
            where_parts.append("a.user = %s")
            params.append(agent)

        where_clause = " AND ".join(where_parts)

        sql = (
            "SELECT c.uniqueid, c.call_date, c.campaign_id,"
            "       c.phone_number, c.length_in_sec,"
            "       a.user AS agent, u.full_name, rl.filename"
            " FROM vicidial_closer_log c"
            " LEFT JOIN vicidial_agent_log a ON c.uniqueid = a.uniqueid"
            " LEFT JOIN vicidial_users u      ON a.user = u.user"
            " JOIN recording_log rl"
            "   ON rl.filename LIKE CONCAT('%%', c.phone_number, '%%')"
            "  AND DATE(rl.start_time) = DATE(c.call_date)"
            " WHERE " + where_clause +
            " GROUP BY c.uniqueid"
            " ORDER BY c.call_date DESC LIMIT 50"
        )
        rows = db.execute_query(sql, params) or []

        return jsonify_ok({'data': [{
            'uniqueid':     r['uniqueid'],
            'date':         str(r['call_date']),
            'campaign':     r.get('campaign_id', ''),
            'phone':        r.get('phone_number', ''),
            'duration':     safe_int(r['length_in_sec']),
            'duration_fmt': sec_to_hms(safe_int(r['length_in_sec'])),
            'agent':        r.get('agent', ''),
            'agent_name':   r.get('full_name', '') or r.get('agent', ''),
            'filename':     r.get('filename', '')
        } for r in rows]})
    except Exception as e:
        return jsonify_err(e)


# ──────────────────────────────────────────────────────────────────────────────
# Billing / Minutes Report API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/billing/summary')
def billing_summary():
    """Talk minutes per campaign — today, this week, this month, last month.
       Optional ?campaigns=A,B filter."""
    try:
        camp_param = request.args.get('campaigns','').strip()
        camp_filter = ''
        camp_params_base = []
        if camp_param:
            selected = [c.strip() for c in camp_param.split(',') if c.strip()]
            if selected:
                placeholders = ','.join(['%s']*len(selected))
                camp_filter = f" AND campaign_id IN ({placeholders})"
                camp_params_base = selected

        def _query(extra_where, params):
            sql = (
                "SELECT campaign_id,"
                " COUNT(*) AS calls,"
                " SUM(CASE WHEN length_in_sec>=5 THEN 1 ELSE 0 END) AS valid_calls,"
                " SUM(CASE WHEN length_in_sec>=5 THEN length_in_sec ELSE 0 END) AS talk_sec"
                " FROM vicidial_closer_log"
                " WHERE " + extra_where + camp_filter +
                " GROUP BY campaign_id ORDER BY talk_sec DESC"
            )
            return db.execute_query(sql, params + camp_params_base) or []

        def _fmt(rows):
            total_sec  = sum(safe_int(r['talk_sec']) for r in rows)
            total_min  = round(total_sec/60, 2)
            total_calls= sum(safe_int(r['calls']) for r in rows)
            return {
                'total_seconds': total_sec,
                'total_minutes': total_min,
                'total_minutes_fmt': f"{int(total_min):,} min {int((total_min % 1)*60):02d} sec",
                'total_calls': total_calls,
                'by_campaign': [{'campaign': r['campaign_id'],
                    'calls': safe_int(r['calls']),
                    'valid_calls': safe_int(r['valid_calls']),
                    'talk_sec': safe_int(r['talk_sec']),
                    'minutes': round(safe_int(r['talk_sec'])/60, 2),
                    'minutes_fmt': sec_to_hms(safe_int(r['talk_sec']))} for r in rows]
            }

        today   = _fmt(_query("DATE(call_date) = CURDATE()", []))
        week    = _fmt(_query("call_date >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)", []))
        month   = _fmt(_query("YEAR(call_date)=YEAR(CURDATE()) AND MONTH(call_date)=MONTH(CURDATE())", []))
        lmonth  = _fmt(_query("YEAR(call_date)=YEAR(DATE_SUB(CURDATE(),INTERVAL 1 MONTH)) AND MONTH(call_date)=MONTH(DATE_SUB(CURDATE(),INTERVAL 1 MONTH))", []))

        # Daily breakdown for last 30 days (for chart)
        daily_rows = db.execute_query(
            "SELECT DATE(call_date) AS d,"
            " SUM(CASE WHEN length_in_sec>=5 THEN length_in_sec ELSE 0 END) AS talk_sec,"
            " COUNT(*) AS calls"
            " FROM vicidial_closer_log"
            " WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 29 DAY)" + camp_filter +
            " GROUP BY DATE(call_date) ORDER BY d",
            camp_params_base
        ) or []

        return jsonify_ok({
            'today':   today,
            'week':    week,
            'month':   month,
            'last_month': lmonth,
            'daily': [{'date': str(r['d']),
                       'minutes': round(safe_int(r['talk_sec'])/60, 2),
                       'calls': safe_int(r['calls'])} for r in daily_rows]
        })
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# Agent Management API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/agents/list')
def agents_list():
    """All active agents with basic info."""
    try:
        # Debug: check connection and total count first
        total = db.execute_query("SELECT COUNT(*) AS n FROM vicidial_users") or [{'n':0}]
        active = db.execute_query("SELECT COUNT(*) AS n FROM vicidial_users WHERE active='Y'") or [{'n':0}]

        rows = db.execute_query(
            "SELECT u.user, u.full_name, u.user_level, u.active,"
            " COALESCE(l.campaign_id, '') AS campaign_id"
            " FROM vicidial_users u"
            " LEFT JOIN vicidial_live_agents l ON u.user = l.user"
            " WHERE u.active='Y'"
            "   AND u.user_level BETWEEN 1 AND 4"
            "   AND u.user NOT IN ('6666','6667','6668','VDAD','VDCL')"
            " ORDER BY u.full_name"
        ) or []

        return jsonify_ok({
            'data': [{'user': r['user'],
                'name': r.get('full_name') or r['user'],
                'level': safe_int(r.get('user_level')),
                'campaign': r.get('campaign_id') or ''
            } for r in rows],
            'count': len(rows)
        })
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/agents/lookup/<username>')
def agent_lookup(username):
    """Full agent profile + recent stats."""
    try:
        agent = db.execute_query("""
            SELECT u.*,
                COUNT(DISTINCT a.uniqueid) AS total_calls,
                SUM(a.talk_sec) AS total_talk,
                AVG(a.talk_sec) AS avg_talk,
                MAX(a.event_time) AS last_active
            FROM vicidial_users u
            LEFT JOIN vicidial_agent_log a ON u.user = a.user
                AND a.event_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            WHERE u.user = %s GROUP BY u.user
        """, (username,))
        if not agent:
            return jsonify_err('Agent not found', 404)
        a = agent[0]

        # Last 7 days daily breakdown
        daily = db.execute_query("""
            SELECT DATE(event_time) AS d,
                COUNT(*) AS calls, SUM(talk_sec) AS talk_sec
            FROM vicidial_agent_log
            WHERE user=%s AND event_time >= DATE_SUB(NOW(), INTERVAL 6 DAY)
            GROUP BY DATE(event_time) ORDER BY d
        """, (username,)) or []

        # Recent calls
        recent = db.execute_query("""
            SELECT c.call_date, c.campaign_id, c.phone_number,
                   c.length_in_sec, c.term_reason
            FROM vicidial_closer_log c
            WHERE c.uniqueid IN (
                SELECT uniqueid FROM vicidial_agent_log WHERE user=%s
                AND event_time >= DATE_SUB(NOW(), INTERVAL 7 DAY))
            ORDER BY c.call_date DESC LIMIT 10
        """, (username,)) or []

        return jsonify_ok({'data': {
            'user': a['user'], 'name': a.get('full_name') or a['user'],
            'level': safe_int(a.get('user_level')),
            'campaign': a.get('campaign_id',''),
            'email': a.get('email',''),
            'active': a.get('active',''),
            'total_calls_30d': safe_int(a.get('total_calls')),
            'total_talk_30d': sec_to_hms(safe_int(a.get('total_talk'))),
            'avg_talk_30d': sec_to_hms(safe_int(a.get('avg_talk'))),
            'last_active': str(a.get('last_active','')),
            'daily': [{'date':str(r['d']),'calls':safe_int(r['calls']),
                       'talk':sec_to_hms(safe_int(r['talk_sec']))} for r in daily],
            'recent_calls': [{'date':str(r['call_date']),
                'campaign':r.get('campaign_id',''),
                'phone':r.get('phone_number',''),
                'duration':sec_to_hms(safe_int(r['length_in_sec'])),
                'result':r.get('term_reason','')} for r in recent]}})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/agents/performance')
def agents_performance():
    """Agent performance for a period. ?days=7&campaign="""
    try:
        days     = int(request.args.get('days', 7))
        campaign = request.args.get('campaign','')
        camp_filter = " AND c.campaign_id=%s" if campaign else ""
        camp_params = [campaign] if campaign else []

        rows = db.execute_query(
            "SELECT a.user, u.full_name,"
            " COUNT(DISTINCT c.uniqueid) AS calls,"
            " SUM(CASE WHEN c.length_in_sec>=5 THEN 1 ELSE 0 END) AS valid,"
            " SUM(c.length_in_sec) AS talk_sec,"
            " AVG(CASE WHEN c.length_in_sec>=5 THEN c.length_in_sec END) AS avg_talk,"
            " COUNT(DISTINCT DATE(c.call_date)) AS days_active"
            " FROM vicidial_agent_log a"
            " LEFT JOIN vicidial_users u ON a.user=u.user"
            " LEFT JOIN vicidial_closer_log c ON a.uniqueid=c.uniqueid"
            "  AND c.call_date >= DATE_SUB(NOW(), INTERVAL %s DAY)"
            + camp_filter +
            " WHERE a.event_time >= DATE_SUB(NOW(), INTERVAL %s DAY)"
            " GROUP BY a.user ORDER BY calls DESC LIMIT 30",
            [days] + camp_params + [days]) or []

        return jsonify_ok({'data': [{'user':r['user'],
            'name': r.get('full_name') or r['user'],
            'calls': safe_int(r['calls']),
            'valid': safe_int(r['valid']),
            'days_active': safe_int(r['days_active']),
            'talk_time': sec_to_hms(safe_int(r['talk_sec'])),
            'avg_call': sec_to_hms(safe_int(r['avg_talk'])),
            'minutes': round(safe_int(r['talk_sec'])/60, 1)} for r in rows],
            'period': days})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/agents/login-history/<username>')
def agent_login_history(username):
    """Login/logout sessions for an agent. ?days=7"""
    try:
        days = int(request.args.get('days', 7))
        rows = db.execute_query("""
            SELECT event_time, status, campaign_id, talk_sec, wait_sec
            FROM vicidial_agent_log
            WHERE user=%s AND event_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY event_time DESC LIMIT 200
        """, (username, days)) or []

        # Group by day
        from collections import defaultdict
        by_day = defaultdict(list)
        for r in rows:
            d = str(r['event_time'].date()) if hasattr(r['event_time'],'date') else str(r['event_time'])[:10]
            by_day[d].append({'time': str(r['event_time']),
                'status': r.get('status',''),
                'campaign': r.get('campaign_id',''),
                'talk_sec': safe_int(r.get('talk_sec')),
                'wait_sec': safe_int(r.get('wait_sec'))})

        days_data = []
        for d in sorted(by_day.keys(), reverse=True):
            events = by_day[d]
            total_talk = sum(e['talk_sec'] for e in events)
            days_data.append({'date': d, 'events': events,
                'total_talk': sec_to_hms(total_talk),
                'event_count': len(events)})

        return jsonify_ok({'data': days_data, 'username': username})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/agents/notes/<username>', methods=['GET'])
def agent_notes_get(username):
    """Get notes for an agent (file-based)."""
    try:
        import json
        notes_dir  = Path(__file__).parent.parent / 'data' / 'agent_notes'
        index_file = notes_dir / 'notes_index.json'
        if not index_file.exists():
            return jsonify_ok({'data': [], 'username': username})
        idx = json.loads(index_file.read_text())
        agent_notes = idx.get('agents', {}).get(username, [])
        result = []
        for note_id in agent_notes:
            nf = notes_dir / f"{note_id}.json"
            if nf.exists():
                result.append(json.loads(nf.read_text()))
        result.sort(key=lambda x: x.get('created_at',''), reverse=True)
        return jsonify_ok({'data': result, 'username': username})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/agents/notes/<username>', methods=['POST'])
def agent_notes_add(username):
    """Add a note for an agent."""
    try:
        import json
        body = request.get_json(force=True)
        note_type = (body.get('type') or 'general').strip()
        content   = (body.get('content') or '').strip()
        if not content:
            return jsonify_err('content required', 400)

        notes_dir  = Path(__file__).parent.parent / 'data' / 'agent_notes'
        notes_dir.mkdir(parents=True, exist_ok=True)
        index_file = notes_dir / 'notes_index.json'

        if index_file.exists():
            idx = json.loads(index_file.read_text())
        else:
            idx = {'agents': {}, 'last_id': 0}

        idx['last_id'] = idx.get('last_id', 0) + 1
        note_id = f"note_{idx['last_id']:05d}"
        note = {'id': note_id, 'agent': username, 'type': note_type,
                'content': content, 'created_at': datetime.now().isoformat(),
                'created_by': 'web'}

        (notes_dir / f"{note_id}.json").write_text(json.dumps(note, indent=2))
        if username not in idx['agents']:
            idx['agents'][username] = []
        idx['agents'][username].append(note_id)
        index_file.write_text(json.dumps(idx, indent=2))

        return jsonify_ok({'note_id': note_id, 'message': 'Note saved'})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/agents/sales-dashboard')
def agents_sales_dashboard():
    """Sales/outbound metrics per agent. ?days=7"""
    try:
        days = int(request.args.get('days', 7))
        rows = db.execute_query("""
            SELECT a.user, u.full_name,
                COUNT(DISTINCT c.uniqueid) AS dials,
                SUM(CASE WHEN c.length_in_sec>=5 THEN 1 ELSE 0 END) AS contacts,
                SUM(c.length_in_sec) AS talk_sec,
                AVG(CASE WHEN c.length_in_sec>=5 THEN c.length_in_sec END) AS avg_talk,
                COUNT(DISTINCT DATE(c.call_date)) AS days_worked
            FROM vicidial_agent_log a
            LEFT JOIN vicidial_users u ON a.user=u.user
            LEFT JOIN vicidial_closer_log c ON a.uniqueid=c.uniqueid
            WHERE a.event_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
              AND c.campaign_id IN (
                  SELECT DISTINCT campaign_id FROM vicidial_closer_log
                  WHERE call_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
                  AND length_in_sec >= 5)
            GROUP BY a.user
            HAVING dials > 0
            ORDER BY contacts DESC LIMIT 20
        """, (days, days)) or []

        return jsonify_ok({'data': [{'user': r['user'],
            'name': r.get('full_name') or r['user'],
            'dials': safe_int(r['dials']),
            'contacts': safe_int(r['contacts']),
            'contact_rate': round(safe_int(r['contacts'])/safe_int(r['dials'])*100,1) if safe_int(r['dials']) else 0,
            'talk_time': sec_to_hms(safe_int(r['talk_sec'])),
            'avg_call': sec_to_hms(safe_int(r['avg_talk'])),
            'days_worked': safe_int(r['days_worked'])} for r in rows],
            'period': days})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/agents/outbound-monitor')
def agents_outbound_monitor():
    """Live outbound agents + recent 30min activity."""
    try:
        # Get outbound campaigns
        camp_rows = db.execute_query("""
            SELECT campaign_id FROM vicidial_campaigns
            WHERE campaign_allow_inbound='N'
               OR dial_method IN ('RATIO','ADAPT_HARD_LIMIT','ADAPT_TAPERED','ADAPT_AVERAGE','MANUAL','INBOUND_MAN')
            ORDER BY campaign_id
        """) or []
        camp_list = list({r['campaign_id'] for r in camp_rows})
        if not camp_list:
            camp_list = ['YPDirect','K1','UpliftDeals','Zappify']  # fallback

        placeholders = ','.join(['%s']*len(camp_list))

        # Live agents on outbound calls
        live = db.execute_query(
            "SELECT l.user, u.full_name, l.status, l.campaign_id,"
            " TIMESTAMPDIFF(SECOND, l.last_state_change, NOW()) AS seconds_in_status"
            " FROM vicidial_live_agents l"
            " LEFT JOIN vicidial_users u ON l.user=u.user"
            " WHERE l.status='INCALL' AND l.campaign_id IN (" + placeholders + ")"
            " ORDER BY seconds_in_status DESC",
            camp_list) or []

        # Recent activity last 30 min
        recent = db.execute_query(
            "SELECT c.call_date, c.campaign_id, c.phone_number,"
            " c.length_in_sec, c.term_reason,"
            " a.user, u.full_name"
            " FROM vicidial_closer_log c"
            " LEFT JOIN vicidial_agent_log a ON c.uniqueid=a.uniqueid"
            " LEFT JOIN vicidial_users u ON a.user=u.user"
            " WHERE c.call_date >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)"
            "   AND c.campaign_id IN (" + placeholders + ")"
            " ORDER BY c.call_date DESC LIMIT 50",
            camp_list) or []

        # Campaign summary from live agents
        from collections import Counter
        camp_counts = Counter(r['campaign_id'] for r in live)

        return jsonify_ok({
            'live_agents': [{'user': r['user'],
                'name': r.get('full_name') or r['user'],
                'campaign': r.get('campaign_id',''),
                'status': r.get('status',''),
                'duration': safe_int(r.get('seconds_in_status')),
                'duration_fmt': sec_to_hms(safe_int(r.get('seconds_in_status')))} for r in live],
            'campaign_summary': [{'campaign': c, 'count': n} for c,n in camp_counts.most_common()],
            'recent': [{'time': str(r['call_date']),
                'agent': r.get('user',''),
                'name': r.get('full_name') or r.get('user',''),
                'campaign': r.get('campaign_id',''),
                'phone': r.get('phone_number',''),
                'duration': sec_to_hms(safe_int(r['length_in_sec'])),
                'result': r.get('term_reason','')} for r in recent],
            'total_live': len(live)
        })
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/agents/inbound-groups')
def agents_inbound_groups():
    """Inbound group stats."""
    try:
        rows = db.execute_query("""
            SELECT group_id, group_name, active,
                   calls_today, calls_waiting, oldest_call_waiting,
                   next_agent_call
            FROM vicidial_inbound_groups
            ORDER BY calls_today DESC
        """) or []
        return jsonify_ok({'data': [{'id': r.get('group_id'),
            'name': r.get('group_name',''),
            'active': r.get('active',''),
            'calls_today': safe_int(r.get('calls_today')),
            'waiting': safe_int(r.get('calls_waiting')),
            'oldest_wait': str(r.get('oldest_call_waiting',''))} for r in rows]})
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# Agent Mapping API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/mapping/agents')
def mapping_agents():
    """All pinktools agents with their mapping status and email count."""
    try:
        from core.email_database import email_db
        from core.email_integration import get_all_mappings, ensure_mapping_table
        ensure_mapping_table()
        mapping = get_all_mappings()
        rows = email_db.execute_query("""
            SELECT agent_name, COUNT(*) AS total,
                   MAX(DATE(created_2)) AS last_seen
            FROM tbl_email
            WHERE agent_name IS NOT NULL AND agent_name != ''
            GROUP BY agent_name ORDER BY total DESC
        """) or []
        result = [{'pinktools_name': r['agent_name'],
                   'altria_username': mapping.get(r['agent_name'], ''),
                   'total_emails': safe_int(r['total']),
                   'last_seen': str(r['last_seen']) if r['last_seen'] else ''} for r in rows]
        return jsonify_ok({'data': result, 'total': len(result),
                           'linked': sum(1 for r in result if r['altria_username']),
                           'unlinked': sum(1 for r in result if not r['altria_username'])})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/mapping/vicidial-users')
def mapping_vicidial_users():
    """All VICIdial users for the mapping dropdown."""
    try:
        rows = db.execute_query("""
            SELECT user, full_name FROM vicidial_users
            WHERE user_level >= 1 ORDER BY full_name
        """) or []
        return jsonify_ok({'data': [{'user': r['user'],
                                     'full_name': r.get('full_name') or r['user']} for r in rows]})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/mapping/save', methods=['POST'])
def mapping_save():
    """Save multiple mappings at once. Body: [{pinktools_name, altria_username}]"""
    try:
        from core.email_integration import add_mapping, ensure_mapping_table
        from core.email_database import email_db
        ensure_mapping_table()
        body = request.get_json(force=True)
        mappings = body if isinstance(body, list) else body.get('mappings', [])
        saved = 0
        for m in mappings:
            pt = (m.get('pinktools_name') or '').strip()
            al = (m.get('altria_username') or '').strip()
            if pt and al:
                add_mapping(pt, al)
                saved += 1
            elif pt and not al:
                email_db.execute_query(
                    "UPDATE tbl_agent_map SET active=0 WHERE pinktools_agent_name=%s", (pt,))
        return jsonify_ok({'saved': saved})
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# VICIdial Reports API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/reports/agent-performance')
def report_agent_performance():
    """Agent performance for a date range. ?start=YYYY-MM-DD&end=YYYY-MM-DD"""
    try:
        from datetime import date as dt
        start = request.args.get('start', str(dt.today()))
        end   = request.args.get('end',   str(dt.today()))
        rows = db.execute_query("""
            SELECT a.user, u.full_name,
                COUNT(*) AS total_calls,
                SUM(CASE WHEN a.talk_sec >= 5 THEN 1 ELSE 0 END) AS valid_calls,
                SUM(a.talk_sec) AS total_talk,
                AVG(CASE WHEN a.talk_sec >= 5 THEN a.talk_sec END) AS avg_talk,
                SUM(CASE WHEN a.talk_sec = 0 THEN 1 ELSE 0 END) AS ghost_calls
            FROM vicidial_agent_log a
            LEFT JOIN vicidial_users u ON a.user = u.user
            WHERE DATE(a.event_time) BETWEEN %s AND %s
            GROUP BY a.user ORDER BY valid_calls DESC
        """, (start, end)) or []
        return jsonify_ok({'data': [{'user': r['user'],
            'name': r.get('full_name') or r['user'],
            'total_calls': safe_int(r['total_calls']),
            'valid_calls': safe_int(r['valid_calls']),
            'ghost_calls': safe_int(r['ghost_calls']),
            'total_talk': sec_to_hms(safe_int(r['total_talk'])),
            'avg_talk': sec_to_hms(safe_int(r['avg_talk'])),
            'answer_rate': round(safe_int(r['valid_calls'])/safe_int(r['total_calls'])*100,1)
                           if safe_int(r['total_calls']) else 0} for r in rows],
            'period': {'start': start, 'end': end}})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/reports/campaign-trend')
def report_campaign_trend():
    """7-day or 30-day campaign trend. ?days=7"""
    try:
        days = int(request.args.get('days', 7))
        rows = db.execute_query(f"""
            SELECT DATE(call_date) AS d,
                COUNT(*) AS calls,
                SUM(CASE WHEN length_in_sec>=5 THEN 1 ELSE 0 END) AS answered,
                SUM(CASE WHEN term_reason IN ('ABANDON','QUEUETIMEOUT','NOAGENT') THEN 1 ELSE 0 END) AS abandoned,
                AVG(queue_seconds) AS avg_queue
            FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            GROUP BY DATE(call_date) ORDER BY d
        """, (days,)) or []
        return jsonify_ok({'data': [{'date': str(r['d']),
            'calls': safe_int(r['calls']), 'answered': safe_int(r['answered']),
            'abandoned': safe_int(r['abandoned']),
            'answer_rate': round(safe_int(r['answered'])/safe_int(r['calls'])*100,1) if safe_int(r['calls']) else 0,
            'avg_queue': round(safe_float(r['avg_queue']),1)} for r in rows]})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/reports/hourly-heatmap')
def report_hourly_heatmap():
    """Hourly call volume heatmap for last 7 days."""
    try:
        rows = db.execute_query("""
            SELECT DATE(call_date) AS d, HOUR(call_date) AS h, COUNT(*) AS calls
            FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
            GROUP BY DATE(call_date), HOUR(call_date)
        """) or []
        return jsonify_ok({'data': [{'date': str(r['d']), 'hour': safe_int(r['h']),
                                     'calls': safe_int(r['calls'])} for r in rows]})
    except Exception as e:
        return jsonify_err(e)


@app.route('/api/reports/dispositions')
def report_dispositions():
    """
    Disposition pivot table per agent per campaign.
    Params:
      agents     – comma-separated VICIdial usernames, or '' for all
      campaign   – specific campaign_id, or '' for all
      date_start – YYYY-MM-DD (default today in EST)
      date_end   – YYYY-MM-DD (default = date_start)
    Returns rows pivoted: each unique status becomes a key in `dispositions`.
    """
    try:
        est_today = get_est_time().strftime('%Y-%m-%d')
        date_start  = request.args.get('date_start') or est_today
        date_end    = request.args.get('date_end')   or date_start
        agents_raw  = request.args.get('agents', '').strip()   # comma-separated
        campaign    = request.args.get('campaign', '').strip()

        # Build WHERE clause
        where = ["vl.call_date >= %s", "vl.call_date < DATE_ADD(%s, INTERVAL 1 DAY)"]
        params = [date_start, date_end]

        if agents_raw:
            agent_list = [a.strip() for a in agents_raw.split(',') if a.strip()]
            if agent_list:
                placeholders = ','.join(['%s'] * len(agent_list))
                where.append(f"vl.user IN ({placeholders})")
                params.extend(agent_list)
        if campaign:
            where.append("vl.campaign_id = %s")
            params.append(campaign)

        where_sql = " AND ".join(where)

        rows = db.execute_query(
            "SELECT vl.user, COALESCE(u.full_name, vl.user) AS full_name,"
            "       vl.campaign_id, vl.status, COUNT(*) AS cnt,"
            "       SUM(vl.length_in_sec) AS total_sec"
            " FROM vicidial_log vl"
            " LEFT JOIN vicidial_users u ON vl.user = u.user"
            " WHERE " + where_sql +
            " GROUP BY vl.user, u.full_name, vl.campaign_id, vl.status"
            " ORDER BY vl.user, vl.campaign_id, cnt DESC",
            params
        ) or []

        # Pivot: build per-agent-campaign bucket
        buckets = {}   # key = (user, campaign_id)
        all_statuses = []

        for r in rows:
            key   = (r['user'], r['campaign_id'] or '')
            st    = (r['status'] or 'OTHER').upper()
            cnt   = safe_int(r['cnt'])
            secs  = safe_int(r['total_sec'])

            if key not in buckets:
                buckets[key] = {
                    'user':         r['user'],
                    'name':         r['full_name'] or r['user'],
                    'campaign_id':  r['campaign_id'] or '',
                    'dispositions': {},
                    'total':        0,
                    'total_sec':    0
                }
            buckets[key]['dispositions'][st] = buckets[key]['dispositions'].get(st, 0) + cnt
            buckets[key]['total']    += cnt
            buckets[key]['total_sec'] += secs

            if st not in all_statuses:
                all_statuses.append(st)

        # Compute column-level totals
        col_totals   = {s: 0 for s in all_statuses}
        grand_total  = 0
        agent_list   = []
        for bk in buckets.values():
            for s, c in bk['dispositions'].items():
                col_totals[s] = col_totals.get(s, 0) + c
            grand_total += bk['total']
            # format talk time
            h, rem = divmod(bk['total_sec'], 3600)
            m, s2  = divmod(rem, 60)
            bk['talk_time'] = f"{int(h):02d}:{int(m):02d}:{int(s2):02d}"
            agent_list.append(bk)

        # Sort statuses: put common ones first
        priority = ['YPVM', 'YPCBCK', 'YPNI', 'YPNA', 'INCALL', 'SALE', 'DNC',
                    'DROP', 'CBHOLD', 'XFER', 'NI', 'NA', 'B', 'DC', 'DNCL']
        all_statuses.sort(key=lambda s: (priority.index(s) if s in priority else 99, s))

        # Sort agents by name then campaign
        agent_list.sort(key=lambda a: (a['name'].lower(), a['campaign_id']))

        return jsonify_ok({
            'agents':      agent_list,
            'statuses':    all_statuses,
            'col_totals':  col_totals,
            'grand_total': grand_total,
            'date_start':  date_start,
            'date_end':    date_end
        })
    except Exception as e:
        return jsonify_err(e)


# ──────────────────────────────────────────────────────────────────────────────
# Quality Scoring API
# ──────────────────────────────────────────────────────────────────────────────

def _qc_tables_exist():
    r = db.execute_query("SHOW TABLES LIKE 'qc_results'")
    return bool(r)

@app.route('/api/qc/dashboard')
def qc_dashboard():
    """QC overall stats."""
    try:
        if not _qc_tables_exist():
            return jsonify_ok({'available': False, 'message': 'QC tables not found'})
        row = db.execute_query("""
            SELECT COUNT(*) AS total,
                COUNT(DISTINCT a.user) AS agents,
                ROUND(AVG(qcr.total_score),1) AS avg_score,
                ROUND(MIN(qcr.total_score),1) AS min_score,
                ROUND(MAX(qcr.total_score),1) AS max_score,
                SUM(qcr.total_score >= 90) AS excellent,
                SUM(qcr.total_score >= 80 AND qcr.total_score < 90) AS good,
                SUM(qcr.total_score >= 70 AND qcr.total_score < 80) AS average,
                SUM(qcr.total_score < 70) AS needs_work
            FROM qc_results qcr
            JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
            WHERE (qcr.status='ACTIVE' OR qcr.status IS NULL)
        """) or [{}]
        s = row[0]
        return jsonify_ok({'available': True, 'stats': {
            'total': safe_int(s.get('total')), 'agents': safe_int(s.get('agents')),
            'avg_score': safe_float(s.get('avg_score')),
            'min_score': safe_float(s.get('min_score')),
            'max_score': safe_float(s.get('max_score')),
            'distribution': {'excellent': safe_int(s.get('excellent')),
                             'good': safe_int(s.get('good')),
                             'average': safe_int(s.get('average')),
                             'needs_work': safe_int(s.get('needs_work'))}}})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/qc/evaluations')
def qc_evaluations():
    """List evaluations. ?agent=&days=30&limit=50"""
    try:
        if not _qc_tables_exist():
            return jsonify_ok({'available': False, 'data': []})
        agent = request.args.get('agent', '')
        days  = int(request.args.get('days', 30))
        limit = int(request.args.get('limit', 50))
        where = "WHERE (qcr.status='ACTIVE' OR qcr.status IS NULL) AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)"
        params = [days]
        if agent:
            where += " AND a.user = %s"
            params.append(agent)
        rows = db.execute_query(f"""
            SELECT qcr.result_id, DATE(qcr.evaluation_date) AS eval_date,
                qcr.total_score, qcr.ai_total_score, qcr.ai_confidence,
                qcr.source, qcr.comments,
                a.user AS agent, u.full_name AS agent_name,
                c.campaign_id, c.length_in_sec
            FROM qc_results qcr
            JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
            LEFT JOIN vicidial_users u ON a.user = u.user
            LEFT JOIN vicidial_closer_log c ON qcr.uniqueid = c.uniqueid
            {where} ORDER BY qcr.evaluation_date DESC LIMIT %s
        """, params + [limit]) or []
        return jsonify_ok({'available': True, 'data': [{'id': r['result_id'],
            'date': str(r['eval_date']), 'agent': r['agent'],
            'agent_name': r.get('agent_name') or r['agent'],
            'campaign': r.get('campaign_id','—'),
            'duration': sec_to_hms(safe_int(r.get('length_in_sec'))),
            'score': safe_float(r['total_score']),
            'ai_score': safe_float(r.get('ai_total_score')) if r.get('ai_total_score') else None,
            'ai_confidence': safe_float(r.get('ai_confidence')),
            'source': r.get('source','Manual'),
            'comments': r.get('comments','')} for r in rows]})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/qc/evaluation/<int:result_id>')
def qc_evaluation_detail(result_id):
    """Full detail for one evaluation including checkpoints."""
    try:
        if not _qc_tables_exist():
            return jsonify_err('QC tables not available', 404)
        header = db.execute_query("""
            SELECT qcr.*, a.user AS agent, u.full_name AS agent_name,
                c.campaign_id, c.phone_number, c.length_in_sec
            FROM qc_results qcr
            JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
            LEFT JOIN vicidial_users u ON a.user = u.user
            LEFT JOIN vicidial_closer_log c ON qcr.uniqueid = c.uniqueid
            WHERE qcr.result_id = %s AND (qcr.status='ACTIVE' OR qcr.status IS NULL)
        """, (result_id,))
        if not header:
            return jsonify_err('Evaluation not found', 404)
        h = header[0]
        checkpoints = db.execute_query("""
            SELECT cp.display_order, cp.checkpoint_text,
                d.score_given, cp.max_points,
                ROUND(d.score_given/cp.max_points*100,1) AS pct
            FROM qc_results_detail d
            JOIN qc_checkpoints cp ON d.checkpoint_id = cp.checkpoint_id
            WHERE d.result_id = %s ORDER BY cp.display_order
        """, (result_id,)) or []
        return jsonify_ok({'data': {
            'id': result_id, 'agent': h['agent'],
            'agent_name': h.get('agent_name') or h['agent'],
            'campaign': h.get('campaign_id','—'),
            'phone': h.get('phone_number','—'),
            'duration': sec_to_hms(safe_int(h.get('length_in_sec'))),
            'date': str(h.get('evaluation_date','')),
            'score': safe_float(h.get('total_score')),
            'ai_score': safe_float(h.get('ai_total_score')) if h.get('ai_total_score') else None,
            'ai_confidence': safe_float(h.get('ai_confidence')),
            'source': h.get('source','Manual'),
            'comments': h.get('comments',''),
            'checkpoints': [{'order': cp['display_order'],
                'text': cp['checkpoint_text'],
                'score': safe_float(cp['score_given']),
                'max': safe_float(cp['max_points']),
                'pct': safe_float(cp['pct'])} for cp in checkpoints]}})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/qc/top-performers')
def qc_top_performers():
    """Top performers by QC score. ?days=30"""
    try:
        if not _qc_tables_exist():
            return jsonify_ok({'available': False, 'data': []})
        days = int(request.args.get('days', 30))
        rows = db.execute_query("""
            SELECT a.user, u.full_name,
                COUNT(*) AS evals,
                ROUND(AVG(qcr.total_score),1) AS avg_score,
                ROUND(STDDEV(qcr.total_score),1) AS stddev,
                MIN(qcr.total_score) AS min_score,
                MAX(qcr.total_score) AS max_score,
                SUM(qcr.source='HYBRID') AS ai_count
            FROM qc_results qcr
            JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
            LEFT JOIN vicidial_users u ON a.user = u.user
            WHERE (qcr.status='ACTIVE' OR qcr.status IS NULL)
              AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY a.user HAVING evals >= 1
            ORDER BY avg_score DESC LIMIT 15
        """, (days,)) or []
        return jsonify_ok({'available': True, 'data': [{'user': r['user'],
            'name': r.get('full_name') or r['user'],
            'evals': safe_int(r['evals']),
            'avg_score': safe_float(r['avg_score']),
            'stddev': safe_float(r['stddev']),
            'min_score': safe_float(r['min_score']),
            'max_score': safe_float(r['max_score']),
            'ai_count': safe_int(r['ai_count'])} for r in rows]})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/qc/coaching')
def qc_coaching():
    """Agents needing coaching (score < 70). ?days=30"""
    try:
        if not _qc_tables_exist():
            return jsonify_ok({'available': False, 'data': []})
        days = int(request.args.get('days', 30))
        rows = db.execute_query("""
            SELECT a.user, u.full_name,
                COUNT(*) AS evals,
                ROUND(AVG(qcr.total_score),1) AS avg_score,
                MIN(qcr.total_score) AS min_score,
                SUM(qcr.total_score < 70) AS below_threshold
            FROM qc_results qcr
            JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
            LEFT JOIN vicidial_users u ON a.user = u.user
            WHERE (qcr.status='ACTIVE' OR qcr.status IS NULL)
              AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY a.user
            HAVING avg_score < 80
            ORDER BY avg_score ASC LIMIT 15
        """, (days,)) or []
        return jsonify_ok({'available': True, 'data': [{'user': r['user'],
            'name': r.get('full_name') or r['user'],
            'evals': safe_int(r['evals']),
            'avg_score': safe_float(r['avg_score']),
            'min_score': safe_float(r['min_score']),
            'below_threshold': safe_int(r['below_threshold'])} for r in rows]})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/qc/add-evaluation', methods=['POST'])
def qc_add_evaluation():
    """Submit a manual QC evaluation."""
    try:
        if not _qc_tables_exist():
            return jsonify_err('QC tables not available', 404)
        body = request.get_json(force=True)
        uniqueid    = body.get('uniqueid','').strip()
        scores      = body.get('scores', {})     # {checkpoint_id: score}
        comments    = body.get('comments','').strip()
        evaluator   = body.get('evaluator','web').strip()

        if not uniqueid or not scores:
            return jsonify_err('uniqueid and scores are required', 400)

        # Check call exists
        call = db.execute_query("SELECT uniqueid FROM vicidial_closer_log WHERE uniqueid=%s LIMIT 1", (uniqueid,))
        if not call:
            return jsonify_err('Call not found in VICIdial', 404)

        # Get checkpoints to calculate total
        checkpoints = db.execute_query("SELECT checkpoint_id, max_points FROM qc_checkpoints") or []
        total_possible = sum(safe_float(cp['max_points']) for cp in checkpoints)
        total_given    = sum(safe_float(scores.get(str(cp['checkpoint_id']), 0)) for cp in checkpoints)
        total_score    = round(total_given / total_possible * 100, 1) if total_possible else 0

        # Insert result header
        db.execute_query("""
            INSERT INTO qc_results (uniqueid, evaluation_date, total_score, source, comments, status)
            VALUES (%s, NOW(), %s, 'MANUAL', %s, 'ACTIVE')
        """, (uniqueid, total_score, comments))

        result_row = db.execute_query("SELECT LAST_INSERT_ID() AS id")
        result_id  = result_row[0]['id'] if result_row else None

        if result_id:
            for cp in checkpoints:
                cid   = cp['checkpoint_id']
                score = safe_float(scores.get(str(cid), 0))
                db.execute_query("""
                    INSERT INTO qc_results_detail (result_id, checkpoint_id, score_given)
                    VALUES (%s, %s, %s)
                """, (result_id, cid, score))

        return jsonify_ok({'result_id': result_id, 'total_score': total_score,
                           'message': f'Evaluation saved — score {total_score}%'})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/qc/checkpoints')
def qc_checkpoints():
    """Return all QC checkpoints for the evaluation form."""
    try:
        if not _qc_tables_exist():
            return jsonify_ok({'available': False, 'data': []})
        rows = db.execute_query("""
            SELECT checkpoint_id, checkpoint_text, max_points, display_order, category
            FROM qc_checkpoints ORDER BY display_order
        """) or []
        return jsonify_ok({'available': True, 'data': [{'id': r['checkpoint_id'],
            'text': r['checkpoint_text'], 'max_points': safe_float(r['max_points']),
            'order': safe_int(r['display_order']),
            'category': r.get('category','')} for r in rows]})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/qc/recent-calls')
def qc_recent_calls():
    """Recent calls available for evaluation. ?agent=&campaign=&limit=30"""
    try:
        agent    = request.args.get('agent','')
        campaign = request.args.get('campaign','')
        limit    = int(request.args.get('limit', 30))
        where = "WHERE c.call_date >= DATE_SUB(NOW(), INTERVAL 7 DAY) AND c.length_in_sec >= 30"
        params = []
        if agent:    where += " AND a.user=%s";         params.append(agent)
        if campaign: where += " AND c.campaign_id=%s";  params.append(campaign)
        # Exclude already-evaluated
        where += " AND c.uniqueid NOT IN (SELECT uniqueid FROM qc_results WHERE status='ACTIVE' OR status IS NULL)"
        rows = db.execute_query(f"""
            SELECT c.uniqueid, c.call_date, c.campaign_id, c.length_in_sec,
                a.user, u.full_name
            FROM vicidial_closer_log c
            LEFT JOIN vicidial_agent_log a ON c.uniqueid = a.uniqueid
            LEFT JOIN vicidial_users u ON a.user = u.user
            {where} ORDER BY c.call_date DESC LIMIT %s
        """, params + [limit]) or []
        return jsonify_ok({'data': [{'uniqueid': r['uniqueid'],
            'date': str(r['call_date']), 'campaign': r.get('campaign_id',''),
            'duration': sec_to_hms(safe_int(r['length_in_sec'])),
            'agent': r.get('user',''), 'agent_name': r.get('full_name','') or r.get('user','')} for r in rows]})
    except Exception as e:
        return jsonify_err(e)

@app.route('/api/qc/score-trend')
def qc_score_trend():
    """Daily average QC score trend. ?days=30"""
    try:
        if not _qc_tables_exist():
            return jsonify_ok({'available': False, 'data': []})
        days = int(request.args.get('days', 30))
        rows = db.execute_query("""
            SELECT DATE(qcr.evaluation_date) AS d,
                ROUND(AVG(qcr.total_score),1) AS avg_score,
                COUNT(*) AS evals
            FROM qc_results qcr
            WHERE (qcr.status='ACTIVE' OR qcr.status IS NULL)
              AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY DATE(qcr.evaluation_date) ORDER BY d
        """, (days,)) or []
        return jsonify_ok({'available': True, 'data': [{'date': str(r['d']),
            'avg_score': safe_float(r['avg_score']),
            'evals': safe_int(r['evals'])} for r in rows]})
    except Exception as e:
        return jsonify_err(e)

# ──────────────────────────────────────────────────────────────────────────────
# Service Level Analysis API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/service-level/current')
def service_level_current():
    """Current service level per campaign (calls answered within 20s)."""
    try:
        rows = db.execute_query("""
            SELECT campaign_id,
                COUNT(*) AS total_calls,
                SUM(CASE WHEN queue_seconds <= 20 THEN 1 ELSE 0 END) AS answered_in_sla,
                AVG(queue_seconds) AS avg_wait_sec,
                SUM(CASE WHEN status='DROP' THEN 1 ELSE 0 END) AS abandoned
            FROM vicidial_log
            WHERE call_date >= CURDATE() AND queue_seconds IS NOT NULL
            GROUP BY campaign_id ORDER BY campaign_id
        """) or []
        result = []
        for r in rows:
            total = safe_int(r['total_calls'])
            in_sla = safe_int(r['answered_in_sla'])
            sl_pct = round(in_sla / total * 100, 1) if total else 0
            result.append({
                'campaign': r['campaign_id'],
                'total': total,
                'in_sla': in_sla,
                'sl_pct': sl_pct,
                'avg_wait': round(safe_float(r['avg_wait_sec']), 1),
                'abandoned': safe_int(r['abandoned']),
                'status': 'good' if sl_pct >= 80 else ('warning' if sl_pct >= 60 else 'critical')
            })
        return jsonify_ok({'data': result, 'target_pct': 80, 'sla_threshold_sec': 20})
    except Exception as e:
        return jsonify_err(e)


@app.route('/api/service-level/trend')
def service_level_trend():
    """Daily service level trend. ?days=7"""
    try:
        days = int(request.args.get('days', 7))
        rows = db.execute_query("""
            SELECT DATE(call_date) AS call_day,
                COUNT(*) AS total_calls,
                SUM(CASE WHEN queue_seconds <= 20 THEN 1 ELSE 0 END) AS answered_in_sla,
                AVG(queue_seconds) AS avg_wait_sec
            FROM vicidial_log
            WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
              AND queue_seconds IS NOT NULL
            GROUP BY DATE(call_date) ORDER BY call_day DESC
        """, (days,)) or []
        result = []
        for r in rows:
            total = safe_int(r['total_calls'])
            in_sla = safe_int(r['answered_in_sla'])
            sl_pct = round(in_sla / total * 100, 1) if total else 0
            result.append({
                'date': str(r['call_day']),
                'total': total,
                'in_sla': in_sla,
                'sl_pct': sl_pct,
                'avg_wait': round(safe_float(r['avg_wait_sec']), 1)
            })
        return jsonify_ok({'data': result, 'days': days})
    except Exception as e:
        return jsonify_err(e)


@app.route('/api/service-level/hourly')
def service_level_hourly():
    """Hourly service level breakdown for today."""
    try:
        rows = db.execute_query("""
            SELECT HOUR(call_date) AS hour_of_day,
                COUNT(*) AS total_calls,
                SUM(CASE WHEN queue_seconds <= 20 THEN 1 ELSE 0 END) AS answered_in_sla,
                AVG(queue_seconds) AS avg_wait_sec
            FROM vicidial_log
            WHERE call_date >= CURDATE() AND queue_seconds IS NOT NULL
            GROUP BY HOUR(call_date) ORDER BY hour_of_day
        """) or []
        result = []
        for r in rows:
            total = safe_int(r['total_calls'])
            in_sla = safe_int(r['answered_in_sla'])
            sl_pct = round(in_sla / total * 100, 1) if total else 0
            h = safe_int(r['hour_of_day'])
            result.append({
                'hour': h,
                'label': f"{h:02d}:00",
                'total': total,
                'in_sla': in_sla,
                'sl_pct': sl_pct,
                'avg_wait': round(safe_float(r['avg_wait_sec']), 1)
            })
        return jsonify_ok({'data': result})
    except Exception as e:
        return jsonify_err(e)


@app.route('/api/service-level/breaches')
def service_level_breaches():
    """Campaigns that breached SLA (<80%) in the last 7 days."""
    try:
        rows = db.execute_query("""
            SELECT campaign_id, DATE(call_date) AS call_day,
                COUNT(*) AS total_calls,
                SUM(CASE WHEN queue_seconds <= 20 THEN 1 ELSE 0 END) AS answered_in_sla,
                AVG(queue_seconds) AS avg_wait_sec,
                MAX(queue_seconds) AS max_wait_sec
            FROM vicidial_log
            WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
              AND queue_seconds IS NOT NULL
            GROUP BY campaign_id, DATE(call_date)
            HAVING (answered_in_sla / total_calls * 100) < 80
            ORDER BY call_day DESC, campaign_id
        """) or []
        result = []
        for r in rows:
            total = safe_int(r['total_calls'])
            in_sla = safe_int(r['answered_in_sla'])
            sl_pct = round(in_sla / total * 100, 1) if total else 0
            result.append({
                'date': str(r['call_day']),
                'campaign': r['campaign_id'],
                'total': total,
                'sl_pct': sl_pct,
                'avg_wait': round(safe_float(r['avg_wait_sec']), 1),
                'max_wait': round(safe_float(r['max_wait_sec']), 1)
            })
        return jsonify_ok({'data': result, 'count': len(result)})
    except Exception as e:
        return jsonify_err(e)


# ──────────────────────────────────────────────────────────────────────────────
# DID Inspector API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/dids/list')
def dids_list():
    """All DIDs with rich metadata and 30-day call stats."""
    try:
        days = int(request.args.get('days', 30))
        rows = db.execute_query(f"""
            SELECT d.did_id, d.did_pattern AS did_number, d.did_active,
                   d.group_id, d.did_description, d.did_carrier_description,
                   d.did_route, d.campaign_id, d.user_group, d.modify_stamp,
                   COUNT(l.call_date)     AS calls_period,
                   MAX(l.call_date)       AS last_call,
                   AVG(l.length_in_sec)   AS avg_duration_sec,
                   SUM(l.length_in_sec)   AS total_talk_sec
            FROM vicidial_inbound_dids d
            LEFT JOIN vicidial_closer_log l
                ON l.phone_number LIKE CONCAT('%%', d.did_pattern, '%%')
               AND l.call_date >= DATE_SUB(NOW(), INTERVAL {days} DAY)
            GROUP BY d.did_id
            ORDER BY calls_period DESC, d.did_pattern
        """) or []
        result = []
        for r in rows:
            last = r['last_call']
            result.append({
                'did_id':       r['did_id'],
                'did':          r.get('did_number', ''),
                'active':       r.get('did_active', 'N'),
                'group':        r.get('group_id', '') or '',
                'description':  r.get('did_description', '') or '',
                'carrier':      r.get('did_carrier_description', '') or '',
                'route':        r.get('did_route', '') or '',
                'campaign':     r.get('campaign_id', '') or '',
                'user_group':   r.get('user_group', '') or '',
                'modified':     r['modify_stamp'].strftime('%Y-%m-%d') if r.get('modify_stamp') else '',
                'calls_period': safe_int(r['calls_period']),
                'last_call':    last.strftime('%Y-%m-%d %H:%M') if last else 'Never',
                'avg_talk':     round(safe_float(r['avg_duration_sec']), 0),
                'total_talk_min': round(safe_float(r['total_talk_sec']) / 60, 1),
            })
        return jsonify_ok({'data': result, 'total': len(result), 'days': days,
                           'active':   sum(1 for r in result if r['active'] == 'Y'),
                           'inactive': sum(1 for r in result if r['active'] != 'Y')})
    except Exception as e:
        return jsonify_err(e)


@app.route('/api/dids/problematic')
def dids_problematic():
    """DIDs that are inactive or have zero calls in the last 30 days."""
    try:
        rows = db.execute_query("""
            SELECT d.did_id, d.did_pattern AS did_number, d.did_active,
                   d.group_id, d.did_description,
                   COUNT(l.call_date) AS calls_30d
            FROM vicidial_inbound_dids d
            LEFT JOIN vicidial_closer_log l
                ON l.phone_number LIKE CONCAT('%%', d.did_pattern, '%%')
               AND l.call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY d.did_id
            HAVING d.did_active != 'Y' OR calls_30d = 0
            ORDER BY d.did_active DESC, calls_30d ASC
        """) or []
        result = [{'did_id': r['did_id'], 'did': r.get('did_number',''),
                   'active': r.get('did_active','N'), 'group': r.get('group_id',''),
                   'description': r.get('did_description',''),
                   'calls_30d': safe_int(r['calls_30d']),
                   'issue': 'Inactive' if r.get('did_active') != 'Y' else 'No recent calls'
                  } for r in rows]
        return jsonify_ok({'data': result, 'count': len(result)})
    except Exception as e:
        return jsonify_err(e)


@app.route('/api/dids/search')
def dids_search():
    """Search DIDs by number or description. ?q=<term>"""
    try:
        q = request.args.get('q', '').strip()
        if not q:
            return jsonify_err('q parameter required', 400)
        rows = db.execute_query("""
            SELECT did_id, did_pattern AS did_number, did_active,
                   group_id, did_description
            FROM vicidial_inbound_dids
            WHERE did_pattern LIKE %s OR did_description LIKE %s
            ORDER BY did_pattern LIMIT 50
        """, (f'%{q}%', f'%{q}%')) or []
        return jsonify_ok({'data': [{'did_id': r['did_id'], 'did': r['did_number'],
                                     'active': r.get('did_active',''), 'group': r.get('group_id',''),
                                     'description': r.get('did_description','')} for r in rows],
                           'query': q})
    except Exception as e:
        return jsonify_err(e)


# ──────────────────────────────────────────────────────────────────────────────
# Anomaly Detection API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/anomaly/detect')
def anomaly_detect():
    """Detect anomalies: abandon rate spikes, call volume drops, agent idle time. ?hours=1"""
    try:
        hours = int(request.args.get('hours', 1))
        anomalies = []

        # Abandon rate spike vs. 7-day average
        ab_row = db.execute_query("""
            SELECT
                (SELECT SUM(term_reason IN ('ABANDON','QUEUETIMEOUT')) / COUNT(*) * 100
                 FROM vicidial_closer_log
                 WHERE call_date >= DATE_SUB(NOW(), INTERVAL %s HOUR)) AS current_abd,
                (SELECT SUM(term_reason IN ('ABANDON','QUEUETIMEOUT')) / COUNT(*) * 100
                 FROM vicidial_closer_log
                 WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                   AND call_date < CURDATE()) AS baseline_abd
        """, (hours,)) or [{}]
        ab = ab_row[0]
        cur_abd = safe_float(ab.get('current_abd'))
        base_abd = safe_float(ab.get('baseline_abd'))
        if base_abd > 0 and cur_abd > base_abd * 1.5 and cur_abd > 10:
            anomalies.append({'type': 'abandon_spike', 'severity': 'critical',
                               'message': f"Abandon rate {cur_abd:.1f}% vs {base_abd:.1f}% baseline (last {hours}h)",
                               'current': cur_abd, 'baseline': base_abd})

        # Call volume drop vs. same hour yesterday
        vol_row = db.execute_query("""
            SELECT
                (SELECT COUNT(*) FROM vicidial_closer_log
                 WHERE call_date >= DATE_SUB(NOW(), INTERVAL %s HOUR)) AS current_vol,
                (SELECT COUNT(*) FROM vicidial_closer_log
                 WHERE call_date >= DATE_SUB(DATE_SUB(NOW(), INTERVAL 1 DAY), INTERVAL %s HOUR)
                   AND call_date <  DATE_SUB(NOW(), INTERVAL 1 DAY)) AS yesterday_vol
        """, (hours, hours)) or [{}]
        vr = vol_row[0]
        cur_vol = safe_int(vr.get('current_vol'))
        yest_vol = safe_int(vr.get('yesterday_vol'))
        if yest_vol > 0 and cur_vol < yest_vol * 0.5:
            anomalies.append({'type': 'volume_drop', 'severity': 'warning',
                               'message': f"Call volume {cur_vol} vs {yest_vol} same period yesterday",
                               'current': cur_vol, 'baseline': yest_vol})

        # Agents idle too long (READY > 30 min)
        idle_rows = db.execute_query("""
            SELECT user, campaign_id,
                   TIMESTAMPDIFF(MINUTE, last_state_change, NOW()) AS idle_min
            FROM vicidial_live_agents
            WHERE status='READY'
              AND TIMESTAMPDIFF(MINUTE, last_state_change, NOW()) > 30
            ORDER BY idle_min DESC LIMIT 5
        """) or []
        if idle_rows:
            names = [f"{r['user']} ({safe_int(r['idle_min'])}m)" for r in idle_rows]
            anomalies.append({'type': 'agent_idle', 'severity': 'warning',
                               'message': f"{len(idle_rows)} agent(s) idle >30 min: {', '.join(names)}",
                               'agents': [{'user': r['user'], 'campaign': r.get('campaign_id',''),
                                           'idle_min': safe_int(r['idle_min'])} for r in idle_rows]})

        # Long queue wait (any call waiting > 3 min)
        long_wait = db.execute_query("""
            SELECT campaign_id,
                   COUNT(*) AS calls,
                   MAX(queue_seconds) AS max_wait
            FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(NOW(), INTERVAL 10 MINUTE)
              AND length_in_sec = 0 AND queue_seconds > 180
            GROUP BY campaign_id ORDER BY max_wait DESC LIMIT 5
        """) or []
        for lw in long_wait:
            anomalies.append({'type': 'long_queue', 'severity': 'critical',
                               'message': f"{lw['calls']} call(s) waited >{safe_int(lw['max_wait'])}s in {lw['campaign_id']}",
                               'campaign': lw['campaign_id'], 'max_wait': safe_int(lw['max_wait'])})

        return jsonify_ok({'anomalies': anomalies, 'count': len(anomalies),
                           'checked_at': datetime.now().isoformat(), 'window_hours': hours})
    except Exception as e:
        return jsonify_err(e)


# ──────────────────────────────────────────────────────────────────────────────
# Predictive Analytics / Forecast API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/forecast/volume')
def forecast_volume():
    """Simple call volume forecast based on 30-day rolling average. ?days_ahead=7"""
    try:
        days_ahead = int(request.args.get('days_ahead', 7))

        # Get 30-day historical by day-of-week
        hist = db.execute_query("""
            SELECT DAYOFWEEK(call_date) AS dow,
                   DAYNAME(call_date) AS day_name,
                   AVG(daily_count) AS avg_calls,
                   STDDEV(daily_count) AS stddev_calls
            FROM (
                SELECT DATE(call_date) AS d,
                       DAYOFWEEK(call_date) AS dow,
                       DAYNAME(call_date) AS day_name,
                       COUNT(*) AS daily_count
                FROM vicidial_closer_log
                WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                  AND call_date < CURDATE()
                GROUP BY DATE(call_date)
            ) daily
            GROUP BY DAYOFWEEK(call_date), DAYNAME(call_date)
            ORDER BY dow
        """) or []

        dow_avg = {safe_int(r['dow']): {'name': r['day_name'],
                                         'avg': round(safe_float(r['avg_calls'])),
                                         'stddev': round(safe_float(r['stddev_calls']))} for r in hist}

        forecast = []
        for i in range(1, days_ahead + 1):
            fdate = (datetime.now() + timedelta(days=i)).date()
            dow = fdate.isoweekday() % 7 + 1  # MySQL DAYOFWEEK: 1=Sun
            data = dow_avg.get(dow, {'name': fdate.strftime('%A'), 'avg': 0, 'stddev': 0})
            forecast.append({
                'date': str(fdate),
                'day': data['name'][:3],
                'predicted_calls': data['avg'],
                'low': max(0, data['avg'] - data['stddev']),
                'high': data['avg'] + data['stddev'],
                'recommended_agents': max(1, round(data['avg'] / 60)) if data['avg'] else 1
            })

        # Historical actuals (last 7 days) for chart context
        actuals = db.execute_query("""
            SELECT DATE(call_date) AS d, COUNT(*) AS calls
            FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
              AND call_date < CURDATE()
            GROUP BY DATE(call_date) ORDER BY d
        """) or []

        return jsonify_ok({
            'forecast': forecast,
            'actuals': [{'date': str(r['d']), 'calls': safe_int(r['calls'])} for r in actuals],
            'model': 'day-of-week average (30-day window)',
            'days_ahead': days_ahead
        })
    except Exception as e:
        return jsonify_err(e)


@app.route('/api/forecast/staffing')
def forecast_staffing():
    """Recommended staffing by hour based on today's call pattern."""
    try:
        campaign = request.args.get('campaign', '')
        camp_filter = " AND campaign_id=%s" if campaign else ""
        camp_params = [campaign] if campaign else []

        rows = db.execute_query(
            "SELECT HOUR(call_date) AS h,"
            " AVG(hourly_count) AS avg_calls"
            " FROM ("
            "   SELECT DATE(call_date) AS d, HOUR(call_date) AS h,"
            "          COUNT(*) AS hourly_count"
            "   FROM vicidial_closer_log"
            "   WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)"
            "     AND call_date < CURDATE()" + camp_filter +
            "   GROUP BY DATE(call_date), HOUR(call_date)"
            " ) hourly"
            " GROUP BY HOUR ORDER BY h",
            camp_params
        ) or []

        result = []
        for r in rows:
            avg = safe_float(r['avg_calls'])
            result.append({
                'hour': safe_int(r['h']),
                'label': f"{safe_int(r['h']):02d}:00",
                'avg_calls': round(avg),
                'recommended_agents': max(1, round(avg / 45))
            })
        return jsonify_ok({'data': result, 'campaign': campaign or 'all',
                           'note': '1 agent per 45 calls/hr baseline'})
    except Exception as e:
        return jsonify_err(e)


# ──────────────────────────────────────────────────────────────────────────────
# Schedule Management API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/schedule/agents')
def schedule_agents():
    """Agent schedules and today's login adherence."""
    try:
        # Actual login windows today from agent log
        rows = db.execute_query("""
            SELECT al.user, u.full_name,
                   MIN(al.event_time) AS first_login,
                   MAX(al.event_time) AS last_activity,
                   SUM(al.talk_sec)   AS total_talk,
                   COUNT(DISTINCT DATE(al.event_time)) AS days_active_week,
                   SUM(al.status='INCALL') AS incall_events
            FROM vicidial_agent_log al
            LEFT JOIN vicidial_users u ON al.user=u.user
            WHERE al.event_time >= CURDATE()
            GROUP BY al.user ORDER BY first_login
        """) or []

        result = []
        for r in rows:
            fl = r['first_login']
            ll = r['last_activity']
            result.append({
                'user': r['user'],
                'name': r.get('full_name') or r['user'],
                'first_login': str(fl) if fl else None,
                'last_activity': str(ll) if ll else None,
                'total_talk': sec_to_hms(safe_int(r['total_talk'])),
                'total_talk_sec': safe_int(r['total_talk']),
                'incall_events': safe_int(r['incall_events'])
            })

        return jsonify_ok({'data': result, 'date': str(datetime.now().date()), 'total': len(result)})
    except Exception as e:
        return jsonify_err(e)


@app.route('/api/schedule/adherence')
def schedule_adherence():
    """Login adherence: actual vs expected hours per agent this week."""
    try:
        rows = db.execute_query("""
            SELECT al.user, u.full_name,
                   DATE(al.event_time) AS work_date,
                   MIN(TIME(al.event_time)) AS clock_in,
                   MAX(TIME(al.event_time)) AS clock_out,
                   SUM(al.talk_sec + COALESCE(al.wait_sec,0)) AS active_sec
            FROM vicidial_agent_log al
            LEFT JOIN vicidial_users u ON al.user=u.user
            WHERE al.event_time >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
            GROUP BY al.user, DATE(al.event_time)
            ORDER BY work_date DESC, al.user
        """) or []

        result = []
        for r in rows:
            active_sec = safe_int(r['active_sec'])
            active_hrs = round(active_sec / 3600, 2)
            result.append({
                'user': r['user'],
                'name': r.get('full_name') or r['user'],
                'date': str(r['work_date']),
                'clock_in': str(r['clock_in']) if r.get('clock_in') else None,
                'clock_out': str(r['clock_out']) if r.get('clock_out') else None,
                'active_hours': active_hrs,
                'active_time': sec_to_hms(active_sec)
            })
        return jsonify_ok({'data': result})
    except Exception as e:
        return jsonify_err(e)


# ──────────────────────────────────────────────────────────────────────────────
# Agent Behavior Alerts API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/agent-behavior/alerts')
def agent_behavior_alerts():
    """Flag agents with unusual behavior: excessive pause, low call rate, long calls."""
    try:
        behavior_alerts = []

        # Excessive pause (paused > 30 min continuously)
        pause_rows = db.execute_query("""
            SELECT l.user, u.full_name, l.campaign_id,
                   TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) AS pause_min
            FROM vicidial_live_agents l
            LEFT JOIN vicidial_users u ON l.user=u.user
            WHERE l.status='PAUSE'
              AND TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) > 30
            ORDER BY pause_min DESC
        """) or []
        for r in pause_rows:
            behavior_alerts.append({
                'type': 'excessive_pause', 'severity': 'warning',
                'user': r['user'], 'name': r.get('full_name') or r['user'],
                'campaign': r.get('campaign_id', ''),
                'message': f"Paused for {safe_int(r['pause_min'])} min",
                'value': safe_int(r['pause_min'])
            })

        # Low call rate: fewer than 5 calls in last 2 hours (while logged in)
        low_call_rows = db.execute_query("""
            SELECT al.user, u.full_name, COUNT(*) AS calls_2h
            FROM vicidial_agent_log al
            LEFT JOIN vicidial_users u ON al.user=u.user
            WHERE al.event_time >= DATE_SUB(NOW(), INTERVAL 2 HOUR)
            GROUP BY al.user
            HAVING calls_2h < 5
              AND al.user IN (
                  SELECT user FROM vicidial_live_agents
                  WHERE status IN ('READY','INCALL','PAUSE')
              )
        """) or []
        for r in low_call_rows:
            behavior_alerts.append({
                'type': 'low_call_rate', 'severity': 'info',
                'user': r['user'], 'name': r.get('full_name') or r['user'],
                'campaign': '',
                'message': f"Only {safe_int(r['calls_2h'])} calls in last 2 hours",
                'value': safe_int(r['calls_2h'])
            })

        # Abnormally long call (> 30 min INCALL)
        long_call_rows = db.execute_query("""
            SELECT l.user, u.full_name, l.campaign_id,
                   TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) AS call_min
            FROM vicidial_live_agents l
            LEFT JOIN vicidial_users u ON l.user=u.user
            WHERE l.status='INCALL'
              AND TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) > 30
            ORDER BY call_min DESC
        """) or []
        for r in long_call_rows:
            behavior_alerts.append({
                'type': 'long_call', 'severity': 'warning',
                'user': r['user'], 'name': r.get('full_name') or r['user'],
                'campaign': r.get('campaign_id', ''),
                'message': f"On call for {safe_int(r['call_min'])} min",
                'value': safe_int(r['call_min'])
            })

        return jsonify_ok({'alerts': behavior_alerts, 'count': len(behavior_alerts),
                           'checked_at': datetime.now().isoformat()})
    except Exception as e:
        return jsonify_err(e)


# ──────────────────────────────────────────────────────────────────────────────
# QC — SOP Compliance & Calibration (missing from existing QC block)
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/qc/sop-compliance')
def qc_sop_compliance():
    """Average score per checkpoint across all evaluations. ?days=30"""
    try:
        if not _qc_tables_exist():
            return jsonify_ok({'available': False, 'data': []})
        days = int(request.args.get('days', 30))
        rows = db.execute_query("""
            SELECT cp.display_order, cp.checkpoint_text, cp.max_points,
                   ROUND(AVG(d.score_given), 1) AS avg_score,
                   ROUND(AVG(d.score_given) / cp.max_points * 100, 1) AS avg_pct,
                   COUNT(*) AS eval_count
            FROM qc_results_detail d
            JOIN qc_checkpoints cp ON d.checkpoint_id = cp.checkpoint_id
            JOIN qc_results qcr ON d.result_id = qcr.result_id
            WHERE (qcr.status='ACTIVE' OR qcr.status IS NULL)
              AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY cp.checkpoint_id ORDER BY cp.display_order
        """, (days,)) or []

        result = []
        for r in rows:
            pct = safe_float(r['avg_pct'])
            result.append({
                'order': safe_int(r['display_order']),
                'checkpoint': r['checkpoint_text'],
                'max_points': safe_float(r['max_points']),
                'avg_score': safe_float(r['avg_score']),
                'avg_pct': pct,
                'evals': safe_int(r['eval_count']),
                'status': 'good' if pct >= 80 else ('review' if pct >= 60 else 'needs_training')
            })
        return jsonify_ok({'available': True, 'data': result, 'days': days})
    except Exception as e:
        return jsonify_err(e)


@app.route('/api/qc/calibration')
def qc_calibration():
    """AI vs QA score comparison per checkpoint. ?days=30"""
    try:
        if not _qc_tables_exist():
            return jsonify_ok({'available': False, 'data': []})
        days = int(request.args.get('days', 30))

        # Overall calibration
        overall = db.execute_query("""
            SELECT ROUND(AVG(qcr.total_score), 1) AS avg_qa_score,
                   ROUND(AVG(qcr.ai_total_score), 1) AS avg_ai_score,
                   ROUND(AVG(ABS(qcr.total_score - qcr.ai_total_score)), 1) AS avg_diff,
                   COUNT(*) AS total_evals,
                   SUM(ABS(qcr.total_score - qcr.ai_total_score) <= 5) AS well_aligned,
                   SUM(ABS(qcr.total_score - qcr.ai_total_score) > 10) AS needs_calibration
            FROM qc_results qcr
            WHERE qcr.ai_total_score IS NOT NULL
              AND (qcr.status='ACTIVE' OR qcr.status IS NULL)
              AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        """, (days,)) or [{}]
        ov = overall[0]

        # Per-agent calibration
        agents = db.execute_query("""
            SELECT a.user, u.full_name,
                   COUNT(*) AS evals,
                   ROUND(AVG(qcr.total_score), 1) AS qa_avg,
                   ROUND(AVG(qcr.ai_total_score), 1) AS ai_avg,
                   ROUND(AVG(qcr.total_score - qcr.ai_total_score), 1) AS avg_diff
            FROM qc_results qcr
            JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
            LEFT JOIN vicidial_users u ON a.user = u.user
            WHERE qcr.ai_total_score IS NOT NULL
              AND (qcr.status='ACTIVE' OR qcr.status IS NULL)
              AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY a.user HAVING evals >= 2
            ORDER BY ABS(avg_diff) DESC LIMIT 20
        """, (days,)) or []

        return jsonify_ok({
            'available': True,
            'days': days,
            'overall': {
                'avg_qa': safe_float(ov.get('avg_qa_score')),
                'avg_ai': safe_float(ov.get('avg_ai_score')),
                'avg_diff': safe_float(ov.get('avg_diff')),
                'total_evals': safe_int(ov.get('total_evals')),
                'well_aligned': safe_int(ov.get('well_aligned')),
                'needs_calibration': safe_int(ov.get('needs_calibration'))
            },
            'by_agent': [{'user': r['user'],
                          'name': r.get('full_name') or r['user'],
                          'evals': safe_int(r['evals']),
                          'qa_avg': safe_float(r['qa_avg']),
                          'ai_avg': safe_float(r['ai_avg']),
                          'avg_diff': safe_float(r['avg_diff']),
                          'status': 'good' if abs(safe_float(r['avg_diff'])) <= 5
                                    else ('monitor' if abs(safe_float(r['avg_diff'])) <= 10
                                          else 'needs_calibration')} for r in agents]
        })
    except Exception as e:
        return jsonify_err(e)


# ──────────────────────────────────────────────────────────────────────────────
# Campaign Detail (daily breakdown) API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/campaigns/detail')
def campaign_detail():
    """Daily breakdown for a single campaign (UNION inbound+outbound). ?campaign=X&days=30&time_start=06:00&time_end=18:00"""
    try:
        campaign   = request.args.get('campaign', '').strip()
        days       = int(request.args.get('days', 30))
        time_start = request.args.get('time_start', '').strip()
        time_end   = request.args.get('time_end', '').strip()
        tz_offset  = int(request.args.get('tz_offset', 0))
        if not campaign:
            return jsonify_err('campaign parameter required', 400)

        def hms(sec):
            sec = int(sec or 0)
            return f"{sec//3600}:{(sec%3600)//60:02d}:{sec%60:02d}"

        def _ts():
            if tz_offset:
                return f"DATE_ADD(call_date, INTERVAL {tz_offset} HOUR)"
            return "call_date"

        def _to_mins(t):
            parts = t.split(':')
            return int(parts[0]) * 60 + int(parts[1])

        def extra_time(params):
            ts = _ts()
            clauses = []
            if time_start:
                params.append(_to_mins(time_start))
                clauses.append(f"(HOUR({ts})*60+MINUTE({ts})) >= %s")
            if time_end:
                params.append(_to_mins(time_end))
                clauses.append(f"(HOUR({ts})*60+MINUTE({ts})) <= %s")
            return (' AND ' + ' AND '.join(clauses)) if clauses else ''

        if days == 0:
            date_filter_sql = "DATE(call_date) = CURDATE()"
            p1 = [campaign]
            p2 = [campaign]
        else:
            date_filter_sql = "call_date >= DATE_SUB(NOW(), INTERVAL %s DAY)"
            p1 = [campaign, days]
            p2 = [campaign, days]
        t1, t2 = extra_time(p1), extra_time(p2)

        union_query = f"""
            SELECT
                call_day,
                SUM(total_calls)    AS total_calls,
                SUM(answered)       AS answered,
                SUM(abandoned)      AS abandoned,
                SUM(answered_talk)  AS answered_talk,
                SUM(answered_cnt)   AS answered_cnt,
                SUM(total_talk_sec) AS total_talk_sec,
                AVG(avg_queue)      AS avg_queue
            FROM (
                SELECT
                    DATE(call_date)  AS call_day,
                    COUNT(*)         AS total_calls,
                    SUM(CASE WHEN length_in_sec >= 5
                              AND term_reason NOT IN ('ABANDON','QUEUETIMEOUT','NOAGENT')
                              AND NOT (length_in_sec = 0 AND queue_seconds > 0)
                             THEN 1 ELSE 0 END) AS answered,
                    SUM(CASE WHEN term_reason IN ('ABANDON','QUEUETIMEOUT','NOAGENT')
                             OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) AS abandoned,
                    SUM(CASE WHEN length_in_sec >= 5
                              AND term_reason NOT IN ('ABANDON','QUEUETIMEOUT','NOAGENT')
                             THEN length_in_sec ELSE 0 END) AS answered_talk,
                    SUM(CASE WHEN length_in_sec >= 5
                              AND term_reason NOT IN ('ABANDON','QUEUETIMEOUT','NOAGENT')
                             THEN 1 ELSE 0 END) AS answered_cnt,
                    SUM(length_in_sec) AS total_talk_sec,
                    AVG(queue_seconds) AS avg_queue
                FROM vicidial_closer_log
                WHERE campaign_id = %s AND {date_filter_sql}{t1}
                GROUP BY DATE(call_date)

                UNION ALL

                SELECT
                    DATE(call_date)  AS call_day,
                    COUNT(*)         AS total_calls,
                    SUM(CASE WHEN status NOT IN ('DROP','ABAND','AFAIL','QUEUETIMEOUT') AND length_in_sec >= 5 THEN 1 ELSE 0 END) AS answered,
                    SUM(CASE WHEN status IN ('DROP','ABAND','AFAIL','QUEUETIMEOUT') THEN 1 ELSE 0 END) AS abandoned,
                    SUM(CASE WHEN length_in_sec >= 5 THEN length_in_sec ELSE 0 END) AS answered_talk,
                    SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS answered_cnt,
                    SUM(length_in_sec) AS total_talk_sec,
                    0                  AS avg_queue
                FROM vicidial_log
                WHERE campaign_id = %s AND {date_filter_sql}{t2}
                GROUP BY DATE(call_date)
            ) combined
            GROUP BY call_day
            ORDER BY call_day DESC
        """
        rows = db.execute_query(union_query, p1 + p2) or []

        data = []
        for r in rows:
            c = safe_int(r['total_calls'])
            a = safe_int(r['answered'])
            b = safe_int(r['abandoned'])
            avg_talk_sec = (safe_float(r['answered_talk']) / safe_float(r['answered_cnt'])
                           ) if safe_float(r['answered_cnt']) else 0
            data.append({
                'call_date':      str(r['call_day']),
                'total_calls':    c,
                'answered':       a,
                'abandoned':      b,
                'answer_rate':    round(a / c * 100, 1) if c else 0,
                'abandon_rate':   round(b / c * 100, 1) if c else 0,
                'avg_talk':       hms(avg_talk_sec),
                'talk_time_mins': round(safe_float(r['total_talk_sec']) / 60, 1),
                'avg_queue':      round(safe_float(r['avg_queue']), 1),
            })
        return jsonify_ok({'data': data, 'campaign': campaign, 'days': days})
    except Exception as e:
        return jsonify_err(str(e))


# Campaign Individual Calls API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/campaigns/calls')
def campaign_calls():
    """Individual call records for a campaign.
    ?campaign=X&days=0&limit=500&time_start=09:00&time_end=18:00
    Returns calls tagged: within_hours | before_hours | after_hours
    """
    try:
        campaign   = request.args.get('campaign', '').strip()
        days       = int(request.args.get('days', 0))
        limit      = int(request.args.get('limit', 500))
        time_start = request.args.get('time_start', '').strip()   # 'HH:MM'
        time_end   = request.args.get('time_end',   '').strip()
        if not campaign:
            return jsonify_err('campaign parameter required', 400)

        if days == 0:
            date_clause = "DATE(call_date) = CURDATE()"
        else:
            date_clause = "call_date >= DATE_SUB(NOW(), INTERVAL %s DAY)"

        def make_params(base):
            return base + ([days] if days != 0 else [])

        q1 = f"""
            SELECT call_date, user AS agent, length_in_sec, queue_seconds,
                   term_reason AS disposition, 'inbound' AS direction
            FROM vicidial_closer_log
            WHERE campaign_id = %s AND {date_clause}
            ORDER BY call_date DESC LIMIT {limit}
        """
        q2 = f"""
            SELECT call_date, user AS agent, length_in_sec,
                   0 AS queue_seconds, status AS disposition, 'outbound' AS direction
            FROM vicidial_log
            WHERE campaign_id = %s AND {date_clause}
            ORDER BY call_date DESC LIMIT {limit}
        """

        rows1 = db.execute_query(q1, make_params([campaign])) or []
        rows2 = db.execute_query(q2, make_params([campaign])) or []

        def time_zone(call_dt_str):
            """Return 'before_hours'|'within_hours'|'after_hours' based on HH:MM."""
            if not time_start and not time_end:
                return 'within_hours'
            try:
                hhmm = str(call_dt_str)[11:16]   # '2026-06-15 08:07:35' → '08:07'
                if time_start and hhmm < time_start:
                    return 'before_hours'
                if time_end and hhmm > time_end:
                    return 'after_hours'
            except Exception:
                pass
            return 'within_hours'

        def fmt_row(r):
            sec = int(r['length_in_sec'] or 0)
            qs  = int(r['queue_seconds'] or 0)
            t   = str(r['call_date'])
            return {
                'time':         t,
                'agent':        r['agent'] or '',
                'duration':     f"{sec//60}:{sec%60:02d}",
                'duration_sec': sec,
                'queue_sec':    qs,
                'disposition':  r['disposition'] or '',
                'direction':    r['direction'],
                'period':       time_zone(t),   # before_hours | within_hours | after_hours
            }

        all_rows = sorted(
            [fmt_row(r) for r in rows1] + [fmt_row(r) for r in rows2],
            key=lambda x: x['time'], reverse=True
        )[:limit]

        within = [r for r in all_rows if r['period'] == 'within_hours']
        before = [r for r in all_rows if r['period'] == 'before_hours']
        after  = [r for r in all_rows if r['period'] == 'after_hours']

        return jsonify_ok({
            'data':         within,
            'before_hours': before,
            'after_hours':  after,
            'all':          all_rows,
            'campaign':     campaign,
            'total':        len(all_rows),
            'time_start':   time_start or 'any',
            'time_end':     time_end   or 'any',
        })
    except Exception as e:
        return jsonify_err(str(e))


# Campaign Hourly Stats API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/campaigns/hourly')
def campaigns_hourly():
    """Hourly call breakdown for a campaign (defaults to today, all campaigns if no campaign param)."""
    try:
        campaign = request.args.get('campaign', '').strip()
        date_str = request.args.get('date', '').strip()

        where_clauses = ['call_date >= CURDATE()']
        params = []
        if date_str:
            where_clauses = ['DATE(call_date) = %s']
            params = [date_str]
        if campaign:
            where_clauses.append('campaign_id = %s')
            params.append(campaign)

        where = ' AND '.join(where_clauses)
        query = f"""
            SELECT
                HOUR(call_date) AS hour_of_day,
                COUNT(*) AS total_calls,
                SUM(CASE WHEN status NOT IN ('DROP','ABAND','AFAIL') THEN 1 ELSE 0 END) AS answered,
                AVG(length_in_sec) AS avg_handle_time
            FROM vicidial_log
            WHERE {where}
            GROUP BY HOUR(call_date)
            ORDER BY hour_of_day
        """
        rows = db.execute_query(query, params)
        data = []
        for r in (rows or []):
            data.append({
                'hour_of_day': int(r['hour_of_day']),
                'total_calls': int(r['total_calls'] or 0),
                'answered': int(r['answered'] or 0),
                'avg_handle_time': float(r['avg_handle_time'] or 0)
            })
        return jsonify_ok({'data': data})
    except Exception as e:
        return jsonify_err(str(e))


# Campaign Comparison API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/campaigns/compare')
def campaigns_compare():
    """Side-by-side stats for two or more campaigns. ?campaigns=A,B&days=7"""
    try:
        camp_raw = request.args.get('campaigns', '').strip()
        days     = int(request.args.get('days', 7))

        if not camp_raw:
            return jsonify_err('campaigns parameter required (comma-separated)', 400)

        camp_list = [c.strip() for c in camp_raw.split(',') if c.strip()]
        if len(camp_list) < 2:
            return jsonify_err('At least 2 campaigns required for comparison', 400)

        placeholders = ','.join(['%s'] * len(camp_list))
        rows = db.execute_query(
            "SELECT campaign_id,"
            " COUNT(*) AS total,"
            " SUM(CASE WHEN length_in_sec>=5 THEN 1 ELSE 0 END) AS answered,"
            " SUM(CASE WHEN term_reason IN ('ABANDON','QUEUETIMEOUT','NOAGENT') THEN 1 ELSE 0 END) AS abandoned,"
            " AVG(CASE WHEN length_in_sec>=5 THEN length_in_sec END) AS avg_talk,"
            " SUM(length_in_sec) AS total_talk,"
            " AVG(queue_seconds) AS avg_queue,"
            " COUNT(DISTINCT DATE(call_date)) AS active_days"
            " FROM vicidial_closer_log"
            " WHERE call_date >= DATE_SUB(NOW(), INTERVAL %s DAY)"
            "   AND campaign_id IN (" + placeholders + ")"
            " GROUP BY campaign_id ORDER BY total DESC",
            [days] + camp_list
        ) or []

        result = []
        for r in rows:
            total = safe_int(r['total'])
            ans   = safe_int(r['answered'])
            abd   = safe_int(r['abandoned'])
            result.append({
                'campaign_id':   r['campaign_id'],
                'campaign':      r['campaign_id'],
                'total_calls':   total,
                'calls':         total,
                'answered':      ans,
                'abandoned':     abd,
                'answer_rate':   round(ans / total * 100, 1) if total else 0,
                'abandon_rate':  round(abd / total * 100, 1) if total else 0,
                'avg_talk':      sec_to_hms(safe_int(r['avg_talk'])),
                'avg_handle_time': safe_int(r['avg_talk']),
                'talk_time_mins': round(safe_float(r['total_talk']) / 60, 1),
                'last_call':     '—',
                'avg_queue':     round(safe_float(r['avg_queue']), 1),
                'active_days':   safe_int(r['active_days']),
            })
        return jsonify_ok({'data': result, 'campaigns': camp_list, 'days': days})
    except Exception as e:
        return jsonify_err(e)


# ──────────────────────────────────────────────────────────────────────────────
# Week-over-Week Report API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/reports/week-over-week')
def report_week_over_week():
    """Compare current week vs prior week across key metrics."""
    try:
        def _week_stats(start_offset, end_offset):
            rows = db.execute_query("""
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN length_in_sec>=5 THEN 1 ELSE 0 END) AS answered,
                       SUM(CASE WHEN term_reason IN ('ABANDON','QUEUETIMEOUT','NOAGENT') THEN 1 ELSE 0 END) AS abandoned,
                       AVG(CASE WHEN length_in_sec>=5 THEN length_in_sec END) AS avg_talk,
                       SUM(length_in_sec) AS total_talk,
                       COUNT(DISTINCT campaign_id) AS campaigns_active,
                       COUNT(DISTINCT DATE(call_date)) AS active_days
                FROM vicidial_closer_log
                WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND call_date <  DATE_SUB(CURDATE(), INTERVAL %s DAY)
            """, (start_offset, end_offset)) or [{}]
            r = rows[0]
            total = safe_int(r.get('total'))
            ans   = safe_int(r.get('answered'))
            abd   = safe_int(r.get('abandoned'))
            return {
                'total': total,
                'answered': ans,
                'abandoned': abd,
                'answer_rate': round(ans / total * 100, 1) if total else 0,
                'abandon_rate': round(abd / total * 100, 1) if total else 0,
                'avg_talk': sec_to_hms(safe_int(r.get('avg_talk'))),
                'avg_talk_sec': safe_int(r.get('avg_talk')),
                'total_talk': sec_to_hms(safe_int(r.get('total_talk'))),
                'campaigns_active': safe_int(r.get('campaigns_active')),
                'active_days': safe_int(r.get('active_days'))
            }

        current = _week_stats(7, 0)
        prior   = _week_stats(14, 7)

        def _delta(cur, prev, key):
            c, p = cur.get(key, 0), prev.get(key, 0)
            if isinstance(c, str):
                return None
            change = c - p
            pct    = round(change / p * 100, 1) if p else None
            return {'current': c, 'prior': p, 'change': change, 'change_pct': pct,
                    'direction': 'up' if change > 0 else ('down' if change < 0 else 'flat')}

        return jsonify_ok({
            'current_week': current,
            'prior_week':   prior,
            'comparison': {
                'total_calls':    _delta(current, prior, 'total'),
                'answer_rate':    _delta(current, prior, 'answer_rate'),
                'abandon_rate':   _delta(current, prior, 'abandon_rate'),
                'avg_talk_sec':   _delta(current, prior, 'avg_talk_sec'),
            }
        })
    except Exception as e:
        return jsonify_err(e)


# ──────────────────────────────────────────────────────────────────────────────
# Query Monitor API
# ──────────────────────────────────────────────────────────────────────────────

@app.route('/api/query-monitor/status')
def query_monitor_status():
    """DB health check: process list, slow queries, table sizes."""
    try:
        # Active processes
        processes = db.execute_query("SHOW PROCESSLIST") or []
        active = [{'id': p.get('Id'), 'user': p.get('User'), 'host': p.get('Host'),
                   'db': p.get('db'), 'command': p.get('Command'), 'time': p.get('Time'),
                   'state': p.get('State'), 'info': str(p.get('Info') or '')[:100]}
                  for p in processes if p.get('Command') != 'Sleep']

        # Key table sizes
        table_sizes = db.execute_query("""
            SELECT table_name,
                   ROUND(data_length / 1024 / 1024, 1) AS data_mb,
                   ROUND(index_length / 1024 / 1024, 1) AS index_mb,
                   table_rows
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_name IN (
                'vicidial_log', 'vicidial_closer_log', 'vicidial_agent_log',
                'vicidial_live_agents', 'qc_results', 'vicidial_inbound_dids'
              )
            ORDER BY data_length DESC
        """) or []

        return jsonify_ok({
            'active_queries': active,
            'active_count': len(active),
            'table_sizes': [{'table': r['table_name'],
                              'data_mb': safe_float(r['data_mb']),
                              'index_mb': safe_float(r['index_mb']),
                              'rows': safe_int(r['table_rows'])} for r in table_sizes],
            'checked_at': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify_err(e)


# ──────────────────────────────────────────────────────────────────────────────
# APT Download API
# ──────────────────────────────────────────────────────────────────────────────

APT_EXCLUDED_STATUSES = {'NA','AFTHRS','DROP','QUEUE','CLOSER','DISPO'}
EST_TZ = pytz.timezone('America/New_York')
PST_TZ = pytz.timezone('America/Los_Angeles')
UTC_TZ = pytz.UTC


@app.route('/api/apt/campaigns')
def apt_campaigns():
    """List campaigns available for APT download."""
    try:
        rows = db.execute_query("""
            SELECT DISTINCT campaign_id FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY campaign_id
        """) or []
        return jsonify_ok({'campaigns': [r['campaign_id'] for r in rows]})
    except Exception as e:
        return jsonify_err(str(e))


@app.route('/api/apt/download', methods=['POST'])
def apt_download():
    """
    Download & process APT data.
    Body JSON: {campaigns:[...], start_date:'YYYY-MM-DD', end_date:'YYYY-MM-DD', timezone:'EST'|'PST'}
    Returns summary + processed rows (up to 5000).
    """
    try:
        body              = request.get_json(force=True) or {}
        campaigns         = body.get('campaigns', [])
        start_str         = body.get('start_date', '')
        end_str           = body.get('end_date', start_str)
        tz_name           = body.get('timezone', 'EST')
        excl_statuses     = set(body.get('excluded_statuses', list(APT_EXCLUDED_STATUSES)))
        min_answered_sec  = int(body.get('min_answered_sec', 5))
        hours_start       = body.get('hours_start', '')   # 'HH:MM' or ''
        hours_end         = body.get('hours_end',   '')

        if not campaigns or not start_str:
            return jsonify_err('campaigns and start_date required', 400)

        target_tz  = EST_TZ if tz_name == 'EST' else PST_TZ
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        end_date   = datetime.strptime(end_str,   '%Y-%m-%d').date()

        # Build UTC range
        start_dt = target_tz.localize(datetime.combine(start_date, datetime.min.time()))
        end_dt   = target_tz.localize(datetime.combine(end_date,   datetime.max.time()))
        start_utc = start_dt.astimezone(UTC_TZ)
        end_utc   = end_dt.astimezone(UTC_TZ)

        placeholders = ','.join(['%s'] * len(campaigns))
        raw = db.execute_query(f"""
            SELECT c.call_date, c.campaign_id, c.uniqueid, c.phone_number,
                   c.length_in_sec, c.queue_seconds, c.term_reason, c.status AS call_status,
                   a.user AS agent, u.full_name AS agent_name,
                   a.talk_sec, a.dispo_sec, a.status AS agent_status,
                   a.pause_sec, a.wait_sec
            FROM vicidial_closer_log c
            LEFT JOIN vicidial_agent_log a ON c.uniqueid = a.uniqueid
            LEFT JOIN vicidial_users u ON a.user = u.user
            WHERE c.campaign_id IN ({placeholders})
              AND c.call_date BETWEEN %s AND %s
            ORDER BY c.call_date DESC
            LIMIT 10000
        """, campaigns + [start_utc, end_utc]) or []

        processed = []
        removed = {'before': 0, 'after': 0, 'status': 0, 'by_type': {}}

        for row in raw:
            cd_utc = row['call_date']
            if cd_utc.tzinfo is None:
                cd_utc = UTC_TZ.localize(cd_utc)
            cd_tz  = cd_utc.astimezone(target_tz)
            cd_pst = cd_utc.astimezone(PST_TZ)
            cd_local = cd_tz.date()

            if cd_local < start_date:
                removed['before'] += 1; continue
            if cd_local > end_date:
                removed['after'] += 1; continue

            tr = (row['term_reason'] or '').upper()
            ag = (row['agent_status'] or '').upper()
            excl = tr if tr in excl_statuses else (ag if ag in excl_statuses else None)
            if excl:
                removed['status'] += 1
                removed['by_type'][excl] = removed['by_type'].get(excl, 0) + 1
                continue

            # Working hours filter
            if hours_start and hours_end:
                call_hhmm = cd_tz.strftime('%H:%M')
                if not (hours_start <= call_hhmm <= hours_end):
                    removed['status'] += 1
                    removed['by_type']['AFTER_HOURS'] = removed['by_type'].get('AFTER_HOURS', 0) + 1
                    continue

            length_s = safe_int(row['length_in_sec'])
            dispo_s  = safe_int(row['dispo_sec'])
            talk_s   = safe_int(row['talk_sec'])
            call_time_s = max(0, length_s - dispo_s)

            processed.append({
                'call_date_utc':  cd_utc.strftime('%Y-%m-%d %H:%M:%S'),
                'call_date_local': cd_tz.strftime('%Y-%m-%d %H:%M:%S'),
                'call_date_pst':  cd_pst.strftime('%Y-%m-%d %H:%M:%S'),
                'timezone':       target_tz.zone,
                'campaign_id':    row['campaign_id'],
                'uniqueid':       row['uniqueid'],
                'phone_number':   row['phone_number'] or '',
                'length_sec':     length_s,
                'queue_sec':      safe_int(row['queue_seconds']),
                'talk_sec':       talk_s,
                'dispo_sec':      dispo_s,
                'call_time_sec':  call_time_s,
                'call_time_hms':  sec_to_hms(call_time_s),
                'term_reason':    row['term_reason'] or '',
                'call_status':    row['call_status'] or '',
                'agent':          row['agent'] or '',
                'agent_name':     row['agent_name'] or '',
                'agent_status':   row['agent_status'] or '',
            })

        total = len(processed)
        answered  = sum(1 for r in processed if r['length_sec'] >= min_answered_sec)
        abandoned = sum(1 for r in processed if r['term_reason'] in ('ABANDON','QUEUETIMEOUT','NOAGENT'))
        total_talk     = sum(r['talk_sec']      for r in processed)
        total_calltime = sum(r['call_time_sec'] for r in processed)

        # Campaign breakdown
        camp_stats = {}
        for r in processed:
            c = r['campaign_id']
            s = camp_stats.setdefault(c, {'calls':0,'talk':0,'call_time':0})
            s['calls'] += 1; s['talk'] += r['talk_sec']; s['call_time'] += r['call_time_sec']
        camp_breakdown = sorted([
            {'campaign': k, 'calls': v['calls'],
             'talk_hms': sec_to_hms(v['talk']),
             'call_time_hms': sec_to_hms(v['call_time']),
             'avg_call_hms': sec_to_hms(v['call_time'] // v['calls'] if v['calls'] else 0)}
            for k, v in camp_stats.items()], key=lambda x: -x['calls'])

        summary = {
            'total_raw':       len(raw),
            'total_processed': total,
            'answered':        answered,
            'abandoned':       abandoned,
            'answer_rate':     round(answered / total * 100, 1) if total else 0,
            'abandon_rate':    round(abandoned / total * 100, 1) if total else 0,
            'total_talk_hms':     sec_to_hms(total_talk),
            'total_calltime_hms': sec_to_hms(total_calltime),
            'avg_talk_hms':       sec_to_hms(total_talk // total if total else 0),
            'avg_calltime_hms':   sec_to_hms(total_calltime // total if total else 0),
            'removed': removed,
            'campaigns': camp_breakdown,
            'date_range': f"{start_str} to {end_str}",
            'timezone': target_tz.zone,
            'params_used': {
                'excluded_statuses': sorted(excl_statuses),
                'min_answered_sec': min_answered_sec,
                'hours_start': hours_start or 'any',
                'hours_end':   hours_end   or 'any',
                'formula': 'Call Time = length_in_sec - dispo_sec',
            },
        }

        return jsonify_ok({'summary': summary, 'rows': processed[:5000]})
    except Exception as e:
        return jsonify_err(str(e))


@app.route('/api/apt/export/csv', methods=['POST'])
def apt_export_csv():
    """Return processed APT data as a CSV file download."""
    import csv, io
    from flask import Response
    try:
        body      = request.get_json(force=True) or {}
        rows      = body.get('rows', [])
        filename  = body.get('filename', 'APT_Report.csv')
        if not rows:
            return jsonify_err('no rows provided', 400)

        out = io.StringIO()
        w   = csv.writer(out)
        w.writerow(['Call Date (UTC)','Call Date (Local)','Call Date (PST)','Timezone',
                    'Campaign','Unique ID','Phone',
                    'Length (s)','Queue (s)','Talk (s)','Dispo (s)',
                    'Call Time (s)','Call Time','Term Reason',
                    'Call Status','Agent','Agent Name','Agent Status'])
        for r in rows:
            w.writerow([r.get('call_date_utc'), r.get('call_date_local'), r.get('call_date_pst'),
                        r.get('timezone'), r.get('campaign_id'), r.get('uniqueid'), r.get('phone_number'),
                        r.get('length_sec'), r.get('queue_sec'), r.get('talk_sec'), r.get('dispo_sec'),
                        r.get('call_time_sec'), r.get('call_time_hms'), r.get('term_reason'),
                        r.get('call_status'), r.get('agent'), r.get('agent_name'), r.get('agent_status')])

        return Response(out.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition': f'attachment; filename="{filename}"'})
    except Exception as e:
        return jsonify_err(str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Client QA Package API
# ──────────────────────────────────────────────────────────────────────────────

_qa_jobs = {}   # job_id → {status, log, result, error}

PACKAGES_DIR = Path(__file__).parent.parent / 'exports' / 'client_packages'
PACKAGES_DIR.mkdir(parents=True, exist_ok=True)


@app.route('/api/qa-package/campaigns')
def qa_package_campaigns():
    try:
        rows = db.execute_query("""
            SELECT DISTINCT campaign_id FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY campaign_id
        """) or []
        return jsonify_ok({'campaigns': [r['campaign_id'] for r in rows if r['campaign_id']]})
    except Exception as e:
        return jsonify_err(str(e))


@app.route('/api/qa-package/history')
def qa_package_history():
    try:
        hf = PACKAGES_DIR / 'qa_package_history.json'
        history = json.loads(hf.read_text(encoding='utf-8')) if hf.exists() else []
        return jsonify_ok({'history': list(reversed(history[-30:]))})
    except Exception as e:
        return jsonify_err(str(e))


def _run_qa_job(job_id, campaigns, pkg_date_str, n_per_agent):
    job = _qa_jobs[job_id]
    log = job['log']

    def emit(msg, level='info'):
        log.append({'ts': datetime.now().strftime('%H:%M:%S'), 'msg': msg, 'level': level})

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from quality.client_qa_package import (
            get_agents_for_campaign, get_random_calls_for_agent,
            get_checkpoints, process_single_call, generate_summary_excel,
            zip_package, safe_name, record_package, get_last_call_date, PACKAGES_DIR as PKG_DIR
        )
        from quality.ai_assistant import get_whisper_model

        from datetime import date as _date
        pkg_date = _date.fromisoformat(pkg_date_str)

        emit(f'Starting QA Package for {", ".join(campaigns)} on {pkg_date_str}')
        job['status'] = 'running'

        # Pre-flight
        emit('Checking available agents and calls…')
        preflight = {}
        for c in campaigns:
            agents = get_agents_for_campaign(c, pkg_date)
            preflight[c] = agents
            if agents:
                emit(f'  {c}: {len(agents)} agent(s) found', 'ok')
            else:
                last = get_last_call_date(c)
                emit(f'  {c}: no calls on this date (last: {last or "unknown"})', 'warn')

        total_available = sum(len(v) for v in preflight.values())
        if total_available == 0:
            emit('No calls found on selected date for any campaign', 'error')
            job['status'] = 'error'
            job['error']  = 'No calls found on selected date'
            return

        # Load checkpoints
        checkpoints = get_checkpoints()
        if not checkpoints:
            emit('No QA checkpoints found in database', 'error')
            job['status'] = 'error'; job['error'] = 'No checkpoints'; return

        emit(f'Loaded {len(checkpoints)} checkpoints')

        # Load Whisper
        emit('Loading AI model (Whisper)… this may take 30s')
        get_whisper_model()
        emit('AI model ready', 'ok')

        camp_label = '_'.join(safe_name(c) for c in campaigns)
        pkg_name   = f"ClientQA_{camp_label}_{pkg_date.strftime('%Y%m%d')}"
        import shutil
        pkg_dir = PKG_DIR / pkg_name
        if pkg_dir.exists(): shutil.rmtree(pkg_dir)
        pkg_dir.mkdir(parents=True)

        all_results  = []
        total_agents = total_calls = total_ghost = 0
        MIN_DUR      = 60

        for campaign in campaigns:
            emit(f'── Campaign: {campaign}', 'section')
            agents = preflight.get(campaign, [])
            if not agents:
                emit(f'  Skipped — no agents', 'warn'); continue

            for agent in agents:
                label = agent['name']
                emit(f'  Agent: {label}')
                candidates = get_random_calls_for_agent(
                    campaign, agent['user'], pkg_date, n_per_agent, MIN_DUR)
                if not candidates:
                    emit(f'    No recordings found', 'warn'); continue

                agent_dir = pkg_dir / safe_name(label)
                agent_dir.mkdir(exist_ok=True)
                scored = 0
                for call in candidates:
                    if scored >= n_per_agent: break
                    emit(f'    Processing call {call.get("phone_number","?")} ({call.get("length_in_sec",0)//60}m)')
                    result = process_single_call(call, checkpoints, agent_dir,
                                                 pkg_date.strftime('%Y%m%d'))
                    if result is None:
                        total_ghost += 1
                        emit(f'    Skipped (ghost/no recording)', 'warn')
                    else:
                        all_results.append(result)
                        scored += 1; total_calls += 1
                        emit(f'    Scored {result["total_score"]}/{result["total_max"]} ({result["percentage"]:.0f}%)', 'ok')

                if scored == 0:
                    try: agent_dir.rmdir()
                    except: pass
                else:
                    total_agents += 1

        if total_calls == 0:
            emit('No calls were successfully processed', 'error')
            job['status'] = 'error'; job['error'] = 'No calls processed'; return

        # Excel
        xlsx_path = pkg_dir / f"ClientQA_Summary_{camp_label}_{pkg_date.strftime('%Y%m%d')}.xlsx"
        emit('Generating Excel summary…')
        if generate_summary_excel(all_results, xlsx_path, pkg_date.strftime('%Y-%m-%d')):
            emit(f'Excel created: {xlsx_path.name}', 'ok')

        # ZIP
        zip_path = PKG_DIR / f"{pkg_name}.zip"
        emit('Assembling ZIP…')
        zip_package(pkg_dir, zip_path)
        zip_mb = zip_path.stat().st_size / (1024*1024) if zip_path.exists() else 0
        emit(f'ZIP ready: {zip_path.name} ({zip_mb:.1f} MB)', 'ok')

        # Save history
        record_package({
            'request_date': str(pkg_date), 'campaign_ids': ', '.join(campaigns),
            'created_at':   datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'n_per_agent':  n_per_agent, 'total_agents': total_agents,
            'total_calls':  total_calls, 'ghost_skipped': total_ghost,
            'zip_filename': zip_path.name, 'zip_size_mb': round(zip_mb, 2),
            'status':       'COMPLETE',
            'calls': [{'agent': r['agent_name'], 'campaign': r['campaign'],
                       'phone': str(r['phone'])[-10:], 'call_date': str(r['call_date']),
                       'call_type': r['call_type'], 'score': f"{r['total_score']}/{r['total_max']}",
                       'pct': round(r['percentage'], 1)} for r in all_results],
        })

        job['status'] = 'done'
        job['result'] = {
            'zip_filename':  zip_path.name,
            'zip_size_mb':   round(zip_mb, 2),
            'total_agents':  total_agents,
            'total_calls':   total_calls,
            'ghost_skipped': total_ghost,
            'calls':         [{'agent': r['agent_name'], 'campaign': r['campaign'],
                               'score': f"{r['total_score']}/{r['total_max']}",
                               'pct': round(r['percentage'],1),
                               'call_type': r['call_type'],
                               'phone': str(r['phone'])[-10:]} for r in all_results],
        }
        emit(f'Package complete — {total_calls} calls, {total_agents} agents', 'ok')

    except Exception as e:
        import traceback
        job['status'] = 'error'
        job['error']  = str(e)
        log.append({'ts': datetime.now().strftime('%H:%M:%S'), 'msg': f'ERROR: {e}', 'level': 'error'})


@app.route('/api/qa-package/start', methods=['POST'])
def qa_package_start():
    try:
        body       = request.get_json(force=True) or {}
        campaigns  = body.get('campaigns', [])
        date_str   = body.get('date', '')
        n_per      = int(body.get('n_per_agent', 3))
        if not campaigns or not date_str:
            return jsonify_err('campaigns and date required', 400)

        job_id = str(uuid.uuid4())[:8]
        _qa_jobs[job_id] = {'status': 'starting', 'log': [], 'result': None, 'error': None}

        t = threading.Thread(target=_run_qa_job, args=(job_id, campaigns, date_str, n_per), daemon=True)
        t.start()
        return jsonify_ok({'job_id': job_id})
    except Exception as e:
        return jsonify_err(str(e))


@app.route('/api/qa-package/status/<job_id>')
def qa_package_status(job_id):
    job = _qa_jobs.get(job_id)
    if not job:
        return jsonify_err('job not found', 404)
    return jsonify_ok({'status': job['status'], 'log': job['log'],
                       'result': job['result'], 'error': job['error']})


@app.route('/api/qa-package/download/<filename>')
def qa_package_download(filename):
    safe = Path(filename).name   # prevent path traversal
    f = PACKAGES_DIR / safe
    if not f.exists():
        return jsonify_err('file not found', 404)
    return send_file(str(f), as_attachment=True, download_name=safe)


# ──────────────────────────────────────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', '1') == '1'
    print_color("🌐 Starting Altria Ops Web Dashboard v2.0.0", Colors.CYAN)
    print_color(f"📍 http://localhost:{port}", Colors.GREEN)
    try:
        import socket
        ip = socket.gethostbyname(socket.gethostname())
        print_color(f"📍 Network: http://{ip}:{port}", Colors.YELLOW)
    except: pass
    print_color("Press Ctrl+C to stop", Colors.YELLOW)
    app.run(debug=debug, host='0.0.0.0', port=port)
