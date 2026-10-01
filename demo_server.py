"""
MedAnnotate - Demo Mode Server
Runs without needing MongoDB. Uses in-memory storage for demo.
Perfect for testing the UI/frontend.
"""
from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt as pyjwt
import os
import uuid
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='frontend', static_url_path='')
CORS(app, resources={r"/api/*": {"origins": "*"}})

SECRET_KEY = "medannotate-demo-secret-2026"
PAY_PER_IMAGE = 4.0

# ========== IN-MEMORY STORE ==========
users = {}
images_store = {}
annotations_store = {}
payouts_store = {}

def seed_demo_data():
    """Pre-seed with demo users."""
    # Admin
    users['admin-001'] = {
        'id': 'admin-001', 'name': 'Super Admin',
        'email': 'admin@medannotate.com',
        'password': generate_password_hash('Admin@1234'),
        'role': 'admin', 'verified': True,
        'created_at': datetime.utcnow().isoformat(),
        'total_earnings': 0
    }
    # Demo doctor
    users['doctor-001'] = {
        'id': 'doctor-001', 'name': 'Dr. Sarah Johnson',
        'email': 'doctor@demo.com',
        'password': generate_password_hash('Doctor@1234'),
        'role': 'doctor', 'verified': True,
        'specialty': 'Radiology',
        'license_number': 'RAD-2024-001',
        'created_at': datetime.utcnow().isoformat(),
        'total_earnings': 48.0
    }
    # Demo company
    users['company-001'] = {
        'id': 'company-001', 'name': 'DeepMed AI',
        'email': 'company@demo.com',
        'password': generate_password_hash('Company@1234'),
        'role': 'company', 'verified': True,
        'company_name': 'DeepMed AI Inc.',
        'created_at': datetime.utcnow().isoformat(),
        'total_earnings': 0
    }
    # Demo images
    for i in range(1, 13):
        img_id = f'img-{i:04d}'
        depts = ['Radiology', 'Dermatology', 'Neurology', 'Oncology', 'Radiology', 'Radiology']
        status = ['assigned', 'assigned', 'assigned', 'annotating', 'qa_review', 'approved',
                  'approved', 'assigned', 'annotating', 'approved', 'qa_review', 'assigned'][i-1]
        images_store[img_id] = {
            'id': img_id,
            'filename': f'scan_{i:04d}.dcm',
            'department': depts[i % len(depts)],
            'status': status,
            'company_id': 'company-001',
            'company_name': 'DeepMed AI Inc.',
            'assigned_doctor_id': 'doctor-001',
            'anonymized': True,
            'created_at': (datetime.utcnow() - timedelta(days=i)).isoformat()
        }

seed_demo_data()

# ========== AUTH HELPERS ==========
def make_token(user_id, role):
    payload = {'sub': user_id, 'role': role, 'exp': datetime.utcnow() + timedelta(days=7)}
    return pyjwt.encode(payload, SECRET_KEY, algorithm='HS256')

def get_current_user():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '): return None
    token = auth[7:]
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return users.get(payload.get('sub'))
    except Exception:
        return None

def user_to_dict(u):
    d = {k: v for k, v in u.items() if k != 'password'}
    return d

