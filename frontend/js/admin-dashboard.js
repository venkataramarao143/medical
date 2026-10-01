// Admin Dashboard — fully fixed and functional

document.addEventListener('DOMContentLoaded', async () => {
  // 1. Auth guard — MUST be admin role in localStorage
  const user = requireAuth(['admin']);
  if (!user) return;

  // 2. Populate navbar from localStorage (instant)
  document.getElementById('nav-user-name').textContent  = user.name || 'Admin';
  document.getElementById('nav-user-role').textContent  = 'Super Admin';
  document.getElementById('nav-user-avatar').textContent = (user.name || 'AD').slice(0,2).toUpperCase();
  document.getElementById('today-date').textContent =
    new Date().toLocaleDateString('en-US', { weekday:'long', month:'long', day:'numeric', year:'numeric' });

  // 3. Fetch fresh data from DB in parallel (fast)
  try {
    await Promise.all([loadStats(), loadVerificationQueue(), loadPayouts()]);
  } catch(e) {
    showToast('Error loading dashboard data', 'error');
  }
  initActivityChart();
});

// ── STATS ──────────────────────────────────────────
async function loadStats() {
  const res = await api.get('/admin/stats');
  if (!res || !res.ok) { showToast('Could not load stats', 'warning'); return; }
  const d = res.data;

  setText('stat-doctors',        d.doctors?.total ?? 0);
  setText('stat-v-doctors',      `${d.doctors?.verified ?? 0} verified`);
  // companies can be object {total, active} or number — handle both
  const compCount = typeof d.companies === 'object' ? (d.companies?.total ?? 0) : (d.companies ?? 0);
  setText('stat-companies',      compCount);
  setText('stat-images',         (d.images?.total ?? 0).toLocaleString());
  setText('stat-payouts',        '$' + Number(d.payouts?.pending_amount ?? 0).toFixed(0));
  setText('stat-payout-count',   `${d.payouts?.pending_count ?? 0} pending`);
  setText('stat-today',          d.annotations_today ?? 0);
  const pending = d.doctors?.pending_verification ?? 0;
  setText('stat-pending-verify', pending);
  setText('notif-count',         pending);

  if (pending > 0) {
    const alert = document.getElementById('pending-alert');
    if (alert) {
      alert.style.display = 'flex';
      setText('pending-alert-text',
        `${pending} doctor${pending > 1 ? 's' : ''} pending verification — review and approve.`);
    }
  }
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ── VERIFICATION QUEUE ─────────────────────────────
async function loadVerificationQueue() {
  const res   = await api.get('/admin/doctors?verified=false');
  const tbody = document.getElementById('verify-tbody');
  if (!tbody) return;
  if (!res?.ok || !res.data.doctors?.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--green);">
      <i class="fa fa-circle-check"></i> No pending verifications</td></tr>`;
    return;
  }
  tbody.innerHTML = res.data.doctors.slice(0, 5).map(d => `
    <tr class="fade-in">
      <td>
        <div style="font-weight:600">${escHtml(d.name)}</div>
        <div style="font-size:0.72rem;color:var(--text-secondary)">${escHtml(d.email)}</div>
      </td>
      <td><span class="badge badge-cyan">${escHtml(d.specialty || '—')}</span></td>
      <td style="font-family:monospace;font-size:0.78rem;color:var(--text-secondary)">${escHtml(d.license_number || '—')}</td>
      <td style="font-size:0.8rem;color:var(--text-secondary)">${timeAgo(d.created_at)}</td>
      <td>
        <div style="display:flex;gap:6px">
          <button class="btn btn-green btn-sm" onclick="verifyDoctor('${d.id || d._id}',this)">
            <i class="fa fa-check"></i> Approve
          </button>
          <button class="btn btn-danger btn-sm" onclick="rejectDoctor('${d.id || d._id}',this)">
            <i class="fa fa-times"></i>
          </button>
        </div>
      </td>
    </tr>`).join('');
}

// ── PENDING PAYOUTS ────────────────────────────────
async function loadPayouts() {
  const res   = await api.get('/admin/payouts?status=pending');
  const tbody = document.getElementById('payouts-tbody');
  if (!tbody) return;
  if (!res?.ok || !res.data.payouts?.length) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--text-muted);">
      <i class="fa fa-circle-check" style="color:var(--green)"></i> No pending payouts</td></tr>`;
    return;
  }
  tbody.innerHTML = res.data.payouts.slice(0, 6).map(p => `
    <tr class="fade-in">
      <td style="font-weight:600">${escHtml(p.doctor_name)}</td>
      <td><span class="badge badge-cyan" style="font-size:0.7rem">${escHtml(p.specialty || '—')}</span></td>
      <td style="color:var(--gold);font-weight:700">$${Number(p.amount || 0).toFixed(2)}</td>
      <td><button class="btn btn-gold btn-sm" onclick="markPaid('${p.id || p._id}',this)">
        <i class="fa fa-dollar-sign"></i> Pay Now</button></td>
    </tr>`).join('');
}

