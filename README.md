# 🩺 MedAnnotate — Medical Image Annotation & Quality Assurance Platform

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Framework](https://img.shields.io/badge/framework-Flask%203.0-green.svg)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/database-MongoDB%20%7C%20GridFS-leaf.svg)](https://www.mongodb.com/)
[![AI Engine](https://img.shields.io/badge/AI%20Vision-Groq%20%7C%20Llama%203.2%20Vision-purple.svg)](https://console.groq.com/)
[![HIPAA Compliant Anonymization](https://img.shields.io/badge/HIPAA-Safe%20Anonymization-red.svg)](#-privacy--hipaa-compliance)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](LICENSE)

> **MedAnnotate** is an end-to-end, HIPAA-compliant web platform bridging **AI healthcare companies** and **verified medical specialists** to create **Gold Standard** training datasets for diagnostic AI models.

---

## 🌟 Executive Summary

Building diagnostic medical AI models requires verified, high-precision training data. **MedAnnotate** automates the dataset lifecycle:
1. **AI Companies** upload raw DICOM, X-Ray, CT, or MRI images.
2. **AI Vision Engine** strips patient identifiers (PHI) and automatically routes images to matching medical departments (e.g., Radiology, Cardiology).
3. **Verified Doctors** draw high-precision annotations using an interactive Fabric.js canvas studio.
4. **Peer Specialists (QA)** conduct double-blind reviews for 100% data fidelity.
5. **Ledger System** credits doctors per approved image ($4.00) and enables dataset exports in COCO, Pascal VOC, and YOLO JSON formats.

---

## ⚡ Key Features & Innovations

### 1. 🛡️ Automated HIPAA-Safe Anonymization
- **DICOM & EXIF Stripping**: Automatically scrubs Patient Name, DOB, MRN, Hospital Identifiers, and camera metadata upon upload.
- **Pixel-Level Privacy**: Guarantees zero leakage of Protected Health Information (PHI) before storage.

### 2. 🤖 AI-Powered Department Detection & Load Balancing
- **Automated Vision Classifier**: Integrated with **Groq Llama 3.2 Vision API** to classify incoming scans into specialties (*Radiology, Cardiology, Dermatology, Ophthalmology, Pathology, Neurology*).
- **Smart Load Balancer**: Distributes images automatically to available verified doctors with the lowest current workload.

### 3. 🎨 Interactive Web Canvas Studio (Fabric.js)
- **Tooling Suite**: Draw bounding boxes, freehand polygons, keypoint dots, diagnostic labels, and clinical notes.
- **View Adjustments**: Built-in zoom, pan, brightness, and contrast controls optimized for medical imaging analysis.
- **Confidence Scoring**: Doctors assign diagnostic certainty (0–100%) to every annotation.

### 4. 🔍 Peer-Reviewed Quality Assurance (Double-Blind)
- **QA Queue**: Submitted annotations are routed to a second specialist for independent review.
- **Approval Workflow**: On approval, the annotation is locked as *Gold Standard* and earnings are released. On rejection, feedback is provided for revision.

### 5. 💰 Financial Earnings & Payout Ledger
- **Per-Image Compensation**: Tracks doctor earnings transparently ($4.00 per approved image).
- **Admin Settlement**: Platform admins inspect earnings ledgers and mark payouts as completed.

### 6. 📦 Multi-Format Dataset Exporter
- Export gold-standard datasets into industry-standard ML formats:
  - **COCO JSON** (Object detection)
  - **Pascal VOC XML**
  - **YOLO Format**

---

## 📐 System Architecture

```
[ AI Company ] ──► ( Upload DICOM/X-Ray )
                        │
                        ▼
                [ Anonymizer (pydicom / PIL) ] ──► ( PHI Stripped )
                        │
                        ▼
                [ Groq AI Vision Classifier ] ──► ( Department Identified )
                        │
                        ▼
                [ Smart Workload Balancer ]
                        │
                        ▼
    ┌───────────────────┴───────────────────┐
    ▼                                       ▼
[ Radiologist Queue ]               [ Cardiologist Queue ]
    │                                       │
    ▼                                       ▼
( Annotate Scan )                       ( Annotate Scan )
    │                                       │
    └───────────────────┬───────────────────┘
                        ▼
             [ Peer Doctor QA Review ]
                        │
               ┌────────┴────────┐
               ▼                 ▼
          [ Approved ]      [ Rejected ]
               │                 │
               ▼                 ▼
       ( $4.00 Credit )   ( Revision Request )
               │
               ▼
     [ Export COCO/YOLO/VOC ]
```

---

## 🛠️ Technology Stack

- **Backend**: Python 3.11+, Flask 3.0, PyMongo 4.6, Flask-JWT-Extended, Flask-CORS
- **Database**: MongoDB (Atlas Cloud or Local Community Server) + GridFS for binary image storage
- **AI & Processing**: Groq Llama 3.2 Vision API, `pydicom`, `Pillow`, `certifi`
- **Frontend**: Responsive HTML5, Vanilla CSS3 (Custom Dark Theme), JavaScript ES6+, Fabric.js (Canvas renderer), FontAwesome 6.5
- **Authentication**: JWT (JSON Web Tokens) with role-based access control (`admin`, `doctor`, `company`)

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.11+** installed
- **MongoDB** running locally (`localhost:27017`) or a MongoDB Atlas URI

### 1. Clone & Navigate
```bash
git clone https://github.com/YOUR_USERNAME/medannotate.git
cd medannotate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Setup (`.env`)
Create a `.env` file in the root directory:
```env
MONGO_URI=mongodb://localhost:27017/medannotate
SECRET_KEY=your-jwt-secret-key-2026
JWT_SECRET_KEY=your-jwt-secret-key-2026
PAY_PER_IMAGE=4.0
GROQ_API_KEY=your-groq-api-key-here
```

### 4. Initialize Admin & DB Indexes
```bash
python seed_db.py
```

### 5. Start the Server
```bash
python app.py
```
Open **[http://localhost:5000](http://localhost:5000)** in your browser.

> 💡 **Demo Mode (No MongoDB required)**: Run `python demo_server.py` for instant UI testing with pre-populated dummy data.

---

## 🔐 Default Credentials

| Role | Email | Password | Access Rights |
|---|---|---|---|
| **Admin** | `admin@medannotate.com` | `Admin@1234` | Full System Control, Doctor Verifications, Financial Payouts |
| **Doctor (Demo)** | `doctor@demo.com` | `Doctor@1234` | Radiology Queue, Canvas Studio, Earnings Dashboard |
| **Company (Demo)** | `company@demo.com` | `Company@1234` | Batch Upload, Dataset Status, Gold Standard Downloads |

---

## 📁 Project Structure

```
medannotate/
├── app.py                # Main Flask production entry point
├── demo_server.py        # Standalone in-memory server for frontend demo
├── config.py             # System configuration & environment loader
├── extensions.py         # MongoDB PyMongo & JWT extensions
├── seed_db.py            # Database indexer & admin seeder
├── requirements.txt      # Python dependencies
│
├── routes/               # Modular REST API endpoints
│   ├── auth.py           # JWT Registration, Authentication, Profile
│   ├── images.py         # Anonymized Uploads, Serving, Workload Distribution
│   ├── annotations.py    # Fabric.js JSON persistence, QA submission, Earnings
│   └── admin.py          # Doctor approval, Financial payout settlements
│
├── utils/                # AI & Media Utilities
│   ├── anonymize.py      # DICOM/EXIF metadata stripper
│   └── detect_department.py # Groq AI Vision classifier
│
└── frontend/             # Responsive Web Interface
    ├── index.html        # Landing page & platform overview
    ├── login.html        # Unified login portal
    ├── register.html     # Doctor / Company registration
    ├── doctor/           # Doctor workspace (Dashboard, Canvas Studio, Earnings)
    ├── company/          # AI Company workspace (Uploads, Batches, Export)
    ├── admin/            # Admin workspace (Verification & Financial audit)
    ├── css/main.css      # Dark-mode Design System
    └── js/               # Client scripts & Fabric.js engine (`annotate.js`, `api.js`)
```

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.
