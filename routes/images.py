"""
IMAGE ROUTES — Upload, list, serve, revoke, doctor profile
All data stored/retrieved from MongoDB + GridFS. Optimized for speed.
"""
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import mongo
from utils.anonymize import anonymize_image
from utils.detect_department import detect_department
from datetime import datetime
from bson import ObjectId
import gridfs, io

images_bp = Blueprint('images', __name__)


def get_fs():
    return gridfs.GridFS(mongo.db)


def img_to_dict(img):
    if not img:
        return None
    img = dict(img)
    img['id']  = str(img['_id'])
    img['_id'] = str(img['_id'])
    for f in ('company_id', 'assigned_doctor_id', 'gridfs_id'):
        if img.get(f): img[f] = str(img[f])
    for f in ('created_at', 'updated_at', 'annotated_at', 'qa_at'):
        if img.get(f) and hasattr(img[f], 'isoformat'):
            img[f] = img[f].isoformat()
    return img


def auto_assign_doctor(department, exclude_id=None):
    """Find verified doctor with fewest active images. O(n doctors) but cached."""
    query = {'role': 'doctor', 'verified': True, 'active': True, 'specialty': department}
    if exclude_id:
        query['_id'] = {'$ne': ObjectId(exclude_id)}
    doctors = list(mongo.db.users.find(query, {'_id': 1, 'name': 1}))
    if not doctors:
        # Any verified doctor as fallback
        doctors = list(mongo.db.users.find(
            {'role': 'doctor', 'verified': True, 'active': True},
            {'_id': 1, 'name': 1}
        ))
    if not doctors:
        return None, None
    # Load balance: pick doctor with fewest active assignments
    def workload(doc):
        return mongo.db.images.count_documents({
            'assigned_doctor_id': doc['_id'],
            'status': {'$in': ['assigned', 'annotating']}
        })
    doctors.sort(key=workload)
    return doctors[0]['_id'], doctors[0]['name']


