// Image Upload Logic

let selectedFiles = [];
let autoDetect = true;

document.addEventListener('DOMContentLoaded', () => {
  const user = requireAuth(['company']);
  if (!user) return;
  initNavbar(user);
  initDropZone();
});

function initDropZone() {
  const zone = document.getElementById('drop-zone');
  const input = document.getElementById('file-input');

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    addFiles(Array.from(e.dataTransfer.files));
  });
  input.addEventListener('change', e => addFiles(Array.from(e.target.files)));
}

function addFiles(files) {
  const allowed = ['jpg','jpeg','png','dcm','dicom','tiff','tif','bmp'];
  files.forEach(f => {
    const ext = f.name.split('.').pop().toLowerCase();
    if (!allowed.includes(ext)) { showToast(`${f.name} — unsupported format`, 'error'); return; }
    if (!selectedFiles.find(x => x.name === f.name && x.size === f.size)) selectedFiles.push(f);
  });
  renderFileList();
  updateStats();
}

function removeFile(idx) {
  selectedFiles.splice(idx, 1);
  renderFileList();
  updateStats();
}

function renderFileList() {
  const container = document.getElementById('file-list');
  if (!selectedFiles.length) { container.innerHTML = ''; return; }
  container.innerHTML = selectedFiles.map((f, i) => {
    const ext = f.name.split('.').pop().toLowerCase();
    const isDicom = ['dcm','dicom'].includes(ext);
    const size = f.size < 1024*1024 ? (f.size/1024).toFixed(0)+'KB' : (f.size/1024/1024).toFixed(1)+'MB';
    return `
      <div style="display:flex;align-items:center;gap:10px;background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:10px 14px;">
        <i class="fa fa-file-medical" style="color:${isDicom?'var(--orange)':'var(--cyan)'};font-size:1.1rem;"></i>
        <div style="flex:1;overflow:hidden;">
          <div style="font-size:0.85rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${f.name}</div>
          <div style="font-size:0.72rem;color:var(--text-secondary);">${size}</div>
        </div>
        ${isDicom ? '<span class="badge badge-gold" style="font-size:0.65rem;">DICOM → Anonymized</span>' : '<span class="badge badge-green" style="font-size:0.65rem;">Valid</span>'}
        <button onclick="removeFile(${i})" style="background:none;border:none;color:var(--text-muted);cursor:pointer;"><i class="fa fa-times"></i></button>
      </div>`;
  }).join('');
}

function updateStats() {
  const count = selectedFiles.length;
  document.getElementById('file-count').textContent = count;
  document.getElementById('est-cost').textContent   = '$' + (count * 4).toFixed(2);
  document.getElementById('est-time').textContent   = count ? Math.ceil(count / 10) + '-' + Math.ceil(count / 5) + ' hrs' : '—';
  document.getElementById('upload-btn').disabled = count === 0;
  document.getElementById('upload-btn-text').textContent = count > 0 ? `Upload ${count} Image${count>1?'s':''}` : 'Start Upload';
}

function toggleAutoDetect() {
  autoDetect = !autoDetect;
  const track = document.getElementById('toggle-track');
  track.classList.toggle('on', autoDetect);
}

async function startUpload() {
  if (!selectedFiles.length) return;
  const btn = document.getElementById('upload-btn');
  btn.disabled = true;
  document.getElementById('upload-progress-section').style.display = 'block';

  const dept = document.getElementById('department').value;
  const batchName = document.getElementById('batch-name').value || `Batch ${new Date().toLocaleDateString()}`;
  let uploaded = 0, failed = 0;

  for (let i = 0; i < selectedFiles.length; i++) {
    const file = selectedFiles[i];
    document.getElementById('upload-progress-text').textContent = `${i+1} / ${selectedFiles.length}`;
    document.getElementById('upload-bar').style.width = ((i / selectedFiles.length) * 100) + '%';
    document.getElementById('upload-current-file').textContent = `Uploading: ${file.name}`;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('department', dept);
    formData.append('auto_detect', autoDetect.toString());
    formData.append('batch_name', batchName);

    const res = await api.upload('/images/upload', formData);
    if (res && res.ok) {
      uploaded++;
      // Show detection result on first file
      if (i === 0 && res.data.detection) {
        const det = res.data.detection;
        document.getElementById('detection-preview').style.display = 'flex';
        document.getElementById('detection-result-text').textContent =
          `Detected: ${res.data.department} (${det.method === 'ai' ? 'AI' : 'Keyword'} · ${Math.round((det.confidence||0)*100)}% confidence)`;
      }
    } else {
      failed++;
      showToast(`Failed: ${file.name}`, 'error');
    }
  }

  document.getElementById('upload-bar').style.width = '100%';
  document.getElementById('upload-current-file').textContent = '✓ Upload complete!';
  document.getElementById('upload-progress-text').textContent = `${uploaded} uploaded`;

  showToast(`🎉 ${uploaded} image${uploaded>1?'s':''} uploaded successfully!${failed?' ('+failed+' failed)':''}`, 'success');
  selectedFiles = [];
  renderFileList();
  updateStats();

  setTimeout(() => window.location.href = '/company/batches', 2000);
}