// ── SECTION NAVIGATION ─────────────────────────────
function showSection(name) {
  ['overview','doctors','payouts','companies','images'].forEach(s => {
    const el = document.getElementById(`section-${s}`);
    if (el) el.style.display = (s === name) ? 'block' : 'none';
  });
  // Update active nav item
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const active = document.querySelector(`.nav-item[onclick*="${name}"]`);
  if (active) active.classList.add('active');
  // Also set overview as base
  if (name === 'overview') {
    const el = document.querySelector('.nav-item[href="/admin/dashboard"]');
    if (el) el.classList.add('active');
  }

  if (name === 'doctors')   loadDoctors('');
  if (name === 'payouts')   loadAllPayouts();
  if (name === 'companies') loadCompanies();
  if (name === 'images')    loadAdminImages();
}

// ── DOCTORS TABLE ─────────────────────────────────
async function loadDoctors(verified = '') {
  const url   = `/admin/doctors${verified !== '' ? `?verified=${verified}` : ''}`;
  const res   = await api.get(url);
  const tbody = document.getElementById('doctors-tbody');
  if (!tbody) return;
  if (!res?.ok || !res.data.doctors?.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:32px;color:var(--text-muted)">No doctors found</td></tr>`;
    return;
  }
  tbody.innerHTML = res.data.doctors.map(d => `
    <tr>
      <td>
        <div style="font-weight:600">${escHtml(d.name)}</div>
        <div style="font-size:0.75rem;color:var(--text-secondary)">${escHtml(d.email)}</div>
      </td>
      <td><span class="badge badge-cyan">${escHtml(d.specialty || '—')}</span></td>
      <td style="font-size:0.78rem;font-family:monospace">${escHtml(d.license_number || '—')}</td>
      <td>${d.verified
        ? '<span class="badge badge-green"><i class="fa fa-check"></i> Verified</span>'
        : '<span class="badge badge-gold"><i class="fa fa-clock"></i> Pending</span>'}</td>
      <td style="color:var(--gold);font-weight:600">${formatMoney(d.total_earnings || 0)}</td>
      <td style="font-size:0.8rem;color:var(--text-secondary)">${formatDate(d.created_at)}</td>
      <td>
        <div style="display:flex;gap:6px;align-items:center">
          ${!d.verified
            ? `<button class="btn btn-green btn-sm" onclick="verifyDoctor('${d.id || d._id}',this)">
                <i class="fa fa-check"></i> Approve</button>
               <button class="btn btn-danger btn-sm" onclick="rejectDoctor('${d.id || d._id}',this)">
                <i class="fa fa-times"></i></button>`
            : `<button class="btn btn-ghost btn-sm" onclick="suspendUser('${d.id || d._id}',this)">
                <i class="fa fa-ban"></i> Suspend</button>`}
        </div>
      </td>
    </tr>`).join('');
}

// ── ALL PAYOUTS TABLE ──────────────────────────────
async function loadAllPayouts() {
  const res   = await api.get('/admin/payouts?status=pending&per_page=50');
  const tbody = document.getElementById('all-payouts-tbody');
  if (!tbody) return;
  if (!res?.ok || !res.data.payouts?.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:32px;color:var(--text-muted)">No pending payouts</td></tr>`;
    return;
  }
  tbody.innerHTML = res.data.payouts.map(p => `
    <tr>
      <td style="font-weight:600">${escHtml(p.doctor_name)}</td>
      <td><span class="badge badge-cyan">${escHtml(p.specialty || '—')}</span></td>
      <td style="font-size:0.8rem;color:var(--text-secondary);max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
        ${escHtml(p.image_filename || '—')}</td>
      <td style="color:var(--gold);font-weight:700">$${Number(p.amount || 0).toFixed(2)}</td>
      <td style="font-size:0.8rem;color:var(--text-secondary)">${formatDate(p.created_at)}</td>
      <td><button class="btn btn-gold btn-sm" onclick="markPaid('${p.id || p._id}',this)">
        <i class="fa fa-dollar-sign"></i> Pay</button></td>
    </tr>`).join('');
}

// ── COMPANIES TABLE ────────────────────────────────
async function loadCompanies() {
  const res   = await api.get('/admin/companies');
  const tbody = document.getElementById('companies-tbody');
  if (!tbody) return;
  if (!res?.ok) return;
  tbody.innerHTML = (res.data.companies || []).map(c => `
    <tr>
      <td style="font-weight:600">${escHtml(c.company_name || c.name)}</td>
      <td style="color:var(--text-secondary)">${escHtml(c.email)}</td>
      <td style="font-weight:600">${(c.image_count || 0).toLocaleString()}</td>
      <td style="color:var(--text-secondary)">${formatDate(c.created_at)}</td>
    </tr>`).join('');
}

