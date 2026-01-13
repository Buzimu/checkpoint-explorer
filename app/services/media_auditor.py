"""
Media Auditor - Self-Healing Media Association System

Scans media files for standardized naming pattern and automatically 
re-associates orphaned media with their correct models based on hash matching.

Filename format: [First8CharModelHash]-[age]-[img/vid]-[#].ext
Example: a1b2c3d4-pg-img-001.jpg

This allows orphaned media to be automatically reunited with their models
by extracting the hash from the filename and matching it to the model's hash.
"""
import os
import re
from app.services.database import load_db, save_db
from config import IMAGES_DIR


def parse_media_filename(filename):
    """
    Parse media filename to extract model hash, rating, type, and number
    
    Filename pattern: [Hash8]-[rating]-[img/vid]-[#].ext
    Example: a1b2c3d4-pg-img-001.jpg
    
    Args:
        filename: Media filename to parse
        
    Returns:
        Dict with keys: hash_prefix, rating, media_type, number, extension
        Returns None if filename doesn't match pattern
    """
    # Pattern: 8 hex chars - rating - img/vid - number . extension
    pattern = r'^([a-f0-9]{8})-([a-z]+)-(img|vid)-(\d+)(\..+)$'
    match = re.match(pattern, filename.lower())
    
    if match:
        return {
            'hash_prefix': match.group(1),
            'rating': match.group(2),
            'media_type': match.group(3),
            'number': match.group(4),
            'extension': match.group(5)
        }
    return None


def get_model_hash_prefix(model):
    """
    Get the first 8 characters of a model's SHA256 hash
    
    Args:
        model: Model dictionary
        
    Returns:
        First 8 characters of hash, or None if no hash exists
    """
    file_hash = model.get('fileHash')
    if file_hash and len(file_hash) >= 8:
        return file_hash[:8].lower()
    return None


def find_model_by_hash_prefix(db, hash_prefix):
    """
    Find model in database that matches the given hash prefix
    
    Args:
        db: Database dictionary
        hash_prefix: First 8 characters of model hash
        
    Returns:
        (model_path, model) tuple if found, (None, None) otherwise
    """
    for model_path, model in db['models'].items():
        model_hash_prefix = get_model_hash_prefix(model)
        if model_hash_prefix == hash_prefix.lower():
            return model_path, model
    return None, None


def rename_media_file(old_filename, new_filename):
    """
    Rename a media file on disk
    
    Args:
        old_filename: Current filename
        new_filename: New standardized filename
        
    Returns:
        True if successful, False otherwise
    """
    try:
        old_path = os.path.join(IMAGES_DIR, old_filename)
        new_path = os.path.join(IMAGES_DIR, new_filename)
        
        # Don't rename if already correct
        if old_filename == new_filename:
            return True
        
        # Don't rename if target already exists
        if os.path.exists(new_path):
            print(f"   ⚠️  Cannot rename {old_filename} - {new_filename} already exists")
            return False
        
        # Rename the file
        os.rename(old_path, new_path)
        return True
    except Exception as e:
        print(f"   ❌ Failed to rename {old_filename}: {e}")
        return False


def audit_media_for_model(db, model_path, model):
    """
    Audit media files for a specific model
    Removes invalid references, adds missing media, and renames to standard format
    
    Args:
        db: Database dictionary
        model_path: Path to the model
        model: Model dictionary
        
    Returns:
        Dict with stats: removed, added, verified, renamed
    """
    stats = {'removed': 0, 'added': 0, 'verified': 0, 'renamed': 0}
    
    model_hash_prefix = get_model_hash_prefix(model)
    if not model_hash_prefix:
        return stats
    
    # Get existing media references
    existing_media = model.get('exampleImages', [])
    if not isinstance(existing_media, list):
        existing_media = []
    
    # Verify and rename each existing media file
    verified_media = []
    media_counter = {}  # Track counters for each rating/type combo
    
    for media_item in existing_media:
        filename = media_item['filename']
        file_path = os.path.join(IMAGES_DIR, filename)
        
        if not os.path.exists(file_path):
            print(f"   🗑️  Removed missing reference: {filename}")
            stats['removed'] += 1
            continue
        
        # Check if filename matches standard format
        parsed = parse_media_filename(filename)
        
        if not parsed or parsed['hash_prefix'] != model_hash_prefix:
            # File needs to be renamed to standard format
            rating = media_item.get('rating', 'pg')
            ext = os.path.splitext(filename)[1].lower()
            media_type = 'vid' if ext in ['.mp4', '.webm'] else 'img'
            
            # Get next number for this rating/type combo
            key = f"{rating}-{media_type}"
            if key not in media_counter:
                media_counter[key] = 1
            else:
                media_counter[key] += 1
            
            number = f"{media_counter[key]:03d}"
            new_filename = generate_standard_filename(model_hash_prefix, rating, ext, number)
            
            # Rename the file
            if rename_media_file(filename, new_filename):
                print(f"   📝 Renamed: {filename} -> {new_filename}")
                media_item['filename'] = new_filename
                stats['renamed'] += 1
            else:
                # Keep old filename if rename failed
                pass
        else:
            # File already has standard format
            # Update counter to avoid duplicates
            key = f"{parsed['rating']}-{parsed['media_type']}"
            try:
                num = int(parsed['number'])
                media_counter[key] = max(media_counter.get(key, 0), num)
            except ValueError:
                pass
        
        verified_media.append(media_item)
        stats['verified'] += 1
    
    # Scan images directory for files matching this model's hash
    if os.path.exists(IMAGES_DIR):
        existing_filenames = {item['filename'] for item in verified_media}
        
        for filename in os.listdir(IMAGES_DIR):
            # Skip if already referenced
            if filename in existing_filenames:
                continue
            
            # Try to parse filename
            parsed = parse_media_filename(filename)
            if not parsed:
                continue
            
            # Check if hash matches this model
            if parsed['hash_prefix'] == model_hash_prefix:
                file_path = os.path.join(IMAGES_DIR, filename)
                if os.path.isfile(file_path):
                    # Add this media to the model
                    verified_media.append({
                        'filename': filename,
                        'rating': parsed['rating'],
                        'caption': f'Auto-recovered from filename'
                    })
                    print(f"   ✅ Re-associated: {filename}")
                    stats['added'] += 1
    
    # Update model's media list
    model['exampleImages'] = verified_media
    
    return stats


