// Company Batches Page — with doctor profiles, revoke, download

document.addEventListener('DOMContentLoaded', async () => {
  const user = requireAuth(['company']);
  if (!user) return;
  initNavbar(user);
  setEl('sf-company', user.company_name || user.name);
  setEl('today-date', new Date().toLocaleDateString('en-US',
    {weekday:'long', month:'long', day:'numeric'}));

  await loadImages();
});

let allImages = [];
let currentFilter = '';

async function loadImages(status = '') {
  const container = document.getElementById('images-container');
  if (!container) return;
  container.innerHTML = `<div style="text-align:center;padding:60px"><span class="spinner"></span><p style="margin-top:12px;color:var(--text-muted)">Loading images...</p></div>`;

  const url = status ? `/images/?status=${status}&per_page=50` : '/images/?per_page=50';
  const res = await api.get(url);

  if (!res?.ok) {
    container.innerHTML = `<div class="empty-state"><i class="fa fa-exclamation-triangle"></i><p>Failed to load images</p></div>`;
    return;
  }

  allImages = res.data.images || [];
  currentFilter = status;
  renderImages(allImages);
  updateFilterCounts(res.data.total);
}

function renderImages(images) {
  const container = document.getElementById('images-container');
  if (!images.length) {
    container.innerHTML = `
      <div class="empty-state" style="padding:80px 20px;text-align:center">
        <i class="fa fa-images" style="font-size:3rem;opacity:0.3;display:block;margin-bottom:16px"></i>
        <h3>No images found</h3>
        <p>Upload some images to get started</p>
        <a href="/company/upload" class="btn btn-purple" style="margin-top:16px;display:inline-flex">
          <i class="fa fa-upload"></i> Upload Images</a>
      </div>`;
    return;
  }

  const deptColors = { Radiology:'cyan', Dermatology:'gold', Neurology:'purple',
    Oncology:'red', Ophthalmology:'green', Cardiology:'cyan', default:'gray' };
  const icons = { Radiology:'fa-x-ray', Dermatology:'fa-band-aid', Neurology:'fa-brain',
    Oncology:'fa-ribbon', Ophthalmology:'fa-eye', Cardiology:'fa-heart', default:'fa-file-medical' };

  container.innerHTML = `
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Image</th>
            <th>Department</th>
            <th>Status</th>
            <th>Assigned Doctor</th>
            <th>Uploaded</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${images.map(img => {
            const color = deptColors[img.department] || 'gray';
            const icon  = icons[img.department] || icons.default;
            const canRevoke = ['approved','qa_review','annotating'].includes(img.status);
            const hasDoctorProfile = img.assigned_doctor_id && img.assigned_doctor_name;
            return `<tr class="fade-in">
              <td>
                <div style="display:flex;align-items:center;gap:10px">
                  <div style="width:36px;height:36px;background:var(--bg-secondary);border-radius:8px;display:grid;place-items:center;flex-shrink:0">
                    <i class="fa ${icon}" style="color:var(--cyan)"></i>
                  </div>
                  <div>
                    <div style="font-weight:600;font-size:0.85rem;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                      ${escHtml(img.filename)}</div>
                    <div style="font-size:0.7rem;color:var(--text-muted);font-family:monospace">
                      #${(img.id||img._id||'').slice(-8).toUpperCase()}</div>
                  </div>
                </div>
              </td>
              <td><span class="badge badge-${color}">${escHtml(img.department)}</span></td>
              <td>${statusBadge(img.status)}</td>
              <td>
                ${hasDoctorProfile
                  ? `<button class="btn btn-ghost btn-sm" onclick="viewDoctorProfile('${img.id||img._id}','${escHtml(img.assigned_doctor_name||'')}')">
                      <i class="fa fa-user-doctor"></i> ${escHtml(img.assigned_doctor_name)}</button>`
                  : `<span style="color:var(--text-muted);font-size:0.8rem">Not assigned</span>`}
              </td>
              <td style="color:var(--text-secondary);font-size:0.8rem">${timeAgo(img.created_at)}</td>
              <td>
                <div style="display:flex;gap:6px">
                  <button class="btn btn-ghost btn-sm" onclick="openFullImage('${img.id||img._id}')"><i class="fa fa-eye"></i> View</button>
                  ${img.status === 'approved'
                    ? `<button class="btn btn-green btn-sm" onclick="downloadAnnotation('${img.id||img._id}')">
                        <i class="fa fa-download"></i></button>` : ''}
                  ${canRevoke
                    ? `<button class="btn btn-danger btn-sm" onclick="revokeImage('${img.id||img._id}','${escHtml(img.filename)}')"
                        title="Revoke annotation - send to another doctor">
                        <i class="fa fa-rotate-left"></i> Revoke</button>` : ''}
                </div>
              </td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>`;
}

function updateFilterCounts(total) {
  setEl('total-count', `${total} images`);
}

// ── FILTER BUTTONS ─────────────────────────────────
function filterImages(status) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  const activeBtn = document.querySelector(`.filter-btn[data-status="${status}"]`);
  if (activeBtn) activeBtn.classList.add('active');
  loadImages(status);
}

// ── VIEW DOCTOR PROFILE ────────────────────────────
async function viewDoctorProfile(imageId, doctorName) {
  // Show loading
  showToast(`Loading Dr. ${doctorName}'s profile...`, 'info');

  const res = await api.get(`/images/${imageId}/doctor-profile`);
  if (!res?.ok) {
    showToast(res?.data?.error || 'Could not load doctor profile', 'error');
    return;
  }

  const doc = res.data;
  openDoctorModal(doc);
}

