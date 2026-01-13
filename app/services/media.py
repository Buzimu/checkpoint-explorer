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


def save_uploaded_file(file_content, original_filename, model_hash_prefix=None, rating='pg', number='001'):
    """
    Save uploaded file to images directory with standardized filename
    
    New standardized format: [Hash8]-[rating]-[img/vid]-[#].ext
    Example: a1b2c3d4-pg-img-001.jpg
    
    Falls back to content hash if model_hash_prefix not provided.
    
    Args:
        file_content: Binary content of the file
        original_filename: Original filename with extension
        model_hash_prefix: First 8 chars of model's hash (optional)
        rating: Content rating (pg, r, x) - default 'pg'
        number: Sequential number as string (e.g., '001') - default '001'
        
    Returns:
        New filename if successful, None otherwise
    """
    try:
        is_valid, ext = validate_file(original_filename)
        if not is_valid:
            return None
        
        # If no model hash provided, fall back to content hash (legacy behavior)
        if not model_hash_prefix:
            file_hash = generate_file_hash(file_content)
            filename = f"{file_hash}{ext}"
        else:
            # Use standardized naming: [Hash8]-[rating]-[img/vid]-[#].ext
            ext_lower = ext.lower()
            media_type = 'vid' if ext_lower in ['.mp4', '.webm'] else 'img'
            filename = f"{model_hash_prefix}-{rating}-{media_type}-{number}{ext}"
        
        # Save file
        file_path = os.path.join(IMAGES_DIR, filename)
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        return filename
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        return None