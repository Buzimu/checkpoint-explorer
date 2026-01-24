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
import json
import subprocess
from app.services.database import load_db, save_db
from config import IMAGES_DIR


def check_video_compatibility(video_path):
    """
    Check if a video file is browser-compatible
    Detects YUV444 chroma subsampling and other incompatible formats
    
    Args:
        video_path: Full path to video file
        
    Returns:
        Dict with keys: compatible (bool), issues (list), pix_fmt (str), codec (str)
    """
    try:
        # Use ffprobe to analyze video
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_streams', '-select_streams', 'v:0',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return {'compatible': False, 'issues': ['Failed to analyze video'], 'pix_fmt': None, 'codec': None}
        
        data = json.loads(result.stdout)
        if not data.get('streams'):
            return {'compatible': False, 'issues': ['No video stream found'], 'pix_fmt': None, 'codec': None}
        
        stream = data['streams'][0]
        pix_fmt = stream.get('pix_fmt', '')
        codec = stream.get('codec_name', '')
        profile = stream.get('profile', '')
        
        issues = []
        compatible = True
        
        # Check for YUV444 (incompatible with most browsers)
        if 'yuv444' in pix_fmt.lower() or '444' in pix_fmt:
            issues.append(f'Incompatible chroma subsampling: {pix_fmt} (YUV444)')
            compatible = False
        
        # Check for H.264 High 4:4:4 Predictive profile (incompatible with Firefox/most browsers)
        if codec == 'h264' and '4:4:4' in profile:
            issues.append(f'Incompatible H.264 profile: {profile} (not supported by Firefox)')
            compatible = False
        
        # Check for uncommon pixel formats
        if pix_fmt not in ['yuv420p', 'yuvj420p', 'yuv422p']:
            if compatible:  # Only add as warning if not already flagged
                issues.append(f'Uncommon pixel format: {pix_fmt}')
        
        return {
            'compatible': compatible,
            'issues': issues,
            'pix_fmt': pix_fmt,
            'codec': codec,
            'profile': profile
        }
    except subprocess.TimeoutExpired:
        return {'compatible': False, 'issues': ['Video analysis timed out'], 'pix_fmt': None, 'codec': None}
    except FileNotFoundError:
        return {'compatible': False, 'issues': ['ffprobe not found - install ffmpeg'], 'pix_fmt': None, 'codec': None}
    except Exception as e:
        return {'compatible': False, 'issues': [f'Analysis error: {str(e)}'], 'pix_fmt': None, 'codec': None}