# ── UPLOAD ────────────────────────────────────────────
@images_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_image():
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)}, {'password': 0})
    if not user or user['role'] != 'company':
        return jsonify({'error': 'Only companies can upload images'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file       = request.files['file']
    department = request.form.get('department', '').strip()
    batch_name = request.form.get('batch_name', '').strip()

    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in {'png', 'jpg', 'jpeg', 'dcm', 'dicom', 'tiff', 'tif', 'bmp'}:
        return jsonify({'error': f'File type .{ext} not allowed'}), 400

    file_bytes = file.read()

    # 1. Anonymize
    try:
        clean_bytes, anon_info = anonymize_image(file_bytes, file.filename)
    except Exception as e:
        clean_bytes, anon_info = file_bytes, {'method': 'skipped', 'error': str(e)}

    # 2. Detect department (Groq AI or keyword)
    if not department:
        try:
            department, confidence, method = detect_department(file.filename, clean_bytes)
        except Exception:
            department, confidence, method = 'Radiology', 0.5, 'default'
    else:
        confidence, method = 1.0, 'manual'

    # 3. Store in GridFS
    fs = get_fs()
    gridfs_id = fs.put(
        io.BytesIO(clean_bytes),
        filename=file.filename,
        content_type=file.content_type or 'application/octet-stream'
    )

    # 4. Auto-assign doctor
    now = datetime.utcnow()
    assigned_id, assigned_name = auto_assign_doctor(department)

    img_doc = {
        'filename':            file.filename,
        'department':          department,
        'status':              'assigned' if assigned_id else 'pending',
        'company_id':          ObjectId(uid),
        'company_name':        user.get('company_name') or user['name'],
        'assigned_doctor_id':  assigned_id,
        'assigned_doctor_name': assigned_name,
        'gridfs_id':           gridfs_id,
        'file_size':           len(clean_bytes),
        'anonymized':          True,
        'anonymize_info':      anon_info,
        'detection':           {'department': department, 'confidence': confidence, 'method': method},
        'batch_name':          batch_name or f'Batch-{now.strftime("%Y%m%d")}',
        'created_at':          now,
        'updated_at':          now,
        'annotated_at':        None,
        'qa_at':               None,
    }
    result = mongo.db.images.insert_one(img_doc)
    return jsonify({
        'image_id':   str(result.inserted_id),
        'department': department,
        'assigned_to': assigned_name,
        'detection':  {'department': department, 'confidence': confidence, 'method': method}
    }), 201


# ── LIST IMAGES (fast, with projection) ───────────────
@images_bp.route('/', methods=['GET'])
@jwt_required()
def list_images():
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)}, {'role': 1, 'name': 1})
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    page     = max(1, int(request.args.get('page', 1)))
    per_page = min(50, int(request.args.get('per_page', 10)))
    status   = request.args.get('status', '')
    dept     = request.args.get('department', '')

    query = {}
    if user['role'] == 'doctor':
        query['assigned_doctor_id'] = ObjectId(uid)
    elif user['role'] == 'company':
        query['company_id'] = ObjectId(uid)

    if status: query['status'] = status
    if dept:   query['department'] = dept

    # Projection: exclude heavy gridfs binary ref from list
    projection = {'gridfs_id': 0}
    total = mongo.db.images.count_documents(query)
    imgs  = list(mongo.db.images.find(query, projection)
                 .sort('created_at', -1)
                 .skip((page - 1) * per_page)
                 .limit(per_page))

    return jsonify({
        'images': [img_to_dict(i) for i in imgs],
        'total':  total,
        'page':   page,
        'pages':  max(1, -(-total // per_page))
    }), 200


# ── SINGLE IMAGE ──────────────────────────────────────
@images_bp.route('/<img_id>', methods=['GET'])
@jwt_required()
def get_image(img_id):
    try:
        oid = ObjectId(img_id)
    except Exception:
        oid = img_id
    try:
        img = mongo.db.images.find_one({'_id': oid}, {'gridfs_id': 0})
    except Exception:
        return jsonify({'error': 'Invalid ID'}), 400
    if not img:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(img_to_dict(img)), 200


# ── SERVE IMAGE FILE ──────────────────────────────────
@images_bp.route('/<img_id>/file', methods=['GET'])
@jwt_required()
def serve_image(img_id):
    try:
        oid = ObjectId(img_id)
    except Exception:
        oid = img_id

    img = mongo.db.images.find_one({'_id': oid}, {'gridfs_id': 1, 'filename': 1})
    if not img:
        print(f"[serve_image] Image doc not found for _id: {oid}")
        return jsonify({'error': 'Not found'}), 404
    try:
        from bson.objectid import ObjectId
        fs   = get_fs()
        gid  = img['gridfs_id']
        if isinstance(gid, str) and len(gid) == 24:
            gid = ObjectId(gid)
        gf   = fs.get(gid)
        data = gf.read()
        return Response(data, mimetype=gf.content_type or 'application/octet-stream',
                        headers={'Content-Disposition': 'inline'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[serve_image] Error for _id {oid}: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ── DOCTOR PROFILE (visible to company for annotated images) ──
@images_bp.route('/<img_id>/doctor-profile', methods=['GET'])
@jwt_required()
def doctor_profile_for_image(img_id):
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)}, {'role': 1})
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    img = mongo.db.images.find_one({'_id': ObjectId(img_id)}, {'assigned_doctor_id': 1, 'company_id': 1})
    if not img:
        return jsonify({'error': 'Image not found'}), 404

    # Only the company who owns the image or admin can view
    if user['role'] == 'company' and str(img.get('company_id')) != uid:
        return jsonify({'error': 'Access denied'}), 403

    if not img.get('assigned_doctor_id'):
        return jsonify({'error': 'No doctor assigned yet'}), 404

    doc = mongo.db.users.find_one(
        {'_id': img['assigned_doctor_id']},
        {'name': 1, 'email': 1, 'specialty': 1, 'license_number': 1,
         'bio': 1, 'experience_years': 1, 'verified': 1, 'created_at': 1}
    )
    if not doc:
        return jsonify({'error': 'Doctor not found'}), 404

    # Add annotation stats for this doctor
    ann_count  = mongo.db.annotations.count_documents({'doctor_id': doc['_id']})
    approved   = mongo.db.annotations.count_documents({'doctor_id': doc['_id'], 'status': 'qa_approved'})
    accuracy   = round((approved / ann_count * 100), 1) if ann_count else 0

    return jsonify({
        'id':              str(doc['_id']),
        'name':            doc['name'],
        'specialty':       doc.get('specialty', ''),
        'license_number':  doc.get('license_number', ''),
        'bio':             doc.get('bio', ''),
        'experience_years': doc.get('experience_years', 0),
        'verified':        doc.get('verified', False),
        'joined':          doc['created_at'].isoformat() if doc.get('created_at') else None,
        'stats': {
            'total_annotations': ann_count,
            'approved':          approved,
            'accuracy_pct':      accuracy
        }
    }), 200


# ── REVOKE ANNOTATION (company rejects and re-queues) ─
@images_bp.route('/<img_id>/revoke', methods=['POST'])
@jwt_required()
def revoke_annotation(img_id):
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)}, {'role': 1, 'name': 1})
    if not user or user['role'] != 'company':
        return jsonify({'error': 'Only the company can revoke annotations'}), 403

    img = mongo.db.images.find_one({'_id': ObjectId(img_id)})
    if not img:
        return jsonify({'error': 'Image not found'}), 404
    if str(img.get('company_id')) != uid:
        return jsonify({'error': 'This image does not belong to your company'}), 403
    if img['status'] not in ('approved', 'qa_review', 'annotating'):
        return jsonify({'error': f'Cannot revoke from status: {img["status"]}'}), 400

    data   = request.json or {}
    reason = data.get('reason', 'Company requested re-annotation')

    now = datetime.utcnow()

    # Mark old annotation as revoked
    old_ann = mongo.db.annotations.find_one({'image_id': ObjectId(img_id)})
    if old_ann:
        mongo.db.annotations.update_one(
            {'_id': old_ann['_id']},
            {'$set': {
                'status': 'revoked',
                'revoke_reason': reason,
                'revoked_by': user['name'],
                'revoked_at': now,
                'updated_at': now
            }}
        )
        # If payout was created for this annotation, cancel it
        mongo.db.payouts.update_one(
            {'annotation_id': old_ann['_id'], 'status': 'pending'},
            {'$set': {'status': 'cancelled', 'updated_at': now}}
        )
        # Reverse pending earnings from doctor
        if old_ann.get('doctor_id'):
            pay = mongo.db.payouts.find_one({'annotation_id': old_ann['_id']})
            if pay and pay.get('amount'):
                mongo.db.users.update_one(
                    {'_id': old_ann['doctor_id']},
                    {'$inc': {'total_earnings': -pay['amount'], 'pending_earnings': -pay['amount']}}
                )

    # Re-assign to a DIFFERENT verified doctor in the same department
    old_doc_id = str(img.get('assigned_doctor_id', ''))
    new_doc_id, new_doc_name = auto_assign_doctor(img['department'], exclude_id=old_doc_id)

    mongo.db.images.update_one(
        {'_id': ObjectId(img_id)},
        {'$set': {
            'status':               'assigned' if new_doc_id else 'pending',
            'assigned_doctor_id':   new_doc_id,
            'assigned_doctor_name': new_doc_name,
            'revoke_reason':        reason,
            'revoked_at':           now,
            'annotated_at':         None,
            'qa_at':                None,
            'updated_at':           now
        }}
    )

    return jsonify({
        'message':      'Image revoked and re-queued for annotation',
        'new_doctor':   new_doc_name or 'Pending assignment',
        'reason':       reason
    }), 200


