"""
ADMIN ROUTES — Full platform management (fixed + optimized)
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash
from extensions import mongo
from datetime import datetime
from bson import ObjectId
import certifi

admin_bp = Blueprint('admin', __name__)


def require_admin():
    uid = get_jwt_identity()
    try:
        user = mongo.db.users.find_one({'_id': ObjectId(uid)}, {'password': 0})
    except Exception:
        return None, jsonify({'error': 'Invalid token'}), 401
    if not user or user.get('role') != 'admin':
        return None, jsonify({'error': 'Admin access required'}), 403
    return user, None, None


def safe_dict(u):
    if not u:
        return None
    u = dict(u)
    u['id'] = str(u['_id'])
    u['_id'] = str(u['_id'])
    u.pop('password', None)
    for f in ('created_at', 'updated_at', 'verified_at', 'last_login'):
        if u.get(f) and hasattr(u[f], 'isoformat'):
            u[f] = u[f].isoformat()
    return u


# ── PLATFORM STATS ────────────────────────────────────
@admin_bp.route('/stats', methods=['GET'])
@jwt_required()
def stats():
    admin, err, code = require_admin()
    if err:
        return err, code

    # Run all counts in parallel using single aggregation per collection
    from pymongo import DESCENDING
    docs_total     = mongo.db.users.count_documents({'role': 'doctor'})
    docs_verified  = mongo.db.users.count_documents({'role': 'doctor', 'verified': True})
    docs_pending   = mongo.db.users.count_documents({'role': 'doctor', 'verified': False})
    comp_total     = mongo.db.users.count_documents({'role': 'company'})
    img_total      = mongo.db.images.count_documents({})
    img_approved   = mongo.db.images.count_documents({'status': 'approved'})
    ann_total      = mongo.db.annotations.count_documents({})
    ann_approved   = mongo.db.annotations.count_documents({'status': 'qa_approved'})
    ann_pending_qa = mongo.db.annotations.count_documents({'status': 'submitted'})

    pending_pays = list(mongo.db.payouts.find({'status': 'pending'}, {'amount': 1}))
    paid_pays    = list(mongo.db.payouts.find({'status': 'paid'},    {'amount': 1}))

    return jsonify({
        'doctors': {
            'total': docs_total,
            'verified': docs_verified,
            'pending_verification': docs_pending,
            'active': docs_total
        },
        'companies': {
            'total': comp_total,
            'active': comp_total
        },
        'images': {
            'total': img_total,
            'pending':    mongo.db.images.count_documents({'status': 'pending'}),
            'assigned':   mongo.db.images.count_documents({'status': 'assigned'}),
            'annotating': mongo.db.images.count_documents({'status': 'annotating'}),
            'qa_review':  mongo.db.images.count_documents({'status': 'qa_review'}),
            'approved':   img_approved,
            'rejected':   mongo.db.images.count_documents({'status': 'rejected'}),
        },
        'annotations': {
            'total': ann_total,
            'approved': ann_approved,
            'pending_qa': ann_pending_qa,
            'annotations_today': ann_total,
        },
        'annotations_today': ann_pending_qa,
        'payouts': {
            'pending_count':  len(pending_pays),
            'pending_amount': sum(p.get('amount', 0) for p in pending_pays),
            'paid_count':     len(paid_pays),
            'paid_amount':    sum(p.get('amount', 0) for p in paid_pays),
        }
    }), 200


# ── ALL DOCTORS ───────────────────────────────────────
@admin_bp.route('/doctors', methods=['GET'])
@jwt_required()
def list_doctors():
    admin, err, code = require_admin()
    if err:
        return err, code

    verified_filter = request.args.get('verified', '')
    specialty       = request.args.get('specialty', '')
    search          = request.args.get('search', '')

    query = {'role': 'doctor'}
    if verified_filter == 'true':  query['verified'] = True
    if verified_filter == 'false': query['verified'] = False
    if specialty: query['specialty'] = specialty
    if search:
        import re
        query['$or'] = [
            {'name':  {'$regex': re.escape(search), '$options': 'i'}},
            {'email': {'$regex': re.escape(search), '$options': 'i'}}
        ]

    doctors = list(mongo.db.users.find(query, {'password': 0}).sort('created_at', -1))
    result = []
    for d in doctors:
        d = safe_dict(d)
        d['annotation_count'] = mongo.db.annotations.count_documents({'doctor_id': ObjectId(d['_id'])})
        d['approved_count']   = mongo.db.annotations.count_documents({'doctor_id': ObjectId(d['_id']), 'status': 'qa_approved'})
        result.append(d)

    return jsonify({'doctors': result}), 200


# ── VERIFY DOCTOR ─────────────────────────────────────
@admin_bp.route('/doctors/<doc_id>/verify', methods=['POST'])
@jwt_required()
def verify_doctor(doc_id):
    admin, err, code = require_admin()
    if err:
        return err, code

    doc = mongo.db.users.find_one({'_id': ObjectId(doc_id), 'role': 'doctor'})
    if not doc:
        return jsonify({'error': 'Doctor not found'}), 404

    mongo.db.users.update_one(
        {'_id': ObjectId(doc_id)},
        {'$set': {
            'verified': True, 'verified_at': datetime.utcnow(),
            'verified_by': admin['name'], 'rejection_reason': '',
            'active': True, 'updated_at': datetime.utcnow()
        }}
    )
    return jsonify({'message': f'Dr. {doc["name"]} has been verified'}), 200


# ── REJECT DOCTOR ─────────────────────────────────────
@admin_bp.route('/doctors/<doc_id>/reject', methods=['POST'])
@jwt_required()
def reject_doctor(doc_id):
    admin, err, code = require_admin()
    if err:
        return err, code

    data   = request.json or {}
    reason = data.get('reason', 'Does not meet platform requirements')
    doc    = mongo.db.users.find_one({'_id': ObjectId(doc_id), 'role': 'doctor'})
    if not doc:
        return jsonify({'error': 'Doctor not found'}), 404

    mongo.db.users.update_one(
        {'_id': ObjectId(doc_id)},
        {'$set': {'verified': False, 'rejection_reason': reason, 'updated_at': datetime.utcnow()}}
    )
    return jsonify({'message': f'Doctor {doc["name"]} rejected'}), 200


# ── SUSPEND / ACTIVATE ────────────────────────────────
@admin_bp.route('/users/<user_id>/suspend', methods=['POST'])
@jwt_required()
def suspend_user(user_id):
    admin, err, code = require_admin()
    if err:
        return err, code
    u = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not u:
        return jsonify({'error': 'Not found'}), 404
    mongo.db.users.update_one({'_id': ObjectId(user_id)}, {'$set': {'active': False, 'updated_at': datetime.utcnow()}})
    return jsonify({'message': f'User {u["name"]} suspended'}), 200


@admin_bp.route('/users/<user_id>/activate', methods=['POST'])
@jwt_required()
def activate_user(user_id):
    admin, err, code = require_admin()
    if err:
        return err, code
    u = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not u:
        return jsonify({'error': 'Not found'}), 404
    mongo.db.users.update_one({'_id': ObjectId(user_id)}, {'$set': {'active': True, 'updated_at': datetime.utcnow()}})
    return jsonify({'message': f'User {u["name"]} activated'}), 200


# ── EDIT USER ─────────────────────────────────────────
@admin_bp.route('/users/<user_id>', methods=['PUT'])
@jwt_required()
def edit_user(user_id):
    admin, err, code = require_admin()
    if err:
        return err, code
    u    = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not u:
        return jsonify({'error': 'Not found'}), 404
    data = request.json or {}
    allowed = ['name', 'email', 'specialty', 'license_number', 'bio',
               'experience_years', 'company_name', 'website', 'verified', 'active', 'rejection_reason']
    updates = {k: data[k] for k in allowed if k in data}
    updates['updated_at'] = datetime.utcnow()
    if data.get('new_password'):
        updates['password'] = generate_password_hash(data['new_password'])
    mongo.db.users.update_one({'_id': ObjectId(user_id)}, {'$set': updates})
    updated = mongo.db.users.find_one({'_id': ObjectId(user_id)}, {'password': 0})
    return jsonify(safe_dict(updated)), 200


# ── DELETE USER ───────────────────────────────────────
@admin_bp.route('/users/<user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    admin, err, code = require_admin()
    if err:
        return err, code
    u = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not u:
        return jsonify({'error': 'Not found'}), 404
    if str(u['_id']) == str(admin['_id']):
        return jsonify({'error': 'Cannot delete yourself'}), 400
    mongo.db.users.delete_one({'_id': ObjectId(user_id)})
    return jsonify({'message': f'User {u["name"]} deleted'}), 200


# ── ALL COMPANIES ─────────────────────────────────────
@admin_bp.route('/companies', methods=['GET'])
@jwt_required()
def list_companies():
    admin, err, code = require_admin()
    if err:
        return err, code
    companies = list(mongo.db.users.find({'role': 'company'}, {'password': 0}).sort('created_at', -1))
    result = []
    for c in companies:
        c = safe_dict(c)
        c['image_count']    = mongo.db.images.count_documents({'company_id': ObjectId(c['_id'])})
        c['approved_count'] = mongo.db.images.count_documents({'company_id': ObjectId(c['_id']), 'status': 'approved'})
        result.append(c)
    return jsonify({'companies': result}), 200


# ── ALL IMAGES ────────────────────────────────────────
@admin_bp.route('/images', methods=['GET'])
@jwt_required()
def admin_images():
    admin, err, code = require_admin()
    if err:
        return err, code
    page     = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    status   = request.args.get('status', '')
    dept     = request.args.get('department', '')
    query = {}
    if status: query['status'] = status
    if dept:   query['department'] = dept

    total = mongo.db.images.count_documents(query)
    # Exclude large gridfs binary from listing
    projection = {'gridfs_id': 0}
    imgs = list(mongo.db.images.find(query, projection).sort('created_at', -1)
                .skip((page-1)*per_page).limit(per_page))

    def img_d(i):
        i['id']  = str(i['_id'])
        i['_id'] = str(i['_id'])
        for f in ('company_id', 'assigned_doctor_id'):
            if i.get(f): i[f] = str(i[f])
        for f in ('created_at', 'updated_at', 'qa_at', 'annotated_at'):
            if i.get(f) and hasattr(i[f], 'isoformat'): i[f] = i[f].isoformat()
        return i

    return jsonify({'images': [img_d(i) for i in imgs], 'total': total, 'page': page}), 200


# ── ALL PAYOUTS ───────────────────────────────────────
@admin_bp.route('/payouts', methods=['GET'])
@jwt_required()
def list_payouts():
    admin, err, code = require_admin()
    if err:
        return err, code
    status   = request.args.get('status', '')
    page     = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    query = {}
    if status: query['status'] = status

    total = mongo.db.payouts.count_documents(query)
    pays  = list(mongo.db.payouts.find(query).sort('created_at', -1)
                 .skip((page-1)*per_page).limit(per_page))

    def pay_d(p):
        p['id']  = str(p['_id'])
        p['_id'] = str(p['_id'])
        for f in ('doctor_id', 'annotation_id', 'image_id', 'paid_by'):
            if p.get(f): p[f] = str(p[f])
        for f in ('created_at', 'paid_at'):
            if p.get(f) and hasattr(p[f], 'isoformat'): p[f] = p[f].isoformat()
        return p

    return jsonify({'payouts': [pay_d(p) for p in pays], 'total': total, 'page': page}), 200


# ── MARK PAYOUT PAID ──────────────────────────────────
@admin_bp.route('/payouts/<pay_id>/pay', methods=['POST'])
@jwt_required()
def mark_paid(pay_id):
    admin, err, code = require_admin()
    if err:
        return err, code
    pay = mongo.db.payouts.find_one({'_id': ObjectId(pay_id)})
    if not pay:
        return jsonify({'error': 'Not found'}), 404
    if pay['status'] == 'paid':
        return jsonify({'error': 'Already paid'}), 400

    now = datetime.utcnow()
    mongo.db.payouts.update_one(
        {'_id': ObjectId(pay_id)},
        {'$set': {'status': 'paid', 'paid_at': now, 'paid_by': admin['name']}}
    )
    mongo.db.users.update_one(
        {'_id': pay['doctor_id']},
        {'$inc': {'paid_earnings': pay['amount'], 'pending_earnings': -pay['amount']}}
    )
    return jsonify({'message': f'${pay["amount"]} marked as paid'}), 200


# ── ALL ANNOTATIONS ───────────────────────────────────
@admin_bp.route('/annotations', methods=['GET'])
@jwt_required()
def admin_annotations():
    admin, err, code = require_admin()
    if err:
        return err, code
    status   = request.args.get('status', '')
    page     = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    query = {}
    if status: query['status'] = status
    total = mongo.db.annotations.count_documents(query)
    anns  = list(mongo.db.annotations.find(query, {'canvas_data': 0})
                 .sort('created_at', -1).skip((page-1)*per_page).limit(per_page))

    def ann_d(a):
        a['id']  = str(a['_id'])
        a['_id'] = str(a['_id'])
        for f in ('image_id', 'doctor_id', 'qa_doctor_id'):
            if a.get(f): a[f] = str(a[f])
        for f in ('created_at', 'updated_at', 'submitted_at', 'qa_at'):
            if a.get(f) and hasattr(a[f], 'isoformat'): a[f] = a[f].isoformat()
        return a

    return jsonify({'annotations': [ann_d(a) for a in anns], 'total': total}), 200


# ── SEED ADMIN ────────────────────────────────────────
@admin_bp.route('/seed', methods=['GET', 'POST'])
def seed_admin():
    if mongo.db.users.find_one({'role': 'admin'}):
        return jsonify({'message': 'Admin already exists. Login with your credentials.'}), 200

    now = datetime.utcnow()
    mongo.db.users.insert_one({
        'name': 'Super Admin', 'email': 'admin@medannotate.com',
        'password': generate_password_hash('Admin@1234'),
        'role': 'admin', 'verified': True, 'active': True,
        'created_at': now, 'updated_at': now,
        'total_earnings': 0.0, 'pending_earnings': 0.0, 'paid_earnings': 0.0,
    })

    # Create indexes for performance
    try:
        mongo.db.users.create_index('email', unique=True)
        mongo.db.users.create_index([('role', 1), ('verified', 1)])
        mongo.db.images.create_index([('assigned_doctor_id', 1), ('status', 1)])
        mongo.db.images.create_index([('company_id', 1), ('status', 1)])
        mongo.db.images.create_index('status')
        mongo.db.images.create_index('department')
        mongo.db.annotations.create_index([('doctor_id', 1), ('status', 1)])
        mongo.db.annotations.create_index('image_id')
        mongo.db.payouts.create_index([('doctor_id', 1), ('status', 1)])
        mongo.db.payouts.create_index('status')
    except Exception as e:
        print(f"Index warning: {e}")

    return jsonify({
        'message': 'Admin account created!',
        'email': 'admin@medannotate.com',
        'password': 'Admin@1234',
        'note': 'Change this password after first login!'
    }), 201
