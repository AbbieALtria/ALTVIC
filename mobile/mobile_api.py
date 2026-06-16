#!/usr/bin/env python3
# =============================================================================
# File:         mobile_api.py
# Version:      1.0.0
# Date:         2026-03-03
# Description:  Mobile API for Altria Ops (Lightweight endpoints)
# Location:     D:/Altria_Ops/mobile/api/mobile_api.py
# =============================================================================

from flask import Flask, jsonify, request, abort
from flask_cors import CORS
import sys
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import hmac

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.database import db
from utils.colors import print_color, Colors
from utils.formatter import sec_to_hms

app = Flask(__name__)
CORS(app)

# Simple API key authentication (in production, use JWT)
API_KEYS = {
    'mobile-app-2026': 'altria-mobile-secret'
}

def authenticate():
    """Simple API key authentication"""
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key not in API_KEYS:
        abort(401, description="Invalid API Key")
    return True

@app.before_request
def before_request():
    """Authenticate all requests except health check"""
    if request.path != '/health':
        authenticate()

# =============================================================================
# Mobile-Optimized Endpoints
# =============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint (no auth required)"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route('/api/v1/dashboard/summary', methods=['GET'])
def dashboard_summary():
    """Get dashboard summary for mobile home screen"""
    try:
        # Today's stats
        today_query = """
        SELECT 
            COUNT(*) as calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned
        FROM vicidial_closer_log
        WHERE DATE(call_date) = CURDATE()
        """
        today = db.execute_query(today_query)[0]
        
        # Online agents
        agents_query = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'INCALL' THEN 1 ELSE 0 END) as incall
        FROM vicidial_live_agents
        WHERE status IN ('READY', 'INCALL', 'PAUSE', 'QUEUE')
        """
        agents = db.execute_query(agents_query)[0]
        
        # Queue waiting
        queue_query = """
        SELECT COUNT(*) as waiting
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
          AND length_in_sec = 0
        """
        queue = db.execute_query(queue_query)[0]
        
        return jsonify({
            'success': True,
            'data': {
                'calls_today': today['calls'] or 0,
                'answered_today': today['answered'] or 0,
                'abandoned_today': today['abandoned'] or 0,
                'answer_rate': round((today['answered'] or 0) / (today['calls'] or 1) * 100, 1),
                'agents_online': agents['total'] or 0,
                'agents_incall': agents['incall'] or 0,
                'calls_waiting': queue['waiting'] or 0,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/v1/agents/status', methods=['GET'])
def agents_status():
    """Get simplified agent status for mobile"""
    try:
        query = """
        SELECT 
            l.user,
            u.full_name,
            l.status,
            l.campaign_id
        FROM vicidial_live_agents l
        LEFT JOIN vicidial_users u ON l.user = u.user
        WHERE l.status IN ('READY', 'INCALL', 'PAUSE', 'QUEUE')
        ORDER BY l.status
        LIMIT 50
        """
        
        agents = db.execute_query(query) or []
        
        result = []
        for a in agents:
            result.append({
                'user': a['user'],
                'name': a.get('full_name', a['user'])[:20],
                'status': a['status'],
                'campaign': a['campaign_id'] or 'N/A'
            })
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/v1/campaigns/top', methods=['GET'])
def top_campaigns():
    """Get top campaigns by volume (for mobile)"""
    try:
        query = """
        SELECT 
            campaign_id,
            COUNT(*) as calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered
        FROM vicidial_closer_log
        WHERE DATE(call_date) = CURDATE()
        GROUP BY campaign_id
        ORDER BY calls DESC
        LIMIT 10
        """
        
        campaigns = db.execute_query(query) or []
        
        result = []
        for c in campaigns:
            result.append({
                'campaign': c['campaign_id'],
                'calls': c['calls'],
                'answered': c['answered'] or 0,
                'answer_rate': round((c['answered'] or 0) / c['calls'] * 100, 1)
            })
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/v1/alerts/active', methods=['GET'])
def active_alerts_mobile():
    """Get active alerts for mobile (simplified)"""
    try:
        from alerts.monitoring import get_active_alerts
        alerts = get_active_alerts()
        
        result = []
        for a in alerts[:5]:
            result.append({
                'severity': a['severity'],
                'message': a['message'],
                'explanation': a.get('explanation', '')
            })
        
        return jsonify({
            'success': True,
            'data': result,
            'count': len(result)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/v1/agent/<username>/stats', methods=['GET'])
def agent_stats(username):
    """Get agent stats for mobile"""
    try:
        query = """
        SELECT 
            COUNT(*) as calls_today,
            SUM(talk_sec) as talk_time_today
        FROM vicidial_agent_log
        WHERE user = %s AND DATE(event_time) = CURDATE()
        """
        stats = db.execute_query(query, (username,))
        
        # Get current status
        status_query = """
        SELECT status, campaign_id
        FROM vicidial_live_agents
        WHERE user = %s
        """
        status = db.execute_query(status_query, (username,))
        
        return jsonify({
            'success': True,
            'data': {
                'username': username,
                'calls_today': stats[0]['calls_today'] if stats else 0,
                'talk_time_today': sec_to_hms(stats[0]['talk_time_today'] or 0) if stats else "0:00",
                'current_status': status[0]['status'] if status else 'Offline',
                'current_campaign': status[0]['campaign_id'] if status else None
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print_color("📱 Starting Altria Ops Mobile API...", Colors.CYAN)
    print_color("📍 http://localhost:5001", Colors.GREEN)
    print_color("📍 Mobile API endpoints available", Colors.YELLOW)
    print_color("Press Ctrl+C to stop", Colors.YELLOW)
    app.run(debug=False, host='0.0.0.0', port=5001)