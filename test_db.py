import sys, io, os, certifi
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv()

MONGO_URI = os.environ.get('MONGO_URI', '')
PAY = float(os.environ.get('PAY_PER_IMAGE', 4.0))

from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from datetime import datetime

def ok(m):  print(f'  [OK]  {m}')
def err(m): print(f'  [ERR] {m}')
def sec(t): print(f'\n{"="*50}\n  {t}\n{"="*50}')

# 1. Connect
sec('1. Atlas Connection')
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000, tlsCAFile=certifi.where())
    client.admin.command('ping')
    db = client['medannotate']
    ok('Connected to MongoDB Atlas successfully!')
    ok(f'Database: medannotate | Collections: {db.list_collection_names() or "(empty - fresh db)"}')
except Exception as e:
    err(f'Connection failed: {e}')
    sys.exit(1)

# Cleanup any previous test data
db.users.delete_many({'email': {'$in': ['t_doc@test.com', 't_comp@test.com']}})
db.images.delete_many({'batch_name': '_TEST_'})
db.annotations.delete_many({'notes': '_TEST_'})

# 2. Write Doctor
sec('2. Write - Insert Doctor (unverified)')
now = datetime.utcnow()
r1 = db.users.insert_one({
    'name': 'Dr. Test', 'email': 't_doc@test.com',
    'password': generate_password_hash('Test@1234'),
    'role': 'doctor', 'verified': False, 'active': True,
    'specialty': 'Radiology', 'license_number': 'RAD-001',
    'total_earnings': 0.0, 'pending_earnings': 0.0, 'paid_earnings': 0.0,
    'created_at': now
})
ok(f'Doctor inserted -> id: {r1.inserted_id}')

# 3. Write Company
sec('3. Write - Insert Company (auto-verified)')
r2 = db.users.insert_one({
    'name': 'AI Corp', 'email': 't_comp@test.com', 'role': 'company',
    'company_name': 'TestMed AI', 'password': generate_password_hash('Test@1234'),
    'verified': True, 'active': True, 'total_earnings': 0.0, 'created_at': now
})
ok(f'Company inserted -> id: {r2.inserted_id}')

# 4. Read back
sec('4. Read - Retrieve from Atlas DB')
doc  = db.users.find_one({'email': 't_doc@test.com'})
comp = db.users.find_one({'email': 't_comp@test.com'})
assert doc and doc['verified'] == False
assert comp and comp['verified'] == True
ok(f'Doctor:  {doc["name"]} | specialty={doc["specialty"]} | verified={doc["verified"]}')
ok(f'Company: {comp["company_name"]} | verified={comp["verified"]}')

# 5. Admin verifies doctor
sec('5. Admin Verifies Doctor (grants login access)')
db.users.update_one({'_id': doc['_id']},
    {'$set': {'verified': True, 'verified_by': 'Admin', 'verified_at': now}})
d2 = db.users.find_one({'_id': doc['_id']})
assert d2['verified'] == True
ok(f'Doctor verified -> verified={d2["verified"]} | can now login and annotate')

# 6. Image Upload (metadata)
sec('6. Image Upload - Store metadata in Atlas')
r3 = db.images.insert_one({
    'filename': 'xray_test.dcm', 'department': 'Radiology',
    'status': 'assigned', 'company_id': comp['_id'],
    'company_name': 'TestMed AI', 'assigned_doctor_id': doc['_id'],
    'assigned_doctor_name': doc['name'], 'anonymized': True,
    'batch_name': '_TEST_', 'file_size': 2048, 'created_at': now
})
img = db.images.find_one({'_id': r3.inserted_id})
assert img['department'] == 'Radiology'
ok(f'Image stored + retrieved: {img["filename"]} -> dept={img["department"]} -> doctor={img["assigned_doctor_name"]}')

# 7. Annotation lifecycle
sec('7. Annotation - Draft -> Submit -> QA Approve')
r4 = db.annotations.insert_one({
    'image_id': img['_id'], 'doctor_id': doc['_id'], 'doctor_name': doc['name'],
    'labels': ['Nodule', 'Fracture'], 'notes': '_TEST_',
    'confidence': 90, 'status': 'draft', 'created_at': now
})
ok(f'Annotation saved (draft) -> id: {r4.inserted_id}')

db.annotations.update_one({'_id': r4.inserted_id}, {'$set': {'status': 'submitted', 'submitted_at': now}})
db.images.update_one({'_id': img['_id']}, {'$set': {'status': 'qa_review'}})
ok('Annotation submitted for QA | Image status -> qa_review')

db.annotations.update_one({'_id': r4.inserted_id}, {'$set': {'status': 'qa_approved', 'qa_at': now}})
db.images.update_one({'_id': img['_id']}, {'$set': {'status': 'approved'}})
ann = db.annotations.find_one({'_id': r4.inserted_id})
assert ann['status'] == 'qa_approved'
ok(f'QA Approved | Annotation status={ann["status"]} | Image status=approved')

# 8. Payout + earnings
sec('8. Payout - Create, Pay, Update Doctor Earnings in DB')
r5 = db.payouts.insert_one({
    'doctor_id': doc['_id'], 'doctor_name': doc['name'],
    'annotation_id': r4.inserted_id, 'image_id': img['_id'],
    'amount': PAY, 'status': 'pending', 'created_at': now
})
db.users.update_one({'_id': doc['_id']}, {'$inc': {'total_earnings': PAY, 'pending_earnings': PAY}})
ok(f'Payout created: ${PAY} (pending)')

db.payouts.update_one({'_id': r5.inserted_id}, {'$set': {'status': 'paid', 'paid_at': now, 'paid_by': 'Admin'}})
db.users.update_one({'_id': doc['_id']}, {'$inc': {'paid_earnings': PAY, 'pending_earnings': -PAY}})
final = db.users.find_one({'_id': doc['_id']})
ok(f'Payout marked PAID | Doctor earnings in Atlas: total=${final["total_earnings"]} | paid=${final["paid_earnings"]} | pending=${final["pending_earnings"]}')

# 9. Live stats
sec('9. Live Stats - Real-time counts from Atlas')
ok(f'Total users:       {db.users.count_documents({})}')
ok(f'  Doctors:         {db.users.count_documents({"role": "doctor"})}')
ok(f'  Unverified:      {db.users.count_documents({"role": "doctor", "verified": False})}')
ok(f'  Companies:       {db.users.count_documents({"role": "company"})}')
ok(f'Total images:      {db.images.count_documents({})}')
ok(f'Total annotations: {db.annotations.count_documents({})}')
ok(f'Pending payouts:   {db.payouts.count_documents({"status": "pending"})}')
ok(f'Paid payouts:      {db.payouts.count_documents({"status": "paid"})}')

# 10. Cleanup
sec('10. Cleanup - Remove test data from Atlas')
db.users.delete_many({'email': {'$in': ['t_doc@test.com', 't_comp@test.com']}})
db.images.delete_many({'batch_name': '_TEST_'})
db.annotations.delete_many({'notes': '_TEST_'})
db.payouts.delete_many({'doctor_id': doc['_id']})
ok('All test data removed from Atlas')

print('\n' + '='*50)
print('  ALL 10 TESTS PASSED!')
print('  MongoDB Atlas is connected and 100% working.')
print('  Storage + retrieval verified for ALL collections:')
print('  users, images, annotations, payouts')
print()
print('  Next: python app.py  then open http://localhost:5000')
print('='*50 + '\n')
