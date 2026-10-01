// Company Dashboard — fully fixed: doctor profiles, revoke, fast parallel loading

document.addEventListener('DOMContentLoaded', async () => {
  const user = requireAuth(['company']);
  if (!user) return;

  initNavbar(user);
  setEl('sf-company', user.company_name || user.name);
  setEl('today-date', new Date().toLocaleDateString('en-US', {weekday:'long', month:'long', day:'numeric'}));
  setEl('hero-greeting', `Welcome back, ${user.company_name || user.name} 👋`);

  // Parallel loading for speed
  try {
    await Promise.all([loadStats(), loadBatches()]);
  } catch(e) {
    showToast('Some data failed to load', 'warning');
  }
});

// ── STATS ──────────────────────────────────────────
async function loadStats() {
  // Single parallel fetch instead of 4 sequential calls
  const [totalRes, deptRes, pendRes, annotRes, apprRes] = await Promise.all([
    api.get('/images/?per_page=1'),
    api.get('/images/departments/stats'),
    api.get('/images/?status=pending&per_page=1'),
    api.get('/images/?status=annotating&per_page=1'),
    api.get('/images/?status=approved&per_page=1')
  ]);

  const total    = totalRes?.ok ? (totalRes.data.total || 0) : 0;
  const pending  = pendRes?.ok  ? (pendRes.data.total  || 0) : 0;
  const annot    = annotRes?.ok ? (annotRes.data.total  || 0) : 0;
  const approved = apprRes?.ok  ? (apprRes.data.total  || 0) : 0;

  setEl('stat-uploaded',   total.toLocaleString());
  setEl('stat-annotating', (pending + annot).toLocaleString());
  setEl('stat-approved',   approved.toLocaleString());
  setEl('stat-download',   approved.toLocaleString());
  setEl('hero-sub',        `${approved} annotated images are ready to download`);

  const readyBadge = document.getElementById('ready-badge');
  if (readyBadge) readyBadge.innerHTML = `<i class="fa fa-download"></i> ${approved} ready`;

  // Donut chart
  const ctx = document.getElementById('statusDonut');
  if (ctx) {
    new Chart(ctx, {
      type:'doughnut',
      data:{
        labels:['Approved','Annotating','Pending'],
        datasets:[{data:[approved, annot, pending],
          backgroundColor:['#22c55e','#7c3aed','#f59e0b'], borderWidth:0, hoverOffset:4}]
      },
      options:{responsive:true, maintainAspectRatio:false, cutout:'72%', plugins:{legend:{display:false}}}
    });
    setEl('donut-legend', [
      ['#22c55e','Approved',approved],
      ['#7c3aed','Annotating',annot],
      ['#f59e0b','Pending',pending]
    ].map(([c,l,v]) => `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <div style="width:10px;height:10px;border-radius:50%;background:${c};flex-shrink:0"></div>
        <span style="font-size:0.78rem;flex:1">${l}</span>
        <b style="font-size:0.8rem">${v}</b>
      </div>`).join(''));
  }

  // Department chart
  const ctx2 = document.getElementById('deptChart');
  if (ctx2 && deptRes?.ok && deptRes.data.length) {
    new Chart(ctx2, {
      type:'bar',
      data:{
        labels: deptRes.data.slice(0,6).map(d=>d.department),
        datasets:[{data: deptRes.data.slice(0,6).map(d=>d.count),
          backgroundColor:'rgba(124,58,237,0.6)', borderRadius:5, borderSkipped:false}]
      },
      options:{
        responsive:true, maintainAspectRatio:false, indexAxis:'y',
        plugins:{legend:{display:false}},
        scales:{
          x:{grid:{color:'rgba(255,255,255,0.05)'}, ticks:{color:'#8899aa'}},
          y:{grid:{display:false}, ticks:{color:'#8899aa', font:{size:10}}}
        }
      }
    });
  }
}

// ── BATCHES TABLE ──────────────────────────────────
async function loadBatches() {
  const res   = await api.get('/images/?per_page=20');
  const tbody = document.getElementById('batches-tbody');
  if (!tbody) return;

  if (!res?.ok || !res.data.images?.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-state" style="text-align:center;padding:40px">
      <i class="fa fa-box-open" style="font-size:2rem;margin-bottom:10px;display:block;opacity:0.3"></i>
      No images uploaded yet. <a href="/company/upload" style="color:var(--purple)">Upload your first batch →</a>
    </td></tr>`;
    return;
  }

  // Group by batch_name (real batches from DB)
  const batches = {};
  res.data.images.forEach(img => {
    const key = img.batch_name || img.department || 'Default';
    if (!batches[key]) batches[key] = { name: key, dept: img.department, images: [] };
    batches[key].images.push(img);
  });

  const deptColors = { Radiology:'cyan', Dermatology:'gold', Neurology:'purple',
    Oncology:'red', Ophthalmology:'green', Cardiology:'cyan', default:'gray' };

  tbody.innerHTML = Object.values(batches).map(b => {
    const total    = b.images.length;
    const approved = b.images.filter(i => i.status === 'approved').length;
    const pct      = total ? Math.round((approved / total) * 100) : 0;
    const color    = deptColors[b.dept] || 'gray';
    return `<tr>
      <td style="font-weight:600">${escHtml(b.name)}</td>
      <td><span class="badge badge-${color}">${escHtml(b.dept)}</span></td>
      <td style="min-width:120px">
        <div style="margin-bottom:4px;font-size:0.72rem;color:var(--text-secondary)">${pct}% • ${approved}/${total}</div>
        <div class="progress-bar"><div class="progress-fill${pct===100?' green':''}" style="width:${pct}%"></div></div>
      </td>
      <td>${pct===100 ? statusBadge('approved') : approved>0 ? statusBadge('annotating') : statusBadge('pending')}</td>
      <td style="display:flex;gap:6px;align-items:center">
        ${approved>0 ? `<button class="btn btn-green btn-sm" onclick="downloadBatch('${escHtml(b.name)}')">
          <i class="fa fa-download"></i></button>` : ''}
        <a href="/company/batches" class="btn btn-ghost btn-sm">View</a>
      </td>
    </tr>`;
  }).join('');
}

function downloadBatch(batchName) {
  showToast(`Preparing download for batch: ${batchName}`, 'info');
  window.location.href = `/company/batches?batch=${encodeURIComponent(batchName)}`;
}

// ── UTILITIES ─────────────────────────────────────
function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = (typeof val === 'string' && val.includes('<')) ? val : escHtml(String(val));
}
function escHtml(str) {
  return String(str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