# ========== AUTH ROUTES ==========
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email', '').lower()
    if any(u['email'] == email for u in users.values()):
        return jsonify({'error': 'Email already registered'}), 400
    uid = str(uuid.uuid4())[:12]
    role = data.get('role', 'doctor')
    user = {
        'id': uid, 'name': data.get('name'),
        'email': email, 'password': generate_password_hash(data.get('password', '')),
        'role': role, 'verified': role == 'company',
        'specialty': data.get('specialty', ''),
        'license_number': data.get('license_number', ''),
        'company_name': data.get('company_name', ''),
        'created_at': datetime.utcnow().isoformat(),
        'total_earnings': 0
    }
    users[uid] = user
    token = make_token(uid, role)
    return jsonify({'token': token, 'user': user_to_dict(user)}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').lower()
    u = next((u for u in users.values() if u['email'] == email), None)
    if not u or not check_password_hash(u['password'], data.get('password', '')):
        return jsonify({'error': 'Invalid email or password'}), 401
    token = make_token(u['id'], u['role'])
    return jsonify({'token': token, 'user': user_to_dict(u)}), 200

@app.route('/api/auth/me', methods=['GET'])
def me():
    u = get_current_user()
    if not u: return jsonify({'error': 'Unauthorized'}), 401
    return jsonify(user_to_dict(u)), 200

# ========== IMAGE ROUTES ==========
@app.route('/api/images/', methods=['GET'])
def list_images():
    u = get_current_user()
    if not u: return jsonify({'error': 'Unauthorized'}), 401
    status_filter = request.args.get('status')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))

    imgs = list(images_store.values())
    if u['role'] == 'doctor':
        imgs = [i for i in imgs if i.get('assigned_doctor_id') == u['id']]
    if status_filter:
        imgs = [i for i in imgs if i['status'] == status_filter]

    imgs.sort(key=lambda x: x['created_at'], reverse=True)
    total = len(imgs)
    start = (page - 1) * per_page
    return jsonify({
        'images': imgs[start:start+per_page],
        'total': total, 'page': page,
        'pages': max(1, (total + per_page - 1) // per_page)
    }), 200

@app.route('/api/images/<img_id>', methods=['GET'])
def get_image(img_id):
    img = images_store.get(img_id)
    if not img: return jsonify({'error': 'Not found'}), 404
    return jsonify(img), 200

@app.route('/api/images/upload', methods=['POST'])
def upload_image():
    u = get_current_user()
    if not u: return jsonify({'error': 'Unauthorized'}), 401
    dept = request.form.get('department', 'Radiology')
    file = request.files.get('file')
    filename = file.filename if file else 'demo_scan.dcm'

    if not dept:
        # simple keyword detection
        keywords = filename.lower()
        if any(w in keywords for w in ['xray','x-ray','chest','lung','bone']): dept = 'Radiology'
        elif any(w in keywords for w in ['skin','derm','mole']): dept = 'Dermatology'
        elif any(w in keywords for w in ['brain','neuro','mri']): dept = 'Neurology'
        else: dept = 'Radiology'

    img_id = 'img-' + str(uuid.uuid4())[:8]
    # Find a matching verified doctor
    matching = [u2 for u2 in users.values()
                if u2['role'] == 'doctor' and u2.get('verified') and u2.get('specialty') == dept]
    assigned_id = matching[0]['id'] if matching else 'doctor-001'

    images_store[img_id] = {
        'id': img_id, 'filename': filename, 'department': dept,
        'status': 'assigned',
        'company_id': u['id'], 'company_name': u.get('company_name', u['name']),
        'assigned_doctor_id': assigned_id,
        'anonymized': True,
        'created_at': datetime.utcnow().isoformat(),
        'detection': {'method': 'keyword', 'confidence': 0.75}
    }
    return jsonify({'image_id': img_id, 'department': dept,
                    'detection': {'method': 'keyword', 'confidence': 0.75}}), 201

@app.route('/api/images/departments/stats', methods=['GET'])
def dept_stats():
    counts = {}
    for img in images_store.values():
        d = img['department']
        counts[d] = counts.get(d, 0) + 1
    result = [{'department': k, 'count': v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]
    return jsonify(result), 200

# ========== ANNOTATION ROUTES ==========
@app.route('/api/annotations/', methods=['POST'])
def save_annotation():
    u = get_current_user()
    if not u: return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    img_id = data.get('image_id')
    ann_id = 'ann-' + str(uuid.uuid4())[:8]
    annotations_store[ann_id] = {
        'id': ann_id, 'image_id': img_id,
        'doctor_id': u['id'], 'doctor_name': u['name'],
        'labels': data.get('labels', []),
        'notes': data.get('notes', ''),
        'confidence': data.get('confidence', 80),
        'canvas_data': data.get('canvas_data', ''),
        'status': 'draft',
        'created_at': datetime.utcnow().isoformat()
    }
    if img_id in images_store:
        images_store[img_id]['status'] = 'annotating'
    return jsonify({'annotation_id': ann_id, 'status': 'saved'}), 201

@app.route('/api/annotations/<ann_id>/submit', methods=['POST'])
def submit_annotation(ann_id):
    u = get_current_user()
    if not u: return jsonify({'error': 'Unauthorized'}), 401
    ann = annotations_store.get(ann_id)
    if not ann: return jsonify({'error': 'Not found'}), 404
    ann['status'] = 'submitted'
    ann['submitted_at'] = datetime.utcnow().isoformat()
    if ann['image_id'] in images_store:
        images_store[ann['image_id']]['status'] = 'qa_review'
    return jsonify({'status': 'submitted'}), 200

@app.route('/api/annotations/<ann_id>/qa', methods=['POST'])
def qa_review(ann_id):
    u = get_current_user()
    if not u: return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    ann = annotations_store.get(ann_id)
    if not ann: return jsonify({'error': 'Not found'}), 404
    decision = data.get('decision')
    ann['status'] = 'qa_approved' if decision == 'approve' else 'qa_rejected'
    ann['qa_by'] = u['id']
    ann['qa_comment'] = data.get('comment', '')
    ann['qa_at'] = datetime.utcnow().isoformat()
    if ann['image_id'] in images_store:
        images_store[ann['image_id']]['status'] = 'approved' if decision == 'approve' else 'rejected'
    if decision == 'approve':
        # Create payout
        pay_id = 'pay-' + str(uuid.uuid4())[:8]
        doctor = users.get(ann['doctor_id'], {})
        img = images_store.get(ann['image_id'], {})
        payouts_store[pay_id] = {
            'id': pay_id, 'doctor_id': ann['doctor_id'],
            'doctor_name': doctor.get('name', '—'),
            'specialty': doctor.get('specialty', '—'),
            'image_id': ann['image_id'],
            'image_filename': img.get('filename', '—'),
            'annotation_id': ann_id,
            'amount': PAY_PER_IMAGE, 'status': 'pending',
            'created_at': datetime.utcnow().isoformat()
        }
        if ann['doctor_id'] in users:
            users[ann['doctor_id']]['total_earnings'] = users[ann['doctor_id']].get('total_earnings', 0) + PAY_PER_IMAGE
    return jsonify({'status': ann['status']}), 200

@app.route('/api/annotations/my-stats', methods=['GET'])
def my_stats():
    u = get_current_user()
    if not u: return jsonify({'error': 'Unauthorized'}), 401
    my_imgs = [i for i in images_store.values() if i.get('assigned_doctor_id') == u['id']]
    my_anns = [a for a in annotations_store.values() if a['doctor_id'] == u['id']]
    approved = sum(1 for a in my_anns if a['status'] == 'qa_approved')
    pending_qa = sum(1 for a in my_anns if a['status'] == 'submitted')
    rejected  = sum(1 for a in my_anns if a['status'] == 'qa_rejected')
    drafts    = sum(1 for a in my_anns if a['status'] == 'draft')
    paid_amount = sum(p['amount'] for p in payouts_store.values()
                      if p['doctor_id'] == u['id'] and p['status'] == 'paid')
    pending_amount = sum(p['amount'] for p in payouts_store.values()
                         if p['doctor_id'] == u['id'] and p['status'] == 'pending')
    total = paid_amount + pending_amount
    assigned = sum(1 for i in my_imgs if i['status'] == 'assigned')
    return jsonify({
        'assigned_images': assigned,
        'approved': approved,
        'pending_qa': pending_qa,
        'rejected': rejected,
        'drafts': drafts,
        'earnings': {
            'paid': paid_amount,
            'pending': pending_amount,
            'total': total,
            'per_image': PAY_PER_IMAGE
        }
    }), 200

@app.route('/api/annotations/image/<img_id>', methods=['GET'])
def get_image_annotation(img_id):
    ann = next((a for a in annotations_store.values() if a['image_id'] == img_id), None)
    return jsonify({'annotation': ann}), 200

@app.route('/api/annotations/qa-queue', methods=['GET'])
def qa_queue():
    u = get_current_user()
    if not u: return jsonify({'error': 'Unauthorized'}), 401
    queue = []
    for ann in annotations_store.values():
        if ann['status'] == 'submitted' and ann['doctor_id'] != u['id']:
            img = images_store.get(ann['image_id'], {})
            queue.append({
                'annotation_id': ann['id'],
                'image_id': ann['image_id'],
                'filename': img.get('filename', '—'),
                'department': img.get('department', '—'),
                'annotating_doctor': ann.get('doctor_name', '—'),
                'label_count': len(ann.get('labels', [])),
                'submitted_at': ann.get('submitted_at', ann['created_at'])
            })
    return jsonify({'queue': queue}), 200

# ========== ADMIN ROUTES ==========
@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    u = get_current_user()
    if not u: return jsonify({'error': 'Unauthorized'}), 401
    all_doctors = [u2 for u2 in users.values() if u2['role'] == 'doctor']
    verified = sum(1 for d in all_doctors if d.get('verified'))
    pending_v = sum(1 for d in all_doctors if not d.get('verified'))
    companies = sum(1 for u2 in users.values() if u2['role'] == 'company')
    total_imgs = len(images_store)
    pending_pay = [p for p in payouts_store.values() if p['status'] == 'pending']
    return jsonify({
        'doctors': {'total': len(all_doctors), 'verified': verified, 'pending_verification': pending_v},
        'companies': companies,
        'images': {'total': total_imgs},
        'payouts': {
            'pending_count': len(pending_pay),
            'pending_amount': sum(p['amount'] for p in pending_pay)
        },
        'annotations_today': len([a for a in annotations_store.values()
                                   if a['created_at'][:10] == datetime.utcnow().strftime('%Y-%m-%d')])
    }), 200

@app.route('/api/admin/doctors', methods=['GET'])
def admin_doctors():
    verified_filter = request.args.get('verified')
    docs = [user_to_dict(u) for u in users.values() if u['role'] == 'doctor']
    if verified_filter == 'false':
        docs = [d for d in docs if not d.get('verified')]
    elif verified_filter == 'true':
        docs = [d for d in docs if d.get('verified')]
    return jsonify({'doctors': docs}), 200

@app.route('/api/admin/doctors/<doc_id>/verify', methods=['POST'])
def verify_doctor(doc_id):
    if doc_id not in users: return jsonify({'error': 'Not found'}), 404
    users[doc_id]['verified'] = True
    return jsonify({'status': 'verified'}), 200

@app.route('/api/admin/doctors/<doc_id>/reject', methods=['POST'])
def reject_doctor(doc_id):
    if doc_id not in users: return jsonify({'error': 'Not found'}), 404
    users[doc_id]['verified'] = False
    users[doc_id]['rejection_reason'] = request.json.get('reason', '')
    return jsonify({'status': 'rejected'}), 200

@app.route('/api/admin/payouts', methods=['GET'])
def admin_payouts():
    status_filter = request.args.get('status')
    pays = list(payouts_store.values())
    if status_filter:
        pays = [p for p in pays if p['status'] == status_filter]
    pays.sort(key=lambda p: p['created_at'], reverse=True)
    return jsonify({'payouts': pays}), 200

@app.route('/api/admin/payouts/<pay_id>/pay', methods=['POST'])
def mark_paid(pay_id):
    if pay_id not in payouts_store: return jsonify({'error': 'Not found'}), 404
    payouts_store[pay_id]['status'] = 'paid'
    payouts_store[pay_id]['paid_at'] = datetime.utcnow().isoformat()
    return jsonify({'status': 'paid'}), 200

@app.route('/api/admin/companies', methods=['GET'])
def admin_companies():
    companies = [user_to_dict(u) for u in users.values() if u['role'] == 'company']
    for c in companies:
        c['image_count'] = sum(1 for i in images_store.values() if i.get('company_id') == c['id'])
    return jsonify({'companies': companies}), 200

@app.route('/api/admin/images', methods=['GET'])
def admin_images():
    imgs = sorted(images_store.values(), key=lambda x: x['created_at'], reverse=True)
    return jsonify({'images': list(imgs)[:50]}), 200

@app.route('/api/admin/seed', methods=['POST'])
def seed():
    return jsonify({'message': 'Demo mode: admin already seeded. Email: admin@medannotate.com / Admin@1234'}), 200

# ========== FRONTEND ROUTES ==========
@app.route('/')
def index():        return send_from_directory('frontend', 'index.html')
@app.route('/login')
def login_page():   return send_from_directory('frontend', 'login.html')
@app.route('/register')
def register_page(): return send_from_directory('frontend', 'register.html')
@app.route('/doctor/dashboard')
def doctor_dash():  return send_from_directory('frontend/doctor', 'dashboard.html')
@app.route('/doctor/annotate')
def doctor_ann():   return send_from_directory('frontend/doctor', 'annotate.html')
@app.route('/doctor/earnings')
def doctor_earn():  return send_from_directory('frontend/doctor', 'earnings.html')
@app.route('/company/dashboard')
def company_dash(): return send_from_directory('frontend/company', 'dashboard.html')
@app.route('/company/upload')
def company_up():   return send_from_directory('frontend/company', 'upload.html')
@app.route('/company/batches')
def company_bat():  return send_from_directory('frontend/company', 'batches.html')
@app.route('/admin/dashboard')
def admin_dash():   return send_from_directory('frontend/admin', 'dashboard.html')
@app.route('/css/<path:filename>')
def css(filename):  return send_from_directory('frontend/css', filename)
@app.route('/js/<path:filename>')
def js(filename):   return send_from_directory('frontend/js', filename)

@app.errorhandler(404)
def not_found(e): return jsonify({'error': 'Not found'}), 404

if __name__ == '__main__':
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print("\n" + "="*55)
    print("  MedAnnotate -- DEMO MODE (no MongoDB needed)")
    print("="*55)
    print("  URL:  http://localhost:5000")
    print("")
    print("  Demo Credentials:")
    print("  [Doctor]  doctor@demo.com   / Doctor@1234")
    print("  [Company] company@demo.com  / Company@1234")
    print("  [Admin]   admin@medannotate.com / Admin@1234")
    print("="*55 + "\n")
    app.run(debug=False, host='0.0.0.0', port=5000)

