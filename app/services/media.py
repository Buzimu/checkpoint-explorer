"""
Media file handling operations
"""
import os
import hashlib
from config import IMAGES_DIR, ALLOWED_EXTENSIONS


def validate_file(filename):
    """
    Validate if file has an allowed extension
    
    Args:
        filename: Name of the file to validate
        
    Returns:
        Tuple of (is_valid, extension)
    """
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS, ext


def generate_file_hash(file_content):
    """
    Generate SHA256 hash for file content
    
    Args:
        file_content: Binary content of the file
        
    Returns:
        First 16 characters of the hash
    """
    return hashlib.sha256(file_content).hexdigest()[:16]


def save_uploaded_file(file_content, original_filename):
    """
    Save uploaded file to images directory with hash-based filename
    
    Args:
        file_content: Binary content of the file
        original_filename: Original filename with extension
        
    Returns:
        New filename if successful, None otherwise
    """
    try:
        is_valid, ext = validate_file(original_filename)
        if not is_valid:
            return None
        
        # Generate hash-based filename
        file_hash = generate_file_hash(file_content)
        filename = f"{file_hash}{ext}"
        
        # Save file
        file_path = os.path.join(IMAGES_DIR, filename)
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        return filename
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        return None