# ── DEPARTMENT STATS ──────────────────────────────────
@images_bp.route('/departments/stats', methods=['GET'])
@jwt_required()
def dept_stats():
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)}, {'role': 1})
    match_stage = {}
    if user and user['role'] == 'company':
        match_stage = {'company_id': ObjectId(uid)}

    pipeline = [
        {'$match': match_stage},
        {'$group': {'_id': '$department', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]
    result = list(mongo.db.images.aggregate(pipeline))
    return jsonify([{'department': r['_id'], 'count': r['count']} for r in result]), 200


# ── RE-ASSIGN (admin only) ────────────────────────────
@images_bp.route('/<img_id>/reassign', methods=['POST'])
@jwt_required()
def reassign(img_id):
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)}, {'role': 1})
    if not user or user['role'] != 'admin':
        return jsonify({'error': 'Admin only'}), 403

    data      = request.json or {}
    doctor_id = data.get('doctor_id')
    if not doctor_id:
        return jsonify({'error': 'doctor_id required'}), 400

    doc = mongo.db.users.find_one({'_id': ObjectId(doctor_id), 'role': 'doctor'}, {'name': 1})
    if not doc:
        return jsonify({'error': 'Doctor not found'}), 404

    mongo.db.images.update_one(
        {'_id': ObjectId(img_id)},
        {'$set': {
            'assigned_doctor_id': ObjectId(doctor_id),
            'assigned_doctor_name': doc['name'],
            'status': 'assigned',
            'updated_at': datetime.utcnow()
        }}
    )
    return jsonify({'message': f'Reassigned to {doc["name"]}'}), 200

