"""
ANNOTATION ROUTES — Save, submit, QA review, earnings
All data stored and retrieved from MongoDB in real-time.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import mongo
from config import Config
from datetime import datetime
from bson import ObjectId

annotations_bp = Blueprint('annotations', __name__)


def ann_to_dict(a):
    if not a: return None
    a = dict(a)
    a['id']  = str(a['_id'])   # frontend uses .id
    a['_id'] = str(a['_id'])
    for f in ('image_id', 'doctor_id', 'qa_doctor_id'):
        if a.get(f): a[f] = str(a[f])
    for f in ('created_at', 'updated_at', 'submitted_at', 'qa_at', 'revoked_at'):
        if a.get(f) and hasattr(a[f], 'isoformat'):
            a[f] = a[f].isoformat()
    a.pop('canvas_data', None)  # don't send large binary on list calls
    return a


# ─────────────────────────────────────────
#  SAVE / UPDATE ANNOTATION (draft)
# ─────────────────────────────────────────
@annotations_bp.route('/', methods=['POST'])
@jwt_required()
def save_annotation():
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)})

    if not user or user['role'] != 'doctor':
        return jsonify({'error': 'Only doctors can annotate'}), 403
    if not user.get('verified'):
        return jsonify({'error': 'You must be verified by admin before annotating'}), 403

    data   = request.json or {}
    img_id = data.get('image_id')
    if not img_id:
        return jsonify({'error': 'image_id required'}), 400

    # Verify image is assigned to this doctor
    img = mongo.db.images.find_one({'_id': ObjectId(img_id)})
    if not img:
        return jsonify({'error': 'Image not found'}), 404
    if str(img.get('assigned_doctor_id')) != uid:
        return jsonify({'error': 'This image is not assigned to you'}), 403
    if img['status'] in ('qa_review', 'approved'):
        return jsonify({'error': 'Image is already submitted/approved'}), 400

    now = datetime.utcnow()

    # Upsert annotation
    existing = mongo.db.annotations.find_one({'image_id': ObjectId(img_id), 'doctor_id': ObjectId(uid)})

    ann_doc = {
        'image_id':      ObjectId(img_id),
        'image_filename': img.get('filename', ''),
        'department':    img.get('department', ''),
        'doctor_id':     ObjectId(uid),
        'doctor_name':   user['name'],
        'doctor_specialty': user.get('specialty', ''),
        'labels':        data.get('labels', []),
        'bounding_boxes': data.get('bounding_boxes', []),
        'canvas_data':   data.get('canvas_data', ''),
        'notes':         data.get('notes', ''),
        'confidence':    int(data.get('confidence', 80)),
        'time_spent_sec': int(data.get('time_spent_sec', 0)),
        'status':        'draft',
        'updated_at':    now,
    }

    if existing:
        mongo.db.annotations.update_one({'_id': existing['_id']}, {'$set': ann_doc})
        ann_id = str(existing['_id'])
    else:
        ann_doc['created_at'] = now
        result = mongo.db.annotations.insert_one(ann_doc)
        ann_id  = str(result.inserted_id)

    # Mark image as "being annotated"
    mongo.db.images.update_one(
        {'_id': ObjectId(img_id)},
        {'$set': {'status': 'annotating', 'updated_at': now}}
    )

    return jsonify({'annotation_id': ann_id, 'status': 'saved'}), 200


# ─────────────────────────────────────────
#  GET ANNOTATION FOR AN IMAGE
# ─────────────────────────────────────────
@annotations_bp.route('/image/<img_id>', methods=['GET'])
@jwt_required()
def get_annotation(img_id):
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)}, {'role': 1})
    query = {'image_id': ObjectId(img_id)}
    # Doctors can only see their own; companies see for their images; admin sees all
    if user and user['role'] == 'doctor':
        query['doctor_id'] = ObjectId(uid)
    elif user and user['role'] == 'company':
        # Verify the image belongs to the company
        img = mongo.db.images.find_one({'_id': ObjectId(img_id)}, {'company_id': 1})
        if not img or str(img.get('company_id')) != uid:
            return jsonify({'annotation': None}), 200

    ann = mongo.db.annotations.find_one(query)

    if ann:
        # include canvas_data for detail views
        ann = dict(ann)
        ann['id']  = str(ann['_id'])
        ann['_id'] = str(ann['_id'])
        for f in ('image_id', 'doctor_id', 'qa_doctor_id'):
            if ann.get(f): ann[f] = str(ann[f])
        for f in ('created_at', 'updated_at', 'submitted_at', 'qa_at', 'revoked_at'):
            if ann.get(f) and hasattr(ann[f], 'isoformat'):
                ann[f] = ann[f].isoformat()
    return jsonify({'annotation': ann}), 200


# ─────────────────────────────────────────
#  SUBMIT FOR QA
# ─────────────────────────────────────────
@annotations_bp.route('/<ann_id>/submit', methods=['POST'])
@jwt_required()
def submit_annotation(ann_id):
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)})
    ann  = mongo.db.annotations.find_one({'_id': ObjectId(ann_id)})

    if not ann:
        return jsonify({'error': 'Annotation not found'}), 404
    if str(ann['doctor_id']) != uid:
        return jsonify({'error': 'Not your annotation'}), 403
    if ann['status'] not in ('draft',):
        return jsonify({'error': f'Cannot submit from status: {ann["status"]}'}), 400
    if not ann.get('labels'):
        return jsonify({'error': 'At least one label is required before submitting'}), 400

    now = datetime.utcnow()
    mongo.db.annotations.update_one(
        {'_id': ObjectId(ann_id)},
        {'$set': {'status': 'submitted', 'submitted_at': now, 'updated_at': now}}
    )
    mongo.db.images.update_one(
        {'_id': ann['image_id']},
        {'$set': {'status': 'qa_review', 'annotated_at': now, 'updated_at': now}}
    )
    return jsonify({'status': 'submitted', 'message': 'Submitted for company review'}), 200


# ─────────────────────────────────────────
#  QA REVIEW — Approve or Reject
# ─────────────────────────────────────────
@annotations_bp.route('/<ann_id>/qa', methods=['POST'])
@jwt_required()
def qa_review(ann_id):
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)})
    ann  = mongo.db.annotations.find_one({'_id': ObjectId(ann_id)})

    if not ann:
        return jsonify({'error': 'Annotation not found'}), 404
    if ann['status'] != 'submitted':
        return jsonify({'error': 'Annotation is not in QA review state'}), 400

    # Must be a different verified doctor, admin, OR the company that owns the image
    if user['role'] == 'doctor':
        if not user.get('verified'):
            return jsonify({'error': 'You must be verified to do QA'}), 403
        if str(ann['doctor_id']) == uid:
            return jsonify({'error': 'You cannot QA your own annotation'}), 403
    elif user['role'] == 'company':
        # verify this company owns the image being annotated
        img_check = mongo.db.images.find_one({'_id': ann['image_id']}, {'company_id': 1})
        if not img_check or str(img_check.get('company_id')) != uid:
            return jsonify({'error': 'This annotation is not for your image'}), 403
    elif user['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data     = request.json or {}
    decision = data.get('decision')  # 'approve' or 'reject'
    comment  = data.get('comment', '')

    if decision not in ('approve', 'reject'):
        return jsonify({'error': 'decision must be approve or reject'}), 400

    now        = datetime.utcnow()
    new_status = 'qa_approved' if decision == 'approve' else 'qa_rejected'

    mongo.db.annotations.update_one(
        {'_id': ObjectId(ann_id)},
        {'$set': {
            'status':       new_status,
            'qa_doctor_id': ObjectId(uid),
            'qa_doctor_name': user['name'],
            'qa_comment':   comment,
            'qa_at':        now,
            'updated_at':   now
        }}
    )

    # Update image status
    img_status = 'approved' if decision == 'approve' else 'rejected'
    mongo.db.images.update_one(
        {'_id': ann['image_id']},
        {'$set': {'status': img_status, 'qa_at': now, 'updated_at': now}}
    )

    # On approval — create payout record + update doctor's earnings in DB
    if decision == 'approve':
        amount = Config.PAY_PER_IMAGE
        img    = mongo.db.images.find_one({'_id': ann['image_id']})

        payout_doc = {
            'doctor_id':      ann['doctor_id'],
            'doctor_name':    ann['doctor_name'],
            'doctor_specialty': ann.get('doctor_specialty', ''),
            'annotation_id':  ObjectId(ann_id),
            'image_id':       ann['image_id'],
            'image_filename': ann.get('image_filename', ''),
            'department':     ann.get('department', ''),
            'amount':         amount,
            'status':         'pending',  # admin must mark as paid
            'created_at':     now,
            'paid_at':        None,
            'paid_by':        None,
        }
        mongo.db.payouts.insert_one(payout_doc)

        # Update doctor's pending earnings in real-time
        mongo.db.users.update_one(
            {'_id': ann['doctor_id']},
            {'$inc': {'total_earnings': amount, 'pending_earnings': amount}}
        )

    return jsonify({'status': new_status, 'decision': decision}), 200


# ─────────────────────────────────────────
#  DOCTOR'S QA QUEUE (images others need QA'd)
# ─────────────────────────────────────────
@annotations_bp.route('/qa-queue', methods=['GET'])
@jwt_required()
def qa_queue():
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)})
    if not user or not user.get('verified'):
        return jsonify({'error': 'Verified doctors only'}), 403

    # Submitted annotations NOT by this doctor, in the same specialty
    query = {
        'status':    'submitted',
        'doctor_id': {'$ne': ObjectId(uid)}
    }
    if user['role'] == 'doctor':
        query['department'] = user.get('specialty', '')

    anns = list(mongo.db.annotations.find(query).sort('submitted_at', 1).limit(20))
    result = []
    for a in anns:
        img = mongo.db.images.find_one({'_id': a['image_id']})
        result.append({
            'annotation_id':    str(a['_id']),
            'image_id':         str(a['image_id']),
            'filename':         img['filename'] if img else '—',
            'department':       a.get('department', '—'),
            'annotating_doctor': a.get('doctor_name', '—'),
            'label_count':      len(a.get('labels', [])),
            'submitted_at':     a['submitted_at'].isoformat() if a.get('submitted_at') else None
        })
    return jsonify({'queue': result}), 200


# ─────────────────────────────────────────
#  DOCTOR STATS — from live DB
# ─────────────────────────────────────────
@annotations_bp.route('/my-stats', methods=['GET'])
@jwt_required()
def my_stats():
    uid  = get_jwt_identity()
    user = mongo.db.users.find_one({'_id': ObjectId(uid)})
    if not user or user['role'] != 'doctor':
        return jsonify({'error': 'Doctors only'}), 403

    anns = list(mongo.db.annotations.find({'doctor_id': ObjectId(uid)}))

    stats = {
        'draft':       sum(1 for a in anns if a['status'] == 'draft'),
        'submitted':   sum(1 for a in anns if a['status'] == 'submitted'),
        'approved':    sum(1 for a in anns if a['status'] == 'qa_approved'),
        'rejected':    sum(1 for a in anns if a['status'] == 'qa_rejected'),
    }

    # Assigned images from DB
    assigned = mongo.db.images.count_documents({
        'assigned_doctor_id': ObjectId(uid),
        'status': {'$in': ['assigned', 'annotating']}
    })

    # Earnings from DB (live)
    payouts = list(mongo.db.payouts.find({'doctor_id': ObjectId(uid)}))
    paid    = sum(p['amount'] for p in payouts if p['status'] == 'paid')
    pending = sum(p['amount'] for p in payouts if p['status'] == 'pending')

    return jsonify({
        'assigned_images': assigned,
        'annotations':     stats,
        'approved':        stats['approved'],    # shortcut for frontend
        'pending_qa':      stats['submitted'],   # shortcut for frontend
        'earnings': {
            'paid':      paid,
            'pending':   pending,
            'total':     paid + pending,
            'per_image': Config.PAY_PER_IMAGE
        }
    }), 200


# ─────────────────────────────────────────
#  DOCTOR'S ANNOTATION HISTORY
# ─────────────────────────────────────────
@annotations_bp.route('/history', methods=['GET'])
@jwt_required()
def annotation_history():
    print("[DEBUG] /history route accessed!", flush=True)
    uid  = get_jwt_identity()
    try:
        page = int(request.args.get('page', 1))
        per  = int(request.args.get('per_page', 10))
    except Exception as e:
        print("[DEBUG] /history argument error:", str(e))
        return jsonify({'error': str(e)}), 400

    total = mongo.db.annotations.count_documents({'doctor_id': ObjectId(uid)})
    anns  = list(mongo.db.annotations.find({'doctor_id': ObjectId(uid)})
                 .sort('created_at', -1)
                 .skip((page - 1) * per)
                 .limit(per))
    
    print(f"[DEBUG] /history found {len(anns)} annotations for doc {uid}", flush=True)

    return jsonify({
        'annotations': [ann_to_dict(a) for a in anns],
        'total': total,
        'page':  page,
        'pages': max(1, -(-total // per))
    }), 200


# ─────────────────────────────────────────
#  PAYOUT HISTORY (doctor's own)
# ─────────────────────────────────────────
@annotations_bp.route('/payouts', methods=['GET'])
@jwt_required()
def my_payouts():
    uid   = get_jwt_identity()
    page  = int(request.args.get('page', 1))
    per   = int(request.args.get('per_page', 10))

    total = mongo.db.payouts.count_documents({'doctor_id': ObjectId(uid)})
    pays  = list(mongo.db.payouts.find({'doctor_id': ObjectId(uid)})
                 .sort('created_at', -1)
                 .skip((page - 1) * per)
                 .limit(per))

    def pay_dict(p):
        p['_id']          = str(p['_id'])
        p['doctor_id']    = str(p['doctor_id'])
        p['annotation_id']= str(p['annotation_id']) if p.get('annotation_id') else None
        p['image_id']     = str(p['image_id']) if p.get('image_id') else None
        for f in ('created_at', 'paid_at'):
            if p.get(f) and hasattr(p[f], 'isoformat'): p[f] = p[f].isoformat()
        return p

    return jsonify({
        'payouts': [pay_dict(p) for p in pays],
        'total':   total,
        'page':    page,
        'pages':   max(1, -(-total // per))
    }), 200
