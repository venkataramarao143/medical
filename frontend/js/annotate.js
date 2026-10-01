// Fabric.js Annotation Engine — Fixed image loading with JWT auth

let canvas, imageId, imageData, annotationId = null;
let currentTool  = 'select';
let currentLabel = 'Anomaly';
let currentColor = '#00d4ff';
let tempRect     = null;
let history = [], historyIndex = -1;
let startTime = Date.now();

document.addEventListener('DOMContentLoaded', async () => {
  const user = requireAuth(['doctor']);
  if (!user) return;

  const params = new URLSearchParams(window.location.search);
  imageId = params.get('id');
  if (!imageId) { showToast('No image ID specified', 'error'); return; }

  const area = document.getElementById('canvas-area');
  canvas = new fabric.Canvas('annotation-canvas', {
    selection: true,
    backgroundColor: '#0a0f1e'
  });
  resizeCanvas();

  // Load image metadata + image file
  await loadImageData();
  // Load existing annotation if any (restore notes/confidence/labels)
  await loadExistingAnnotation();
  // Set up drawing events
  initCanvasEvents();
  // Color picker
  document.getElementById('color-picker').addEventListener('input', e => { currentColor = e.target.value; });

  window.addEventListener('resize', resizeCanvas);

  // Live annotation timer
  const timerEl = document.getElementById('timer');
  if (timerEl) {
    setInterval(() => {
      const secs = Math.floor((Date.now() - startTime) / 1000);
      timerEl.textContent = String(Math.floor(secs / 60)).padStart(2,'0') + ':' + String(secs % 60).padStart(2,'0');
    }, 1000);
  }
});

function resizeCanvas() {
  const area = document.getElementById('canvas-area');
  if (canvas) {
    canvas.setWidth( area.clientWidth  - 20);
    canvas.setHeight(area.clientHeight - 20);
    canvas.renderAll();
  }
}

