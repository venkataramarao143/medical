import os, certifi
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY      = os.environ.get('SECRET_KEY', 'medannotate-secret-2026')
    JWT_SECRET_KEY  = os.environ.get('JWT_SECRET_KEY', 'medannotate-jwt-2026')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    # Use header-based tokens only (no cookies, no CSRF issues)
    JWT_TOKEN_LOCATION  = ['headers']
    JWT_COOKIE_CSRF_PROTECT = False
    JWT_ERROR_MESSAGE_KEY = 'error'  # use 'error' key instead of 'message'

    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/medannotate')
    # Fix Atlas SSL on Python 3.11+
    MONGO_CONNECT_KWARGS = {'tlsCAFile': certifi.where()} if 'mongodb+srv' in os.environ.get('MONGO_URI', '') else {}


    # Uploads
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'dcm', 'dicom', 'tiff', 'tif', 'bmp'}

    # Business logic
    PAY_PER_IMAGE = float(os.environ.get('PAY_PER_IMAGE', 4.0))

    # Optional AI detection
    HUGGINGFACE_API_KEY = os.environ.get('HUGGINGFACE_API_KEY', '')


DEPARTMENTS = [
    "Radiology", "Dermatology", "Neurology", "Oncology",
    "Ophthalmology", "Cardiology", "Orthopedics",
    "Pathology", "Gastroenterology", "Pulmonology"
]

ANNOTATION_LABELS = {
    "Radiology":        ["Fracture", "Nodule", "Mass", "Pneumonia", "Pleural Effusion", "Cardiomegaly", "Normal"],
    "Dermatology":      ["Melanoma", "Lesion", "Rash", "Benign Nevus", "Basal Cell Carcinoma", "Normal"],
    "Neurology":        ["Tumor", "Hemorrhage", "Infarct", "White Matter Lesion", "Aneurysm", "Normal"],
    "Oncology":         ["Tumor", "Metastasis", "Lymph Node", "Mass", "Normal Tissue"],
    "Ophthalmology":    ["Diabetic Retinopathy", "Glaucoma", "Macular Degeneration", "Cataract", "Normal"],
    "Cardiology":       ["Stenosis", "Calcification", "Aneurysm", "Cardiomegaly", "Normal"],
    "Orthopedics":      ["Fracture", "Dislocation", "Arthritis", "Bone Spur", "Normal"],
    "Pathology":        ["Malignant", "Benign", "Inflammation", "Necrosis", "Normal"],
    "Gastroenterology": ["Polyp", "Ulcer", "Mass", "Inflammation", "Normal"],
    "Pulmonology":      ["Nodule", "Consolidation", "Effusion", "Pneumothorax", "Normal"],
}
