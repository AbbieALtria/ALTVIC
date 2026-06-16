// ─── User Management (admin only) ───────────────────────────────────────────

let _umUsers = [];
let _umRoles = ['admin', 'manager', 'agent'];

async function loadUserMgmtPage() {
    const tbody = document.getElementById('umTableBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="4" class="loading-cell"><i class="fas fa-spinner fa-spin"></i> Loading...</td></tr>';
    try {
        const d = await apiFetch('/api/admin/users');
        _umUsers = d.users || [];
        _umRoles = d.roles || _umRoles;
        renderUmTable();
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="4" style="color:red;padding:14px;">' + esc(e.message) + '</td></tr>';
    }
}

function renderUmTable() {
    const tbody = document.getElementById('umTableBody');
    if (!tbody) return;
    if (!_umUsers.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-cell">No users found</td></tr>';
        return;
    }
    const roleColor = r => r === 'admin' ? '#6366f1' : r === 'manager' ? '#0ea5e9' : '#94a3b8';
    tbody.innerHTML = _umUsers.map(u => `
        <tr>
            <td style="font-weight:700;font-family:monospace;">${esc(u.username)}</td>
            <td>${esc(u.display_name)}</td>
            <td>
                <span style="font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;
                    background:${roleColor(u.role)}1a;color:${roleColor(u.role)};text-transform:uppercase;letter-spacing:.04em;">
                    ${esc(u.role)}
                </span>
            </td>
            <td>
                <button onclick="umEditUser('${esc(u.username)}')" style="font-size:12px;padding:4px 10px;border-radius:6px;border:1px solid #e2e8f0;background:white;color:#374151;cursor:pointer;margin-right:6px;">
                    <i class="fas fa-pen"></i> Edit
                </button>
                <button onclick="umDeleteUser('${esc(u.username)}')" style="font-size:12px;padding:4px 10px;border-radius:6px;border:1px solid #fecaca;background:white;color:#ef4444;cursor:pointer;">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        </tr>`).join('');
}

function umShowMsg(text, ok) {
    const el = document.getElementById('umMsg');
    if (!el) return;
    el.style.display = '';
    el.style.background = ok ? '#f0fdf4' : '#fef2f2';
    el.style.color      = ok ? '#16a34a' : '#ef4444';
    el.textContent = text;
    setTimeout(() => { el.style.display = 'none'; }, 4000);
}

function umOpenModal() {
    document.getElementById('umModal').style.display = '';
}
function umCloseModal() {
    document.getElementById('umModal').style.display = 'none';
}

function umAddUserOpen() {
    document.getElementById('umModalTitle').textContent = 'Add User';
    document.getElementById('umEditUsername').value = '';
    document.getElementById('umUsername').value = '';
    document.getElementById('umUsername').disabled = false;
    document.getElementById('umDisplayName').value = '';
    document.getElementById('umRole').value = 'agent';
    document.getElementById('umPassword').value = '';
    document.getElementById('umPasswordLabel').textContent = 'Password';
    document.getElementById('umPasswordHint').style.display = 'none';
    umOpenModal();
}

function umEditUser(username) {
    const u = _umUsers.find(x => x.username === username);
    if (!u) return;
    document.getElementById('umModalTitle').textContent = 'Edit User';
    document.getElementById('umEditUsername').value = username;
    document.getElementById('umUsername').value = username;
    document.getElementById('umUsername').disabled = true;
    document.getElementById('umDisplayName').value = u.display_name;
    document.getElementById('umRole').value = u.role;
    document.getElementById('umPassword').value = '';
    document.getElementById('umPasswordLabel').textContent = 'New Password (optional)';
    document.getElementById('umPasswordHint').style.display = '';
    umOpenModal();
}

async function umSaveUser() {
    const editing  = document.getElementById('umEditUsername').value;
    const username = document.getElementById('umUsername').value.trim();
    const display_name = document.getElementById('umDisplayName').value.trim();
    const role     = document.getElementById('umRole').value;
    const password = document.getElementById('umPassword').value;

    if (!username) { alert('Username is required'); return; }
    if (!editing && !password) { alert('Password is required for a new user'); return; }

    const btn = document.getElementById('umSaveBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

    try {
        let resp;
        if (editing) {
            resp = await fetch('/api/admin/users/' + encodeURIComponent(editing), {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ role, display_name, password: password || undefined })
            });
        } else {
            resp = await fetch('/api/admin/users', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ username, password, role, display_name })
            });
        }
        const d = await resp.json();
        if (!resp.ok || !d.success) throw new Error(d.error || 'Save failed');
        umCloseModal();
        umShowMsg((editing ? 'User updated: ' : 'User created: ') + username, true);
        loadUserMgmtPage();
    } catch(e) {
        alert('Error: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-save"></i> Save';
    }
}

async function umDeleteUser(username) {
    if (!confirm(`Delete user "${username}"? This cannot be undone.`)) return;
    try {
        const resp = await fetch('/api/admin/users/' + encodeURIComponent(username), { method: 'DELETE' });
        const d = await resp.json();
        if (!resp.ok || !d.success) throw new Error(d.error || 'Delete failed');
        umShowMsg('User deleted: ' + username, true);
        loadUserMgmtPage();
    } catch(e) {
        alert('Error: ' + e.message);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('umAddUserBtn')?.addEventListener('click', umAddUserOpen);
});