// ── LOAD IMAGE DATA + IMAGE FILE ───────────────────────────────────────────
async function loadImageData() {
  const res = await api.get(`/images/${imageId}`);
  if (!res.ok) { showToast('Could not load image', 'error'); return; }
  imageData = res.data;

  document.getElementById('top-filename').textContent = imageData.filename || imageId;
  document.getElementById('top-dept').textContent     = imageData.department;
  document.getElementById('info-id').textContent      = imageId.slice(-10).toUpperCase();
  document.getElementById('info-dept').textContent    = imageData.department;
  document.getElementById('info-status').innerHTML    = statusBadge(imageData.status);

  // Department-specific labels
  const labelMap = {
    'Radiology':       ['Fracture','Nodule','Mass','Pneumonia','Pleural Effusion','Cardiomegaly','Normal'],
    'Dermatology':     ['Melanoma','Lesion','Rash','Benign Nevus','Basal Cell','Normal'],
    'Neurology':       ['Tumor','Hemorrhage','Infarct','WM Lesion','Aneurysm','Normal'],
    'Oncology':        ['Tumor','Metastasis','Lymph Node','Mass','Normal'],
    'Ophthalmology':   ['Diabetic Retinopathy','Glaucoma','Macular Degen.','Cataract','Normal'],
    'Cardiology':      ['Stenosis','Calcification','Aneurysm','Cardiomegaly','Normal'],
    'Orthopedics':     ['Fracture','Dislocation','Arthritis','Bone Spur','Normal'],
    'Pathology':       ['Malignant','Benign','Inflammation','Necrosis','Normal'],
    'Gastroenterology':['Polyp','Ulcer','Mass','Inflammation','Normal'],
    'Pulmonology':     ['Nodule','Consolidation','Effusion','Pneumothorax','Normal']
  };
  const labels = labelMap[imageData.department] || ['Anomaly','Normal','Tumor','Fracture','Other'];
  const grid   = document.getElementById('label-grid');
  grid.innerHTML = labels.map((l, i) =>
    `<div class="label-chip ${i === 0 ? 'selected' : ''}" onclick="selectLabel(this,'${l}')" data-label="${l}">${l}</div>`
  ).join('');
  currentLabel = labels[0];

  // ── KEY FIX: fabric.Image.fromURL does NOT support Authorization headers.
  // We fetch() the raw bytes with the JWT token ourselves, create a blob URL
  // (which needs no auth), and pass THAT to Fabric.
  const loading = document.getElementById('canvas-loading');
  try {
    const token  = getToken();
    const resp   = await fetch(`/api/images/${imageId}/file`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob    = await resp.blob();
    const blobUrl = URL.createObjectURL(blob);

    fabric.Image.fromURL(blobUrl, (img) => {
      if (!img || !img.width) {
        showDicomPlaceholder();
        if (loading) loading.style.display = 'none';
        URL.revokeObjectURL(blobUrl);
        return;
      }
      const area  = document.getElementById('canvas-area');
      const maxW  = area.clientWidth  - 40;
      const maxH  = area.clientHeight - 40;
      const scale = Math.min(maxW / img.width, maxH / img.height, 1);
      img.scale(scale);
      img.set({
        left: (canvas.width  - img.getScaledWidth())  / 2,
        top:  (canvas.height - img.getScaledHeight()) / 2,
        selectable: false, evented: false
      });
      canvas.add(img);
      canvas.sendToBack(img);
      canvas.setWidth( Math.max(img.getScaledWidth()  + 40, maxW));
      canvas.setHeight(Math.max(img.getScaledHeight() + 40, maxH));
      canvas.renderAll();
      if (loading) loading.style.display = 'none';
      URL.revokeObjectURL(blobUrl);
    });
  } catch(err) {
    console.error('Image load error:', err);
    showToast(`Image load: ${err.message}. You can still annotate.`, 'warning');
    showDicomPlaceholder();
    if (loading) loading.style.display = 'none';
  }
}

function showDicomPlaceholder() {
  const rect = new fabric.Rect({
    left: 40, top: 40, width: canvas.width - 80, height: canvas.height - 80,
    fill: 'rgba(0,212,255,0.04)', stroke: 'rgba(0,212,255,0.25)',
    strokeWidth: 2, strokeDashArray: [8, 4], rx: 12, selectable: false, evented: false
  });
  const text = new fabric.Text('Medical Image\n\nAnnotate using the tools on the left →', {
    left: canvas.width / 2, top: canvas.height / 2,
    originX: 'center', originY: 'center',
    fontSize: 15, fill: 'rgba(0,212,255,0.55)',
    fontFamily: 'Inter, sans-serif', textAlign: 'center',
    selectable: false, evented: false
  });
  canvas.add(rect, text);
  canvas.sendToBack(rect);
  canvas.renderAll();
}

// ── LOAD EXISTING ANNOTATION ───────────────────────────────────────────────
async function loadExistingAnnotation() {
  const res = await api.get(`/annotations/image/${imageId}`);
  if (!res.ok || !res.data.annotation) return;
  const ann     = res.data.annotation;
  annotationId  = ann.id || ann._id;

  // Restore notes
  if (ann.notes) document.getElementById('notes').value = ann.notes;
  // Restore confidence
  if (ann.confidence) {
    document.getElementById('confidence').value = ann.confidence;
    document.getElementById('conf-val').textContent = ann.confidence + '%';
  }
  // Restore first label as selected
  if (ann.labels && ann.labels.length) {
    const firstLabel = ann.labels[0];
    document.querySelectorAll('.label-chip').forEach(chip => {
      if (chip.dataset.label === firstLabel) { chip.classList.add('selected'); currentLabel = firstLabel; }
      else chip.classList.remove('selected');
    });
  }
  // Note: we do NOT restore canvas_data to avoid showing old annotations
  // on top of freshly loaded image. Doctor must re-annotate if revoked.
}

// ── CANVAS EVENTS ──────────────────────────────────────────────────────────
function initCanvasEvents() {
  let isDown = false, origX, origY;

  canvas.on('mouse:down', (opt) => {
    if (currentTool !== 'rect') return;
    isDown = true;
    const ptr = canvas.getPointer(opt.e);
    origX = ptr.x; origY = ptr.y;
    tempRect = new fabric.Rect({
      left: origX, top: origY, width: 0, height: 0,
      stroke: currentColor, strokeWidth: 2.5,
      fill: currentColor.replace(')', ',0.1)').replace('rgb', 'rgba'),
      strokeDashArray: [4, 2], selectable: true, hasControls: true,
      _label: currentLabel
    });
    canvas.add(tempRect);
  });

  canvas.on('mouse:move', (opt) => {
    if (!isDown || currentTool !== 'rect' || !tempRect) return;
    const ptr = canvas.getPointer(opt.e);
    if (ptr.x < origX) tempRect.set({ left: ptr.x, width: origX - ptr.x });
    else               tempRect.set({ width: ptr.x - origX });
    if (ptr.y < origY) tempRect.set({ top: ptr.y, height: origY - ptr.y });
    else               tempRect.set({ height: ptr.y - origY });
    canvas.renderAll();
  });

  canvas.on('mouse:up', () => {
    if (!isDown || currentTool !== 'rect' || !tempRect) return;
    isDown = false;
    if (tempRect.width < 5 || tempRect.height < 5) { canvas.remove(tempRect); tempRect = null; return; }
    // Label text above box
    const text = new fabric.Text(currentLabel, {
      left: tempRect.left + 4, top: tempRect.top - 18,
      fontSize: 12, fill: currentColor, fontFamily: 'Inter, sans-serif',
      fontWeight: 'bold', selectable: false, evented: false, shadow: '0 1px 3px rgba(0,0,0,0.8)',
      _label: currentLabel
    });
    canvas.add(text);
    saveHistory();
    updateAnnotationsList();
    tempRect = null;
  });

  canvas.on('path:created', (opt) => {
    opt.path.set({ stroke: currentColor, strokeWidth: 2.5, _label: currentLabel });
    saveHistory();
    updateAnnotationsList();
  });

  canvas.on('object:modified', () => { saveHistory(); });
}

// ── TOOLS ──────────────────────────────────────────────────────────────────
function setTool(tool) {
  currentTool = tool;
  document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById(`tool-${tool}`);
  if (btn) btn.classList.add('active');

  canvas.isDrawingMode = (tool === 'draw');
  canvas.selection     = (tool === 'select');

  if (tool === 'draw') {
    canvas.freeDrawingBrush.color = currentColor;
    canvas.freeDrawingBrush.width = 3;
  }
}

function selectLabel(el, label) {
  document.querySelectorAll('.label-chip').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  currentLabel = label;
}

function addCustomLabel() {
  const input = document.getElementById('custom-label');
  const label = input.value.trim();
  if (!label) return;
  const grid = document.getElementById('label-grid');
  const chip = document.createElement('div');
  chip.className = 'label-chip selected';
  chip.dataset.label = label;
  chip.textContent = label;
  chip.onclick = () => selectLabel(chip, label);
  document.querySelectorAll('.label-chip').forEach(c => c.classList.remove('selected'));
  grid.appendChild(chip);
  currentLabel = label;
  input.value  = '';
}

function updateAnnotationsList() {
  const objects = canvas.getObjects().filter(o => o.type !== 'image');
  const rects   = objects.filter(o => o.type === 'rect');
  const paths   = objects.filter(o => o.type === 'path');
  document.getElementById('ann-count').textContent = rects.length + paths.length;

  const colors = ['#00d4ff','#22c55e','#f59e0b','#ef4444','#7c3aed','#f97316'];
  const list   = document.getElementById('annotations-list');
  if (rects.length + paths.length === 0) {
    list.innerHTML = '<p style="font-size:0.8rem;color:var(--text-muted);">Draw on the image to add annotations.</p>';
    return;
  }
  list.innerHTML = [
    ...rects.map((r, i) => `<div class="ann-chip"><div class="dot" style="background:${colors[i%colors.length]};"></div><span style="flex:1;">${r._label||'Box '+(i+1)}</span></div>`),
    ...paths.map((p, i) => `<div class="ann-chip"><div class="dot" style="background:${colors[(i+rects.length)%colors.length]};border-radius:2px;"></div><span style="flex:1;">${p._label||'Path '+(i+1)}</span></div>`)
  ].join('');
}

function deleteSelected() {
  const activeObjs = canvas.getActiveObjects();
  if (!activeObjs.length) return;
  activeObjs.forEach(o => canvas.remove(o));
  canvas.discardActiveObject();
  canvas.renderAll();
  saveHistory();
  updateAnnotationsList();
}

function clearAll() {
  if (!confirm('Clear all annotations? This cannot be undone.')) return;
  canvas.getObjects().filter(o => o.type !== 'image').forEach(o => canvas.remove(o));
  canvas.renderAll();
  updateAnnotationsList();
}

function zoomIn()    { canvas.setZoom(canvas.getZoom() * 1.2);  canvas.renderAll(); }
function zoomOut()   { canvas.setZoom(canvas.getZoom() * 0.8);  canvas.renderAll(); }
function resetZoom() { canvas.setZoom(1); canvas.setViewportTransform([1,0,0,1,0,0]); canvas.renderAll(); }

function saveHistory() {
  historyIndex++;
  history = history.slice(0, historyIndex);
  history.push(JSON.stringify(canvas.toJSON(['_label'])));
}

function undoAction() {
  if (historyIndex <= 0) return;
  historyIndex--;
  restoreHistory();
}

function redoAction() {
  if (historyIndex >= history.length - 1) return;
  historyIndex++;
  restoreHistory();
}

function restoreHistory() {
  canvas.loadFromJSON(history[historyIndex], () => {
    canvas.getObjects().forEach(o => { if (o.type === 'image') canvas.sendToBack(o); });
    canvas.renderAll();
    updateAnnotationsList();
  });
}

// ── BUILD PAYLOAD ──────────────────────────────────────────────────────────
function getAnnotationPayload() {
  const objects = canvas.getObjects().filter(o => o.type !== 'image');
  const rects   = objects.filter(o => o.type === 'rect');

  // Collect all labels from drawn objects + currently selected label
  const usedLabels = [...new Set(objects.map(o => o._label || currentLabel).filter(Boolean))];
  if (!usedLabels.includes(currentLabel)) usedLabels.push(currentLabel);

  // Build bounding boxes with labels
  const bboxes = rects.map(r => ({
    label: r._label || currentLabel,
    x: Math.round(r.left),
    y: Math.round(r.top),
    w: Math.round((r.width  || 0) * (r.scaleX || 1)),
    h: Math.round((r.height || 0) * (r.scaleY || 1))
  }));

  const secs = Math.floor((Date.now() - startTime) / 1000);

  return {
    image_id:       imageId,
    canvas_data:    JSON.stringify(canvas.toJSON(['_label'])),
    labels:         usedLabels,
    bounding_boxes: bboxes,
    notes:          document.getElementById('notes').value.trim(),
    confidence:     parseInt(document.getElementById('confidence').value || '80'),
    time_spent_sec: secs
  };
}

// ── SAVE DRAFT ─────────────────────────────────────────────────────────────
async function saveDraft() {
  const payload = getAnnotationPayload();
  const btn     = document.querySelector('[onclick="saveDraft()"]');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner" style="width:14px;height:14px"></span>'; }

  const res = await api.post('/annotations/', payload);
  if (res.ok) {
    annotationId = res.data.annotation_id;
    showToast('Draft saved successfully', 'success');
  } else {
    showToast(res.data.error || 'Failed to save draft', 'error');
  }
  if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa fa-floppy-disk"></i> Save Draft'; }
}

// ── SUBMIT FOR REVIEW ──────────────────────────────────────────────────────
async function submitAnnotation() {
  const objects = canvas.getObjects().filter(o => o.type !== 'image');
  if (objects.length === 0) {
    showToast('Please add at least one annotation before submitting', 'warning');
    return;
  }

  const payload  = getAnnotationPayload();
  const saveRes  = await api.post('/annotations/', payload);
  if (!saveRes.ok) { showToast(saveRes.data.error || 'Failed to save', 'error'); return; }
  annotationId   = saveRes.data.annotation_id;

  const submitRes = await api.post(`/annotations/${annotationId}/submit`, {});
  if (submitRes.ok) {
    showToast('🎉 Annotation submitted to company for review!', 'success');
    setTimeout(() => window.location.href = '/doctor/dashboard', 1500);
  } else {
    showToast(submitRes.data.error || 'Failed to submit', 'error');
  }
}
