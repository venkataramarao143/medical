"""
AUTH ROUTES — Register, Login, Profile (fixed + optimized)
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import mongo
from datetime import datetime
from bson import ObjectId

auth_bp = Blueprint('auth', __name__)


def user_to_dict(u):
    """Convert MongoDB doc to JSON-safe dict with both id and _id."""
    if not u:
        return None
    u = dict(u)
    u['id']  = str(u['_id'])   # always include 'id' for frontend
    u['_id'] = str(u['_id'])
    u.pop('password', None)
    for f in ('created_at', 'updated_at', 'verified_at', 'last_login'):
        if u.get(f) and hasattr(u[f], 'isoformat'):
            u[f] = u[f].isoformat()
    return u


# ── REGISTER ──────────────────────────────────────────
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json or {}
    required = ['name', 'email', 'password', 'role']
    if not all(data.get(k) for k in required):
        return jsonify({'error': 'Name, email, password and role are required'}), 400

    email = data['email'].strip().lower()
    role  = data['role']

    if role not in ('doctor', 'company'):
        return jsonify({'error': 'Role must be doctor or company'}), 400
    if mongo.db.users.find_one({'email': email}):
        return jsonify({'error': 'Email already registered'}), 409

    if role == 'doctor':
        if not data.get('specialty'):
            return jsonify({'error': 'Specialty is required for doctors'}), 400
        if not data.get('license_number'):
            return jsonify({'error': 'License number is required for doctors'}), 400
    if role == 'company' and not data.get('company_name'):
        return jsonify({'error': 'Company name is required'}), 400

    now = datetime.utcnow()
    doc = {
        'name':            data['name'].strip(),
        'email':           email,
        'password':        generate_password_hash(data['password']),
        'role':            role,
        'verified':        (role == 'company'),  # doctors need admin approval
        'active':          True,
        'created_at':      now,
        'updated_at':      now,
        'specialty':       data.get('specialty', ''),
        'license_number':  data.get('license_number', ''),
        'bio':             data.get('bio', ''),
        'experience_years': int(data.get('experience_years', 0)),
        'company_name':    data.get('company_name', ''),
        'website':         data.get('website', ''),
        'total_earnings':  0.0,
        'pending_earnings': 0.0,
        'paid_earnings':   0.0,
        'rejection_reason': '',
        'verified_at':     None,
        'verified_by':     None,
    }
    result = mongo.db.users.insert_one(doc)
    doc['_id'] = result.inserted_id

    if role == 'doctor':
        return jsonify({
            'message': 'Registration successful. Awaiting admin verification.',
            'status': 'pending_verification'
        }), 201

    token = create_access_token(identity=str(result.inserted_id))
    return jsonify({'token': token, 'user': user_to_dict(doc)}), 201


# ── LOGIN ─────────────────────────────────────────────
@auth_bp.route('/login', methods=['POST'])
def login():
    data     = request.json or {}
    email    = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = mongo.db.users.find_one({'email': email})

    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid email or password'}), 401
    if not user.get('active', True):
        return jsonify({'error': 'Your account has been deactivated. Contact admin.'}), 403

    # Doctors must be admin-verified before logging in
    if user['role'] == 'doctor' and not user.get('verified'):
        reason = user.get('rejection_reason', '')
        if reason:
            return jsonify({'error': f'Account rejected: {reason}'}), 403
        return jsonify({'error': 'Your account is pending admin verification.'}), 403

    # Update last login timestamp
    mongo.db.users.update_one(
        {'_id': user['_id']},
        {'$set': {'last_login': datetime.utcnow()}}
    )

    token = create_access_token(identity=str(user['_id']))
    return jsonify({'token': token, 'user': user_to_dict(user)}), 200


# ── GET CURRENT USER (fresh from DB) ──────────────────
@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    uid  = get_jwt_identity()
    try:
        user = mongo.db.users.find_one({'_id': ObjectId(uid)}, {'password': 0})
    except Exception:
        return jsonify({'error': 'Invalid token'}), 401
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user_to_dict(user)), 200


# ── UPDATE PROFILE ────────────────────────────────────
@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    uid  = get_jwt_identity()
    data = request.json or {}
    allowed = ['name', 'bio', 'experience_years', 'website', 'company_name']
    updates = {k: data[k] for k in allowed if k in data}
    updates['updated_at'] = datetime.utcnow()
    mongo.db.users.update_one({'_id': ObjectId(uid)}, {'$set': updates})
    user = mongo.db.users.find_one({'_id': ObjectId(uid)}, {'password': 0})
    return jsonify(user_to_dict(user)), 200


# ── CHANGE PASSWORD ───────────────────────────────────
@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    uid  = get_jwt_identity()
    data = request.json or {}
    old  = data.get('old_password', '')
    new  = data.get('new_password', '')
    user = mongo.db.users.find_one({'_id': ObjectId(uid)})
    if not user or not check_password_hash(user['password'], old):
        return jsonify({'error': 'Current password is incorrect'}), 401
    if len(new) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400
    mongo.db.users.update_one(
        {'_id': ObjectId(uid)},
        {'$set': {'password': generate_password_hash(new), 'updated_at': datetime.utcnow()}}
    )
    return jsonify({'message': 'Password changed successfully'}), 200