def audit_all_media(db):
    """
    Audit all media files across all models
    
    1. Verify existing media references
    2. Re-associate orphaned media based on hash matching
    3. Report statistics
    
    Args:
        db: Database dictionary
        
    Returns:
        Dict with overall stats and per-model details
    """
    print("\n🔍 === MEDIA AUDIT START ===")
    
    overall_stats = {
        'models_audited': 0,
        'media_verified': 0,
        'references_removed': 0,
        'media_re_associated': 0,
        'media_renamed': 0
    }
    
    model_details = []
    
    # Audit each model
    for model_path, model in db['models'].items():
        model_hash_prefix = get_model_hash_prefix(model)
        if not model_hash_prefix:
            continue
        
        model_stats = audit_media_for_model(db, model_path, model)
        
        overall_stats['models_audited'] += 1
        overall_stats['media_verified'] += model_stats['verified']
        overall_stats['references_removed'] += model_stats['removed']
        overall_stats['media_re_associated'] += model_stats['added']
        overall_stats['media_renamed'] += model_stats['renamed']
        
        if model_stats['removed'] > 0 or model_stats['added'] > 0 or model_stats['renamed'] > 0:
            model_details.append({
                'path': model_path,
                'name': model.get('name', 'Unknown'),
                'stats': model_stats
            })
            print(f"📦 {model.get('name', 'Unknown')}: verified={model_stats['verified']}, removed={model_stats['removed']}, added={model_stats['added']}, renamed={model_stats['renamed']}")
    
    print(f"\n✅ Audit complete:")
    print(f"   Models audited: {overall_stats['models_audited']}")
    print(f"   Media verified: {overall_stats['media_verified']}")
    print(f"   References removed: {overall_stats['references_removed']}")
    print(f"   Media re-associated: {overall_stats['media_re_associated']}")
    print(f"   Media renamed: {overall_stats['media_renamed']}")
    print("=== MEDIA AUDIT END ===\n")
    
    return {
        'stats': overall_stats,
        'details': model_details
    }


def get_next_media_number(model):
    """
    Get the next sequential number for media in this model
    
    Args:
        model: Model dictionary
        
    Returns:
        Next number as zero-padded string (e.g., "001", "002")
    """
    existing_media = model.get('exampleImages', [])
    if not isinstance(existing_media, list):
        return "001"
    
    model_hash_prefix = get_model_hash_prefix(model)
    if not model_hash_prefix:
        return "001"
    
    # Find highest number for this model's media
    max_number = 0
    for item in existing_media:
        parsed = parse_media_filename(item['filename'])
        if parsed and parsed['hash_prefix'] == model_hash_prefix:
            try:
                num = int(parsed['number'])
                max_number = max(max_number, num)
            except ValueError:
                continue
    
    # Return next number, zero-padded to 3 digits
    return f"{max_number + 1:03d}"


def generate_standard_filename(model_hash_prefix, rating, extension, number):
    """
    Generate a standardized media filename
    
    Format: [Hash8]-[rating]-[img/vid]-[#].ext
    
    Args:
        model_hash_prefix: First 8 chars of model hash
        rating: Content rating (pg, r, x)
        extension: File extension (e.g., '.jpg', '.mp4')
        number: Sequential number (e.g., "001")
        
    Returns:
        Standardized filename string
    """
    # Determine if image or video
    ext_lower = extension.lower()
    media_type = 'vid' if ext_lower in ['.mp4', '.webm'] else 'img'
    
    return f"{model_hash_prefix}-{rating}-{media_type}-{number}{extension}"