def reencode_video_to_yuv420(video_path):
    """
    Re-encode a video to YUV420p with baseline H.264 profile for maximum browser compatibility
    Creates a backup of the original file
    
    Args:
        video_path: Full path to video file
        
    Returns:
        Dict with keys: success (bool), message (str), backup_path (str or None)
    """
    try:
        backup_path = video_path + '.backup'
        
        # Create backup
        import shutil
        shutil.copy2(video_path, backup_path)
        
        # Create temporary output file
        temp_output = video_path + '.temp.mp4'
        
        # Re-encode to YUV420p with H.264 baseline profile for maximum compatibility
        cmd = [
            'ffmpeg', '-i', video_path,
            '-pix_fmt', 'yuv420p',
            '-c:v', 'libx264',
            '-profile:v', 'high',  # Use High profile (widely supported), not High 4:4:4
            '-level', '4.1',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-y',  # Overwrite output
            temp_output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            # Cleanup on failure
            if os.path.exists(temp_output):
                os.remove(temp_output)
            os.remove(backup_path)
            return {
                'success': False,
                'message': f'Re-encoding failed: {result.stderr[:200]}',
                'backup_path': None
            }
        
        # Replace original with re-encoded version
        os.replace(temp_output, video_path)
        
        return {
            'success': True,
            'message': 'Successfully re-encoded to YUV420p',
            'backup_path': backup_path
        }
        
    except subprocess.TimeoutExpired:
        # Cleanup
        if os.path.exists(temp_output):
            os.remove(temp_output)
        if os.path.exists(backup_path):
            os.remove(backup_path)
        return {'success': False, 'message': 'Re-encoding timed out (>5 minutes)', 'backup_path': None}
    except FileNotFoundError:
        if os.path.exists(backup_path):
            os.remove(backup_path)
        return {'success': False, 'message': 'ffmpeg not found - install ffmpeg', 'backup_path': None}
    except Exception as e:
        # Cleanup on error
        if os.path.exists(backup_path):
            os.remove(backup_path)
        return {'success': False, 'message': f'Re-encoding error: {str(e)}', 'backup_path': None}


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


def audit_media_for_model(db, model_path, model, reencode_videos=True):
    """
    Audit media files for a specific model
    Removes invalid references, adds missing media, renames to standard format,
    and re-encodes incompatible videos
    
    Args:
        db: Database dictionary
        model_path: Path to the model
        model: Model dictionary
        reencode_videos: Whether to re-encode incompatible videos (default: True)
        
    Returns:
        Dict with stats: removed, added, verified, renamed, reencoded, video_errors
    """
    stats = {'removed': 0, 'added': 0, 'verified': 0, 'renamed': 0, 'reencoded': 0, 'video_errors': 0}
    
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
        
        # Check video compatibility if it's a video file
        ext = os.path.splitext(filename)[1].lower()
        if reencode_videos and ext in ['.mp4', '.webm']:
            compat = check_video_compatibility(file_path)
            
            if not compat['compatible']:
                print(f"   ⚠️  Incompatible video detected: {filename}")
                for issue in compat['issues']:
                    print(f"      - {issue}")
                
                if 'YUV444' in ' '.join(compat['issues']) or '444' in compat.get('pix_fmt', '') or '4:4:4' in compat.get('profile', ''):
                    print(f"   🔄 Re-encoding to compatible format...")
                    result = reencode_video_to_yuv420(file_path)
                    
                    if result['success']:
                        print(f"   ✅ {result['message']}")
                        print(f"      Backup: {result['backup_path']}")
                        stats['reencoded'] += 1
                    else:
                        print(f"   ❌ {result['message']}")
                        stats['video_errors'] += 1
        
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


def audit_all_media(db, reencode_videos=True):
    """
    Audit all media files across all models
    
    1. Verify existing media references
    2. Re-associate orphaned media based on hash matching
    3. Re-encode incompatible videos to YUV420p
    4. Report statistics
    
    Args:
        db: Database dictionary
        reencode_videos: Whether to re-encode incompatible videos (default: True)
        
    Returns:
        Dict with overall stats and per-model details
    """
    print("\n🔍 === MEDIA AUDIT START ===")
    print(f"   Video re-encoding: {'ENABLED' if reencode_videos else 'DISABLED'}")
    
    overall_stats = {
        'models_audited': 0,
        'media_verified': 0,
        'references_removed': 0,
        'media_re_associated': 0,
        'media_renamed': 0,
        'videos_reencoded': 0,
        'video_errors': 0
    }
    
    model_details = []
    
    # Audit each model
    for model_path, model in db['models'].items():
        model_hash_prefix = get_model_hash_prefix(model)
        if not model_hash_prefix:
            continue
        
        model_stats = audit_media_for_model(db, model_path, model, reencode_videos=reencode_videos)
        
        overall_stats['models_audited'] += 1
        overall_stats['media_verified'] += model_stats['verified']
        overall_stats['references_removed'] += model_stats['removed']
        overall_stats['media_re_associated'] += model_stats['added']
        overall_stats['media_renamed'] += model_stats['renamed']
        overall_stats['videos_reencoded'] += model_stats['reencoded']
        overall_stats['video_errors'] += model_stats['video_errors']
        
        if model_stats['removed'] > 0 or model_stats['added'] > 0 or model_stats['renamed'] > 0 or model_stats['reencoded'] > 0:
            model_details.append({
                'path': model_path,
                'name': model.get('name', 'Unknown'),
                'stats': model_stats
            })
            print(f"📦 {model.get('name', 'Unknown')}: verified={model_stats['verified']}, removed={model_stats['removed']}, added={model_stats['added']}, renamed={model_stats['renamed']}, reencoded={model_stats['reencoded']}")
    
    print(f"\n✅ Audit complete:")
    print(f"   Models audited: {overall_stats['models_audited']}")
    print(f"   Media verified: {overall_stats['media_verified']}")
    print(f"   References removed: {overall_stats['references_removed']}")
    print(f"   Media re-associated: {overall_stats['media_re_associated']}")
    print(f"   Media renamed: {overall_stats['media_renamed']}")
    print(f"   Videos re-encoded: {overall_stats['videos_reencoded']}")
    if overall_stats['video_errors'] > 0:
        print(f"   ⚠️  Video errors: {overall_stats['video_errors']}")
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
