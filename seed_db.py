# -*- coding: utf-8 -*-
"""
One-time setup: creates admin account and DB indexes.
Run: py -3 seed_db.py
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from werkzeug.security import generate_password_hash
from datetime import datetime

app = create_app()

with app.app_context():
    from extensions import mongo

    existing = mongo.db.users.find_one({'role': 'admin'})
    if existing:
        print("[OK] Admin already exists:", existing['email'])
        print("     Login: admin@medannotate.com / Admin@1234")
    else:
        now = datetime.utcnow()
        mongo.db.users.insert_one({
            'name': 'Super Admin',
            'email': 'admin@medannotate.com',
            'password': generate_password_hash('Admin@1234'),
            'role': 'admin',
            'verified': True,
            'active': True,
            'created_at': now,
            'updated_at': now,
            'total_earnings': 0.0,
            'pending_earnings': 0.0,
            'paid_earnings': 0.0,
        })
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
            print("[OK] DB indexes created")
        except Exception as e:
            print("[WARN] Index:", e)

        print("")
        print("[SUCCESS] Admin account created!")
        print("  Email:    admin@medannotate.com")
        print("  Password: Admin@1234")
        print("  Change password after first login!")
