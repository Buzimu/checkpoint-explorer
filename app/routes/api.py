"""
API routes for model data operations
"""
from flask import Blueprint, jsonify, request
from datetime import datetime
from app.services.database import load_db, save_db
from app.services.media import save_uploaded_file
from app.services.civitai import get_civitai_service
import subprocess

bp = Blueprint('api', __name__)


@bp.route('/models', methods=['GET'])
def get_models():
    """Load entire database"""
    db = load_db()
    return jsonify(db)


@bp.route('/models', methods=['PUT'])
def update_all_models():
    """Update entire database"""
    try:
        data = request.json
        if save_db(data):
            return jsonify({'success': True, 'message': 'Database saved successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to save database'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/models/<path:model_path>', methods=['PUT'])
def update_model(model_path):
    """
    Update a specific model
    If CivitAI URL changed, automatically scrape for new data
    """
    try:
        db = load_db()
        if model_path not in db['models']:
            return jsonify({'success': False, 'error': 'Model not found'}), 404
        
        # Track hash mismatch state (default false so it's always defined)
        hash_mismatch = False

        # Get old model data
        old_model = db['models'][model_path]
        old_url = old_model.get('civitaiUrl', '')
        
        # Get new model data
        new_model = request.json
        new_url = new_model.get('civitaiUrl', '')
        
        # Check if CivitAI URL changed
        url_changed = old_url != new_url and new_url
        
        scrape_result = None
        
        # If URL changed, try to scrape
        if url_changed:
            print(f"🔍 CivitAI URL changed for {model_path}, auto-scraping...")
            try:
                service = get_civitai_service()
                
                # Check rate limit
                if not service.can_scrape():
                    print("⏳ Rate limit in effect, skipping auto-scrape")
                    scrape_result = {
                        'scraped': False,
                        'error': 'Rate limit - wait 15 seconds between scrapes'
                    }
                else:
                    # Scrape the page
                    model_name = new_model.get('name', 'Unknown')
                    scraped_data = service.scrape_model_page(new_url, model_name)
                    
                    # Extract IDs
                    ids = service.extract_ids_from_url(new_url)
                    new_model['civitaiModelId'] = ids['modelId']
                    new_model['civitaiVersionId'] = ids['versionId']

                    # 🆕 NEW: Check for hash mismatch
                    local_hash = new_model.get('fileHash', '').upper()
                    expected_hash = scraped_data.get('expectedHash', '').upper()
                    
                    if local_hash and expected_hash:
                        # Compare hashes (handle both full SHA256 and AutoV2 partial)
                        if not hash_matches_simple(local_hash, expected_hash):
                            hash_mismatch = True
                            print(f"   🚨 HASH MISMATCH DETECTED!")
                            print(f"      Local:    {local_hash[:16]}...")
                            print(f"      Expected: {expected_hash[:16]}...")
                            print(f"      User likely assigned wrong version URL!")
                            
                            # Store mismatch info
                            new_model['hashMismatch'] = {
                                'detected': True,
                                'localHash': local_hash,
                                'expectedHash': expected_hash,
                                'detectedAt': datetime.now().isoformat()
                            }
                        else:
                            # Clear any previous mismatch
                            if 'hashMismatch' in new_model:
                                del new_model['hashMismatch']
                            print(f"   ✅ Hash verified - correct version!")
                    
                    # Store scraped data
                    new_model['civitaiData'] = scraped_data
                    
                    # Determine what to auto-fill
                    auto_filled = {
                        'tags': [],
                        'triggerWords': []
                    }
                    
                    # Auto-fill tags if empty
                    if not new_model.get('tags') or len(new_model['tags']) == 0:
                        new_model['tags'] = scraped_data.get('tags', [])
                        auto_filled['tags'] = new_model['tags']
                    
                    # Auto-fill trigger words if empty
                    if not new_model.get('triggerWords') or len(new_model['triggerWords']) == 0:
                        new_model['triggerWords'] = scraped_data.get('trainedWords', [])
                        auto_filled['triggerWords'] = new_model['triggerWords']

                    # Auto-fill base model if empty or unknown
                    current_base = new_model.get('baseModel', '').strip()
                    if not current_base or current_base.lower() == 'unknown':
                        # Find the current version's base model
                        current_version_id = scraped_data.get('currentVersionId')
                        versions = scraped_data.get('versions', [])
                        
                        for version in versions:
                            if version.get('id') == current_version_id:
                                version_base = version.get('baseModel', '')
                                if version_base and version_base != 'Unknown':
                                    new_model['baseModel'] = version_base
                                    auto_filled['baseModel'] = version_base
                                    print(f"   ✅ Auto-filled baseModel: {version_base}")
                                break
                    
                    scrape_result = {
                        'scraped': True,
                        'data': scraped_data,
                        'autoFilled': auto_filled,
                        'hashMismatch': hash_mismatch
                    }
                    
                    print(f"✅ Auto-scrape successful for {model_path}")
                    # ====================================================================
                    # NEW: AUTO-LINK RELATED VERSIONS (after auto-scrape)
                    # ====================================================================
                    from app.services.civitai_version_linking import link_versions_from_civitai_scrape, detect_newer_versions

                    try:
                        linking_result = link_versions_from_civitai_scrape(model_path, scraped_data)
                        
                        if linking_result:
                            stats = linking_result.get('stats', {})
                            if stats.get('confirmed', 0) > 0 or stats.get('assumed', 0) > 0:
                                print(f"🔗 Auto-linked versions: {stats.get('confirmed', 0)} confirmed, {stats.get('assumed', 0)} assumed")
                    except Exception as link_error:
                        print(f"⚠️ Version linking failed: {link_error}")
                    
                    # ====================================================================
                    # NEW: AUTO-DETECT NEWER VERSIONS (after scrape)
                    # ====================================================================
                    try:
                        print(f"🔍 Checking for newer versions after scrape...")
                        db_reloaded = load_db()  # Reload to get latest links
                        newer_versions_info = detect_newer_versions(db_reloaded)
                        
                        # Update the model's newVersionAvailable flag
                        if model_path in newer_versions_info:
                            new_model['newVersionAvailable'] = newer_versions_info[model_path]
                            print(f"   ✨ Newer version detected for {model_path}")
                        elif 'newVersionAvailable' in new_model:
                            del new_model['newVersionAvailable']
                            print(f"   ✅ Model is up to date")
                    except Exception as detect_error:
                        print(f"⚠️  Newer version detection failed (non-critical): {detect_error}")
                    
            except Exception as scrape_error:
                print(f"⚠️ Auto-scrape failed: {scrape_error}")
                scrape_result = {
                    'scraped': False,
                    'error': str(scrape_error)
                }
        
        # Update the model
        db['models'][model_path] = new_model
        
        # Save database
        if save_db(db):
            response = {
                'success': True,
                'model': db['models'][model_path],
                'hashMismatch': hash_mismatch
            }
            
            # Include scrape result if available
            if scrape_result:
                response['scrapeResult'] = scrape_result
            
            return jsonify(response)
        else:
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def hash_matches_simple(hash1, hash2):
    """Simple hash comparison helper"""
    if not hash1 or not hash2:
        return False
    
    h1 = hash1.upper()
    h2 = hash2.upper()
    
    # Exact match
    if h1 == h2:
        return True
    
    # Partial match (one is AutoV2, other is full SHA256)
    if len(h1) == 10 and len(h2) == 64:
        return h2.startswith(h1)
    if len(h2) == 10 and len(h1) == 64:
        return h1.startswith(h2)
    
    return False


@bp.route('/models/<path:model_path>/favorite', methods=['POST'])
def toggle_favorite(model_path):
    """Toggle favorite status"""
    try:
        db = load_db()
        if model_path in db['models']:
            current = db['models'][model_path].get('favorite', False)
            db['models'][model_path]['favorite'] = not current
            if save_db(db):
                return jsonify({
                    'success': True,
                    'favorite': db['models'][model_path]['favorite']
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to save'}), 500
        return jsonify({'success': False, 'error': 'Model not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/upload-media', methods=['POST'])
def upload_media():
    """Upload image or video for a model"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        model_path = request.form.get('modelPath')
        rating = request.form.get('rating', 'pg')
        
        if not file.filename:
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if not model_path:
            return jsonify({'success': False, 'error': 'Model path required'}), 400
        
        # Load database to get model info
        db = load_db()
        if model_path not in db['models']:
            return jsonify({'success': False, 'error': 'Model not found'}), 404
        
        model = db['models'][model_path]
        
        # Get model hash prefix (first 8 chars)
        from app.services.media_auditor import get_model_hash_prefix, get_next_media_number
        model_hash_prefix = get_model_hash_prefix(model)
        
        if not model_hash_prefix:
            return jsonify({'success': False, 'error': 'Model has no hash - cannot generate standardized filename'}), 400
        
        # Get next sequential number for this model
        next_number = get_next_media_number(model)
        
        # Read and save file with standardized naming
        file_content = file.read()
        filename = save_uploaded_file(file_content, file.filename, model_hash_prefix, rating, next_number)
        
        if not filename:
            return jsonify({'success': False, 'error': 'Invalid file type'}), 400
        
        print(f"✅ Uploaded media: {filename} for model: {model_path}")
        return jsonify({'success': True, 'filename': filename})
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/models/<path:model_path>/add-media', methods=['POST'])
def add_media_to_model(model_path):
    """Add uploaded media to model's exampleImages and run auditor"""
    try:
        db = load_db()
        if model_path not in db['models']:
            return jsonify({'success': False, 'error': 'Model not found'}), 404
        
        data = request.json
        filename = data.get('filename')
        rating = data.get('rating', 'pg')
        caption = data.get('caption', '')
        
        # 🔧 BUGFIX: Ensure exampleImages is always a list
        if 'exampleImages' not in db['models'][model_path]:
            db['models'][model_path]['exampleImages'] = []
        elif not isinstance(db['models'][model_path]['exampleImages'], list):
            # Convert dict/other types to list
            print(f"⚠️  Converting exampleImages from {type(db['models'][model_path]['exampleImages'])} to list for {model_path}")
            db['models'][model_path]['exampleImages'] = []
        
        db['models'][model_path]['exampleImages'].append({
            'filename': filename,
            'rating': rating,
            'caption': caption
        })
        
        if save_db(db):
            print(f"✅ Added media {filename} to model {model_path}")
            
            # Run media auditor for this model to verify everything is correct
            from app.services.media_auditor import audit_media_for_model
            db_reloaded = load_db()
            audit_stats = audit_media_for_model(db_reloaded, model_path, db_reloaded['models'][model_path])
            if audit_stats['removed'] > 0 or audit_stats['added'] > 0:
                save_db(db_reloaded)
                print(f"🔍 Media audit: verified={audit_stats['verified']}, removed={audit_stats['removed']}, added={audit_stats['added']}")
            
            return jsonify({'success': True, 'audit': audit_stats})
        else:
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
            
    except Exception as e:
        print(f"❌ Add media failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/models/<path:model_path>/update-media-rating', methods=['POST'])
def update_media_rating(model_path):
    """Update rating for a specific media item"""
    try:
        db = load_db()
        if model_path not in db['models']:
            return jsonify({'success': False, 'error': 'Model not found'}), 404
        
        data = request.json
        filename = data.get('filename')
        new_rating = data.get('rating')
        
        if not filename or not new_rating:
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400
        
        # Find and update the media item
        media_list = db['models'][model_path].get('exampleImages', [])
        updated = False
        
        for media in media_list:
            if media['filename'] == filename:
                media['rating'] = new_rating
                updated = True
                break
        
        if not updated:
            return jsonify({'success': False, 'error': 'Media not found'}), 404
        
        if save_db(db):
            print(f"✅ Updated rating for {filename} to {new_rating}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
            
    except Exception as e:
        print(f"❌ Update rating failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/models/<path:model_path>/delete-media', methods=['POST'])
def delete_media(model_path):
    """Delete a media item from model's exampleImages"""
    try:
        db = load_db()
        if model_path not in db['models']:
            return jsonify({'success': False, 'error': 'Model not found'}), 404
        
        data = request.json
        filename = data.get('filename')
        
        if not filename:
            return jsonify({'success': False, 'error': 'Missing filename'}), 400
        
        # Remove from exampleImages
        media_list = db['models'][model_path].get('exampleImages', [])
        original_length = len(media_list)
        
        db['models'][model_path]['exampleImages'] = [
            media for media in media_list 
            if media['filename'] != filename
        ]
        
        if len(db['models'][model_path]['exampleImages']) == original_length:
            return jsonify({'success': False, 'error': 'Media not found'}), 404
        
        if save_db(db):
            print(f"✅ Deleted media {filename} from model {model_path}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
            
    except Exception as e:
        print(f"❌ Delete media failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/scan', methods=['POST'])
def trigger_scan():
    """Trigger PowerShell script to scan for new models"""
    try:
        from config import MODELS_DIR
        result = subprocess.run(
            ['pwsh', '-File', 'generate-modeldb.ps1'],
            cwd=MODELS_DIR,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr if result.returncode != 0 else None
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Scan timed out after 5 minutes'
        }), 500
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': 'PowerShell or script not found'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/activity-log', methods=['GET'])
def get_activity_log():
    """
    Get recent activity from the CivitAI scraping service
    """
    try:
        service = get_civitai_service()
        activities = service.get_activity_log()
        
        return jsonify({
            'success': True,
            'activities': activities,
            'count': len(activities)
        })
    except Exception as e:
        print(f"❌ Failed to get activity log: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/models/<path:model_path>/scrape-civitai', methods=['POST'])
def scrape_civitai(model_path):
    """
    Manually trigger CivitAI scrape for a model
    NOW WITH AUTO VERSION LINKING
    """
    try:
        db = load_db()
        if model_path not in db['models']:
            return jsonify({'success': False, 'error': 'Model not found'}), 404
        
        model = db['models'][model_path]
        civitai_url = model.get('civitaiUrl')
        
        if not civitai_url:
            return jsonify({'success': False, 'error': 'No CivitAI URL set'}), 400
        
        # Get service
        service = get_civitai_service()
        
        # Check rate limit
        if not service.can_scrape():
            return jsonify({
                'success': False,
                'error': 'Rate limit in effect - please wait 15 seconds between scrapes'
            }), 429
        
        # Scrape the page
        model_name = model.get('name', 'Unknown')
        scraped_data = service.scrape_model_page(civitai_url, model_name)
        
        # Extract IDs
        ids = service.extract_ids_from_url(civitai_url)
        model['civitaiModelId'] = ids['modelId']
        model['civitaiVersionId'] = ids['versionId']
        
        # Store scraped data
        model['civitaiData'] = scraped_data
        
        # Determine what to auto-fill
        auto_filled = {
            'tags': [],
            'triggerWords': []
        }
        
        # Auto-fill tags if empty
        if not model.get('tags') or len(model['tags']) == 0:
            model['tags'] = scraped_data.get('tags', [])
            auto_filled['tags'] = model['tags']
        
        # Auto-fill trigger words if empty
        if not model.get('triggerWords') or len(model['triggerWords']) == 0:
            model['triggerWords'] = scraped_data.get('trainedWords', [])
            auto_filled['triggerWords'] = model['triggerWords']

        # Auto-fill base model if empty or unknown
        current_base = model.get('baseModel', '').strip()
        if not current_base or current_base.lower() == 'unknown':
            # Find the current version's base model
            current_version_id = scraped_data.get('currentVersionId')
            versions = scraped_data.get('versions', [])
            
            for version in versions:
                if version.get('id') == current_version_id:
                    version_base = version.get('baseModel', '')
                    if version_base and version_base != 'Unknown':
                        model['baseModel'] = version_base
                        auto_filled['baseModel'] = version_base
                        print(f"   ✅ Auto-filled baseModel: {version_base}")
                    break
        
        # ====================================================================
        # NEW: AUTO-LINK RELATED VERSIONS
        # ====================================================================
        from app.services.civitai_version_linking import link_versions_from_civitai_scrape, detect_newer_versions
        
        linking_result = link_versions_from_civitai_scrape(model_path, scraped_data)
        
        # ====================================================================
        # NEW: AUTO-DETECT NEWER VERSIONS (after scrape)
        # ====================================================================
        try:
            print(f"🔍 Checking for newer versions after scrape...")
            db = load_db()  # Reload to get latest links
            newer_versions_info = detect_newer_versions(db)
            
            # Update the model's newVersionAvailable flag
            if model_path in newer_versions_info:
                db['models'][model_path]['newVersionAvailable'] = newer_versions_info[model_path]
                print(f"   ✨ Newer version detected for {model_path}")
            elif 'newVersionAvailable' in db['models'][model_path]:
                del db['models'][model_path]['newVersionAvailable']
                print(f"   ✅ Model is up to date")
        except Exception as detect_error:
            print(f"⚠️  Newer version detection failed (non-critical): {detect_error}")
        
        # ====================================================================
        # RUN MEDIA AUDITOR (after scrape)
        # ====================================================================
        try:
            from app.services.media_auditor import audit_media_for_model
            print(f"🔍 Running media audit for {model_path}...")
            db_for_audit = load_db()
            audit_stats = audit_media_for_model(db_for_audit, model_path, db_for_audit['models'][model_path])
            if audit_stats['removed'] > 0 or audit_stats['added'] > 0:
                save_db(db_for_audit)
                print(f"   Media audit: verified={audit_stats['verified']}, removed={audit_stats['removed']}, added={audit_stats['added']}")
        except Exception as audit_error:
            print(f"⚠️  Media audit failed (non-critical): {audit_error}")
        
        # Save
        if save_db(db):
            response = {
                'success': True,
                'data': scraped_data,
                'autoFilled': auto_filled
            }
            
            # Include linking results
            if linking_result:
                response['versionLinking'] = linking_result
            
            return jsonify(response)
        
        return jsonify({'success': False, 'error': 'Failed to save'}), 500
        
    except Exception as e:
        print(f"❌ CivitAI scrape failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/models/<path:model_path>/skip-version', methods=['POST'])
def skip_version(model_path):
    """Mark a CivitAI version as skipped"""
    try:
        db = load_db()
        if model_path not in db['models']:
            return jsonify({'success': False, 'error': 'Model not found'}), 404
        
        model = db['models'][model_path]
        data = request.json
        version_id = data.get('versionId')
        
        if not version_id:
            return jsonify({'success': False, 'error': 'Missing versionId'}), 400
        
        # Initialize skipped versions list if needed
        if 'skippedVersions' not in model:
            model['skippedVersions'] = []
        
        # Add to skipped list if not already there
        if version_id not in model['skippedVersions']:
            model['skippedVersions'].append(version_id)
        
        # Update version status in civitaiData if present
        if 'civitaiData' in model and 'versions' in model['civitaiData']:
            for version in model['civitaiData']['versions']:
                if version.get('versionId') == version_id:
                    version['status'] = 'skipped'
        
        if save_db(db):
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'error': 'Failed to save'}), 500
        
    except Exception as e:
        print(f"❌ Skip version failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/gallery', methods=['GET'])
def get_gallery():
    """
    Get all media files from database and identify orphaned files
    
    Returns:
    {
        "media": [
            {
                "filename": "abc123.jpg",
                "rating": "pg",
                "modelName": "Model Name",
                "modelPath": "models/checkpoint.safetensors",
                "isVideo": false,
                "orphaned": false
            }
        ],
        "stats": {
            "total": 150,
            "orphaned": 5,
            "images": 120,
            "videos": 30
        }
    }
    """
    try:
        import os
        from config import IMAGES_DIR
        
        # Load database
        db = load_db()
        
        # Collect all media from database
        media_in_db = {}
        media_list = []
        
        for model_path, model in db['models'].items():
            if model.get('exampleImages'):
                for img in model['exampleImages']:
                    filename = img['filename']
                    ext = filename.lower()
                    is_video = ext.endswith('.mp4') or ext.endswith('.webm')
                    
                    media_in_db[filename] = True
                    media_list.append({
                        'filename': filename,
                        'rating': img.get('rating', 'pg'),
                        'modelName': model.get('name', 'Unknown'),
                        'modelPath': model_path,
                        'isVideo': is_video,
                        'orphaned': False
                    })
        
        # Check for orphaned files in images directory
        if os.path.exists(IMAGES_DIR):
            for filename in os.listdir(IMAGES_DIR):
                file_path = os.path.join(IMAGES_DIR, filename)
                if os.path.isfile(file_path):
                    ext = filename.lower()
                    # Check if it's a valid media file
                    if any(ext.endswith(e) for e in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm']):
                        if filename not in media_in_db:
                            # This is an orphaned file
                            is_video = ext.endswith('.mp4') or ext.endswith('.webm')
                            media_list.append({
                                'filename': filename,
                                'rating': 'pg',  # Default rating for orphaned files
                                'modelName': '⚠️ Orphaned File',
                                'modelPath': None,
                                'isVideo': is_video,
                                'orphaned': True
                            })
        
        # Calculate stats
        stats = {
            'total': len(media_list),
            'orphaned': sum(1 for m in media_list if m['orphaned']),
            'images': sum(1 for m in media_list if not m['isVideo']),
            'videos': sum(1 for m in media_list if m['isVideo'])
        }
        
        return jsonify({
            'success': True,
            'media': media_list,
            'stats': stats
        })
        
    except Exception as e:
        print(f"❌ Gallery fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

        
@bp.route('/models/<path:model_path>/unskip-version', methods=['POST'])
def unskip_version(model_path):
    """Remove a version from the skipped list"""
    try:
        db = load_db()
        if model_path not in db['models']:
            return jsonify({'success': False, 'error': 'Model not found'}), 404
        
        model = db['models'][model_path]
        data = request.json
        version_id = data.get('versionId')
        
        if not version_id:
            return jsonify({'success': False, 'error': 'Missing versionId'}), 400
        
        # Remove from skipped list if present
        if 'skippedVersions' in model and version_id in model['skippedVersions']:
            model['skippedVersions'].remove(version_id)
        
        # Update version status in civitaiData if present
        if 'civitaiData' in model and 'versions' in model['civitaiData']:
            for version in model['civitaiData']['versions']:
                if version.get('versionId') == version_id:
                    version['status'] = 'available'
        
        if save_db(db):
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'error': 'Failed to save'}), 500
        
    except Exception as e:
        print(f"❌ Unskip version failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/detect-newer-versions', methods=['POST'])
def detect_newer_versions_route():
    """
    Detect models that have newer versions available on CivitAI
    
    This compares publishedAt dates from CivitAI data and flags models
    that have newer versions than the current one.
    
    Returns:
        JSON with detected newer versions and statistics
    """
    try:
        from app.services.civitai_version_linking import detect_newer_versions
        
        print("\n🔍 === NEWER VERSION DETECTION START ===")
        
        # Load database
        db = load_db()
        
        # Detect newer versions
        newer_versions_info = detect_newer_versions(db)
        
        # Store the detection results in each model
        for path, info in newer_versions_info.items():
            if path in db['models']:
                db['models'][path]['newVersionAvailable'] = info
        
        # Clear flag for models without newer versions
        for path, model in db['models'].items():
            if path not in newer_versions_info and 'newVersionAvailable' in model:
                del model['newVersionAvailable']
        
        # Save database
        if save_db(db):
            print("✅ Database saved successfully")
            print(f"=== NEWER VERSION DETECTION COMPLETE ===\n")
            
            return jsonify({
                'success': True,
                'count': len(newer_versions_info),
                'models': list(newer_versions_info.keys())
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save database'
            }), 500
    
    except Exception as e:
        print(f"❌ Newer version detection failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/media/<path:filename>', methods=['DELETE'])
def delete_media_file(filename):
    """
    Delete a media file from the images directory
    Used for cleaning up orphaned files
    """
    try:
        import os
        from config import IMAGES_DIR
        
        file_path = os.path.join(IMAGES_DIR, filename)
        
        # Security check - make sure file is in images directory
        if not file_path.startswith(os.path.abspath(IMAGES_DIR)):
            return jsonify({
                'success': False,
                'error': 'Invalid file path'
            }), 400
        
        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
        
        # Delete the file
        os.remove(file_path)
        print(f"🗑️ Deleted orphaned file: {filename}")
        
        return jsonify({
            'success': True,
            'message': f'File {filename} deleted successfully'
        })
        
    except Exception as e:
        print(f"❌ Failed to delete file {filename}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/audit-media', methods=['POST'])
def audit_media():
    """
    Manually trigger a full media audit
    
    Scans all media files and:
    1. Removes references to missing files
    2. Re-associates orphaned media based on hash matching
    
    Optional parameters:
    {
        "modelPath": "path/to/model.safetensors"  // Audit single model only
    }
    """
    try:
        from app.services.media_auditor import audit_all_media, audit_media_for_model
        
        data = request.json or {}
        model_path = data.get('modelPath')
        
        db = load_db()
        
        if model_path:
            # Audit single model
            if model_path not in db['models']:
                return jsonify({'success': False, 'error': 'Model not found'}), 404
            
            print(f"\n🔍 Auditing media for: {model_path}")
            model_stats = audit_media_for_model(db, model_path, db['models'][model_path])
            
            if save_db(db):
                return jsonify({
                    'success': True,
                    'stats': model_stats,
                    'modelPath': model_path
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to save database'}), 500
        else:
            # Audit all models
            result = audit_all_media(db)
            
            if save_db(db):
                return jsonify({
                    'success': True,
                    'stats': result['stats'],
                    'details': result['details']
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to save database'}), 500
        
    except Exception as e:
        print(f"❌ Media audit failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
