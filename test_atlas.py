"""
Quick Atlas SSL connection test with proper TLS config
"""
import ssl, certifi, os
from dotenv import load_dotenv
load_dotenv()

MONGO_URI = os.environ.get('MONGO_URI', '')
print(f"Testing URI: ...{MONGO_URI[-40:]}")

from pymongo import MongoClient

# Method 1: tlsCAFile
try:
    print("\nMethod 1: tlsCAFile=certifi.where()")
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=10000,
        tlsCAFile=certifi.where()
    )
    client.admin.command('ping')
    print("[OK] Connected with tlsCAFile!")
    print("Use this config in your app.")
    # Try insert/read
    db = client['medannotate']
    db.connection_test.insert_one({'test': True, 'ts': __import__('datetime').datetime.utcnow()})
    doc = db.connection_test.find_one({'test': True})
    print(f"[OK] Write+Read verified: {doc['_id']}")
    db.connection_test.delete_many({'test': True})
    print("[OK] Cleanup done")
    print("\nSUCCESS: MongoDB Atlas is fully working!")
    exit(0)
except Exception as e:
    print(f"[FAIL] {e}")

# Method 2: tls=True, tlsAllowInvalidCertificates
try:
    print("\nMethod 2: tls=True, tlsAllowInvalidCertificates=True")
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=10000,
        tls=True,
        tlsAllowInvalidCertificates=True
    )
    client.admin.command('ping')
    print("[OK] Connected!")
    db = client['medannotate']
    db.connection_test.insert_one({'test': True})
    doc = db.connection_test.find_one({'test': True})
    print(f"[OK] Write+Read verified: {doc['_id']}")
    db.connection_test.delete_many({'test': True})
    exit(0)
except Exception as e:
    print(f"[FAIL] {e}")

# Method 3: ssl_cert_reqs=CERT_NONE
try:
    print("\nMethod 3: ssl_cert_reqs=CERT_NONE")
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=10000,
        ssl=True,
        ssl_cert_reqs=ssl.CERT_NONE
    )
    client.admin.command('ping')
    print("[OK] Connected!")
    exit(0)
except Exception as e:
    print(f"[FAIL] {e}")

print("\nAll methods failed. Check Atlas IP whitelist and credentials.")
print("Go to: https://cloud.mongodb.com → Network Access → Add 0.0.0.0/0")
