"""
API routes for model data operations
"""
from flask import Blueprint, jsonify, request
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
                    
                    scrape_result = {
                        'scraped': True,
                        'data': scraped_data,
                        'autoFilled': auto_filled
                    }
                    
                    print(f"✅ Auto-scrape successful for {model_path}")
                    
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
                'model': db['models'][model_path]
            }
            
            # Include scrape result if available
            if scrape_result:
                response['scrapeResult'] = scrape_result
            
            return jsonify(response)
        else:
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
        
        if not file.filename:
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Read and save file
        file_content = file.read()
        filename = save_uploaded_file(file_content, file.filename)
        
        if not filename:
            return jsonify({'success': False, 'error': 'Invalid file type'}), 400
        
        print(f"✅ Uploaded media: {filename} for model: {model_path}")
        return jsonify({'success': True, 'filename': filename})
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/models/<path:model_path>/add-media', methods=['POST'])
def add_media_to_model(model_path):
    """Add uploaded media to model's exampleImages"""
    try:
        db = load_db()
        if model_path not in db['models']:
            return jsonify({'success': False, 'error': 'Model not found'}), 404
        
        data = request.json
        filename = data.get('filename')
        rating = data.get('rating', 'pg')
        caption = data.get('caption', '')
        
        # Add to exampleImages
        if 'exampleImages' not in db['models'][model_path]:
            db['models'][model_path]['exampleImages'] = []
        
        db['models'][model_path]['exampleImages'].append({
            'filename': filename,
            'rating': rating,
            'caption': caption
        })
        
        if save_db(db):
            print(f"✅ Added media {filename} to model {model_path}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
            
    except Exception as e:
        print(f"❌ Add media failed: {e}")
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
        
        # ====================================================================
        # NEW: AUTO-LINK RELATED VERSIONS
        # ====================================================================
        from app.services.civitai_version_linking import link_versions_from_civitai_scrape
        
        linking_result = link_versions_from_civitai_scrape(model_path, scraped_data)
        
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

"""
Version Linking API Endpoint
Add this to app/routes/api.py after the unskip_version endpoint
"""

@bp.route('/link-versions', methods=['POST'])
def link_versions():
    """
    Link related model versions together based on CivitAI IDs and file sizes
    
    Request body (optional):
    {
        "methods": ["civitai", "filesize", "name"],  // Which methods to use
        "tolerance": 0.05,                           // File size tolerance (default 5%)
        "force": false                               // Overwrite existing links
    }
    """
    try:
        from app.services.version_linker import get_version_linker
        
        # Get request parameters
        data = request.json or {}
        methods = data.get('methods', ['civitai', 'filesize'])
        tolerance = data.get('tolerance', 0.05)
        force = data.get('force', False)
        
        print(f"\n🔗 === VERSION LINKING START ===")
        print(f"Methods: {methods}")
        print(f"Tolerance: {tolerance * 100}%")
        print(f"Force: {force}")
        
        # Load database
        db = load_db()
        
        # If not forcing, preserve existing links
        if not force:
            print("📋 Preserving existing relatedVersions links...")
            existing_links = 0
            for model in db['models'].values():
                if model.get('relatedVersions'):
                    existing_links += 1
            print(f"   Found {existing_links} models with existing links")
        
        # Create linker
        linker = get_version_linker(tolerance=tolerance)
        
        # Link versions
        models, stats, groups_info = linker.link_all(db['models'], methods=methods)
        
        # Update database
        db['models'] = models
        
        # Save
        if save_db(db):
            print("✅ Database saved successfully")
            print(f"=== VERSION LINKING COMPLETE ===\n")
            
            return jsonify({
                'success': True,
                'stats': stats,
                'groups': groups_info
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save database'
            }), 500
    
    except Exception as e:
        print(f"❌ Version linking failed: {e}")
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