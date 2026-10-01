// Central API client - handles auth tokens and base URL

const API_BASE = '/api';

function getToken() {
  return localStorage.getItem('token');
}

function getUser() {
  const u = localStorage.getItem('user');
  return u ? JSON.parse(u) : null;
}

function setAuth(token, user) {
  localStorage.setItem('token', token);
  localStorage.setItem('user', JSON.stringify(user));
}

function clearAuth() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
}

async function apiFetch(endpoint, options = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  // Don't set Content-Type for FormData
  if (options.body instanceof FormData) delete headers['Content-Type'];

  const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });

  if (res.status === 401) {
    clearAuth();
    window.location.href = '/login';
    return;
  }

  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

// Convenience methods
const api = {
  get:    (url)          => apiFetch(url, { method: 'GET' }),
  post:   (url, body)    => apiFetch(url, { method: 'POST', body: JSON.stringify(body) }),
  put:    (url, body)    => apiFetch(url, { method: 'PUT',  body: JSON.stringify(body) }),
  delete: (url)          => apiFetch(url, { method: 'DELETE' }),
  upload: (url, formData) => apiFetch(url, { method: 'POST', body: formData })
};

// Toast notifications
function showToast(message, type = 'info') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span> ${message}`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 3500);
}

// Role-based auth guard
function requireAuth(allowedRoles = []) {
  const token = getToken();
  const user  = getUser();
  if (!token || !user) { window.location.href = '/login'; return false; }
  if (allowedRoles.length && !allowedRoles.includes(user.role)) {
    const redirects = { doctor: '/doctor/dashboard', company: '/company/dashboard', admin: '/admin/dashboard' };
    window.location.href = redirects[user.role] || '/login';
    return false;
  }
  return user;
}

// Populate user info in navbar
function initNavbar(user) {
  const nameEl    = document.getElementById('nav-user-name');
  const roleEl    = document.getElementById('nav-user-role');
  const avatarEl  = document.getElementById('nav-user-avatar');
  if (nameEl)   nameEl.textContent   = user.name;
  if (roleEl)   roleEl.textContent   = user.specialty || user.company_name || user.role;
  if (avatarEl) avatarEl.textContent = user.name.split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase();
}

// Logout
function logout() {
  clearAuth();
  window.location.href = '/login';
}

// Format currency
function formatMoney(amount) {
  return '$' + Number(amount).toFixed(2);
}

// Format date
function formatDate(iso) {
  if (!iso) return '-';
  return new Date(iso).toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' });
}

// Format relative time
function timeAgo(iso) {
  if (!iso) return '-';
  const sec = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (sec < 60)   return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec/60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec/3600)}h ago`;
  return `${Math.floor(sec/86400)}d ago`;
}

// Status badge HTML
function statusBadge(status) {
  const map = {
    pending:    ['badge badge-gold',   'Pending'],
    assigned:   ['badge badge-cyan',   'Assigned'],
    annotating: ['badge badge-purple', 'Annotating'],
    qa_review:  ['badge', 'QA Review'],
    approved:   ['badge badge-green',  'Approved'],
    rejected:   ['badge badge-red',    'Rejected'],
    draft:      ['badge badge-gray',   'Draft'],
    submitted:  ['badge', 'In QA'],
    qa_approved:['badge badge-green',  'QA Approved'],
    qa_rejected:['badge badge-red',    'QA Rejected'],
    paid:       ['badge badge-green',  'Paid'],
  };
  const [cls, label] = map[status] || ['badge badge-gray', status];
  return `<span class="${cls} status-${status}">${label}</span>`;
}