function openDoctorModal(doc) {
  document.getElementById('doctor-profile-modal')?.remove();

  const modal = document.createElement('div');
  modal.id = 'doctor-profile-modal';
  modal.style.cssText = `
    position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;
    background:rgba(0,0,0,0.75);backdrop-filter:blur(8px);animation:fadeIn 0.2s ease`;

  const accuracy = doc.stats?.accuracy_pct ?? 0;
  const stars = '★'.repeat(Math.round(accuracy/20)) + '☆'.repeat(5 - Math.round(accuracy/20));

  modal.innerHTML = `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:20px;
      padding:32px;width:480px;max-width:92vw;position:relative;
      box-shadow:0 24px 80px rgba(0,0,0,0.6);animation:fadeIn 0.25s ease">
      <button onclick="document.getElementById('doctor-profile-modal').remove()"
        style="position:absolute;top:16px;right:16px;background:var(--bg-secondary);border:none;
        color:var(--text-primary);border-radius:8px;width:34px;height:34px;cursor:pointer;
        font-size:1rem;display:grid;place-items:center">✕</button>

      <!-- Doctor Header -->
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:24px">
        <div style="width:68px;height:68px;border-radius:50%;
          background:linear-gradient(135deg,var(--cyan),var(--purple));
          display:grid;place-items:center;font-size:1.6rem;font-weight:800;
          color:#fff;flex-shrink:0;box-shadow:0 4px 20px rgba(0,212,255,0.3)">
          ${(doc.name||'D').slice(0,2).toUpperCase()}
        </div>
        <div>
          <h2 style="margin:0 0 4px;font-size:1.2rem">Dr. ${escHtml(doc.name)}</h2>
          <div style="color:var(--cyan);font-size:0.875rem;font-weight:600">${escHtml(doc.specialty)} Specialist</div>
          <div style="font-size:0.78rem;color:var(--gold);margin-top:4px">${stars} ${accuracy}% accuracy</div>
          ${doc.verified ? '<span class="badge badge-green" style="margin-top:6px;display:inline-flex"><i class="fa fa-badge-check"></i> Verified</span>' : ''}
        </div>
      </div>

      <!-- Stats Row -->
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px">
        ${statBox('fa-pen-nib','Total', doc.stats?.total_annotations ?? 0, 'Annotations', 'cyan')}
        ${statBox('fa-check-circle','Approved', doc.stats?.approved ?? 0, 'Images', 'green')}
        ${statBox('fa-chart-line','Accuracy', accuracy + '%', '', 'gold')}
      </div>

      <!-- Details -->
      <div style="display:grid;gap:10px">
        ${infoRow('fa-id-card',    'License',  doc.license_number || 'Not provided')}
        ${infoRow('fa-calendar',   'Member since', formatDate(doc.joined))}
        ${doc.experience_years ? infoRow('fa-clock','Experience', doc.experience_years + ' years') : ''}
        ${doc.bio ? infoRow('fa-circle-info','About', doc.bio) : ''}
      </div>

      <div style="margin-top:20px;display:flex;justify-content:flex-end">
        <button onclick="document.getElementById('doctor-profile-modal').remove()"
          class="btn btn-ghost">Close</button>
      </div>
    </div>`;

  document.body.appendChild(modal);
  modal.addEventListener('click', e => { if(e.target===modal) modal.remove(); });
}