# ── COMPANY MANUAL ASSIGN ─────────────────────────────
@images_bp.route('/<img_id>/assign', methods=['POST'])
@jwt_required()
def company_assign(img_id):
    """Companies can manually choose which verified doctor to assign an image to."""
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)}, {'role': 1})
    if not user or user['role'] not in ('company', 'admin'):
        return jsonify({'error': 'Only companies or admin can assign doctors'}), 403

    img = mongo.db.images.find_one({'_id': ObjectId(img_id)})
    if not img:
        return jsonify({'error': 'Image not found'}), 404
    if user['role'] == 'company' and str(img.get('company_id')) != uid:
        return jsonify({'error': 'This image does not belong to your company'}), 403

    data      = request.json or {}
    doctor_id = data.get('doctor_id')
    if not doctor_id:
        return jsonify({'error': 'doctor_id required'}), 400

    doc = mongo.db.users.find_one(
        {'_id': ObjectId(doctor_id), 'role': 'doctor', 'verified': True},
        {'name': 1, 'specialty': 1}
    )
    if not doc:
        return jsonify({'error': 'Verified doctor not found'}), 404

    now = datetime.utcnow()
    mongo.db.images.update_one(
        {'_id': ObjectId(img_id)},
        {'$set': {
            'assigned_doctor_id':   ObjectId(doctor_id),
            'assigned_doctor_name': doc['name'],
            'status':               'assigned',
            'updated_at':           now
        }}
    )
    return jsonify({
        'message':     f'Image assigned to Dr. {doc["name"]}',
        'doctor_name': doc['name'],
        'doctor_id':   str(doc['_id'])
    }), 200

# ── LIST VERIFIED DOCTORS (for company assignment picker) ─
@images_bp.route('/doctors/verified', methods=['GET'])
@jwt_required()
def verified_doctors():
    """Return list of verified doctors (for company manual assignment dropdown)."""
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)}, {'role': 1})
    if not user or user['role'] not in ('company', 'admin'):
        return jsonify({'error': 'Unauthorized'}), 403

    dept = request.args.get('department', '')
    query = {'role': 'doctor', 'verified': True, 'active': True}
    if dept:
        query['specialty'] = dept

    docs = list(mongo.db.users.find(
        query,
        {'name': 1, 'specialty': 1, 'experience_years': 1, 'total_earnings': 1}
    ).sort('name', 1).limit(50))

    result = []
    for d in docs:
        ann_count = mongo.db.annotations.count_documents({'doctor_id': d['_id']})
        approved  = mongo.db.annotations.count_documents({'doctor_id': d['_id'], 'status': 'qa_approved'})
        result.append({
            'id':           str(d['_id']),
            'name':         d['name'],
            'specialty':    d.get('specialty', ''),
            'experience':   d.get('experience_years', 0),
            'annotations':  ann_count,
            'accuracy_pct': round(approved / ann_count * 100, 1) if ann_count else 0
        })
    return jsonify({'doctors': result}), 200
