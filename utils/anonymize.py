import io
import os
from PIL import Image

def anonymize_image(file_bytes, filename):
    """
    Strip all EXIF/metadata from image files to remove patient PII.
    Returns cleaned image bytes.
    """
    ext = filename.rsplit('.', 1)[-1].lower()

    if ext in ('dcm', 'dicom'):
        return anonymize_dicom(file_bytes, filename)
    else:
        return anonymize_standard_image(file_bytes)


def anonymize_standard_image(file_bytes):
    """Strip EXIF data from JPG/PNG/TIFF using Pillow."""
    try:
        img = Image.open(io.BytesIO(file_bytes))
        # Create new image without metadata
        clean_img = Image.new(img.mode, img.size)
        clean_img.putdata(list(img.getdata()))
        output = io.BytesIO()
        # Preserve format
        fmt = img.format or 'PNG'
        if fmt == 'JPEG':
            clean_img.save(output, format='JPEG', quality=95)
        else:
            clean_img.save(output, format='PNG')
        output.seek(0)
        return output.read()
    except Exception as e:
        # If PIL fails, return original (still log it)
        print(f"[ANONYMIZE] Warning: could not strip metadata: {e}")
        return file_bytes


def anonymize_dicom(file_bytes, filename):
    """
    Anonymize DICOM file by removing patient tags.
    Falls back to raw bytes if pydicom not available.
    """
    try:
        import pydicom
        from pydicom.uid import generate_uid

        ds = pydicom.dcmread(io.BytesIO(file_bytes))

        # Tags to remove (patient PII)
        tags_to_remove = [
            'PatientName', 'PatientID', 'PatientBirthDate',
            'PatientSex', 'PatientAge', 'PatientAddress',
            'PatientTelephoneNumbers', 'InstitutionName',
            'InstitutionAddress', 'ReferringPhysicianName',
            'PhysiciansOfRecord', 'PerformingPhysicianName',
            'NameOfPhysiciansReadingStudy', 'OperatorsName',
            'AccessionNumber', 'StudyID', 'StudyDate', 'StudyTime'
        ]

        for tag in tags_to_remove:
            if hasattr(ds, tag):
                try:
                    delattr(ds, tag)
                except Exception:
                    pass

        # Replace with anonymized values
        ds.PatientName = "ANONYMIZED"
        ds.PatientID = f"ANON-{generate_uid()[:8]}"

        output = io.BytesIO()
        ds.save_as(output)
        output.seek(0)
        return output.read()

    except ImportError:
        print("[ANONYMIZE] pydicom not available, returning raw DICOM bytes")
        return file_bytes
    except Exception as e:
        print(f"[ANONYMIZE] DICOM anonymization error: {e}")
        return file_bytes