function statBox(icon, label, val, sub, color) {
  return `<div style="background:var(--bg-secondary);border-radius:10px;padding:14px;text-align:center;border:1px solid var(--border)">
    <i class="fa ${icon}" style="color:var(--${color});margin-bottom:6px;display:block"></i>
    <div style="font-size:1.2rem;font-weight:800;color:var(--${color})">${escHtml(String(val))}</div>
    <div style="font-size:0.7rem;color:var(--text-muted)">${label}</div>
    ${sub ? `<div style="font-size:0.68rem;color:var(--text-muted)">${sub}</div>` : ''}
  </div>`;
}

function infoRow(icon, label, val) {
  return `<div style="display:flex;align-items:flex-start;gap:12px;padding:10px;
    background:var(--bg-secondary);border-radius:8px;border:1px solid var(--border)">
    <i class="fa ${icon}" style="color:var(--cyan);margin-top:2px;width:16px;text-align:center"></i>
    <div>
      <div style="font-size:0.72rem;color:var(--text-muted);margin-bottom:2px">${label}</div>
      <div style="font-size:0.875rem">${escHtml(String(val))}</div>
    </div>
  </div>`;
}

// ── REVOKE ANNOTATION ──────────────────────────────
async function revokeImage(imageId, filename) {
  const reason = prompt(
    `Revoke annotation for "${filename}"?\n\nReason (required):`,
    'Annotation quality not satisfactory — please re-annotate'
  );
  if (!reason) return;

  const btn = document.querySelector(`[onclick*="revokeImage('${imageId}"]`);
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner" style="width:14px;height:14px"></span>'; }

  const res = await api.post(`/images/${imageId}/revoke`, { reason });
  if (res?.ok) {
    showToast(`Image revoked! New doctor: ${res.data.new_doctor}`, 'success');
    setTimeout(() => loadImages(currentFilter), 1000);
  } else {
    showToast(res?.data?.error || 'Revoke failed', 'error');
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa fa-rotate-left"></i> Revoke'; }
  }
}

async function downloadAnnotation(imageId) {
  showToast('Preparing annotation data...', 'info');
  const res = await api.get(`/annotations/image/${imageId}`);
  if (!res?.ok || !res.data.annotation) {
    showToast('No annotation data available', 'warning');
    return;
  }
  const ann  = res.data.annotation;
  const data = {
    image_id:    imageId,
    labels:      ann.labels,
    bounding_boxes: ann.bounding_boxes,
    confidence:  ann.confidence,
    department:  ann.department,
    doctor:      ann.doctor_name,
    notes:       ann.notes,
    exported_at: new Date().toISOString()
  };
  const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
  const a    = document.createElement('a');
  a.href     = URL.createObjectURL(blob);
  a.download = `annotation_${imageId.slice(-8)}.json`;
  a.click();
  showToast('Annotation downloaded!', 'success');
}

// ── UTILS ──────────────────────────────────────────
function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = String(val);
}
function escHtml(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

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
