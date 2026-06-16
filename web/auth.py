"""
Lightweight role-based auth for Altria Ops web dashboard.
Users are stored in config/users.json (username -> {password_hash, role, display_name}).
No external DB/table needed.
"""
import json
import functools
from pathlib import Path
from flask import session, redirect, url_for, request, jsonify
from werkzeug.security import check_password_hash

USERS_FILE = Path(__file__).parent.parent / 'config' / 'users.json'

# Which nav pages (data-page values) each role can see.
# "agents" is the main Agent Performance dashboard page.
ROLE_PAGES = {
    'admin': [
        'dashboard', 'agents', 'campaigns', 'email', 'reports', 'vicidial-reports',
        'quality', 'alerts', 'agent-mgmt', 'forecast', 'schedule',
        'anomaly', 'dids', 'query-monitor', 'apt', 'qa-package', 'mapping',
    ],
    'manager': [
        'dashboard', 'agents', 'campaigns', 'email', 'reports', 'vicidial-reports',
        'quality', 'alerts', 'agent-mgmt', 'forecast', 'schedule',
        'anomaly', 'dids', 'query-monitor', 'apt', 'qa-package',
        # 'mapping' (Agent Mapping / config) is admin-only
    ],
    'agent': [
        'dashboard', 'agents',  # read-only overview + agent performance
    ],
}

# Roles that may trigger downloads / exports / background jobs
WRITE_ROLES = {'admin', 'manager'}


def load_users():
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def verify_login(username, password):
    users = load_users()
    u = users.get(username)
    if not u:
        return None
    if not check_password_hash(u['password_hash'], password):
        return None
    return {'username': username, 'role': u['role'], 'display_name': u.get('display_name', username)}


def current_user():
    if 'username' not in session:
        return None
    return {
        'username': session['username'],
        'role': session.get('role', 'agent'),
        'display_name': session.get('display_name', session['username']),
    }


# Routes that don't require login
PUBLIC_PATHS = {'/login', '/logout', '/api/health'}


def is_public(path):
    if path in PUBLIC_PATHS:
        return True
    if path.startswith('/static/'):
        return True
    return False


def login_required_guard():
    """Call from app.before_request."""
    if is_public(request.path):
        return None
    if 'username' not in session:
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return redirect(url_for('login_page', next=request.path))
    return None


def role_required(*roles):
    """Decorator for routes that need a specific role (e.g. admin-only)."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user or user['role'] not in roles:
                if request.path.startswith('/api/'):
                    return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403
                return redirect(url_for('index'))
            return fn(*args, **kwargs)
        return wrapper
    return deco


def can_write():
    user = current_user()
    return bool(user and user['role'] in WRITE_ROLES)
