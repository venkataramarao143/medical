"""
Groq AI — Department Detection from image filename + metadata
Falls back to keyword matching if API key not set or call fails.
"""
import os, re, base64, requests
from dotenv import load_dotenv
load_dotenv()

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

DEPARTMENTS = [
    "Radiology", "Dermatology", "Neurology", "Oncology",
    "Ophthalmology", "Cardiology", "Orthopedics",
    "Pathology", "Gastroenterology", "Pulmonology"
]

# Keyword map for fast fallback
KEYWORD_MAP = {
    "Radiology":        ["xray","x-ray","chest","lung","bone","rib","spine","thorax","radiograph","ct","scan"],
    "Dermatology":      ["skin","derm","mole","lesion","rash","melanoma","biopsy","wound"],
    "Neurology":        ["brain","neuro","mri","stroke","head","skull","cortex","cerebral","nerve"],
    "Oncology":         ["tumor","cancer","mass","oncol","metastat","lymph","biopsy","marker"],
    "Ophthalmology":    ["eye","retina","optic","glaucoma","cornea","ophthal","macula","fundus"],
    "Cardiology":       ["heart","cardiac","echo","ecg","ekg","artery","vessel","cardio","coronary"],
    "Orthopedics":      ["joint","knee","hip","shoulder","ankle","orthop","fracture","arthritis"],
    "Pathology":        ["pathol","histol","slide","tissue","cell","micro","stain","biopsy"],
    "Gastroenterology": ["colon","stomach","gastro","bowel","intestin","endo","polyp","liver"],
    "Pulmonology":      ["lung","pulmon","airway","bronch","breath","pneum","alveol"],
}


def keyword_detect(filename: str) -> tuple[str, float]:
    """Fast keyword matching on filename."""
    name = filename.lower().replace('_', ' ').replace('-', ' ')
    scores = {}
    for dept, keywords in KEYWORD_MAP.items():
        score = sum(1 for kw in keywords if kw in name)
        if score:
            scores[dept] = score
    if scores:
        best = max(scores, key=scores.get)
        confidence = min(0.5 + scores[best] * 0.1, 0.85)
        return best, confidence
    return "Radiology", 0.4   # default fallback


def groq_detect(filename: str, file_bytes: bytes = None) -> tuple[str, float]:
    """
    Use Groq LLM to classify the medical image department.
    Uses llama3-8b-8192 with text prompt (filename + file size analysis).
    For actual image analysis, uses llama-3.2-11b-vision-preview if bytes provided.
    """
    if not GROQ_API_KEY:
        raise ValueError("No GROQ_API_KEY set")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    dept_list = ", ".join(DEPARTMENTS)

    # Try vision model if image bytes are provided and small enough
    if file_bytes and len(file_bytes) < 4 * 1024 * 1024:  # < 4MB
        try:
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
            mime = 'image/jpeg' if ext in ('jpg','jpeg') else f'image/{ext}'
            if ext in ('dcm','dicom'):
                # DICOM can't be directly sent as image; use text prompt only
                raise ValueError("DICOM file — use text prompt")

            b64 = base64.b64encode(file_bytes).decode('utf-8')
            payload = {
                "model": "llama-3.2-11b-vision-preview",
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"This is a medical image file named '{filename}'. "
                                f"Based on the image, classify it into exactly ONE of these medical departments: {dept_list}. "
                                "Respond with ONLY the department name, nothing else."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"}
                        }
                    ]
                }],
                "max_tokens": 20,
                "temperature": 0
            }
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers, json=payload, timeout=15
            )
            if resp.status_code == 200:
                result = resp.json()['choices'][0]['message']['content'].strip()
                dept = _normalize_dept(result)
                if dept:
                    return dept, 0.92
        except Exception:
            pass  # fall through to text prompt

    # Text-only prompt using filename
    payload = {
        "model": "llama3-8b-8192",
        "messages": [{
            "role": "system",
            "content": (
                "You are a medical imaging classifier. "
                f"Classify medical images into exactly one of: {dept_list}. "
                "Respond with ONLY the department name."
            )
        }, {
            "role": "user",
            "content": (
                f"Medical image filename: '{filename}'. "
                "What medical department does this image belong to? "
                "Answer with just the department name."
            )
        }],
        "max_tokens": 20,
        "temperature": 0
    }

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers, json=payload, timeout=10
    )
    resp.raise_for_status()
    result = resp.json()['choices'][0]['message']['content'].strip()
    dept = _normalize_dept(result)
    if dept:
        return dept, 0.88
    raise ValueError(f"Groq returned unrecognized dept: {result}")


def _normalize_dept(text: str) -> str:
    """Match Groq response to a known department."""
    text = text.strip().title()
    for d in DEPARTMENTS:
        if d.lower() in text.lower() or text.lower() in d.lower():
            return d
    return ""


def detect_department(filename: str, file_bytes: bytes = None) -> tuple[str, float, str]:
    """
    Main entry point — tries Groq first, falls back to keywords.
    Returns: (department, confidence, method)
    """
    # 1. Try Groq AI
    if GROQ_API_KEY:
        try:
            dept, conf = groq_detect(filename, file_bytes)
            return dept, conf, "groq_ai"
        except Exception as e:
            print(f"[Groq] Failed: {e} — falling back to keywords")

    # 2. Keyword fallback
    dept, conf = keyword_detect(filename)
    return dept, conf, "keyword"
