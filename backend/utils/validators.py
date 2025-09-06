"""
Input validation utilities
"""
import re
import os
from typing import Any, Dict, List, Optional


def validate_model_id(model_id: str) -> bool:
    """
    Validate model ID format
    
    Args:
        model_id: Model identifier to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not model_id:
        return False
    
    # Model IDs should be 16-character hex strings
    pattern = r'^[a-f0-9]{16}$'
    return bool(re.match(pattern, model_id.lower()))


def validate_directory_path(path: str) -> Dict[str, Any]:
    """
    Validate a directory path
    
    Args:
        path: Directory path to validate
        
    Returns:
        Dictionary with validation results
    """
    result = {
        'valid': False,
        'exists': False,
        'is_directory': False,
        'readable': False,
        'writable': False,
        'message': ''
    }
    
    if not path:
        result['message'] = 'Path is empty'
        return result
    
    if not os.path.exists(path):
        result['message'] = 'Path does not exist'
        return result
    
    result['exists'] = True
    
    if not os.path.isdir(path):
        result['message'] = 'Path is not a directory'
        return result
    
    result['is_directory'] = True
    
    if not os.access(path, os.R_OK):
        result['message'] = 'Directory is not readable'
        return result
    
    result['readable'] = True
    
    if not os.access(path, os.W_OK):
        result['message'] = 'Directory is not writable (notes may not be saved)'
        result['valid'] = True  # Still valid, just with warning
        return result
    
    result['writable'] = True
    result['valid'] = True
    result['message'] = 'Directory is valid'
    
    return result


def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
    """
    Validate file extension
    
    Args:
        filename: Filename to check
        allowed_extensions: List of allowed extensions (with dots)
        
    Returns:
        True if extension is allowed
    """
    if not filename:
        return False
    
    ext = os.path.splitext(filename)[1].lower()
    return ext in allowed_extensions


def validate_tag_name(tag: str) -> bool:
    """
    Validate tag name
    
    Args:
        tag: Tag name to validate
        
    Returns:
        True if valid
    """
    if not tag:
        return False
    
    # Tags should be 1-50 characters, alphanumeric with spaces, hyphens, underscores
    if len(tag) > 50:
        return False
    
    pattern = r'^[a-zA-Z0-9\s\-_]+$'
    return bool(re.match(pattern, tag))


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to be safe for filesystem
    
    Args:
        filename: Filename to sanitize
        
    Returns:
        Sanitized filename
    """
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    
    # Limit length
    max_length = 255
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext
    
    return filename or 'unnamed'


def validate_notes_content(content: str, max_length: int = 1000000) -> Dict[str, Any]:
    """
    Validate notes content
    
    Args:
        content: Notes content to validate
        max_length: Maximum allowed length
        
    Returns:
        Validation result dictionary
    """
    result = {
        'valid': True,
        'message': '',
        'char_count': len(content) if content else 0,
        'word_count': len(content.split()) if content else 0,
        'line_count': len(content.splitlines()) if content else 0
    }
    
    if result['char_count'] > max_length:
        result['valid'] = False
        result['message'] = f'Content exceeds maximum length of {max_length} characters'
    
    # Check for problematic characters
    if '\x00' in content:
        result['valid'] = False
        result['message'] = 'Content contains null characters'
    
    return result


def validate_json_data(data: Any, required_fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Validate JSON request data
    
    Args:
        data: Data to validate
        required_fields: List of required field names
        
    Returns:
        Validation result
    """
    result = {
        'valid': True,
        'message': '',
        'missing_fields': []
    }
    
    if data is None:
        result['valid'] = False
        result['message'] = 'No data provided'
        return result
    
    if not isinstance(data, dict):
        result['valid'] = False
        result['message'] = 'Data must be a JSON object'
        return result
    
    if required_fields:
        for field in required_fields:
            if field not in data:
                result['missing_fields'].append(field)
        
        if result['missing_fields']:
            result['valid'] = False
            result['message'] = f"Missing required fields: {', '.join(result['missing_fields'])}"
    
    return result


def validate_sort_params(sort_field: str, sort_order: str) -> Dict[str, str]:
    """
    Validate sorting parameters
    
    Args:
        sort_field: Field to sort by
        sort_order: Sort order (asc/desc)
        
    Returns:
        Validated parameters
    """
    allowed_fields = ['name', 'type', 'size_bytes', 'created_at', 'modified_at']
    allowed_orders = ['asc', 'desc']
    
    if sort_field not in allowed_fields:
        sort_field = 'name'
    
    if sort_order not in allowed_orders:
        sort_order = 'asc'
    
    return {
        'field': sort_field,
        'order': sort_order
    }