// ── IMAGES TABLE ───────────────────────────────────
async function loadAdminImages() {
  const res   = await api.get('/admin/images?per_page=30');
  const tbody = document.getElementById('admin-images-tbody');
  if (!tbody) return;
  if (!res?.ok) return;
  tbody.innerHTML = (res.data.images || []).map(img => `
    <tr>
      <td style="font-size:0.85rem;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
        ${escHtml(img.filename)}</td>
      <td><span class="badge badge-cyan">${escHtml(img.department)}</span></td>
      <td style="color:var(--text-secondary);font-size:0.8rem">${escHtml(img.company_name || '—')}</td>
      <td>${statusBadge(img.status)}</td>
      <td style="color:var(--text-secondary);font-size:0.8rem">${formatDate(img.created_at)}</td>
      <td><button class="btn btn-ghost btn-sm" onclick="openFullImage('${img.id || img._id}')"><i class="fa fa-eye"></i> View</button></td>
    </tr>`).join('');
}

// ── FULL IMAGE VIEWER ──────────────────────────────
async function openFullImage(imgId) {
  const modal = document.getElementById('img-full-modal');
  const imgEl = document.getElementById('full-view-img');
  if (!modal || !imgEl) return;
  imgEl.src = '';
  modal.style.display = 'flex';
  try {
    const token = getToken();
    const r = await fetch(`/api/images/${imgId}/file`, { headers: {'Authorization': `Bearer ${token}`} });
    if (!r.ok) {
        const errText = await r.text();
        throw new Error(`HTTP ${r.status}: ${errText}`);
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    imgEl.src = url;
    imgEl.onload = () => URL.revokeObjectURL(url);
    imgEl.onerror = () => { showToast('Browser cannot render this format naturally (e.g. DICOM)', 'warning'); }
  } catch(e) { 
      modal.style.display = 'none'; 
      showToast('Error loading image: ' + e.message, 'error'); 
  }
}

// ── ACTIONS ────────────────────────────────────────
async function verifyDoctor(id, btn) {
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="width:14px;height:14px"></span>';
  const res = await api.post(`/admin/doctors/${id}/verify`, {});
  if (res?.ok) {
    showToast('Doctor verified and approved!', 'success');
    await Promise.all([loadVerificationQueue(), loadStats()]);
    const doctorsTbody = document.getElementById('doctors-tbody');
    if (doctorsTbody && doctorsTbody.innerHTML) loadDoctors('');
  } else {
    showToast(res?.data?.error || 'Failed', 'error');
    btn.disabled = false;
    btn.innerHTML = '<i class="fa fa-check"></i> Approve';
  }
}

async function rejectDoctor(id, btn) {
  const reason = prompt('Reason for rejection (optional):') || 'Does not meet requirements';
  btn.disabled = true;
  const res = await api.post(`/admin/doctors/${id}/reject`, { reason });
  if (res?.ok) {
    showToast('Doctor rejected', 'warning');
    await loadVerificationQueue();
  } else {
    showToast('Failed to reject', 'error');
    btn.disabled = false;
  }
}

async function markPaid(id, btn) {
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner" style="width:14px;height:14px"></span>';
  const res = await api.post(`/admin/payouts/${id}/pay`, {});
  if (res?.ok) {
    showToast('Payout marked as paid!', 'success');
    await Promise.all([loadPayouts(), loadStats()]);
    loadAllPayouts();
  } else {
    showToast(res?.data?.error || 'Failed', 'error');
    btn.disabled = false;
    btn.innerHTML = '<i class="fa fa-dollar-sign"></i> Pay Now';
  }
}

async function suspendUser(id, btn) {
  if (!confirm('Suspend this user?')) return;
  const res = await api.post(`/admin/users/${id}/suspend`, {});
  if (res?.ok) { showToast('User suspended', 'warning'); loadDoctors(''); }
  else showToast('Failed', 'error');
}

// ── ACTIVITY CHART ─────────────────────────────────
function initActivityChart() {
  const ctx = document.getElementById('activityChart');
  if (!ctx) return;
  const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: days,
      datasets: [
        { label:'Annotations', data:[42,67,89,55,120,95,110],
          borderColor:'#00d4ff', backgroundColor:'rgba(0,212,255,0.08)',
          fill:true, tension:0.4, pointBackgroundColor:'#00d4ff', pointRadius:3 },
        { label:'Uploads', data:[120,80,200,60,150,40,180],
          borderColor:'#7c3aed', backgroundColor:'rgba(124,58,237,0.08)',
          fill:true, tension:0.4, pointBackgroundColor:'#7c3aed', pointRadius:3 }
      ]
    },
    options: {
      responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ labels:{ color:'#8899aa', font:{size:11} } } },
      scales:{
        x:{ grid:{display:false}, ticks:{color:'#8899aa'} },
        y:{ grid:{color:'rgba(255,255,255,0.05)'}, ticks:{color:'#8899aa'} }
      }
    }
  });
}

// ── UTILITY ────────────────────────────────────────
function escHtml(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
